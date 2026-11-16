"""SQLite persistence layer for Smart Grocery & Household Manager."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import math
import unicodedata

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / 'smart_grocery.db'
STOCK_EPSILON = 1e-12
MIN_QUANTITY_STEP = 1e-9

SCHEMA = r'''
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS stores(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, address TEXT DEFAULT '', notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS suppliers(id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE, phone TEXT DEFAULT '', email TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS household_members(id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL DEFAULT 'Member', phone TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS products(
 id INTEGER PRIMARY KEY, name TEXT NOT NULL COLLATE NOCASE UNIQUE, category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
 brand TEXT DEFAULT '', description TEXT DEFAULT '', unit TEXT NOT NULL DEFAULT 'pcs', quantity REAL NOT NULL DEFAULT 0 CHECK(quantity>=0),
 min_quantity REAL NOT NULL DEFAULT 1 CHECK(min_quantity>=0), price TEXT NOT NULL DEFAULT '0.00', store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
 supplier_id INTEGER REFERENCES suppliers(id) ON DELETE SET NULL, favorite INTEGER NOT NULL DEFAULT 0,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS product_batches(
 id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE, batch_code TEXT DEFAULT '', quantity REAL NOT NULL CHECK(quantity>=0),
 unit_cost TEXT NOT NULL DEFAULT '0.00', purchase_date TEXT, expiry_date TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS purchases(id INTEGER PRIMARY KEY, purchase_date TEXT NOT NULL, store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
 member_id INTEGER REFERENCES household_members(id) ON DELETE SET NULL, payment_method TEXT DEFAULT 'Cash', notes TEXT DEFAULT '', total TEXT NOT NULL DEFAULT '0.00', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS purchase_items(id INTEGER PRIMARY KEY, purchase_id INTEGER NOT NULL REFERENCES purchases(id) ON DELETE CASCADE,
 product_id INTEGER NOT NULL REFERENCES products(id), quantity REAL NOT NULL CHECK(quantity>0), unit_price TEXT NOT NULL, line_total TEXT NOT NULL, batch_id INTEGER REFERENCES product_batches(id) ON DELETE SET NULL);
CREATE TABLE IF NOT EXISTS stock_movements(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), batch_id INTEGER REFERENCES product_batches(id) ON DELETE SET NULL,
 movement_type TEXT NOT NULL, quantity REAL NOT NULL, reference TEXT DEFAULT '', note TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS shopping_lists(id INTEGER PRIMARY KEY, name TEXT NOT NULL, list_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Open', notes TEXT DEFAULT '', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS recurring_shopping(id INTEGER PRIMARY KEY, name TEXT NOT NULL, interval_days INTEGER NOT NULL CHECK(interval_days>0), next_due TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, last_generated TEXT, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS shopping_list_items(id INTEGER PRIMARY KEY, list_id INTEGER NOT NULL REFERENCES shopping_lists(id) ON DELETE CASCADE,
 product_id INTEGER REFERENCES products(id) ON DELETE SET NULL, name TEXT NOT NULL, category TEXT DEFAULT '', quantity REAL NOT NULL DEFAULT 1,
 unit TEXT DEFAULT 'pcs', unit_price TEXT NOT NULL DEFAULT '0.00', store_id INTEGER REFERENCES stores(id) ON DELETE SET NULL,
 priority TEXT DEFAULT 'Normal', status TEXT NOT NULL DEFAULT 'Pending', actual_price TEXT DEFAULT '0.00');
CREATE TABLE IF NOT EXISTS expenses(id INTEGER PRIMARY KEY, expense_date TEXT NOT NULL, category TEXT NOT NULL, description TEXT DEFAULT '', amount TEXT NOT NULL,
 member_id INTEGER REFERENCES household_members(id) ON DELETE SET NULL, purchase_id INTEGER UNIQUE REFERENCES purchases(id) ON DELETE CASCADE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS budgets(id INTEGER PRIMARY KEY, name TEXT NOT NULL, category TEXT NOT NULL DEFAULT 'All', period TEXT NOT NULL DEFAULT 'Monthly', amount TEXT NOT NULL,
 start_date TEXT NOT NULL, end_date TEXT NOT NULL, alert_50 INTEGER NOT NULL DEFAULT 1, alert_75 INTEGER NOT NULL DEFAULT 1, alert_90 INTEGER NOT NULL DEFAULT 1, alert_100 INTEGER NOT NULL DEFAULT 1);
CREATE TABLE IF NOT EXISTS price_history(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE, store_id INTEGER NOT NULL REFERENCES stores(id) ON DELETE CASCADE,
 package_quantity REAL NOT NULL, package_unit TEXT NOT NULL, price TEXT NOT NULL, recorded_date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS waste_records(id INTEGER PRIMARY KEY, product_id INTEGER NOT NULL REFERENCES products(id), quantity REAL NOT NULL, reason TEXT NOT NULL,
 waste_date TEXT NOT NULL, unit_cost TEXT NOT NULL, notes TEXT DEFAULT '');
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY, title TEXT NOT NULL, message TEXT NOT NULL, priority TEXT NOT NULL DEFAULT 'Info', related_type TEXT DEFAULT '', related_id INTEGER,
 is_read INTEGER NOT NULL DEFAULT 0, fingerprint TEXT UNIQUE, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_batches_expiry ON product_batches(expiry_date);
CREATE INDEX IF NOT EXISTS idx_purchases_date ON purchases(purchase_date);
CREATE INDEX IF NOT EXISTS idx_expenses_date ON expenses(expense_date);
CREATE INDEX IF NOT EXISTS idx_movements_product ON stock_movements(product_id, created_at);

-- Database-level guards protect records even if a future UI path bypasses Python validation.
CREATE TRIGGER IF NOT EXISTS trg_products_finite_insert BEFORE INSERT ON products
WHEN NEW.quantity > 1.0e308 OR NEW.min_quantity > 1.0e308
 OR (NEW.quantity > 0 AND NEW.quantity < 1.0e-9) OR (NEW.min_quantity > 0 AND NEW.min_quantity < 1.0e-9)
BEGIN SELECT RAISE(ABORT, 'Product quantities must be finite and zero or at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_products_finite_update BEFORE UPDATE OF quantity,min_quantity ON products
WHEN NEW.quantity > 1.0e308 OR NEW.min_quantity > 1.0e308
 OR (NEW.quantity > 0 AND NEW.quantity < 1.0e-9) OR (NEW.min_quantity > 0 AND NEW.min_quantity < 1.0e-9)
BEGIN SELECT RAISE(ABORT, 'Product quantities must be finite and zero or at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_batches_finite_insert BEFORE INSERT ON product_batches
WHEN NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Batch quantity must be finite.'); END;
CREATE TRIGGER IF NOT EXISTS trg_batches_finite_update BEFORE UPDATE OF quantity ON product_batches
WHEN NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Batch quantity must be finite.'); END;
CREATE TRIGGER IF NOT EXISTS trg_batch_dates_insert BEFORE INSERT ON product_batches
WHEN (NEW.purchase_date IS NOT NULL AND (length(NEW.purchase_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.purchase_date), '') != NEW.purchase_date))
 OR (NEW.expiry_date IS NOT NULL AND (length(NEW.expiry_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.expiry_date), '') != NEW.expiry_date))
BEGIN SELECT RAISE(ABORT, 'Batch dates must be real ISO calendar dates.'); END;
CREATE TRIGGER IF NOT EXISTS trg_batch_dates_update BEFORE UPDATE OF purchase_date,expiry_date ON product_batches
WHEN (NEW.purchase_date IS NOT NULL AND (length(NEW.purchase_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.purchase_date), '') != NEW.purchase_date))
 OR (NEW.expiry_date IS NOT NULL AND (length(NEW.expiry_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.expiry_date), '') != NEW.expiry_date))
BEGIN SELECT RAISE(ABORT, 'Batch dates must be real ISO calendar dates.'); END;
CREATE TRIGGER IF NOT EXISTS trg_stock_movements_finite_insert BEFORE INSERT ON stock_movements
WHEN NEW.quantity > 1.0e308 OR NEW.quantity < -1.0e308
BEGIN SELECT RAISE(ABORT, 'Stock movement quantity must be finite.'); END;
CREATE TRIGGER IF NOT EXISTS trg_stock_movements_finite_update BEFORE UPDATE OF quantity ON stock_movements
WHEN NEW.quantity > 1.0e308 OR NEW.quantity < -1.0e308
BEGIN SELECT RAISE(ABORT, 'Stock movement quantity must be finite.'); END;
CREATE TRIGGER IF NOT EXISTS trg_purchase_items_finite_insert BEFORE INSERT ON purchase_items
WHEN NEW.quantity < 1.0e-9 OR NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Purchase quantity must be finite and at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_shopping_items_finite_insert BEFORE INSERT ON shopping_list_items
WHEN NEW.quantity < 1.0e-9 OR NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Shopping quantity must be finite and at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_shopping_items_finite_update BEFORE UPDATE OF quantity ON shopping_list_items
WHEN NEW.quantity < 1.0e-9 OR NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Shopping quantity must be finite and at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_price_history_finite_insert BEFORE INSERT ON price_history
WHEN NEW.package_quantity < 1.0e-9 OR NEW.package_quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Package quantity must be finite and at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_waste_finite_insert BEFORE INSERT ON waste_records
WHEN NEW.quantity < 1.0e-9 OR NEW.quantity > 1.0e308
BEGIN SELECT RAISE(ABORT, 'Wastage quantity must be finite and at least 1e-9.'); END;
CREATE TRIGGER IF NOT EXISTS trg_purchase_date_insert BEFORE INSERT ON purchases
WHEN length(NEW.purchase_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.purchase_date), '') != NEW.purchase_date
BEGIN SELECT RAISE(ABORT, 'Purchase date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_purchase_date_update BEFORE UPDATE OF purchase_date ON purchases
WHEN length(NEW.purchase_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.purchase_date), '') != NEW.purchase_date
BEGIN SELECT RAISE(ABORT, 'Purchase date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_expense_date_insert BEFORE INSERT ON expenses
WHEN length(NEW.expense_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.expense_date), '') != NEW.expense_date
BEGIN SELECT RAISE(ABORT, 'Expense date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_expense_date_update BEFORE UPDATE OF expense_date ON expenses
WHEN length(NEW.expense_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.expense_date), '') != NEW.expense_date
BEGIN SELECT RAISE(ABORT, 'Expense date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_shopping_list_date_insert BEFORE INSERT ON shopping_lists
WHEN length(NEW.list_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.list_date), '') != NEW.list_date
BEGIN SELECT RAISE(ABORT, 'Shopping-list date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_budget_dates_insert BEFORE INSERT ON budgets
WHEN length(NEW.start_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.start_date), '') != NEW.start_date
 OR length(NEW.end_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.end_date), '') != NEW.end_date
 OR NEW.end_date < NEW.start_date
BEGIN SELECT RAISE(ABORT, 'Budget dates must be valid ISO dates and end date cannot precede start date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_price_date_insert BEFORE INSERT ON price_history
WHEN length(NEW.recorded_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.recorded_date), '') != NEW.recorded_date
BEGIN SELECT RAISE(ABORT, 'Price-record date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_waste_date_insert BEFORE INSERT ON waste_records
WHEN length(NEW.waste_date) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.waste_date), '') != NEW.waste_date
BEGIN SELECT RAISE(ABORT, 'Wastage date must be a real ISO calendar date.'); END;
CREATE TRIGGER IF NOT EXISTS trg_recurring_date_insert BEFORE INSERT ON recurring_shopping
WHEN length(NEW.next_due) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.next_due), '') != NEW.next_due
 OR NEW.interval_days > 365
BEGIN SELECT RAISE(ABORT, 'Recurring schedule date or interval is invalid.'); END;
CREATE TRIGGER IF NOT EXISTS trg_recurring_date_update BEFORE UPDATE OF next_due,interval_days ON recurring_shopping
WHEN length(NEW.next_due) != 10 OR COALESCE(strftime('%Y-%m-%d', NEW.next_due), '') != NEW.next_due
 OR NEW.interval_days < 1 OR NEW.interval_days > 365
BEGIN SELECT RAISE(ABORT, 'Recurring schedule date or interval is invalid.'); END;
'''


def money(value) -> Decimal:
    try:
        number=Decimal(str(0 if value is None else value))
        if not number.is_finite(): raise ValueError
        result=number.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        if not result.is_finite(): raise ValueError
        return result
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Money value must be a finite valid number.')


def _clamp_stock(value):
    value=float(value)
    return 0.0 if abs(value) <= STOCK_EPSILON else value


def _nonnegative_money(value, label, *, strictly_positive=False):
    try:
        raw = Decimal(str(0 if value is None else value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label} must be a valid monetary amount.')
    if not raw.is_finite():
        raise ValueError(f'{label} must be a finite monetary amount.')
    if raw < 0:
        raise ValueError(f'{label} cannot be negative.')
    if strictly_positive and raw <= 0:
        raise ValueError(f'{label} must be greater than zero.')
    rounded = money(raw)
    if strictly_positive and rounded <= 0:
        raise ValueError(f'{label} must be at least 0.01 after currency rounding.')
    return rounded


def _required(value, label):
    value = str(value if value is not None else '').strip()
    if not value:
        raise ValueError(f'{label} is required.')
    return value


def _product_name(value):
    name = _required(value, 'Product name')
    if len(name) < 2 or len(name) > 100:
        raise ValueError('Product name must contain between 2 and 100 characters.')
    # Permit common grocery naming conventions and Unicode letters, but reject
    # punctuation-only, control-character, emoji-only and whitespace-only names.
    allowed_punctuation = set(" .,'&()/+-")
    if not any(ch.isalpha() for ch in name):
        raise ValueError('Enter a valid product name containing at least one letter.')
    if any(not (unicodedata.category(ch)[0] in {'L', 'N', 'M'} or ch in allowed_punctuation) for ch in name):
        raise ValueError("Product name may contain letters, numbers, spaces and . , ' & ( ) / + - only.")
    if name[0] in allowed_punctuation or name[-1] in allowed_punctuation:
        raise ValueError('Product name must start and end with a letter or number.')
    return ' '.join(name.split())

def _number(value, label, *, minimum=None, strictly_positive=False):
    try:
        n = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError(f'{label} must be a valid number.')
    if not n.is_finite():
        raise ValueError(f'{label} must be a finite number.')
    if strictly_positive and n < Decimal(str(MIN_QUANTITY_STEP)):
        raise ValueError(f'{label} must be at least {MIN_QUANTITY_STEP:g}.')
    if minimum is not None and n < Decimal(str(minimum)):
        raise ValueError(f'{label} cannot be less than {minimum}.')
    result=float(n)
    if not math.isfinite(result) or result > 1.0e308: raise ValueError(f'{label} is too large for safe database storage.')
    if strictly_positive and result<MIN_QUANTITY_STEP: raise ValueError(f'{label} is too small to represent safely.')
    return result

def _date(value, label, *, optional=False):
    if optional and (value is None or str(value).strip() == ''):
        return None
    try:
        parsed = date.fromisoformat(str(value).strip())
    except (TypeError, ValueError):
        raise ValueError(f'{label} must be a real date in YYYY-MM-DD format.')
    if parsed.isoformat() != str(value).strip():
        raise ValueError(f'{label} must use YYYY-MM-DD format.')
    return parsed.isoformat()

def _date_not_future(value, label):
    parsed = _date(value, label)
    if parsed > date.today().isoformat():
        raise ValueError(f'{label} cannot be in the future.')
    return parsed


def _future_expiry_date(value, label='Expiry date'):
    parsed = _date(value, label, optional=True)
    if parsed and parsed <= date.today().isoformat():
        raise ValueError(f'{label} must be a future date (after today).')
    return parsed


def _validate_date_range(start, end, start_label='Start date', end_label='End date'):
    start = _date(start, start_label); end = _date(end, end_label)
    if end < start:
        raise ValueError(f'{end_label} cannot be earlier than {start_label.lower()}.')
    return start, end

def _optional_id(value, label):
    if value is None or str(value).strip() == '':
        return None
    if isinstance(value, bool):
        raise ValueError(f'{label} must be a valid positive whole number.')
    text=str(value).strip()
    if text.startswith('+'):
        text=text[1:]
    if not text.isdigit():
        raise ValueError(f'{label} must be a valid positive whole number.')
    try:
        number=int(text)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f'{label} must be a valid positive whole number.')
    if number <= 0:
        raise ValueError(f'{label} must be a valid positive whole number.')
    return number

def _unit_dimension(unit):
    unit = str(unit or '').strip().casefold()
    if unit in {'kg', 'g', 'gram', 'grams'}:
        return 'mass'
    if unit in {'l', 'ml', 'litre', 'liter', 'litres', 'liters'}:
        return 'volume'
    if unit in {'pcs', 'piece', 'pieces'}:
        return 'count'
    return None


def _purchase_values(items, purchase_date=None):
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError('Add at least one purchase item.')
    cleaned = []
    total = Decimal('0.00')
    for index, item in enumerate(items, 1):
        if not isinstance(item, dict):
            raise ValueError(f'Purchase item {index} is invalid.')
        product_id = _optional_id(item.get('product_id'), f'Product ID on item {index}')
        if product_id is None:
            raise ValueError(f'Product ID on item {index} is required.')
        quantity = _number(item.get('quantity'), f'Quantity on item {index}', strictly_positive=True)
        unit_price = _nonnegative_money(item.get('unit_price'), f'Unit price on item {index}')
        expiry = _future_expiry_date(item.get('expiry_date'), f'Expiry date on item {index}')
        if expiry and purchase_date and expiry < purchase_date:
            raise ValueError(f'Expiry date on item {index} cannot be earlier than the purchase date.')
        # SQLite stores quantities as REAL; calculate against the same representable value
        # that will be persisted so the line total cannot drift from the stored quantity.
        line_total = money(Decimal(str(quantity)) * unit_price)
        total += line_total
        cleaned.append({
            'product_id': product_id, 'quantity': quantity, 'unit_price': unit_price,
            'expiry_date': expiry, 'batch_code': str(item.get('batch_code') or '').strip(),
            'line_total': line_total,
        })
    return cleaned, money(total)


REQUIRED_BACKUP_COLUMNS = {
    'products': {'id','name','unit','quantity','min_quantity','price'},
    'product_batches': {'id','product_id','quantity','unit_cost','purchase_date','expiry_date'},
    'purchases': {'id','purchase_date','total','store_id','member_id'},
    'purchase_items': {'id','purchase_id','product_id','quantity','unit_price','line_total','batch_id'},
    'expenses': {'id','expense_date','category','amount','purchase_id'},
    'budgets': {'id','category','amount','start_date','end_date','alert_50','alert_75','alert_90','alert_100'},
    'shopping_lists': {'id','name','list_date','status','notes'},
    'shopping_list_items': {'id','list_id','name','quantity','unit','unit_price','status'},
    'recurring_shopping': {'id','name','interval_days','next_due','active'},
    'price_history': {'id','product_id','store_id','package_quantity','package_unit','price','recorded_date'},
    'waste_records': {'id','product_id','quantity','reason','waste_date','unit_cost'},
    'notifications': {'id','title','message','priority','is_read','fingerprint'},
    'settings': {'key','value'},
    'categories': {'id','name'},
    'stores': {'id','name'},
    'household_members': {'id','name','role'},
    'stock_movements': {'id','product_id','movement_type','quantity'},
}


def validate_backup(path):
    """Validate SQLite integrity, foreign keys, and the app's required schema."""
    backup_path = Path(path)
    if not backup_path.is_file():
        raise ValueError('The selected backup file does not exist.')
    try:
        con = sqlite3.connect(str(backup_path), timeout=10)
        con.row_factory=sqlite3.Row
        try:
            integrity = con.execute('PRAGMA integrity_check').fetchone()
            if not integrity or integrity[0] != 'ok':
                raise ValueError('The backup database failed SQLite integrity validation.')
            if con.execute('PRAGMA foreign_key_check').fetchone() is not None:
                raise ValueError('The backup contains broken foreign-key references.')
            tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            missing_tables = set(REQUIRED_BACKUP_COLUMNS) - tables
            if missing_tables:
                raise ValueError('The backup is missing required tables: ' + ', '.join(sorted(missing_tables)))
            for table, required in REQUIRED_BACKUP_COLUMNS.items():
                columns = {row[1] for row in con.execute(f'PRAGMA table_info("{table}")')}
                missing = required - columns
                if missing:
                    raise ValueError(f'The backup table {table} is missing required columns: ' + ', '.join(sorted(missing)))
            # Validate critical stored values, not only the SQLite file structure.
            numeric_rules = {
                'products': {'quantity': False, 'min_quantity': False},
                'product_batches': {'quantity': False},
                'purchase_items': {'quantity': True},
                'shopping_list_items': {'quantity': True},
                'price_history': {'package_quantity': True},
                'waste_records': {'quantity': True},
            }
            for table, fields in numeric_rules.items():
                for row in con.execute(f'SELECT id,{",".join(fields)} FROM {table}'):
                    for field, positive in fields.items():
                        try: value=float(row[field])
                        except (TypeError,ValueError,OverflowError):
                            raise ValueError(f'The backup contains an invalid {field} value in {table} record {row['id']}.')
                        if not math.isfinite(value) or (value < MIN_QUANTITY_STEP if positive else value < 0) or value > 1.0e308 or (not positive and table=='products' and field in {'quantity','min_quantity'} and 0<value<MIN_QUANTITY_STEP):
                            raise ValueError(f'The backup contains an invalid {field} value in {table} record {row['id']}.')
            money_rules = {
                'products': {'price': False}, 'product_batches': {'unit_cost': False},
                'purchases': {'total': False}, 'purchase_items': {'unit_price': False, 'line_total': False},
                'shopping_list_items': {'unit_price': False}, 'price_history': {'price': False},
                'waste_records': {'unit_cost': False}, 'budgets': {'amount': True},
                'expenses': {'amount': False},
            }
            for table, fields in money_rules.items():
                for row in con.execute(f'SELECT id,{",".join(fields)} FROM {table}'):
                    for field, positive in fields.items():
                        try: value=Decimal(str(row[field]))
                        except (InvalidOperation, TypeError, ValueError):
                            raise ValueError(f'The backup contains an invalid monetary value in {table} record {row['id']}.')
                        if not value.is_finite() or value < 0 or (positive and value <= 0):
                            raise ValueError(f'The backup contains an invalid monetary value in {table} record {row['id']}.')
            date_rules = {
                'purchases': ('purchase_date',), 'expenses': ('expense_date',),
                'shopping_lists': ('list_date',), 'budgets': ('start_date','end_date'),
                'price_history': ('recorded_date',), 'waste_records': ('waste_date',),
                'recurring_shopping': ('next_due',), 'product_batches': ('purchase_date','expiry_date'),
            }
            for table, fields in date_rules.items():
                for row in con.execute(f'SELECT id,{",".join(fields)} FROM {table}'):
                    for field in fields:
                        value=row[field]
                        if value in (None,'') and table=='product_batches' and field=='expiry_date': continue
                        try: parsed=date.fromisoformat(str(value))
                        except (TypeError,ValueError):
                            raise ValueError(f'The backup contains an invalid date in {table} record {row['id']}.')
                        if parsed.isoformat()!=value:
                            raise ValueError(f'The backup contains a non-ISO date in {table} record {row['id']}.')
            for row in con.execute('SELECT id,start_date,end_date FROM budgets'):
                if row['end_date'] < row['start_date']:
                    raise ValueError(f'The backup contains a reversed budget date range in budget {row['id']}.')
            today_iso=date.today().isoformat()
            for table, field in (('purchases','purchase_date'),('expenses','expense_date'),('price_history','recorded_date'),('waste_records','waste_date')):
                for row in con.execute(f'SELECT id,{field} FROM {table}'):
                    if row[field] > today_iso:
                        raise ValueError(f'The backup contains a future {field} in {table} record {row['id']}.')
            for row in con.execute('SELECT id,purchase_date FROM product_batches WHERE purchase_date IS NOT NULL'):
                if row['purchase_date'] > today_iso:
                    raise ValueError(f'The backup contains a future batch purchase date in batch {row['id']}.')
            for row in con.execute('SELECT id,interval_days FROM recurring_shopping'):
                try: interval=int(row['interval_days'])
                except (TypeError,ValueError,OverflowError): interval=0
                if not 1 <= interval <= 365:
                    raise ValueError(f'The backup contains an invalid recurring interval in schedule {row['id']}.')
            overlaps=con.execute('''SELECT a.id,b.id,a.category FROM budgets a JOIN budgets b
                ON a.id<b.id AND a.category=b.category AND NOT(a.end_date<b.start_date OR a.start_date>b.end_date) LIMIT 1''').fetchone()
            if overlaps:
                raise ValueError(f'The backup contains overlapping budgets {overlaps[0]} and {overlaps[1]} for category {overlaps[2]}.')
            for product in con.execute('SELECT id,quantity FROM products'):
                batch_total=con.execute('SELECT COALESCE(SUM(quantity),0) FROM product_batches WHERE product_id=?',(product['id'],)).fetchone()[0]
                if not math.isclose(float(product['quantity']),float(batch_total),rel_tol=1e-9,abs_tol=STOCK_EPSILON):
                    raise ValueError(f'The backup has a stock/batch mismatch for product {product['id']}.')
            for row in con.execute('''SELECT ph.id,ph.package_unit,p.unit product_unit FROM price_history ph
                                      JOIN products p ON p.id=ph.product_id'''):
                if _unit_dimension(row['product_unit']) is None or _unit_dimension(row['package_unit']) != _unit_dimension(row['product_unit']):
                    raise ValueError(f'The backup contains incompatible price units in price record {row['id']}.')
            for row in con.execute('SELECT id,amount,purchase_id FROM expenses'):
                if row['purchase_id'] is None and money(row['amount']) <= 0:
                    raise ValueError(f'The backup contains a zero-value manual expense in record {row['id']}.')
            for purchase in con.execute('SELECT id,total FROM purchases'):
                items=con.execute('SELECT id,quantity,unit_price,line_total FROM purchase_items WHERE purchase_id=?',(purchase['id'],)).fetchall()
                if not items:
                    raise ValueError(f'The backup contains purchase {purchase['id']} without any line items.')
                expected_total=Decimal('0.00')
                for item in items:
                    unit_price=money(item['unit_price'])
                    line_total=money(item['line_total'])
                    expected_line=money(Decimal(str(item['quantity']))*unit_price)
                    if expected_line != line_total:
                        raise ValueError(f'The backup contains an inconsistent line total in purchase item {item['id']}.')
                    returned_rows=con.execute("SELECT quantity FROM stock_movements WHERE reference=? AND movement_type='Purchase return'",(f"PURCHASE-ITEM-{item['id']}",)).fetchall()
                    returned=sum((Decimal(str(-r['quantity'])) for r in returned_rows),Decimal('0'))
                    if returned < 0 or returned > Decimal(str(item['quantity']))+Decimal(str(STOCK_EPSILON)):
                        raise ValueError(f'The backup contains an invalid returned quantity in purchase item {item['id']}.')
                    expected_total += line_total - money(returned*unit_price)
                expected_total=money(expected_total)
                if money(purchase['total']) != expected_total:
                    raise ValueError(f'The backup purchase total does not match its items and returns for purchase {purchase['id']}.')
                expense=con.execute('SELECT amount FROM expenses WHERE purchase_id=?',(purchase['id'],)).fetchone()
                if not expense or money(expense['amount']) != money(purchase['total']):
                    raise ValueError(f'The backup is missing or has an inconsistent linked expense for purchase {purchase['id']}.')
        finally:
            con.close()
    except sqlite3.DatabaseError as exc:
        raise ValueError('The selected file is not a readable SQLite database.') from exc
    return True


class Database:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as con:
            con.executescript(SCHEMA)
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('theme','Light')")
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('currency','INR')")
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('language','English')")
            con.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('date_format','%d-%m-%Y')")

    @contextmanager
    def connect(self):
        con = sqlite3.connect(self.path, timeout=15)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        try:
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def seed_demo_data(self):
        with self.connect() as c:
            if c.execute('SELECT COUNT(*) FROM products').fetchone()[0]:
                return
            for name in ['Fruits','Dairy','Bakery','Vegetables','Meat','Household','Personal Care']:
                c.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(name,))
            for name in ['Fresh Farms Co.','Dairy Best','Golden Bakery','Sunny Farm','Green Valley','Premium Meats','Value Mart']:
                c.execute('INSERT OR IGNORE INTO stores(name) VALUES(?)',(name,))
            if not c.execute("SELECT 1 FROM household_members WHERE name='Admin User' AND role='Owner' LIMIT 1").fetchone():
                c.execute("INSERT INTO household_members(name,role) VALUES('Admin User','Owner')")
            samples = [
                ('Organic Bananas','Fruits','kg',245,100,'2.99','Fresh Farms Co.','2027-01-20'),
                ('Fresh Milk','Dairy','L',156,150,'3.99','Dairy Best','2026-11-20'),
                ('Wheat Bread','Bakery','pcs',0,50,'2.49','Golden Bakery','2026-11-16'),
                ('Range Eggs','Dairy','dozen',89,100,'5.99','Sunny Farm','2026-11-25'),
                ('Cherry Tomatoes','Vegetables','kg',178,80,'4.99','Green Valley','2026-11-22'),
                ('Chicken Breast','Meat','kg',124,100,'8.99','Premium Meats','2026-11-19'),
                ('Greek Yogurt','Dairy','pcs',0,60,'4.49','Dairy Best','2026-11-18'),
                ('Dishwashing Liquid','Household','L',12,4,'3.50','Value Mart','2027-06-01'),
                ('Toothpaste','Personal Care','pcs',8,3,'2.25','Value Mart','2027-08-01'),
                ('Apples','Fruits','kg',24,8,'3.20','Fresh Farms Co.','2026-12-01'),
            ]
            for name,cat,unit,qty,minimum,price,store,expiry in samples:
                catid=c.execute('SELECT id FROM categories WHERE name=?',(cat,)).fetchone()[0]
                sid=c.execute('SELECT id FROM stores WHERE name=?',(store,)).fetchone()[0]
                pid=c.execute('INSERT INTO products(name,category_id,unit,quantity,min_quantity,price,store_id) VALUES(?,?,?,?,?,?,?)',(name,catid,unit,qty,minimum,price,sid)).lastrowid
                if qty:
                    c.execute('INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date,expiry_date) VALUES(?,?,?,?,?,?)',(pid,'DEMO-'+str(pid),qty,price,date.today().isoformat(),expiry))
                c.execute('INSERT INTO stock_movements(product_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?)',(pid,'Opening',qty,'DEMO','Demonstration opening stock'))
            for pname,store,qty,unit,price in [('Fresh Milk','Fresh Farms Co.',1,'L','3.75'),('Fresh Milk','Dairy Best',1,'L','3.99'),('Fresh Milk','Value Mart',0.5,'L','2.10'),('Organic Bananas','Fresh Farms Co.',1,'kg','2.99'),('Organic Bananas','Value Mart',1,'kg','3.20'),('Eggs','Sunny Farm',12,'pcs','5.99')]:
                p=c.execute('SELECT id FROM products WHERE name=?',(pname,)).fetchone()
                s=c.execute('SELECT id FROM stores WHERE name=?',(store,)).fetchone()
                if p and s: c.execute('INSERT INTO price_history(product_id,store_id,package_quantity,package_unit,price,recorded_date) VALUES(?,?,?,?,?,?)',(p[0],s[0],qty,unit,price,date.today().isoformat()))
            c.execute("INSERT INTO shopping_lists(name,list_date,notes) VALUES('Weekly Essentials',?,'Editable demonstration list')",(date.today().isoformat(),))
            lid=c.execute('SELECT last_insert_rowid()').fetchone()[0]
            for name,qty,unit,price in [('Fresh Milk',2,'L','3.99'),('Organic Bananas',1,'kg','2.99'),('Wheat Bread',1,'pcs','2.49')]:
                p=c.execute('SELECT id,category_id FROM products WHERE name=?',(name,)).fetchone()
                cat=c.execute('SELECT name FROM categories WHERE id=?',(p['category_id'],)).fetchone()[0]
                c.execute('INSERT INTO shopping_list_items(list_id,product_id,name,category,quantity,unit,unit_price) VALUES(?,?,?,?,?,?,?)',(lid,p['id'],name,cat,qty,unit,price))

    def rows(self, sql, params=()):
        with self.connect() as c: return [dict(r) for r in c.execute(sql,params).fetchall()]
    def one(self, sql, params=()):
        with self.connect() as c:
            r=c.execute(sql,params).fetchone(); return dict(r) if r else None
    def execute(self, sql, params=()):
        with self.connect() as c: cur=c.execute(sql,params); return cur.lastrowid
    def setting(self,key,default=''):
        r=self.one('SELECT value FROM settings WHERE key=?',(key,)); return r['value'] if r else default
    def set_setting(self,key,value): self.execute('INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,str(value)))

    def add_member(self, data):
        name=_required(data.get('name'), 'Member name')
        role=_required(data.get('role','Member'), 'Member role')
        phone=str(data.get('phone') or '').strip()
        if len(name)>100 or len(role)>40 or len(phone)>30:
            raise ValueError('Member name, role or phone number is too long.')
        if phone:
            import phonenumbers
            try: parsed=phonenumbers.parse(phone, None)
            except phonenumbers.NumberParseException as exc: raise ValueError('Phone number must include a valid country calling code.') from exc
            if not phonenumbers.is_valid_number(parsed) or not phonenumbers.is_possible_number(parsed) or phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)!=phone:
                raise ValueError('Enter a valid international phone number.')
        return self.execute('INSERT INTO household_members(name,role,phone) VALUES(?,?,?)',(name,role,phone))

    def add_shopping_list(self, data):
        name=_required(data.get('name'), 'Shopping list name')
        list_date=_date(data.get('list_date',date.today().isoformat()), 'Shopping list date')
        return self.execute('INSERT INTO shopping_lists(name,list_date,notes) VALUES(?,?,?)',(name,list_date,data.get('notes','')))

    def add_shopping_item(self, data):
        name=_required(data.get('name'), 'Shopping item name')
        unit=_required(data.get('unit','pcs'), 'Shopping item unit')
        quantity=_number(data.get('quantity',1), 'Shopping quantity', strictly_positive=True)
        price=_nonnegative_money(data.get('unit_price',0), 'Shopping item price')
        priority=_required(data.get('priority','Normal'), 'Priority')
        if priority not in {'Low','Normal','High'}: raise ValueError('Priority must be Low, Normal or High.')
        list_id=_optional_id(data.get('list_id'), 'Shopping list ID')
        with self.connect() as c:
            if not c.execute('SELECT id FROM shopping_lists WHERE id=?',(list_id,)).fetchone():
                raise ValueError('Selected shopping list does not exist.')
            cur=c.execute('INSERT INTO shopping_list_items(list_id,name,category,quantity,unit,unit_price,priority) VALUES(?,?,?,?,?,?,?)',
                (list_id,name,str(data.get('category') or 'Grocery'),quantity,unit,str(price),priority))
            c.execute("UPDATE shopping_lists SET status='Open' WHERE id=?",(list_id,))
            return cur.lastrowid

    def mark_shopping_item_purchased(self, item_id, actual_price):
        item_id=_optional_id(item_id, 'Shopping item ID')
        price=_nonnegative_money(actual_price, 'Actual price')
        with self.connect() as c:
            item=c.execute('SELECT list_id,status FROM shopping_list_items WHERE id=?',(item_id,)).fetchone()
            if not item or item['status']=='Purchased': raise ValueError('Shopping item not found or already purchased.')
            cur=c.execute("UPDATE shopping_list_items SET status='Purchased',actual_price=? WHERE id=? AND status!='Purchased'",(str(price),item_id))
            if not cur.rowcount: raise ValueError('Shopping item was already purchased or changed.')
            pending=c.execute("SELECT COUNT(*) FROM shopping_list_items WHERE list_id=? AND status!='Purchased'",(item['list_id'],)).fetchone()[0]
            if pending==0: c.execute("UPDATE shopping_lists SET status='Completed' WHERE id=?",(item['list_id'],))

    def convert_shopping_item_to_purchase(self, item_id, quantity, unit_price, purchase_date=None,
                                          expiry_date=None, payment_method='Cash'):
        """Atomically convert one pending shopping item into a purchase and stock receipt."""
        q = _number(quantity, 'Purchased quantity', strictly_positive=True)
        price = _nonnegative_money(unit_price, 'Actual unit price')
        purchase_date = _date_not_future(purchase_date or date.today().isoformat(), 'Purchase date')
        expiry_date = _future_expiry_date(expiry_date, 'Batch expiry date')
        if expiry_date and expiry_date < purchase_date:
            raise ValueError('Batch expiry date cannot be earlier than the purchase date.')
        payment_method = _required(payment_method, 'Payment method')
        with self.connect() as c:
            item = c.execute('SELECT * FROM shopping_list_items WHERE id=?', (item_id,)).fetchone()
            if not item or item['status'] == 'Purchased':
                raise ValueError('Shopping item not found or already purchased.')
            product_id = item['product_id']
            if product_id:
                product = c.execute('SELECT id,name,unit,quantity FROM products WHERE id=?', (product_id,)).fetchone()
                if not product:
                    raise ValueError('The linked product no longer exists. Edit the shopping item and choose a valid product.')
                if str(product['unit']).strip().casefold() != str(item['unit']).strip().casefold():
                    raise ValueError('Shopping item unit does not match the linked product unit.')
            else:
                product = c.execute('SELECT id,name,unit,quantity FROM products WHERE name=? COLLATE NOCASE', (item['name'],)).fetchone()
                if product:
                    if str(product['unit']).strip().casefold() != str(item['unit']).strip().casefold():
                        raise ValueError('A product with this name already exists with a different unit. Link the correct product or rename the shopping item.')
                    product_id = product['id']
                else:
                    category = str(item['category'] or 'Grocery').strip() or 'Grocery'
                    c.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)', (category,))
                    category_id = c.execute('SELECT id FROM categories WHERE name=?', (category,)).fetchone()[0]
                    product_id = c.execute(
                        'INSERT INTO products(name,category_id,unit,quantity,min_quantity,price) VALUES(?,?,?,?,?,?)',
                        (item['name'].strip(), category_id, item['unit'], 0, 1, str(price))
                    ).lastrowid
                    product = c.execute('SELECT id,name,unit,quantity FROM products WHERE id=?', (product_id,)).fetchone()
            if not product:
                product = c.execute('SELECT id,name,unit,quantity FROM products WHERE id=?', (product_id,)).fetchone()
            new_quantity = _number(Decimal(str(product['quantity'])) + Decimal(str(q)), 'Updated stock', minimum=0)
            line_total = money(Decimal(str(q)) * price)
            purchase_id = c.execute(
                'INSERT INTO purchases(purchase_date,payment_method,notes,total) VALUES(?,?,?,?)',
                (purchase_date, payment_method, f'Converted from shopping list #{item["list_id"]}', str(line_total))
            ).lastrowid
            batch_id = c.execute(
                'INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date,expiry_date) VALUES(?,?,?,?,?,?)',
                (product_id, f'SHOPPING-{item_id}', q, str(price), purchase_date, expiry_date)
            ).lastrowid
            c.execute('UPDATE products SET quantity=?,price=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                      (new_quantity, str(price), product_id))
            c.execute('INSERT INTO purchase_items(purchase_id,product_id,quantity,unit_price,line_total,batch_id) VALUES(?,?,?,?,?,?)',
                      (purchase_id, product_id, q, str(price), str(line_total), batch_id))
            c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',
                      (product_id, batch_id, 'Purchase', q, f'PURCHASE-{purchase_id}', 'Converted from shopping list'))
            c.execute('INSERT INTO expenses(expense_date,category,description,amount,purchase_id) VALUES(?,?,?,?,?)',
                      (purchase_date, 'Groceries', f'Purchase #{purchase_id}', str(line_total), purchase_id))
            c.execute("UPDATE shopping_list_items SET product_id=?,status='Purchased',actual_price=? WHERE id=? AND status!='Purchased'",
                      (product_id, str(price), item_id))
            if c.execute('SELECT changes()').fetchone()[0] != 1:
                raise ValueError('The shopping item was changed by another operation. No purchase was saved.')
            pending = c.execute("SELECT COUNT(*) FROM shopping_list_items WHERE list_id=? AND status!='Purchased'", (item['list_id'],)).fetchone()[0]
            if pending == 0:
                c.execute("UPDATE shopping_lists SET status='Completed' WHERE id=?", (item['list_id'],))
            return purchase_id

    def add_store(self, data):
        name=_required(data.get('name'), 'Store name')
        try:
            return self.execute('INSERT INTO stores(name,address,notes) VALUES(?,?,?)',(name,data.get('address',''),data.get('notes','')))
        except sqlite3.IntegrityError as exc:
            raise ValueError('A store with this name already exists.') from exc

    def add_price_record(self, data):
        quantity=_number(data.get('package_quantity'), 'Package quantity', strictly_positive=True)
        price=_nonnegative_money(data.get('price'), 'Package price')
        unit=_required(data.get('package_unit'), 'Package unit').lower()
        if unit not in {'kg','g','l','ml','pcs','piece','pieces'}:
            raise ValueError('Package unit must be kg, g, L, ml or pcs.')
        recorded=_date_not_future(data.get('recorded_date'), 'Price record date')
        product_id=_optional_id(data.get('product_id'), 'Product ID')
        store_id=_optional_id(data.get('store_id'), 'Store ID')
        product=self.one('SELECT id,unit FROM products WHERE id=?',(product_id,)) if product_id else None
        if not product:
            raise ValueError('Selected product does not exist.')
        if not self.one('SELECT id FROM stores WHERE id=?',(store_id,)):
            raise ValueError('Selected store does not exist.')
        expected=_unit_dimension(product['unit'])
        actual=_unit_dimension(unit)
        if expected is None:
            raise ValueError('Price comparison supports products measured in kg/g, L/ml or pieces. This product unit cannot be normalized safely.')
        if actual != expected:
            raise ValueError(f'Package unit is incompatible with this product. Use a {expected} measurement unit.')
        factor={'kg':1000,'g':1,'l':1000,'ml':1,'pcs':1,'piece':1,'pieces':1}[unit]
        normalized_price=float(price)/(quantity*factor)
        if not math.isfinite(normalized_price):
            raise ValueError('Package size is too small to calculate a reliable unit price.')
        return self.execute('INSERT INTO price_history(product_id,store_id,package_quantity,package_unit,price,recorded_date) VALUES(?,?,?,?,?,?)',
            (product_id,store_id,quantity,unit,str(price),recorded))

    def add_budget(self, data):
        name=_required(data.get('name'), 'Budget name')
        category=_required(data.get('category','All'), 'Budget category')
        period=_required(data.get('period','Monthly'), 'Budget period')
        if period not in {'Weekly','Monthly','Quarterly','Yearly','Custom'}:
            raise ValueError('Budget period must be Weekly, Monthly, Quarterly, Yearly or Custom.')
        amount=_nonnegative_money(data.get('amount'), 'Budget amount', strictly_positive=True)
        start,end=_validate_date_range(data.get('start_date'),data.get('end_date'))
        with self.connect() as c:
            overlap=c.execute('SELECT 1 FROM budgets WHERE category=? AND NOT(end_date<? OR start_date>?) LIMIT 1',(category,start,end)).fetchone()
            if overlap:
                raise ValueError(f'An active or historical budget for {category} already overlaps these dates. Edit its dates or choose a non-overlapping period.')
            return c.execute('INSERT INTO budgets(name,category,period,amount,start_date,end_date) VALUES(?,?,?,?,?,?)',
                (name,category,period,str(amount),start,end)).lastrowid

    def update_budget(self, budget_id, data):
        budget_id=_optional_id(budget_id, 'Budget ID')
        name=_required(data.get('name'), 'Budget name')
        category=_required(data.get('category','All'), 'Budget category')
        period=_required(data.get('period','Monthly'), 'Budget period')
        if period not in {'Weekly','Monthly','Quarterly','Yearly','Custom'}:
            raise ValueError('Budget period must be Weekly, Monthly, Quarterly, Yearly or Custom.')
        amount=_nonnegative_money(data.get('amount'), 'Budget amount', strictly_positive=True)
        start,end=_validate_date_range(data.get('start_date'),data.get('end_date'))
        with self.connect() as c:
            if not c.execute('SELECT 1 FROM budgets WHERE id=?',(budget_id,)).fetchone():
                raise ValueError('Budget not found.')
            overlap=c.execute('SELECT 1 FROM budgets WHERE category=? AND id!=? AND NOT(end_date<? OR start_date>?) LIMIT 1',(category,budget_id,start,end)).fetchone()
            if overlap:
                raise ValueError(f'Another budget for {category} already overlaps these dates.')
            c.execute('UPDATE budgets SET name=?,category=?,period=?,amount=?,start_date=?,end_date=? WHERE id=?',
                      (name,category,period,str(amount),start,end,budget_id))

    def add_product(self, data):
        name=_product_name(data.get('name'))
        qty=_number(data.get('quantity',0), 'Quantity', minimum=0); minimum=_number(data.get('min_quantity',1), 'Minimum stock', minimum=0)
        if 0 < qty < MIN_QUANTITY_STEP: raise ValueError(f'Quantity must be zero or at least {MIN_QUANTITY_STEP:g}.')
        if 0 < minimum < MIN_QUANTITY_STEP: raise ValueError(f'Minimum stock must be zero or at least {MIN_QUANTITY_STEP:g}.')
        price=_nonnegative_money(data.get('price',0), 'Price')
        expiry=_future_expiry_date(data.get('expiry_date'), 'Expiry date')
        if expiry and qty<=0: raise ValueError('An opening expiry date requires a positive opening stock quantity.')
        unit=_required(data.get('unit','pcs'), 'Unit')
        with self.connect() as c:
            if c.execute('SELECT 1 FROM products WHERE name=? COLLATE NOCASE',(name,)).fetchone():
                raise ValueError('A product with this name already exists. Use a different product name.')
            cat=str(data.get('category') or 'Other').strip() or 'Other'; c.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(cat,))
            catid=c.execute('SELECT id FROM categories WHERE name=?',(cat,)).fetchone()[0]
            sid=None
            store=str(data.get('store') or '').strip()
            if store:
                c.execute('INSERT OR IGNORE INTO stores(name) VALUES(?)',(store,)); sid=c.execute('SELECT id FROM stores WHERE name=?',(store,)).fetchone()[0]
            pid=c.execute('INSERT INTO products(name,category_id,brand,description,unit,quantity,min_quantity,price,store_id,favorite) VALUES(?,?,?,?,?,?,?,?,?,?)',
                (name,catid,data.get('brand',''),data.get('description',''),unit,qty,minimum,str(price),sid,int(bool(data.get('favorite',False))))).lastrowid
            if qty:
                bid=c.execute('INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date,expiry_date) VALUES(?,?,?,?,?,?)',(pid,'OPENING',qty,str(price),date.today().isoformat(),expiry)).lastrowid
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(pid,bid,'Opening',qty,'PRODUCT', 'Opening stock'))
            return pid

    def update_product(self,pid,data):
        pid=_optional_id(pid, 'Product ID')
        name=_product_name(data.get('name'))
        qty=_number(data.get('quantity',0), 'Quantity', minimum=0); minimum=_number(data.get('min_quantity',1), 'Minimum stock', minimum=0)
        if 0 < qty < MIN_QUANTITY_STEP: raise ValueError(f'Quantity must be zero or at least {MIN_QUANTITY_STEP:g}.')
        if 0 < minimum < MIN_QUANTITY_STEP: raise ValueError(f'Minimum stock must be zero or at least {MIN_QUANTITY_STEP:g}.')
        price=_nonnegative_money(data.get('price',0), 'Price')
        unit=_required(data.get('unit','pcs'), 'Unit')
        with self.connect() as c:
            old=c.execute('SELECT quantity,unit FROM products WHERE id=?',(pid,)).fetchone()
            if not old: raise ValueError('Product not found.')
            duplicate=c.execute('SELECT 1 FROM products WHERE name=? COLLATE NOCASE AND id!=?',(name,pid)).fetchone()
            if duplicate: raise ValueError('Another product already uses this name. Choose a different name.')
            batch_stock = c.execute('SELECT COALESCE(SUM(quantity),0) FROM product_batches WHERE product_id=?', (pid,)).fetchone()[0]
            if unit.strip().casefold() != str(old['unit']).strip().casefold():
                history=sum(c.execute(f'SELECT COUNT(*) FROM {table} WHERE product_id=?',(pid,)).fetchone()[0]
                            for table in ('purchase_items','stock_movements','price_history','waste_records'))
                if float(old['quantity']) > STOCK_EPSILON or float(batch_stock) > STOCK_EPSILON or history:
                    raise ValueError('The unit cannot be changed after stock or transaction history exists. Create a separate product with the correct unit to preserve historical records.')
            if c.execute('SELECT 1 FROM products WHERE name=? COLLATE NOCASE AND id!=?',(name,pid)).fetchone():
                raise ValueError('Another product already uses this name.')
            category=str(data.get('category') or 'Other').strip() or 'Other'
            c.execute('INSERT OR IGNORE INTO categories(name) VALUES(?)',(category,))
            catid=c.execute('SELECT id FROM categories WHERE name=?',(category,)).fetchone()[0]
            sid=None
            store=str(data.get('store') or '').strip()
            if store:
                c.execute('INSERT OR IGNORE INTO stores(name) VALUES(?)',(store,)); sid=c.execute('SELECT id FROM stores WHERE name=?',(store,)).fetchone()[0]
            c.execute('UPDATE products SET name=?,category_id=?,brand=?,description=?,unit=?,quantity=?,min_quantity=?,price=?,store_id=?,favorite=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                (name,catid,data.get('brand',''),data.get('description',''),unit,qty,minimum,str(price),sid,int(bool(data.get('favorite',False))),pid))
            delta=qty-float(old['quantity'])
            if abs(delta)>STOCK_EPSILON:
                batch_movements=[]
                if delta>0:
                    batch_id=c.execute('INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date) VALUES(?,?,?,?,?)',(pid,'MANUAL-ADJUSTMENT',delta,str(price),date.today().isoformat())).lastrowid
                    batch_movements.append((batch_id,delta))
                else:
                    remaining=-delta
                    batches=c.execute('SELECT id,quantity FROM product_batches WHERE product_id=? AND quantity>0 ORDER BY CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END,expiry_date,id',(pid,)).fetchall()
                    for batch in batches:
                        take=min(remaining,batch['quantity'])
                        c.execute('UPDATE product_batches SET quantity=? WHERE id=?',(_clamp_stock(batch['quantity']-take),batch['id']))
                        batch_movements.append((batch['id'],-take))
                        remaining-=take
                        if remaining<=STOCK_EPSILON: break
                    if remaining>STOCK_EPSILON: raise ValueError('Stock batches do not match the product quantity. Reconcile inventory before adjusting stock.')
                for batch_id,movement_quantity in batch_movements:
                    c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(pid,batch_id,'Adjustment',movement_quantity,'MANUAL','Manual quantity adjustment'))

    def update_batch(self, batch_id, data):
        batch_id=_optional_id(batch_id, 'Batch ID')
        with self.connect() as c:
            batch=c.execute('SELECT purchase_date,batch_code,expiry_date,unit_cost FROM product_batches WHERE id=?',(batch_id,)).fetchone()
            if not batch: raise ValueError('Stock batch not found.')
            expiry=_date(data.get('expiry_date',batch['expiry_date']), 'Expiry date', optional=True)
            if expiry != batch['expiry_date'] and expiry and expiry <= date.today().isoformat():
                raise ValueError('A revised expiry date must be in the future (after today).')
            unit_cost=_nonnegative_money(data.get('unit_cost',batch['unit_cost']), 'Unit cost')
            batch_code=str(data.get('batch_code',batch['batch_code']) or '').strip()
            if len(batch_code)>100: raise ValueError('Batch code cannot exceed 100 characters.')
            purchase_date=batch['purchase_date']
            original_code=str(batch['batch_code'] or '').strip().upper()
            if expiry and purchase_date and original_code not in {'OPENING','MANUAL-ADJUSTMENT'} and expiry < purchase_date:
                raise ValueError('Expiry date cannot be earlier than this batch purchase date.')
            c.execute('UPDATE product_batches SET batch_code=?,expiry_date=?,unit_cost=? WHERE id=?',
                      (batch_code,expiry,str(unit_cost),batch_id))

    def delete_product(self,pid):
        pid=_optional_id(pid, 'Product ID')
        with self.connect() as c:
            product=c.execute('SELECT quantity FROM products WHERE id=?',(pid,)).fetchone()
            if not product: raise ValueError('Product not found.')
            batch_total=c.execute('SELECT COALESCE(SUM(quantity),0) FROM product_batches WHERE product_id=?',(pid,)).fetchone()[0]
            if float(product['quantity'])>STOCK_EPSILON or float(batch_total)>STOCK_EPSILON:
                raise ValueError('This product still has stock. Reduce the quantity to zero before deleting it.')
            history=sum(c.execute(f'SELECT COUNT(*) FROM {table} WHERE product_id=?',(pid,)).fetchone()[0]
                         for table in ('purchase_items','waste_records','stock_movements','price_history'))
            if history:
                raise ValueError('This product has transaction or price history and cannot be deleted. Keep it with zero stock to preserve the audit trail.')
            c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE related_type='product' AND related_id=?",(pid,))
            c.execute('DELETE FROM products WHERE id=?',(pid,))

    def create_purchase(self, data):
        purchase_date = _date_not_future(data.get('purchase_date', date.today().isoformat()), 'Purchase date')
        items, total = _purchase_values(data.get('items', []), purchase_date)
        payment_method = _required(data.get('payment_method', 'Cash'), 'Payment method')
        store_id = _optional_id(data.get('store_id'), 'Store ID')
        member_id = _optional_id(data.get('member_id'), 'Household member ID')
        with self.connect() as c:
            if store_id and not c.execute('SELECT 1 FROM stores WHERE id=?', (store_id,)).fetchone():
                raise ValueError('Selected store does not exist.')
            if member_id and not c.execute('SELECT 1 FROM household_members WHERE id=?', (member_id,)).fetchone():
                raise ValueError('Selected household member does not exist.')
            pid = c.execute(
                'INSERT INTO purchases(purchase_date,store_id,member_id,payment_method,notes,total) VALUES(?,?,?,?,?,?)',
                (purchase_date, store_id, member_id, payment_method, str(data.get('notes') or ''), str(total))
            ).lastrowid
            for item in items:
                product = c.execute('SELECT id,quantity FROM products WHERE id=?', (item['product_id'],)).fetchone()
                if not product:
                    raise ValueError(f"Product ID {item['product_id']} does not exist.")
                new_quantity = _number(Decimal(str(product['quantity'])) + Decimal(str(item['quantity'])), 'Updated stock', minimum=0)
                batch_id = c.execute(
                    'INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date,expiry_date) VALUES(?,?,?,?,?,?)',
                    (item['product_id'], item['batch_code'], item['quantity'], str(item['unit_price']), purchase_date, item['expiry_date'])
                ).lastrowid
                c.execute('UPDATE products SET quantity=?,price=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                          (new_quantity, str(item['unit_price']), item['product_id']))
                c.execute('INSERT INTO purchase_items(purchase_id,product_id,quantity,unit_price,line_total,batch_id) VALUES(?,?,?,?,?,?)',
                          (pid, item['product_id'], item['quantity'], str(item['unit_price']), str(item['line_total']), batch_id))
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',
                          (item['product_id'], batch_id, 'Purchase', item['quantity'], f'PURCHASE-{pid}', 'Purchase received'))
            c.execute('INSERT INTO expenses(expense_date,category,description,amount,member_id,purchase_id) VALUES(?,?,?,?,?,?)',
                      (purchase_date, 'Groceries', f'Purchase #{pid}', str(total), member_id, pid))
            return pid

    def delete_purchase(self,pid):
        with self.connect() as c:
            items=c.execute('SELECT id,product_id,quantity,batch_id FROM purchase_items WHERE purchase_id=?',(pid,)).fetchall()
            if not items: raise ValueError('Purchase not found.')
            retained=[]
            totals={}
            for item in items:
                returned=c.execute("SELECT COALESCE(SUM(-quantity),0) FROM stock_movements WHERE reference=? AND movement_type='Purchase return'",(f'PURCHASE-ITEM-{item["id"]}',)).fetchone()[0]
                remaining=max(0.0,float(item['quantity'])-float(returned))
                if float(returned)>float(item['quantity'])+STOCK_EPSILON:
                    raise ValueError('Return history exceeds the original purchased quantity; reconcile this purchase before deleting it.')
                if remaining > STOCK_EPSILON and not item['batch_id']:
                    raise ValueError('This older purchase has no traceable stock batch. It cannot be deleted safely; reconcile it manually first.')
                retained.append((item,remaining))
                totals[item['product_id']]=totals.get(item['product_id'],0.0)+remaining
            for product_id,required in totals.items():
                current=c.execute('SELECT quantity FROM products WHERE id=?',(product_id,)).fetchone()
                if not current or float(current['quantity'])+STOCK_EPSILON<required:
                    raise ValueError('Cannot reverse this purchase because some retained stock has already been consumed or adjusted.')
            for item,remaining in retained:
                if item['batch_id']:
                    batch=c.execute('SELECT quantity FROM product_batches WHERE id=?',(item['batch_id'],)).fetchone()
                    if not batch or float(batch['quantity'])+STOCK_EPSILON<remaining:
                        raise ValueError('This purchase batch has been partly consumed or adjusted; it cannot be deleted safely.')
            for item,remaining in retained:
                current_qty=c.execute('SELECT quantity FROM products WHERE id=?',(item['product_id'],)).fetchone()['quantity']
                c.execute('UPDATE products SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(_clamp_stock(current_qty-remaining),item['product_id']))
                if item['batch_id']:
                    batch=c.execute('SELECT quantity FROM product_batches WHERE id=?',(item['batch_id'],)).fetchone()
                    if remaining>STOCK_EPSILON or (batch and abs(float(batch['quantity']))<=STOCK_EPSILON):
                        c.execute('UPDATE product_batches SET quantity=0 WHERE id=?',(item['batch_id'],))
                if remaining>STOCK_EPSILON:
                    c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(item['product_id'],item['batch_id'],'Purchase reversal',-remaining,f'PURCHASE-{pid}','Purchase deleted after accounting for any returns'))
            c.execute('DELETE FROM purchases WHERE id=?',(pid,))

    def add_expense(self,data):
        amount=_nonnegative_money(data.get('amount'), 'Expense amount', strictly_positive=True)
        expense_date=_date_not_future(data.get('date',date.today().isoformat()), 'Expense date')
        category=_required(data.get('category'), 'Expense category')
        member_id=_optional_id(data.get('member_id'), 'Household member ID')
        with self.connect() as c:
            if member_id and not c.execute('SELECT 1 FROM household_members WHERE id=?',(member_id,)).fetchone():
                raise ValueError('Selected household member does not exist.')
            return c.execute('INSERT INTO expenses(expense_date,category,description,amount,member_id) VALUES(?,?,?,?,?)',(expense_date,category,str(data.get('description') or ''),str(amount),member_id)).lastrowid

    def consume_stock(self,pid,quantity,note='Consumption'):
        pid=_optional_id(pid, 'Product ID')
        q=_number(quantity, 'Quantity', strictly_positive=True)
        with self.connect() as c:
            p=c.execute('SELECT quantity FROM products WHERE id=?',(pid,)).fetchone()
            if not p or p['quantity']<q: raise ValueError('Insufficient stock.')
            remaining=q
            batches=c.execute('SELECT id,quantity FROM product_batches WHERE product_id=? AND quantity>0 AND (expiry_date IS NULL OR expiry_date>=?) ORDER BY CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END, expiry_date, id',(pid,date.today().isoformat())).fetchall()
            available=sum(float(b['quantity']) for b in batches)
            if available+STOCK_EPSILON<q:
                total_batches=float(c.execute('SELECT COALESCE(SUM(quantity),0) FROM product_batches WHERE product_id=?',(pid,)).fetchone()[0])
                if total_batches+STOCK_EPSILON>=q:
                    raise ValueError('There is not enough non-expired stock. Expired batches cannot be consumed; record them as wastage instead.')
                raise ValueError('Stock batches do not match the product quantity. Reconcile inventory before consuming stock.')
            for b in batches:
                take=min(remaining,b['quantity'])
                c.execute('UPDATE product_batches SET quantity=? WHERE id=?',(_clamp_stock(b['quantity']-take),b['id']))
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(pid,b['id'],'Consumption',-take,'CONSUMPTION',note))
                remaining-=take
                if remaining<=STOCK_EPSILON: break
            if remaining>STOCK_EPSILON: raise ValueError('Stock batches do not match the product quantity. Reconcile inventory before consuming stock.')
            c.execute('UPDATE products SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(_clamp_stock(p['quantity']-q),pid))

    def record_waste(self,data):
        product_id=_optional_id(data.get('product_id'), 'Product ID')
        if product_id is None: raise ValueError('Product ID is required.')
        q=_number(data.get('quantity'), 'Wasted quantity', strictly_positive=True)
        cost=_nonnegative_money(data.get('unit_cost',0), 'Unit cost')
        waste_date=_date_not_future(data.get('date',date.today().isoformat()), 'Wastage date')
        reason=_required(data.get('reason'), 'Wastage reason')
        with self.connect() as c:
            p=c.execute('SELECT quantity FROM products WHERE id=?',(product_id,)).fetchone()
            if not p or p['quantity']<q: raise ValueError('Wastage quantity exceeds available stock.')
            remaining=q
            batch_takes=[]
            batches=c.execute('SELECT id,quantity FROM product_batches WHERE product_id=? AND quantity>0 ORDER BY CASE WHEN expiry_date IS NULL THEN 1 ELSE 0 END,expiry_date,id',(product_id,)).fetchall()
            for batch in batches:
                take=min(remaining,batch['quantity'])
                c.execute('UPDATE product_batches SET quantity=? WHERE id=?',(_clamp_stock(batch['quantity']-take),batch['id']))
                batch_takes.append((batch['id'],take))
                remaining-=take
                if remaining<=STOCK_EPSILON: break
            if remaining>STOCK_EPSILON: raise ValueError('Stock batches do not match the product quantity. Reconcile inventory before recording wastage.')
            c.execute('UPDATE products SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',(_clamp_stock(p['quantity']-q),product_id))
            waste_id=c.execute('INSERT INTO waste_records(product_id,quantity,reason,waste_date,unit_cost,notes) VALUES(?,?,?,?,?,?)',(product_id,q,reason,waste_date,str(cost),data.get('notes',''))).lastrowid
            for batch_id,take in batch_takes:
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(product_id,batch_id,'Wastage',-take,f'WASTE-{waste_id}',reason))

    def generate_notifications(self):
        with self.connect() as c:
            for p in c.execute('SELECT id,name,quantity,min_quantity FROM products').fetchall():
                if p['quantity']<=0: title='Out of stock'; msg=f"{p['name']} is out of stock."; priority='High'
                elif p['quantity']<=p['min_quantity']: title='Low stock'; msg=f"{p['name']} has {p['quantity']:g} remaining (minimum {p['min_quantity']:g})."; priority='Medium'
                else:
                    # Keep old alerts in history, but release the unique active fingerprint
                    # so a later stock drop can create a fresh alert.
                    c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE related_type='product' AND related_id=? AND fingerprint LIKE 'stock:%'", (p['id'],))
                    continue
                fp=f"stock:{p['id']}:{title}"
                c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE related_type='product' AND related_id=? AND fingerprint LIKE 'stock:%' AND fingerprint!=?", (p['id'], fp))
                c.execute('INSERT INTO notifications(title,message,priority,related_type,related_id,fingerprint) VALUES(?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET title=excluded.title,message=excluded.message,priority=excluded.priority',(title,msg,priority,'product',p['id'],fp))
            today=date.today().isoformat()
            active_budgets=c.execute('SELECT * FROM budgets WHERE start_date<=? AND end_date>=?',(today,today)).fetchall()
            active_budget_ids={int(b['id']) for b in active_budgets}
            for old_alert in c.execute("SELECT id,related_id,fingerprint FROM notifications WHERE related_type='budget' AND fingerprint LIKE 'budget:%'").fetchall():
                if old_alert['related_id'] not in active_budget_ids:
                    c.execute('UPDATE notifications SET is_read=1,fingerprint=NULL WHERE id=?',(old_alert['id'],))
            for budget in active_budgets:
                sql='SELECT COALESCE(SUM(CAST(amount AS REAL)),0) FROM expenses WHERE expense_date BETWEEN ? AND ?'
                params=[budget['start_date'],budget['end_date']]
                if budget['category']!='All': sql+=' AND category=?'; params.append(budget['category'])
                spent=float(c.execute(sql,params).fetchone()[0]); limit=float(budget['amount'] or 0)
                pref=c.execute("SELECT value FROM settings WHERE key='budget_thresholds'").fetchone()
                try: thresholds=sorted(set(int(x) for x in pref['value'].split(','))) if pref else [50,75,90,100]
                except (ValueError, AttributeError): thresholds=[50,75,90,100]
                pct=spent/limit*100 if limit>0 else 0
                # Global thresholds and per-budget switches must both allow an alert.
                reached=[x for x in thresholds if x in (50,75,90,100) and pct>=x and bool(budget[f'alert_{x}'])] if limit>0 else []
                if not reached:
                    c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE related_type='budget' AND related_id=? AND fingerprint LIKE 'budget:%'",(budget['id'],))
                    continue
                threshold=max(reached)
                title='Budget exceeded' if pct>=100 else f'Budget alert: {threshold}% threshold'
                fp=f"budget:{budget['id']}:{threshold}:{budget['start_date']}"
                c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE related_type='budget' AND related_id=? AND fingerprint LIKE 'budget:%' AND fingerprint!=?",(budget['id'],fp))
                c.execute('INSERT INTO notifications(title,message,priority,related_type,related_id,fingerprint) VALUES(?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET title=excluded.title,message=excluded.message,priority=excluded.priority',(title,f"{budget['name']}: {pct:.1f}% used ({spent:.2f} of {limit:.2f}).",'High' if pct>=90 else 'Medium','budget',budget['id'],fp))
            active_batches = c.execute("SELECT b.id,b.product_id,p.name,b.expiry_date FROM product_batches b JOIN products p ON p.id=b.product_id WHERE b.quantity>0 AND b.expiry_date IS NOT NULL").fetchall()
            active_batch_ids = {int(row['id']) for row in active_batches}
            for old_alert in c.execute("SELECT id,fingerprint FROM notifications WHERE fingerprint LIKE 'expiry:%'").fetchall():
                try: batch_id = int(old_alert['fingerprint'].split(':')[1])
                except (IndexError, ValueError): continue
                if batch_id not in active_batch_ids:
                    c.execute('UPDATE notifications SET is_read=1,fingerprint=NULL WHERE id=?', (old_alert['id'],))
            for b in active_batches:
                try:
                    days=(date.fromisoformat(b['expiry_date'])-date.today()).days
                except ValueError:
                    c.execute('UPDATE notifications SET is_read=1,fingerprint=NULL WHERE fingerprint LIKE ?', (f'expiry:{b["id"]}:%',))
                    continue
                if days>7:
                    c.execute('UPDATE notifications SET is_read=1,fingerprint=NULL WHERE fingerprint LIKE ?', (f'expiry:{b["id"]}:%',))
                    continue
                level='expired' if days<0 else ('urgent' if days<=3 else 'soon')
                title='Expired product' if days<0 else 'Expiry alert'
                msg=f"{b['name']} batch expired {abs(days)} day(s) ago." if days<0 else f"{b['name']} batch expires in {days} day(s)."
                fp=f'expiry:{b["id"]}:{level}'
                c.execute("UPDATE notifications SET is_read=1,fingerprint=NULL WHERE fingerprint LIKE ? AND fingerprint!=?", (f'expiry:{b["id"]}:%', fp))
                c.execute('INSERT INTO notifications(title,message,priority,related_type,related_id,fingerprint) VALUES(?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET title=excluded.title,message=excluded.message,priority=excluded.priority',(title,msg,'High' if days<=3 else 'Medium','product',b['product_id'],fp))

    # Advanced workflow operations added in the completion pass.
    def update_purchase(self, purchase_id, data):
        payment_method = _required(data.get('payment_method', 'Cash'), 'Payment method')
        with self.connect() as c:
            old = c.execute('SELECT * FROM purchases WHERE id=?', (purchase_id,)).fetchone()
            if not old:
                raise ValueError('Purchase not found.')
            purchase_date = _date_not_future(data.get('purchase_date', old['purchase_date']), 'Purchase date')
            items, total = _purchase_values(data.get('items', []), purchase_date)
            store_id = _optional_id(data.get('store_id', old['store_id']), 'Store ID')
            member_id = _optional_id(data.get('member_id', old['member_id']), 'Household member ID')
            if store_id and not c.execute('SELECT 1 FROM stores WHERE id=?', (store_id,)).fetchone():
                raise ValueError('Selected store does not exist.')
            if member_id and not c.execute('SELECT 1 FROM household_members WHERE id=?', (member_id,)).fetchone():
                raise ValueError('Selected household member does not exist.')
            old_items = c.execute('SELECT * FROM purchase_items WHERE purchase_id=?', (purchase_id,)).fetchall()
            # Do not rewrite a purchase if any original batch has already been returned,
            # consumed, adjusted, or otherwise reduced.
            for it in old_items:
                if not it['batch_id']:
                    raise ValueError('This purchase has no traceable stock batch and cannot be edited safely.')
                batch = c.execute('SELECT quantity FROM product_batches WHERE id=?', (it['batch_id'],)).fetchone()
                returned = c.execute("SELECT COALESCE(SUM(-quantity),0) FROM stock_movements WHERE reference=? AND movement_type='Purchase return'",
                                     (f'PURCHASE-ITEM-{it["id"]}',)).fetchone()[0]
                if returned > STOCK_EPSILON or not batch or float(batch['quantity']) + STOCK_EPSILON < float(it['quantity']):
                    raise ValueError('This purchase has been partly returned, consumed or adjusted. It cannot be edited safely; record a separate correction instead.')
            # Aggregate product-level check protects against inconsistent legacy records.
            old_totals = {}
            for it in old_items:
                old_totals[it['product_id']] = old_totals.get(it['product_id'], 0.0) + float(it['quantity'])
            for product_id, old_qty in old_totals.items():
                row = c.execute('SELECT quantity FROM products WHERE id=?', (product_id,)).fetchone()
                if not row or float(row['quantity']) + STOCK_EPSILON < old_qty:
                    raise ValueError('Current stock is inconsistent with the original purchase; reconcile inventory before editing.')
            for it in old_items:
                old_product_qty=c.execute('SELECT quantity FROM products WHERE id=?',(it['product_id'],)).fetchone()['quantity']
                c.execute('UPDATE products SET quantity=?,updated_at=CURRENT_TIMESTAMP WHERE id=?', (_clamp_stock(old_product_qty-it['quantity']), it['product_id']))
                c.execute('UPDATE product_batches SET quantity=0 WHERE id=?', (it['batch_id'],))
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',
                          (it['product_id'], it['batch_id'], 'Purchase edit reversal', -it['quantity'], f'PURCHASE-{purchase_id}', 'Previous purchase values reversed during edit'))
            c.execute('DELETE FROM purchase_items WHERE purchase_id=?', (purchase_id,))
            c.execute('UPDATE purchases SET purchase_date=?,store_id=?,member_id=?,payment_method=?,notes=?,total=? WHERE id=?',
                      (purchase_date, store_id, member_id, payment_method, str(data.get('notes') or ''), str(total), purchase_id))
            for item in items:
                product = c.execute('SELECT id,quantity FROM products WHERE id=?', (item['product_id'],)).fetchone()
                if not product:
                    raise ValueError(f"Product ID {item['product_id']} does not exist.")
                new_quantity = _number(Decimal(str(product['quantity'])) + Decimal(str(item['quantity'])), 'Updated stock', minimum=0)
                batch_id = c.execute(
                    'INSERT INTO product_batches(product_id,batch_code,quantity,unit_cost,purchase_date,expiry_date) VALUES(?,?,?,?,?,?)',
                    (item['product_id'], item['batch_code'] or 'EDITED', item['quantity'], str(item['unit_price']), purchase_date, item['expiry_date'])
                ).lastrowid
                c.execute('UPDATE products SET quantity=?,price=?,updated_at=CURRENT_TIMESTAMP WHERE id=?',
                          (new_quantity, str(item['unit_price']), item['product_id']))
                c.execute('INSERT INTO purchase_items(purchase_id,product_id,quantity,unit_price,line_total,batch_id) VALUES(?,?,?,?,?,?)',
                          (purchase_id, item['product_id'], item['quantity'], str(item['unit_price']), str(item['line_total']), batch_id))
                c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',
                          (item['product_id'], batch_id, 'Purchase edit replacement', item['quantity'], f'PURCHASE-{purchase_id}', 'Edited purchase received'))
            expense = c.execute('SELECT id FROM expenses WHERE purchase_id=?', (purchase_id,)).fetchone()
            if expense:
                c.execute('UPDATE expenses SET expense_date=?,amount=?,member_id=?,description=? WHERE purchase_id=?',
                          (purchase_date, str(total), member_id, f'Purchase #{purchase_id}', purchase_id))
            else:
                c.execute('INSERT INTO expenses(expense_date,category,description,amount,member_id,purchase_id) VALUES(?,?,?,?,?,?)',
                          (purchase_date, 'Groceries', f'Purchase #{purchase_id}', str(total), member_id, purchase_id))

    def return_purchase_item(self, purchase_item_id, quantity, reason='Purchase return'):
        purchase_item_id=_optional_id(purchase_item_id, 'Purchase item ID')
        q=_number(quantity, 'Return quantity', strictly_positive=True)
        reason=_required(reason, 'Return reason')
        with self.connect() as c:
            it=c.execute('SELECT pi.*,p.quantity product_quantity,b.quantity batch_quantity FROM purchase_items pi JOIN products p ON p.id=pi.product_id LEFT JOIN product_batches b ON b.id=pi.batch_id WHERE pi.id=?',(purchase_item_id,)).fetchone()
            if not it: raise ValueError('Purchase item not found.')
            if not it['batch_id']:
                raise ValueError('This older purchase item has no traceable stock batch and cannot be returned safely.')
            return_rows=c.execute("SELECT quantity FROM stock_movements WHERE reference=? AND movement_type='Purchase return'",(f'PURCHASE-ITEM-{purchase_item_id}',)).fetchall()
            already=sum((Decimal(str(-row['quantity'])) for row in return_rows),Decimal('0'))
            q_decimal=Decimal(str(q))
            if q_decimal+already>Decimal(str(it['quantity']))+Decimal('0.00000001'): raise ValueError('Return exceeds the unreturned purchased quantity.')
            if q>float(it['product_quantity'])+STOCK_EPSILON or (it['batch_id'] and q>float(it['batch_quantity'])+STOCK_EPSILON): raise ValueError('Returned stock is no longer available in inventory.')
            c.execute('UPDATE products SET quantity=? WHERE id=?',(_clamp_stock(it['product_quantity']-q),it['product_id']))
            if it['batch_id']: c.execute('UPDATE product_batches SET quantity=? WHERE id=?',(_clamp_stock(it['batch_quantity']-q),it['batch_id']))
            c.execute('INSERT INTO stock_movements(product_id,batch_id,movement_type,quantity,reference,note) VALUES(?,?,?,?,?,?)',(it['product_id'],it['batch_id'],'Purchase return',-q,f'PURCHASE-ITEM-{purchase_item_id}',reason))
            # Calculate cumulative rounded refund, then subtract what was already refunded.
            # Decimal accumulation avoids floating-point drift across many partial returns.
            cumulative_returned = already + q_decimal
            refund = money(cumulative_returned * money(it['unit_price'])) - money(already * money(it['unit_price']))
            refund = money(refund)
            expense=c.execute('SELECT amount FROM expenses WHERE purchase_id=?',(it['purchase_id'],)).fetchone()
            purchase=c.execute('SELECT total FROM purchases WHERE id=?',(it['purchase_id'],)).fetchone()
            if not expense or not purchase:
                raise ValueError('The purchase header or linked expense is missing. Repair the purchase record before returning stock.')
            if money(expense['amount']) < refund: raise ValueError('Refund would exceed the recorded purchase expense.')
            if money(purchase['total']) < refund: raise ValueError('Refund would exceed the purchase total.')
            c.execute('UPDATE expenses SET amount=? WHERE purchase_id=?',(str(money(money(expense['amount'])-refund)),it['purchase_id']))
            c.execute('UPDATE purchases SET total=? WHERE id=?',(str(money(money(purchase['total'])-refund)),it['purchase_id']))
            return refund

    def update_shopping_item(self, item_id, data):
        item_id=_optional_id(item_id, 'Shopping item ID')
        q=_number(data.get('quantity',1), 'Shopping quantity', strictly_positive=True); price=_nonnegative_money(data.get('unit_price',0), 'Price')
        name=_required(data.get('name'), 'Item name')
        unit=_required(data.get('unit','pcs'), 'Shopping item unit')
        priority=_required(data.get('priority','Normal'), 'Priority')
        if priority not in {'Low','Normal','High'}: raise ValueError('Priority must be Low, Normal or High.')
        with self.connect() as c:
            existing=c.execute('SELECT store_id FROM shopping_list_items WHERE id=?',(item_id,)).fetchone()
            if not existing: raise ValueError('Shopping item not found.')
            store_id=_optional_id(data.get('store_id',existing['store_id']), 'Store ID')
            if store_id and not c.execute('SELECT 1 FROM stores WHERE id=?',(store_id,)).fetchone(): raise ValueError('Selected store does not exist.')
            cur=c.execute("UPDATE shopping_list_items SET name=?,category=?,quantity=?,unit=?,unit_price=?,priority=?,store_id=? WHERE id=? AND status!='Purchased'",(name,str(data.get('category') or ''),q,unit,str(price),priority,store_id,item_id))
            if not cur.rowcount: raise ValueError('Item not found or already purchased.')

    def delete_shopping_item(self, item_id):
        item_id=_optional_id(item_id, 'Shopping item ID')
        with self.connect() as c:
            item=c.execute("SELECT list_id FROM shopping_list_items WHERE id=? AND status!='Purchased'",(item_id,)).fetchone()
            if not item: raise ValueError('Item not found or already purchased.')
            c.execute('DELETE FROM shopping_list_items WHERE id=?',(item_id,))
            pending=c.execute("SELECT COUNT(*) FROM shopping_list_items WHERE list_id=? AND status!='Purchased'",(item['list_id'],)).fetchone()[0]
            if pending==0: c.execute("UPDATE shopping_lists SET status='Completed' WHERE id=?",(item['list_id'],))

    def update_member(self, member_id, data):
        member_id=_optional_id(member_id, 'Member ID')
        name=_required(data.get('name'), 'Member name')
        role=_required(data.get('role','Member'), 'Member role')
        phone=str(data.get('phone') or '').strip()
        if len(name)>100 or len(role)>40 or len(phone)>30:
            raise ValueError('Member name, role or phone number is too long.')
        if phone:
            import phonenumbers
            try: parsed=phonenumbers.parse(phone, None)
            except phonenumbers.NumberParseException as exc: raise ValueError('Phone number must include a valid country calling code.') from exc
            if not phonenumbers.is_valid_number(parsed) or not phonenumbers.is_possible_number(parsed) or phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)!=phone:
                raise ValueError('Enter a valid international phone number.')
        with self.connect() as c:
            cur=c.execute('UPDATE household_members SET name=?,role=?,phone=? WHERE id=?',(name,role,phone,member_id))
            if not cur.rowcount: raise ValueError('Household member not found.')

    def update_expense(self, expense_id, data):
        expense_id=_optional_id(expense_id, 'Expense ID')
        amount=_nonnegative_money(data.get('amount'), 'Expense amount', strictly_positive=True)
        expense_date=_date_not_future(data.get('date',date.today().isoformat()), 'Expense date')
        category=_required(data.get('category'), 'Expense category')
        member_id=_optional_id(data.get('member_id'), 'Household member ID')
        with self.connect() as c:
            row=c.execute('SELECT purchase_id FROM expenses WHERE id=?',(expense_id,)).fetchone()
            if not row: raise ValueError('Expense not found.')
            if row['purchase_id'] is not None: raise ValueError('Purchase-linked expenses must be changed through the purchase workflow.')
            if member_id and not c.execute('SELECT 1 FROM household_members WHERE id=?',(member_id,)).fetchone():
                raise ValueError('Selected household member does not exist.')
            c.execute('UPDATE expenses SET expense_date=?,category=?,description=?,amount=?,member_id=? WHERE id=?',(expense_date,category,str(data.get('description') or ''),str(amount),member_id,expense_id))

    def set_budget_alert_thresholds(self, budget_id, thresholds):
        budget_id=_optional_id(budget_id, 'Budget ID')
        try:
            parsed=[]
            for value in thresholds:
                number=Decimal(str(value))
                if not number.is_finite() or number != number.to_integral_value():
                    raise ValueError
                parsed.append(int(number))
            values=sorted(set(parsed))
        except (InvalidOperation, TypeError, ValueError, OverflowError):
            raise ValueError('Choose whole-number alert thresholds from 50, 75, 90 and 100 percent.')
        allowed = {50, 75, 90, 100}
        if any(x not in allowed for x in values):
            raise ValueError('Supported per-budget alert thresholds are 50, 75, 90 and 100 percent.')
        with self.connect() as c:
            cur = c.execute('UPDATE budgets SET alert_50=?,alert_75=?,alert_90=?,alert_100=? WHERE id=?',
                            tuple(int(x in values) for x in (50,75,90,100)) + (budget_id,))
            if not cur.rowcount:
                raise ValueError('Budget not found.')

    def household_contributions(self, start_date, end_date):
        start_date,end_date=_validate_date_range(start_date,end_date)
        return self.rows('''SELECT COALESCE(h.name,'Unassigned') member, COUNT(e.id) entries,
            COALESCE(SUM(CAST(e.amount AS REAL)),0) spending
            FROM expenses e LEFT JOIN household_members h ON h.id=e.member_id
            WHERE e.expense_date BETWEEN ? AND ? GROUP BY e.member_id ORDER BY spending DESC''',(start_date,end_date))

    def consumption_summary(self, days=30):
        window=_number(days, 'Consumption window', strictly_positive=True)
        if not window.is_integer() or window>3650: raise ValueError('Consumption window must be a whole number from 1 to 3650 days.')
        day_count=int(window)
        start=(date.today()-timedelta(days=day_count-1)).isoformat()
        return self.rows('''SELECT p.id,p.name,p.unit,COALESCE(SUM(-sm.quantity),0) consumed,
            COALESCE(SUM(-sm.quantity),0)/? daily_rate,
            p.quantity current_stock FROM products p LEFT JOIN stock_movements sm
            ON sm.product_id=p.id AND sm.movement_type='Consumption' AND date(sm.created_at,'localtime')>=date(?)
            GROUP BY p.id ORDER BY consumed DESC''',(day_count,start))

    def price_comparison(self, product_id):
        rows=self.rows('SELECT ph.*,s.name store FROM price_history ph JOIN stores s ON s.id=ph.store_id WHERE ph.product_id=?',(product_id,))
        factors={'kg':('mass',1000),'g':('mass',1),'l':('volume',1000),'ml':('volume',1),'pcs':('count',1),'piece':('count',1),'pieces':('count',1)}
        normalized=[]
        for r in rows:
            u=r['package_unit'].strip().lower(); info=factors.get(u)
            if not info or float(r['package_quantity'])<=0: continue
            unit_price=float(r['price'])/(float(r['package_quantity'])*info[1])
            if not math.isfinite(unit_price): continue
            normalized.append({**dict(r),'dimension':info[0],'unit_price':unit_price})
        if not normalized: return []
        product = self.one('SELECT unit FROM products WHERE id=?', (product_id,))
        if not product:
            raise ValueError('Product not found.')
        expected = _unit_dimension(product['unit'])
        if expected is None:
            raise ValueError('Price comparison is unavailable for this product unit. Use kg/g, L/ml or pieces.')
        return sorted([r for r in normalized if r['dimension'] == expected], key=lambda x: x['unit_price'])


    # Recurring shopping schedules. Each due occurrence is generated at most once.
    def create_recurring_schedule(self, name, interval_days, next_due, items=None):
        name=_required(name, 'Schedule name'); interval=_number(interval_days, 'Repeat interval', strictly_positive=True)
        if not interval.is_integer(): raise ValueError('Repeat interval must be a whole number of days.')
        days=int(interval)
        if days>365: raise ValueError('Repeat interval must be between 1 and 365 days.')
        due=date.fromisoformat(_date(next_due, 'Next due date'))
        if items is None: items=[]
        if not isinstance(items, (list, tuple)): raise ValueError('Recurring items must be provided as a list.')
        if not items: raise ValueError('Add at least one item to the recurring schedule.')
        with self.connect() as c:
            sid=c.execute('INSERT INTO recurring_shopping(name,interval_days,next_due) VALUES(?,?,?)',(name,days,due.isoformat())).lastrowid
            template_id=c.execute('INSERT INTO shopping_lists(name,list_date,notes) VALUES(?,?,?)',(f'{name} (template)',due.isoformat(),f'recurring-template:{sid}')).lastrowid
            for item in items:
                if not isinstance(item, dict): raise ValueError('Each recurring item must be a valid item record.')
                q=_number(item.get('quantity',1), 'Recurring item quantity', strictly_positive=True); price=_nonnegative_money(item.get('unit_price',0), 'Recurring item price')
                item_name=_required(item.get('name'), 'Recurring item name')
                item_unit=_required(item.get('unit','pcs'), 'Recurring item unit')
                priority=_required(item.get('priority','Normal'), 'Recurring item priority')
                if priority not in {'Low','Normal','High'}: raise ValueError('Recurring item priority must be Low, Normal or High.')
                c.execute('INSERT INTO shopping_list_items(list_id,name,category,quantity,unit,unit_price,priority) VALUES(?,?,?,?,?,?,?)',(template_id,item_name,str(item.get('category') or 'Grocery'),q,item_unit,str(price),priority))
            return sid

    def recurring_schedules(self, active_only=False):
        sql='SELECT * FROM recurring_shopping' + (' WHERE active=1' if active_only else '') + ' ORDER BY next_due,id'
        return self.rows(sql)

    def set_recurring_schedule_active(self, schedule_id, active):
        schedule_id=_optional_id(schedule_id, 'Schedule ID')
        if active not in (True, False, 0, 1): raise ValueError('Schedule active state must be true or false.')
        with self.connect() as c:
            cur=c.execute('UPDATE recurring_shopping SET active=? WHERE id=?',(int(bool(active)),schedule_id))
            if not cur.rowcount: raise ValueError('Recurring schedule not found.')
            return True

    def generate_due_recurring_lists(self, today=None):
        today=_date(today, 'Generation date') if today else date.today().isoformat()
        generated=[]
        with self.connect() as c:
            due_rows=c.execute('SELECT * FROM recurring_shopping WHERE active=1 ORDER BY next_due,id').fetchall()
            for schedule in due_rows:
                try:
                    interval=int(schedule['interval_days'])
                    if interval<1 or interval>365: raise ValueError('Invalid recurring interval')
                    due=date.fromisoformat(schedule['next_due'])
                except (TypeError,ValueError,OverflowError):
                    c.execute('UPDATE recurring_shopping SET active=0 WHERE id=?',(schedule['id'],))
                    continue
                if due.isoformat()>today: continue
                # The template list is kept separately from generated lists.
                template=c.execute('SELECT id FROM shopping_lists WHERE notes=? ORDER BY id LIMIT 1',(f'recurring-template:{schedule["id"]}',)).fetchone()
                if not template:
                    template=c.execute('SELECT id FROM shopping_lists WHERE name=? AND notes=? ORDER BY id LIMIT 1',(f'{schedule["name"]} (template)','Recurring schedule template')).fetchone()
                if not template:
                    c.execute('UPDATE recurring_shopping SET active=0 WHERE id=?',(schedule['id'],))
                    continue
                source_items=c.execute('SELECT * FROM shopping_list_items WHERE list_id=?',(template['id'],)).fetchall()
                try:
                    if not source_items: raise ValueError('Empty recurring template')
                    items=[]
                    for item in source_items:
                        items.append({
                            'product_id':item['product_id'], 'name':_required(item['name'],'Recurring item name'),
                            'category':str(item['category'] or 'Grocery'),
                            'quantity':_number(item['quantity'],'Recurring item quantity',strictly_positive=True),
                            'unit':_required(item['unit'],'Recurring item unit'),
                            'unit_price':str(_nonnegative_money(item['unit_price'],'Recurring item price')),
                            'priority':item['priority'] if item['priority'] in {'Low','Normal','High'} else 'Normal',
                        })
                except (TypeError,ValueError,OverflowError):
                    c.execute('UPDATE recurring_shopping SET active=0 WHERE id=?',(schedule['id'],))
                    continue
                # Bound work per page load if a schedule has been dormant for years.
                # Remaining missed occurrences are generated on subsequent visits.
                processed = 0
                max_occurrences_per_schedule = 50
                while due.isoformat()<=today and processed < max_occurrences_per_schedule:
                    occurrence_date = due.isoformat()
                    exists=c.execute('SELECT id FROM shopping_lists WHERE notes=?',(f'recurring:{schedule["id"]}:{occurrence_date}',)).fetchone()
                    if not exists:
                        lid=c.execute('INSERT INTO shopping_lists(name,list_date,notes) VALUES(?,?,?)',(f'{schedule["name"]} — {occurrence_date}',occurrence_date,f'recurring:{schedule["id"]}:{occurrence_date}')).lastrowid
                        for item in items:
                            c.execute('INSERT INTO shopping_list_items(list_id,product_id,name,category,quantity,unit,unit_price,priority) VALUES(?,?,?,?,?,?,?,?)',(lid,item['product_id'],item['name'],item['category'],item['quantity'],item['unit'],item['unit_price'],item['priority']))
                        generated.append(lid)
                    try: due += timedelta(days=interval)
                    except OverflowError:
                        c.execute('UPDATE recurring_shopping SET active=0 WHERE id=?',(schedule['id'],))
                        break
                    processed += 1
                c.execute('UPDATE recurring_shopping SET next_due=?,last_generated=? WHERE id=?',(due.isoformat(),today,schedule['id']))
        return generated
