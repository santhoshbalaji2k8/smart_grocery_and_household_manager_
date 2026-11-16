import tempfile
import unittest
from pathlib import Path
from datetime import date
from decimal import Decimal
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from database import Database, money, validate_backup

class RegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / 'regression.db')
    def tearDown(self):
        self.tmp.cleanup()
    def product(self, quantity=0, unit='L'):
        return self.db.add_product({'name':'Regression product','category':'Dairy','unit':unit,'quantity':quantity,'min_quantity':1,'price':'2.50'})

    def test_partial_returns_do_not_create_rounding_overrefund(self):
        pid = self.product()
        purchase = self.db.create_purchase({'items':[{'product_id':pid,'quantity':'1','unit_price':'0.01'}]})
        item = self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        first = self.db.return_purchase_item(item['id'],'0.5')
        second = self.db.return_purchase_item(item['id'],'0.5')
        self.assertEqual(first + second, Decimal('0.01'))
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'], '0.00')
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount'], '0.00')

    def test_purchase_total_matches_sum_of_rounded_lines(self):
        pid = self.product()
        purchase = self.db.create_purchase({'items':[
            {'product_id':pid,'quantity':'0.5','unit_price':'0.01'},
            {'product_id':pid,'quantity':'0.5','unit_price':'0.01'}]})
        lines = self.db.rows('SELECT line_total FROM purchase_items WHERE purchase_id=?',(purchase,))
        self.assertEqual(sum((money(x['line_total']) for x in lines), Decimal('0.00')), Decimal('0.02'))
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'], '0.02')

    def test_unit_change_blocked_while_stock_exists(self):
        pid = self.product(2)
        with self.assertRaises(ValueError):
            self.db.update_product(pid, {'name':'Regression product','category':'Dairy','unit':'pcs','quantity':2,'min_quantity':1,'price':'2.50'})
        self.assertEqual(self.db.one('SELECT unit FROM products WHERE id=?',(pid,))['unit'], 'L')

    def test_shopping_to_purchase_is_atomic_and_consistent(self):
        lid = self.db.add_shopping_list({'name':'List','list_date':date.today().isoformat()})
        iid = self.db.add_shopping_item({'list_id':lid,'name':'Rice','category':'Grains','quantity':2,'unit':'kg','unit_price':'50'})
        pid = self.db.convert_shopping_item_to_purchase(iid, 1.5, '48', date.today().isoformat())
        self.assertEqual(self.db.one('SELECT status FROM shopping_list_items WHERE id=?',(iid,))['status'], 'Purchased')
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE name=?',('Rice',))['quantity'], 1.5)
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(pid,))['total'], '72.00')
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(pid,))['amount'], '72.00')
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'], 'Completed')

    def test_shopping_conversion_rolls_back_everything_on_bad_date(self):
        lid = self.db.add_shopping_list({'name':'List','list_date':date.today().isoformat()})
        iid = self.db.add_shopping_item({'list_id':lid,'name':'Rice','category':'Grains','quantity':1,'unit':'kg','unit_price':'50'})
        with self.assertRaises(ValueError):
            self.db.convert_shopping_item_to_purchase(iid,1,'50',date.today().isoformat(),'2026-02-30')
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT status FROM shopping_list_items WHERE id=?',(iid,))['status'],'Pending')
        self.assertIsNone(self.db.one('SELECT id FROM products WHERE name=?',('Rice',)))

    def test_price_comparison_never_mixes_mass_and_volume(self):
        pid = self.product(unit='box')
        a = self.db.add_store({'name':'Mass shop'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':a,'package_quantity':1,'package_unit':'kg','price':'10','recorded_date':date.today().isoformat()})

    def test_product_unit_dimension_filters_price_history(self):
        pid = self.product(unit='L')
        mass = self.db.add_store({'name':'Mass store'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':mass,'package_quantity':1,'package_unit':'kg','price':'10','recorded_date':date.today().isoformat()})

    def test_budget_alert_switches_are_respected(self):
        today = date.today().isoformat()
        bid = self.db.add_budget({'name':'Budget','category':'All','amount':'100','start_date':today,'end_date':today})
        self.db.set_budget_alert_thresholds(bid,[100])
        self.db.add_expense({'date':today,'category':'Food','amount':'80'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='budget' AND related_id=?",(bid,))['n'],0)
        self.db.add_expense({'date':today,'category':'Food','amount':'25'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='budget' AND related_id=?",(bid,))['n'],1)

    def test_stock_alerts_do_not_duplicate_until_recovered(self):
        pid = self.product(1)
        self.db.generate_notifications(); self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n'],1)
        self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'L','quantity':5,'min_quantity':1,'price':'2.50'})
        self.db.generate_notifications()
        self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'L','quantity':1,'min_quantity':1,'price':'2.50'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n'],1)

    def test_recurring_empty_template_rejected(self):
        with self.assertRaises(ValueError): self.db.create_recurring_schedule('Empty',7,date.today().isoformat(),[])

    def test_recurring_catchup_is_bounded(self):
        sid = self.db.create_recurring_schedule('Old',1,'2000-01-01',[{'name':'Rice','quantity':1,'unit':'kg','unit_price':'1'}])
        created = self.db.generate_due_recurring_lists('2026-11-15')
        self.assertLessEqual(len(created),50)
        self.assertGreater(self.db.one('SELECT next_due FROM recurring_shopping WHERE id=?',(sid,))['next_due'],'2000-01-01')

    def test_purchase_rejects_expiry_before_purchase_date_and_future_purchase(self):
        pid = self.product()
        with self.assertRaises(ValueError):
            self.db.create_purchase({'purchase_date':'2026-11-10','items':[{'product_id':pid,'quantity':1,'unit_price':'2','expiry_date':'2026-11-09'}]})
        future = (date.today().replace(day=min(date.today().day, 28))).isoformat()
        from datetime import timedelta
        future = (date.today() + timedelta(days=1)).isoformat()
        with self.assertRaises(ValueError):
            self.db.create_purchase({'purchase_date':future,'items':[{'product_id':pid,'quantity':1,'unit_price':'2'}]})
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)

    def test_expense_rejects_future_date(self):
        from datetime import timedelta
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':(date.today()+timedelta(days=1)).isoformat(),'category':'Food','amount':'1'})

    def test_budget_periods_of_same_category_cannot_overlap(self):
        self.db.add_budget({'name':'First','category':'Food','amount':'100','start_date':'2026-01-01','end_date':'2026-01-31'})
        with self.assertRaises(ValueError):
            self.db.add_budget({'name':'Overlap','category':'Food','amount':'200','start_date':'2026-01-15','end_date':'2026-02-15'})
        self.db.add_budget({'name':'Next','category':'Food','amount':'100','start_date':'2026-02-01','end_date':'2026-02-28'})

    def test_backup_validation_rejects_unrelated_sqlite_file(self):
        import sqlite3
        bad_path=Path(self.tmp.name)/'unrelated.db'
        con=sqlite3.connect(bad_path)
        con.execute('CREATE TABLE random_data(value TEXT)')
        con.commit(); con.close()
        with self.assertRaises(ValueError): validate_backup(bad_path)

    def test_backup_validation_accepts_current_database(self):
        self.assertTrue(validate_backup(self.db.path))

    def test_stock_notification_changes_from_out_to_low_without_stale_active_alert(self):
        pid = self.product(0)
        self.db.generate_notifications()
        self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'L','quantity':0.5,'min_quantity':1,'price':'2.50'})
        self.db.generate_notifications()
        active = self.db.rows("SELECT fingerprint,title FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))
        self.assertEqual(len(active),1)
        self.assertEqual(active[0]['title'],'Low stock')

    def test_expiry_alert_refreshes_and_resolves_when_batch_is_safe(self):
        from datetime import timedelta
        expiry=(date.today()+timedelta(days=5)).isoformat()
        pid=self.db.add_product({'name':'Expiry product','unit':'pcs','quantity':1,'min_quantity':0,'price':'1','expiry_date':expiry})
        self.db.generate_notifications()
        row=self.db.one("SELECT message FROM notifications WHERE fingerprint LIKE 'expiry:%' LIMIT 1")
        self.assertIn('5 day(s)',row['message'])
        with self.db.connect() as c:
            c.execute('UPDATE product_batches SET expiry_date=? WHERE product_id=?',((date.today()+timedelta(days=20)).isoformat(),pid))
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE fingerprint LIKE 'expiry:%'")['n'],0)

    def test_stock_alert_message_refreshes_when_minimum_changes(self):
        pid=self.product(1)
        self.db.generate_notifications()
        self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'L','quantity':1,'min_quantity':5,'price':'2.50'})
        self.db.generate_notifications()
        row=self.db.one("SELECT message FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))
        self.assertIn('minimum 5',row['message'])

    def test_legacy_purchase_without_batch_cannot_be_returned_or_deleted(self):
        pid = self.product(0)
        purchase = self.db.create_purchase({'items':[{'product_id':pid,'quantity':2,'unit_price':'2'}]})
        with self.db.connect() as c:
            item_id = c.execute('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,)).fetchone()[0]
            c.execute('UPDATE purchase_items SET batch_id=NULL WHERE id=?',(item_id,))
        with self.assertRaises(ValueError): self.db.return_purchase_item(item_id,1)
        with self.assertRaises(ValueError): self.db.delete_purchase(purchase)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)

    def test_tiny_negative_money_values_are_rejected_before_rounding(self):
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'Negative tiny price','unit':'pcs','quantity':0,'price':'-0.001'})
        pid=self.product(1)
        lid=self.db.add_shopping_list({'name':'Money validation','list_date':date.today().isoformat()})
        with self.assertRaises(ValueError):
            self.db.add_shopping_item({'list_id':lid,'name':'Bad item','quantity':1,'unit_price':'-0.001'})
        with self.assertRaises(ValueError):
            self.db.create_purchase({'items':[{'product_id':pid,'quantity':1,'unit_price':'-0.001'}]})
        store=self.db.add_store({'name':'Tiny price store'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':store,'package_quantity':1,'package_unit':'L','price':'-0.001','recorded_date':date.today().isoformat()})
        with self.assertRaises(ValueError):
            self.db.record_waste({'product_id':pid,'quantity':0.1,'reason':'Test','unit_cost':'-0.001'})
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':date.today().isoformat(),'category':'Test','amount':'-0.001'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],1)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM expenses')['n'],0)

    def test_consumption_report_excludes_wastage(self):
        pid=self.product(5)
        self.db.consume_stock(pid,1)
        self.db.record_waste({'product_id':pid,'quantity':1,'reason':'Spoiled','unit_cost':'2.50'})
        row=self.db.consumption_summary(30)[0]
        self.assertEqual(row['consumed'],1)

    def test_consumption_and_wastage_movements_reference_batches(self):
        pid=self.product(3)
        self.db.consume_stock(pid,1)
        self.db.record_waste({'product_id':pid,'quantity':1,'reason':'Spoiled','unit_cost':'2.50'})
        rows=self.db.rows("SELECT batch_id,movement_type FROM stock_movements WHERE product_id=? AND movement_type IN ('Consumption','Wastage')",(pid,))
        self.assertEqual(len(rows),2)
        self.assertTrue(all(row['batch_id'] is not None for row in rows))

    def test_stock_batch_and_movement_totals_stay_in_sync_across_workflow(self):
        pid=self.product(10)
        first=self.db.create_purchase({'items':[{'product_id':pid,'quantity':3,'unit_price':'2'}]})
        self.db.consume_stock(pid,2)
        self.db.record_waste({'product_id':pid,'quantity':1,'reason':'Spoiled','unit_cost':'2'})
        self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'L','quantity':8,'min_quantity':1,'price':'2.50'})
        second=self.db.create_purchase({'items':[{'product_id':pid,'quantity':2,'unit_price':'3'}]})
        second_item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(second,))
        self.db.return_purchase_item(second_item['id'],0.5)
        self.db.delete_purchase(second)
        product_qty=float(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'])
        batch_qty=float(self.db.one('SELECT COALESCE(SUM(quantity),0) n FROM product_batches WHERE product_id=?',(pid,))['n'])
        movement_qty=float(self.db.one('SELECT COALESCE(SUM(quantity),0) n FROM stock_movements WHERE product_id=?',(pid,))['n'])
        self.assertAlmostEqual(product_qty,8,places=7)
        self.assertAlmostEqual(batch_qty,product_qty,places=7)
        self.assertAlmostEqual(movement_qty,product_qty,places=7)
        purchase_total=self.db.one('SELECT total FROM purchases WHERE id=?',(first,))['total']
        linked_expense=self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(first,))['amount']
        self.assertEqual(purchase_total,linked_expense)
        self.assertTrue(validate_backup(self.db.path))

    def test_product_with_opening_stock_cannot_be_deleted(self):
        pid=self.product(2)
        with self.assertRaises(ValueError): self.db.delete_product(pid)
        self.assertIsNotNone(self.db.one('SELECT id FROM products WHERE id=?',(pid,)))

    def test_product_with_historical_movements_cannot_be_deleted_even_when_empty(self):
        pid=self.product(1)
        self.db.consume_stock(pid,1)
        with self.assertRaises(ValueError): self.db.delete_product(pid)
        self.assertIsNotNone(self.db.one('SELECT id FROM products WHERE id=?',(pid,)))

    def test_sqlite_triggers_reject_invalid_dates_and_infinite_quantities(self):
        import sqlite3
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as c:
                c.execute("INSERT INTO purchases(purchase_date,total) VALUES('2026-02-30','1.00')")
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as c:
                c.execute("INSERT INTO products(name,unit,quantity,min_quantity,price) VALUES('Infinite stock','pcs',? ,0,'1.00')",(float('inf'),))
        lid=self.db.add_shopping_list({'name':'Trigger list','list_date':date.today().isoformat()})
        with self.assertRaises(sqlite3.IntegrityError):
            with self.db.connect() as c:
                c.execute("INSERT INTO shopping_list_items(list_id,name,quantity,unit,unit_price) VALUES(?,?,?,'pcs','1.00')",(lid,'Infinite item',float('inf')))

    def test_batch_expiry_and_cost_can_be_corrected_safely(self):
        from datetime import timedelta
        expiry=(date.today()+timedelta(days=10)).isoformat()
        pid=self.db.add_product({'name':'Batch edit product','unit':'pcs','quantity':2,'min_quantity':0,'price':'1','expiry_date':expiry})
        batch=self.db.one('SELECT id FROM product_batches WHERE product_id=?',(pid,))
        new_expiry=(date.today()+timedelta(days=20)).isoformat()
        self.db.update_batch(batch['id'],{'batch_code':'OPENING-EDITED','expiry_date':new_expiry,'unit_cost':'1.25'})
        updated=self.db.one('SELECT expiry_date,unit_cost,quantity FROM product_batches WHERE id=?',(batch['id'],))
        self.assertEqual(updated['expiry_date'],new_expiry)
        self.assertEqual(updated['unit_cost'],'1.25')
        self.assertEqual(updated['quantity'],2)

    def test_batch_edit_rejects_invalid_expiry_and_negative_small_cost(self):
        pid=self.product(2)
        batch=self.db.one('SELECT id FROM product_batches WHERE product_id=?',(pid,))
        with self.assertRaises(ValueError):
            self.db.update_batch(batch['id'],{'expiry_date':'2026-02-30','unit_cost':'1'})
        with self.assertRaises(ValueError):
            self.db.update_batch(batch['id'],{'expiry_date':'','unit_cost':'-0.001'})
        self.assertEqual(self.db.one('SELECT quantity FROM product_batches WHERE id=?',(batch['id'],))['quantity'],2)

    def test_consumption_daily_rate_uses_full_requested_window(self):
        pid=self.product(5)
        self.db.consume_stock(pid,2)
        row=self.db.consumption_summary(30)[0]
        self.assertEqual(row['consumed'],2)
        self.assertAlmostEqual(row['daily_rate'],2/30,places=8)

    def test_purchase_line_total_uses_the_quantity_precision_actually_stored(self):
        pid=self.product()
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':'1.234567890123456789','unit_price':'3.25'}]})
        item=self.db.one('SELECT quantity,line_total FROM purchase_items WHERE purchase_id=?',(purchase,))
        expected=money(Decimal(str(item['quantity']))*Decimal('3.25'))
        self.assertEqual(item['line_total'],str(expected))
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],str(expected))

    def test_unrepresentable_quantities_and_price_normalization_are_rejected(self):
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'Too much stock','unit':'pcs','quantity':'1.5e308','price':'1'})
        pid=self.product()
        store=self.db.add_store({'name':'Tiny package store'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':store,'package_quantity':'1e-320','package_unit':'L','price':'10','recorded_date':date.today().isoformat()})

    def test_budget_alerts_resolve_and_move_to_the_current_threshold(self):
        today=date.today().isoformat()
        bid=self.db.add_budget({'name':'Flexible budget','category':'All','amount':'100','start_date':today,'end_date':today})
        eid=self.db.add_expense({'date':today,'category':'Food','amount':'110'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'budget:%'",(bid,))['n'],1)
        self.db.update_expense(eid,{'date':today,'category':'Food','amount':'60'})
        self.db.generate_notifications()
        active=self.db.rows("SELECT fingerprint FROM notifications WHERE related_id=? AND fingerprint LIKE 'budget:%'",(bid,))
        self.assertEqual(len(active),1)
        self.assertIn(':50:',active[0]['fingerprint'])
        self.db.update_expense(eid,{'date':today,'category':'Food','amount':'10'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'budget:%'",(bid,))['n'],0)

    def test_budget_alert_is_archived_when_budget_period_ends(self):
        today=date.today().isoformat()
        bid=self.db.add_budget({'name':'Ending budget','category':'All','amount':'10','start_date':today,'end_date':today})
        self.db.add_expense({'date':today,'category':'Food','amount':'20'})
        self.db.generate_notifications()
        with self.db.connect() as c:
            c.execute('UPDATE budgets SET end_date=? WHERE id=?',('2000-01-01',bid))
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'budget:%'",(bid,))['n'],0)

    def test_deleting_unused_product_closes_its_stock_alert(self):
        pid=self.product(0)
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n'],1)
        self.db.delete_product(pid)
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n'],0)

    def test_opening_expiry_requires_positive_opening_stock(self):
        from datetime import timedelta
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'No stock expiry','unit':'pcs','quantity':0,'price':'1','expiry_date':(date.today()+timedelta(days=5)).isoformat()})
        self.assertIsNone(self.db.one('SELECT id FROM products WHERE name=?',('No stock expiry',)))

    def test_unit_change_is_blocked_after_stock_history_even_when_current_stock_is_zero(self):
        pid=self.product(1)
        self.db.consume_stock(pid,1)
        with self.assertRaises(ValueError):
            self.db.update_product(pid,{'name':'Regression product','category':'Dairy','unit':'pcs','quantity':0,'min_quantity':1,'price':'2.50'})
        self.assertEqual(self.db.one('SELECT unit FROM products WHERE id=?',(pid,))['unit'],'L')

    def test_return_rolls_back_when_linked_purchase_expense_is_missing(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':2,'unit_price':'5'}]})
        item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        with self.db.connect() as c:c.execute('DELETE FROM expenses WHERE purchase_id=?',(purchase,))
        with self.assertRaises(ValueError):self.db.return_purchase_item(item['id'],1)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'10.00')

    def test_backup_validation_rejects_stock_batch_mismatch(self):
        pid=self.product(2)
        with self.db.connect() as c:c.execute('UPDATE products SET quantity=1 WHERE id=?',(pid,))
        with self.assertRaises(ValueError):validate_backup(self.db.path)

    def test_stock_quantity_below_supported_precision_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'Tiny stock','unit':'kg','quantity':'1e-10','price':'1'})
        pid=self.product(1)
        with self.assertRaises(ValueError):
            self.db.update_product(pid,{'name':'Regression product','unit':'L','quantity':'1e-10','min_quantity':1,'price':'2.50'})
        with self.assertRaises(ValueError):
            self.db.consume_stock(pid,'1e-10')
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],1)

    def test_purchase_batch_cannot_be_edited_to_expire_before_its_purchase_date(self):
        from datetime import timedelta
        pid=self.product(0)
        today=date.today().isoformat()
        expiry=(date.today()+timedelta(days=5)).isoformat()
        purchase=self.db.create_purchase({'purchase_date':today,'items':[{'product_id':pid,'quantity':1,'unit_price':'2','expiry_date':expiry}]})
        batch=self.db.one('SELECT batch_id FROM purchase_items WHERE purchase_id=?',(purchase,))
        with self.assertRaises(ValueError):
            self.db.update_batch(batch['batch_id'],{'expiry_date':(date.today()-timedelta(days=1)).isoformat()})
        current=self.db.one('SELECT expiry_date,unit_cost FROM product_batches WHERE id=?',(batch['batch_id'],))
        self.assertEqual(current['expiry_date'],expiry)
        self.assertEqual(current['unit_cost'],'2.00')

    def test_budget_update_changes_fields_and_preserves_alert_flags(self):
        today=date.today().isoformat()
        bid=self.db.add_budget({'name':'Old budget','category':'Food','amount':'100','start_date':'2026-01-01','end_date':'2026-01-31'})
        self.db.set_budget_alert_thresholds(bid,[50,90])
        self.db.update_budget(bid,{'name':'Updated budget','category':'Food','period':'Quarterly','amount':'250','start_date':'2026-02-01','end_date':'2026-04-30'})
        row=self.db.one('SELECT * FROM budgets WHERE id=?',(bid,))
        self.assertEqual(row['name'],'Updated budget')
        self.assertEqual(row['period'],'Quarterly')
        self.assertEqual(row['amount'],'250.00')
        self.assertEqual((row['alert_50'],row['alert_75'],row['alert_90'],row['alert_100']),(1,0,1,0))

    def test_budget_update_rejects_overlapping_period_without_partial_change(self):
        first=self.db.add_budget({'name':'Food one','category':'Food','amount':'100','start_date':'2026-01-01','end_date':'2026-01-31'})
        second=self.db.add_budget({'name':'Food two','category':'Food','amount':'100','start_date':'2026-02-01','end_date':'2026-02-28'})
        with self.assertRaises(ValueError):
            self.db.update_budget(second,{'name':'Conflict','category':'Food','amount':'200','start_date':'2026-01-15','end_date':'2026-02-15'})
        self.assertEqual(self.db.one('SELECT name FROM budgets WHERE id=?',(second,))['name'],'Food two')

    def test_invalid_optional_member_id_rejected_as_validation_error(self):
        with self.assertRaises(ValueError): self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'10','member_id':'1.5'})

if __name__ == '__main__':
    unittest.main()
