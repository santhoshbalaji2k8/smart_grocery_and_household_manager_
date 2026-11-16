import importlib.util
import sys
import types
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))

# The validation method is pure Python. A tiny CustomTkinter base-class stub
# lets this test module load without creating a graphical window.
if 'customtkinter' not in sys.modules:
    stub = types.ModuleType('customtkinter')
    stub.CTk = type('CTk', (), {})
    sys.modules['customtkinter'] = stub

spec = importlib.util.spec_from_file_location('grocery_main_for_validation', APP_DIR / 'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
GroceryApp = module.GroceryApp


class FormValidationTests(unittest.TestCase):
    def validate(self, values, **kwargs):
        return GroceryApp.validate_form_values(None, values, **kwargs)

    def test_product_form_allows_zero_stock_and_has_no_date_requirement(self):
        self.validate({'name':'Rice','category':'Grains','unit':'kg','quantity':'0','min_quantity':'0','price':'2'}, allow_zero_quantity=True)

    def test_product_form_rejects_negative_stock(self):
        with self.assertRaises(ValueError):
            self.validate({'name':'Rice','category':'Grains','unit':'kg','quantity':'-1','min_quantity':'0','price':'2'}, allow_zero_quantity=True)

    def test_form_rejects_invalid_calendar_date(self):
        with self.assertRaises(ValueError):
            self.validate({'date':'2026-02-30','category':'Food','amount':'10'})

    def test_form_rejects_negative_amount(self):
        with self.assertRaises(ValueError):
            self.validate({'date':'2026-11-15','category':'Food','amount':'-10'})

    def test_form_rejects_reversed_date_range(self):
        with self.assertRaises(ValueError):
            self.validate({'name':'Budget','category':'All','amount':'100','start_date':'2026-11-20','end_date':'2026-11-01'})

    def test_purchase_form_allows_optional_store_and_member(self):
        self.validate({'purchase_date':'2026-11-15','store_id':'','member_id':'','payment_method':'Cash'}, optional_ids={'store_id','member_id'})

    def test_shopping_estimated_total_uses_raw_values_before_currency_formatting(self):
        total = module.shopping_estimated_total([
            {'quantity': 2, 'unit_price': '12.50'},
            {'quantity': 0.5, 'unit_price': '10.00'},
        ])
        self.assertEqual(total, module.Decimal('30.00'))

    def test_form_rejects_future_purchase_date(self):
        from datetime import date, timedelta
        future = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.validate({'purchase_date': future})

    def test_form_rejects_expiry_when_opening_quantity_is_zero(self):
        from datetime import date, timedelta
        expiry=(date.today()+timedelta(days=5)).isoformat()
        with self.assertRaises(ValueError):
            self.validate({'quantity':'0','expiry_date':expiry}, allow_zero_quantity=True)

    def test_form_rejects_past_expiry_date(self):
        with self.assertRaises(ValueError):
            self.validate({'expiry_date': '2000-01-01'})

    def test_form_rejects_today_as_expiry_date(self):
        from datetime import date
        with self.assertRaises(ValueError):
            self.validate({'expiry_date': date.today().isoformat()})

    def test_form_accepts_future_expiry_date(self):
        from datetime import date, timedelta
        self.validate({'expiry_date': (date.today() + timedelta(days=1)).isoformat()})

    def test_product_form_rejects_punctuation_only_name(self):
        with self.assertRaises(ValueError):
            self.validate({'name':'!!!','category':'Food','unit':'kg','quantity':'1','min_quantity':'1','price':'2'}, allow_zero_quantity=True)

    def test_product_form_rejects_digit_only_name(self):
        with self.assertRaises(ValueError):
            self.validate({'name':'12345','category':'Food','unit':'kg','quantity':'1','min_quantity':'1','price':'2'}, allow_zero_quantity=True)

    def test_product_form_accepts_normal_grocery_name(self):
        self.validate({'name':'Aashirvaad Atta 5kg','category':'Food','unit':'kg','quantity':'1','min_quantity':'1','price':'2'}, allow_zero_quantity=True)

    def test_form_rejects_huge_finite_decimal_that_overflows_float(self):
        with self.assertRaises(ValueError):
            self.validate({'quantity': '1e10000'})

    def test_demo_data_is_not_loaded_automatically_on_startup(self):
        import inspect
        source = inspect.getsource(GroceryApp.__init__)
        self.assertNotIn('seed_demo_data', source)

    def test_date_format_preference_formats_iso_date(self):
        self.assertEqual(module.format_date_value('2026-11-15', '%d-%m-%Y'), '15-11-2026')
        self.assertEqual(module.format_date_value('not-a-date', '%d-%m-%Y'), 'not-a-date')

    def test_form_rejects_quantity_below_supported_precision(self):
        with self.assertRaises(ValueError):
            self.validate({'quantity':'1e-10'})

    def test_form_rejects_positive_amount_that_rounds_to_zero(self):
        with self.assertRaises(ValueError):
            self.validate({'amount': '0.001'})

    def test_form_rejects_nonfinite_quantity(self):
        with self.assertRaises(ValueError):
            self.validate({'quantity':'nan'})


if __name__ == '__main__':
    unittest.main()

class PageRenderLogicTests(unittest.TestCase):
    class FakeWidget:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
        def pack(self, *args, **kwargs):
            return self
        def grid(self, *args, **kwargs):
            return self
        def grid_columnconfigure(self, *args, **kwargs):
            return self
        def winfo_exists(self): return True
        def winfo_children(self): return []
        def destroy(self): return None
        def bind(self, *args, **kwargs): return None
        def get(self): return ''
        def set(self, value): self.value=value
        def insert(self, *args, **kwargs): return None

    def build_app(self, db):
        app = GroceryApp.__new__(GroceryApp)
        app.db = db
        app.currency = 'INR'
        app.date_format = '%d-%m-%Y'
        app.theme = 'Light'
        app.language = 'English'
        app.content = self.FakeWidget()
        app.colors = {'red':'red','orange':'orange','green':'green','muted':'grey','card':'white','border':'grey'}
        app.stats = lambda *args, **kwargs: None
        app.section = lambda *args, **kwargs: None
        app.label = lambda *args, **kwargs: self.FakeWidget()
        app.button = lambda *args, **kwargs: self.FakeWidget()
        app.table = lambda *args, **kwargs: self.FakeWidget()
        return app

    def test_main_data_pages_render_without_records(self):
        import tempfile
        from database import Database
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / 'ui.db')
            app = self.build_app(db)
            old_frame = getattr(module.ctk, 'CTkFrame', None)
            old_option = getattr(module.ctk, 'CTkOptionMenu', None)
            old_entry = getattr(module.ctk, 'CTkEntry', None)
            module.ctk.CTkFrame = self.FakeWidget
            module.ctk.CTkOptionMenu = self.FakeWidget
            module.ctk.CTkEntry = self.FakeWidget
            try:
                for page_name in ('page_dashboard','page_purchases','page_household','page_shopping',
                                  'page_stores','page_expiry','page_assistant','page_notifications','page_reports','page_settings','page_help'):
                    with self.subTest(page=page_name):
                        getattr(GroceryApp,page_name)(app)
            finally:
                if old_frame is None: delattr(module.ctk, 'CTkFrame')
                else: module.ctk.CTkFrame = old_frame
                if old_option is None: delattr(module.ctk, 'CTkOptionMenu')
                else: module.ctk.CTkOptionMenu = old_option
                if old_entry is None: delattr(module.ctk, 'CTkEntry')
                else: module.ctk.CTkEntry = old_entry

    def test_expenses_page_renders_with_no_budget(self):
        import tempfile
        from database import Database
        from datetime import date
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / 'ui.db')
            db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'25'})
            app = self.build_app(db)
            old_frame = getattr(module.ctk, 'CTkFrame', None)
            module.ctk.CTkFrame = self.FakeWidget
            try:
                GroceryApp.page_expenses(app)
            finally:
                if old_frame is None:
                    delattr(module.ctk, 'CTkFrame')
                else:
                    module.ctk.CTkFrame = old_frame

    def test_expenses_page_renders_with_overall_and_category_budgets(self):
        import tempfile
        from database import Database
        from datetime import date
        today = date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            db = Database(Path(tmp) / 'ui.db')
            db.add_expense({'date':today,'category':'Food','amount':'25'})
            db.add_budget({'name':'Household','category':'All','amount':'100','start_date':today,'end_date':today})
            db.add_budget({'name':'Food','category':'Food','amount':'50','start_date':today,'end_date':today})
            app = self.build_app(db)
            old_frame = getattr(module.ctk, 'CTkFrame', None)
            module.ctk.CTkFrame = self.FakeWidget
            try:
                GroceryApp.page_expenses(app)
            finally:
                if old_frame is None:
                    delattr(module.ctk, 'CTkFrame')
                else:
                    module.ctk.CTkFrame = old_frame

class ExportWorkflowTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from database import Database
        self.temp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.temp.name) / 'export.db')
        self.app = GroceryApp.__new__(GroceryApp)
        self.app.db = self.db
        self.app.currency = 'INR'

    def tearDown(self):
        self.temp.cleanup()

    def run_export(self, method, path):
        from unittest.mock import patch
        with patch.object(module.filedialog, 'asksaveasfilename', return_value=str(path)), \
             patch.object(module.messagebox, 'showinfo'), \
             patch.object(module.messagebox, 'showerror') as showerror:
            getattr(GroceryApp, method)(self.app)
            self.assertFalse(showerror.called, f'{method} reported an export error')

    def test_inventory_csv_export(self):
        self.db.add_product({'name':'Rice','category':'Grains','unit':'kg','quantity':2,'price':'50'})
        path=Path(self.temp.name)/'inventory.csv'
        self.run_export('export_inventory',path)
        content=path.read_text(encoding='utf-8-sig')
        self.assertIn('Rice',content)
        self.assertIn('quantity',content)

    def test_inventory_excel_export(self):
        from openpyxl import load_workbook
        self.db.add_product({'name':'Milk','category':'Dairy','unit':'L','quantity':1,'price':'30'})
        path=Path(self.temp.name)/'inventory.xlsx'
        self.run_export('export_inventory',path)
        workbook=load_workbook(path,read_only=True)
        try:
            sheet=workbook.active
            self.assertEqual(sheet.cell(row=2,column=1).value,'Milk')
        finally:
            workbook.close()

    def test_csv_export_neutralizes_formula_like_product_names(self):
        self.db.execute("INSERT INTO products(name,unit,quantity,min_quantity,price) VALUES('=1+1','pcs',1,0,'1')")
        path=Path(self.temp.name)/'formula.csv'
        self.run_export('export_inventory',path)
        self.assertIn("'=1+1",path.read_text(encoding='utf-8-sig'))

    def test_expense_csv_export(self):
        from datetime import date
        self.db.add_expense({'date':date.today().isoformat(),'category':'Food','description':'Groceries','amount':'25'})
        path=Path(self.temp.name)/'expenses.csv'
        self.run_export('export_expenses',path)
        self.assertIn('Groceries',path.read_text(encoding='utf-8-sig'))

    def test_pdf_export_handles_non_latin_user_text_without_crashing(self):
        from datetime import date
        self.db.add_product({'name':'அரிசி','category':'மளிகை','unit':'kg','quantity':1,'price':'50'})
        self.db.add_expense({'date':date.today().isoformat(),'category':'மளிகை','description':'தமிழ் விவரம்','amount':'25'})
        path=Path(self.temp.name)/'report.pdf'
        self.run_export('export_pdf_report',path)
        self.assertGreater(path.stat().st_size,500)

    def test_main_data_pages_render_with_populated_records(self):
        import tempfile
        from database import Database
        from datetime import date, timedelta
        today=date.today().isoformat()
        with tempfile.TemporaryDirectory() as tmp:
            db=Database(Path(tmp)/'ui-populated.db')
            member=db.add_member({'name':'Household Owner','role':'Owner'})
            product=db.add_product({'name':'Test Rice','category':'Grains','unit':'kg','quantity':5,'min_quantity':2,'price':'50','expiry_date':(date.today()+timedelta(days=5)).isoformat()})
            store=db.add_store({'name':'Local Market'})
            db.add_price_record({'product_id':product,'store_id':store,'package_quantity':1,'package_unit':'kg','price':'48','recorded_date':today})
            db.add_expense({'date':today,'category':'Food','description':'Vegetables','amount':'20','member_id':member})
            db.add_budget({'name':'Household Budget','category':'All','amount':'100','start_date':today,'end_date':today})
            lid=db.add_shopping_list({'name':'Weekly List','list_date':today})
            db.add_shopping_item({'list_id':lid,'name':'Rice','quantity':1,'unit':'kg','unit_price':'50'})
            db.create_recurring_schedule('Weekly staples',7,today,[{'name':'Milk','quantity':1,'unit':'L','unit_price':'30'}])
            db.create_purchase({'purchase_date':today,'member_id':member,'store_id':store,'items':[{'product_id':product,'quantity':1,'unit_price':'48'}]})
            db.generate_notifications()
            class FakeWidget:
                def __init__(self,*args,**kwargs): self.value=''
                def pack(self,*args,**kwargs): return self
                def grid(self,*args,**kwargs): return self
                def grid_columnconfigure(self,*args,**kwargs): return self
                def winfo_exists(self): return True
                def winfo_children(self): return []
                def destroy(self): return None
                def bind(self,*args,**kwargs): return None
                def get(self): return self.value
            class FakeVar:
                def __init__(self,value=''): self.value=value
                def get(self): return self.value
            app=GroceryApp.__new__(GroceryApp)
            app.db=db; app.currency='INR'; app.date_format='%d-%m-%Y'
            app.content=FakeWidget(); app.colors={'red':'red','orange':'orange','green':'green','muted':'grey','card':'white','border':'grey'}
            app.stats=lambda *args,**kwargs:None
            app.section=lambda *args,**kwargs:None
            app.label=lambda *args,**kwargs:FakeWidget()
            app.button=lambda *args,**kwargs:FakeWidget()
            app.table=lambda *args,**kwargs:FakeWidget()
            old_frame=getattr(module.ctk,'CTkFrame',None)
            old_entry=getattr(module.ctk,'CTkEntry',None)
            old_segment=getattr(module.ctk,'CTkSegmentedButton',None)
            old_stringvar=module.tk.StringVar
            module.ctk.CTkFrame=FakeWidget; module.ctk.CTkEntry=FakeWidget; module.ctk.CTkSegmentedButton=FakeWidget
            module.tk.StringVar=lambda value='':FakeVar(value)
            try:
                for page_name in ('page_inventory','page_dashboard','page_purchases','page_household','page_shopping',
                                  'page_stores','page_expiry','page_assistant','page_notifications','page_reports','page_expenses'):
                    with self.subTest(page=page_name):
                        getattr(GroceryApp,page_name)(app)
            finally:
                if old_frame is None: delattr(module.ctk,'CTkFrame')
                else: module.ctk.CTkFrame=old_frame
                if old_entry is None: delattr(module.ctk,'CTkEntry')
                else: module.ctk.CTkEntry=old_entry
                if old_segment is None: delattr(module.ctk,'CTkSegmentedButton')
                else: module.ctk.CTkSegmentedButton=old_segment
                module.tk.StringVar=old_stringvar

class ExpenseBudgetVisibleIdColumnTests(unittest.TestCase):
    def test_expense_and_budget_tables_hide_ids_but_keep_internal_ids(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / 'app' / 'main.py').read_text(encoding='utf-8')
        self.assertIn("budget_tree=self.table(self.content,['budget','category','period','spent','limit','used'],budget_rows,7)", source)
        self.assertIn("tree=self.table(self.content,['expense_date','category','description','amount','member'],rows,13)", source)
        self.assertIn("raw_id = row.get('_id', row.get('id', ''))", source)
        self.assertIn("return int(tag[0]) if tag and tag[0] else None", source)
