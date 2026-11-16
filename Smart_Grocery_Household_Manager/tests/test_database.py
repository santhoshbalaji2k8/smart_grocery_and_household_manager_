from decimal import Decimal
import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
from database import Database, money

class DatabaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.db=Database(Path(self.tmp.name)/'test.db')
    def tearDown(self): self.tmp.cleanup()
    def product(self,qty=5):
        return self.db.add_product({'name':'Test Milk','category':'Dairy','unit':'L','quantity':qty,'min_quantity':2,'price':'2.50'})
    def test_product_create_and_stock_status_data(self):
        pid=self.product(1); p=self.db.one('SELECT * FROM products WHERE id=?',(pid,))
        self.assertEqual(p['quantity'],1); self.assertLessEqual(p['quantity'],p['min_quantity'])
    def test_purchase_atomic_stock_and_expense(self):
        pid=self.product(2)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':3,'unit_price':'2.25'}]})
        p=self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))
        e=self.db.one('SELECT amount,purchase_id FROM expenses WHERE purchase_id=?',(purchase,))
        self.assertEqual(p['quantity'],5); self.assertEqual(e['amount'],'6.75')
    def test_purchase_delete_reverses_effects(self):
        pid=self.product(2)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':3,'unit_price':'2.25'}]})
        self.db.delete_purchase(purchase)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM expenses')['n'],0)
    def test_consume_prevents_negative_stock(self):
        pid=self.product(2); self.db.consume_stock(pid,1)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],1)
        with self.assertRaises(ValueError): self.db.consume_stock(pid,2)
    def test_waste_reduces_stock_and_records_cost(self):
        pid=self.product(4); self.db.record_waste({'product_id':pid,'quantity':1,'reason':'Expired','unit_cost':'2.50'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],3)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM waste_records')['n'],1)
    def test_settings_persist(self):
        self.db.set_setting('theme','Dark'); self.assertEqual(self.db.setting('theme'),'Dark')
    def test_money_rounding(self): self.assertEqual(str(money('1.235')),'1.24')
    def test_demo_seed_is_idempotent(self):
        self.db.seed_demo_data(); first=self.db.one('SELECT COUNT(*) n FROM products')['n']; self.db.seed_demo_data(); second=self.db.one('SELECT COUNT(*) n FROM products')['n']
        self.assertEqual(first,10); self.assertEqual(first,second)
    def test_low_stock_notification_deduplicates(self):
        self.product(1); self.db.generate_notifications(); first=self.db.one('SELECT COUNT(*) n FROM notifications')['n']; self.db.generate_notifications(); second=self.db.one('SELECT COUNT(*) n FROM notifications')['n']
        self.assertEqual(first,second)
    def test_purchase_edit_replaces_stock_and_expense_atomically(self):
        pid=self.product(2)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':2,'unit_price':'2.00'}]})
        self.db.update_purchase(purchase,{'purchase_date':date.today().isoformat(),'items':[{'product_id':pid,'quantity':4,'unit_price':'3.00'}]})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],6)
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount'],'12.00')

    def test_multi_item_purchase_edit_updates_each_product(self):
        first=self.product(1)
        second=self.db.add_product({'name':'Test Rice','category':'Grains','unit':'kg','quantity':2,'min_quantity':1,'price':'4.00'})
        purchase=self.db.create_purchase({'items':[{'product_id':first,'quantity':2,'unit_price':'2.00'},{'product_id':second,'quantity':3,'unit_price':'4.00'}]})
        self.db.update_purchase(purchase,{'items':[{'product_id':first,'quantity':1,'unit_price':'3.00'},{'product_id':second,'quantity':2,'unit_price':'5.00'}]})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(first,))['quantity'],2)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(second,))['quantity'],4)
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'13.00')
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount'],'13.00')

    def test_purchase_return_reduces_stock_and_expense(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':3,'unit_price':'2.50'}]})
        item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        refund=self.db.return_purchase_item(item['id'],1)
        self.assertEqual(str(refund),'2.50')
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)
        self.assertEqual(float(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount']),5.0)

    def test_shopping_item_edit_and_delete(self):
        lid=self.db.execute("INSERT INTO shopping_lists(name,list_date) VALUES('Weekly',?)",(date.today().isoformat(),))
        iid=self.db.execute("INSERT INTO shopping_list_items(list_id,name,quantity,unit_price) VALUES(?,?,?,?)",(lid,'Rice',1,'10'))
        self.db.update_shopping_item(iid,{'name':'Rice','quantity':2,'unit_price':'12.50'})
        self.assertEqual(self.db.one('SELECT quantity,unit_price FROM shopping_list_items WHERE id=?',(iid,))['quantity'],2)
        self.db.delete_shopping_item(iid)
        self.assertIsNone(self.db.one('SELECT id FROM shopping_list_items WHERE id=?',(iid,)))

    def test_member_update_and_contribution_summary(self):
        mid=self.db.execute("INSERT INTO household_members(name,role) VALUES('A','Member')")
        self.db.update_member(mid,{'name':'B','role':'Adult','phone':''})
        self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'25','member_id':mid})
        self.assertEqual(self.db.household_contributions(date.today().replace(day=1).isoformat(),date.today().isoformat())[0]['member'],'B')

    def test_price_comparison_normalizes_package_size(self):
        pid=self.product(0)
        sid1=self.db.execute("INSERT INTO stores(name) VALUES('Store A')")
        sid2=self.db.execute("INSERT INTO stores(name) VALUES('Store B')")
        for sid,qty,unit,price in [(sid1,1,'L','60'),(sid2,500,'ml','32')]:
            self.db.execute('INSERT INTO price_history(product_id,store_id,package_quantity,package_unit,price,recorded_date) VALUES(?,?,?,?,?,?)',(pid,sid,qty,unit,price,date.today().isoformat()))
        comparison=self.db.price_comparison(pid)
        self.assertEqual(comparison[0]['store'],'Store A')
        self.assertAlmostEqual(comparison[1]['unit_price'],0.064)

    def test_recurring_schedule_generates_due_list_and_advances_date(self):
        sid=self.db.create_recurring_schedule('Weekly essentials',7,'2026-11-01',[{'name':'Milk','quantity':2,'unit':'L','unit_price':'30'}])
        generated=self.db.generate_due_recurring_lists('2026-11-15')
        self.assertEqual(len(generated),3)
        self.assertEqual(self.db.one('SELECT next_due FROM recurring_shopping WHERE id=?',(sid,))['next_due'],'2026-11-22')
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM shopping_lists WHERE notes LIKE 'recurring:%' AND notes NOT LIKE 'recurring-template:%'")['n'],3)
        self.assertEqual(self.db.generate_due_recurring_lists('2026-11-15'),[])

    def test_recurring_schedule_can_be_paused(self):
        sid=self.db.create_recurring_schedule('Monthly',30,'2026-11-01',[{'name':'Milk','quantity':1,'unit':'L','unit_price':'2'}])
        self.db.set_recurring_schedule_active(sid,False)
        self.assertEqual(self.db.generate_due_recurring_lists('2026-12-31'),[])

    def test_recurring_schedule_validates_interval_and_items(self):
        with self.assertRaises(ValueError):self.db.create_recurring_schedule('Bad',0,'2026-11-15',[])
        with self.assertRaises(ValueError):self.db.create_recurring_schedule('Bad item',7,'2026-11-15',[{'name':'','quantity':1}])


    def test_product_rejects_negative_nonfinite_and_invalid_expiry(self):
        for value in (-1, 'nan', 'inf', '-inf'):
            with self.subTest(quantity=value), self.assertRaises(ValueError):
                self.db.add_product({'name':f'Bad {value}','quantity':value,'min_quantity':0,'price':'1'})
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'Bad date','quantity':0,'expiry_date':'2026-02-30'})

    def test_product_allows_zero_quantity_but_not_negative_price(self):
        pid=self.db.add_product({'name':'Zero stock','quantity':0,'min_quantity':0,'price':'0'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],0)
        with self.assertRaises(ValueError):
            self.db.add_product({'name':'Negative price','quantity':0,'price':'-0.01'})

    def test_purchase_rejects_invalid_quantity_date_and_price_atomically(self):
        pid=self.product(0)
        bad_items=[
            {'product_id':pid,'quantity':-1,'unit_price':'2'},
            {'product_id':pid,'quantity':0,'unit_price':'2'},
            {'product_id':pid,'quantity':'nan','unit_price':'2'},
            {'product_id':pid,'quantity':1,'unit_price':'-2'},
            {'product_id':pid,'quantity':1,'unit_price':'2','expiry_date':'2026-02-30'},
        ]
        for item in bad_items:
            with self.subTest(item=item), self.assertRaises(ValueError):
                self.db.create_purchase({'purchase_date':date.today().isoformat(),'items':[item]})
        with self.assertRaises(ValueError):
            self.db.create_purchase({'purchase_date':'2026-13-40','items':[{'product_id':pid,'quantity':1,'unit_price':'2'}]})
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],0)

    def test_expense_and_waste_reject_invalid_dates_and_values(self):
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':'2026-02-30','category':'Food','amount':'10'})
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'-1'})
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'nan'})
        pid=self.product(2)
        with self.assertRaises(ValueError):
            self.db.record_waste({'product_id':pid,'quantity':-1,'reason':'Expired'})
        with self.assertRaises(ValueError):
            self.db.record_waste({'product_id':pid,'quantity':1,'reason':'Expired','date':'2026-02-30'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)

    def test_budget_and_shopping_list_date_validation(self):
        with self.assertRaises(ValueError):
            self.db.add_shopping_list({'name':'Bad date','list_date':'2026-02-30'})
        with self.assertRaises(ValueError):
            self.db.add_budget({'name':'Bad range','category':'All','amount':'100','start_date':'2026-11-20','end_date':'2026-11-01'})
        with self.assertRaises(ValueError):
            self.db.add_budget({'name':'Bad amount','category':'All','amount':'0','start_date':'2026-11-01','end_date':'2026-11-30'})
        budget=self.db.add_budget({'name':'Valid','category':'All','amount':'1000','start_date':'2026-11-01','end_date':'2026-11-30'})
        self.assertGreater(budget,0)

    def test_shopping_item_rejects_zero_negative_and_nonfinite_quantity(self):
        lid=self.db.add_shopping_list({'name':'Valid','list_date':date.today().isoformat()})
        for q in (0,-1,'nan','inf'):
            with self.subTest(quantity=q), self.assertRaises(ValueError):
                self.db.add_shopping_item({'list_id':lid,'name':'Rice','quantity':q,'unit_price':'1'})
        with self.assertRaises(ValueError):
            self.db.add_shopping_item({'list_id':lid,'name':'Rice','quantity':1,'unit_price':'-1'})

    def test_price_record_validates_units_and_date(self):
        pid=self.product(0); sid=self.db.add_store({'name':'Local store'})
        base={'product_id':pid,'store_id':sid,'package_quantity':1,'package_unit':'kg','price':'50','recorded_date':date.today().isoformat()}
        with self.assertRaises(ValueError): self.db.add_price_record({**base,'package_quantity':0})
        with self.assertRaises(ValueError): self.db.add_price_record({**base,'package_unit':'box'})
        with self.assertRaises(ValueError): self.db.add_price_record({**base,'recorded_date':'2026-02-30'})
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM price_history')['n'],0)

    def test_recurring_schedule_rejects_fractional_interval_and_bad_date(self):
        with self.assertRaises(ValueError): self.db.create_recurring_schedule('Fractional',1.5,date.today().isoformat())
        with self.assertRaises(ValueError): self.db.create_recurring_schedule('Bad date',7,'2026-02-30')

    def test_money_rejects_nonfinite_and_empty_values(self):
        for value in ('nan','inf','-inf',''):
            with self.subTest(value=value), self.assertRaises(ValueError): money(value)


    def test_fractional_purchase_quantity_is_not_rounded_before_total(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':'0.125','unit_price':'100'}]})
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'12.50')
        self.assertEqual(self.db.one('SELECT line_total FROM purchase_items WHERE purchase_id=?',(purchase,))['line_total'],'12.50')

    def test_delete_purchase_with_duplicate_product_lines_checks_aggregate_stock(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':4,'unit_price':'1'},{'product_id':pid,'quantity':4,'unit_price':'1'}]})
        self.db.consume_stock(pid,1)
        with self.assertRaises(ValueError): self.db.delete_purchase(purchase)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],7)


    def test_purchase_edit_keeps_fractional_quantity_precision(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':'0.125','unit_price':'100'}]})
        self.db.update_purchase(purchase,{'purchase_date':date.today().isoformat(),'items':[{'product_id':pid,'quantity':'0.375','unit_price':'100'}]})
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'37.50')
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],0.375)


    def test_shopping_list_marks_complete_and_reopens_when_new_item_added(self):
        lid=self.db.add_shopping_list({'name':'Checklist','list_date':date.today().isoformat()})
        first=self.db.add_shopping_item({'list_id':lid,'name':'Milk','quantity':1,'unit_price':'2'})
        self.db.mark_shopping_item_purchased(first,'2.50')
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'],'Completed')
        second=self.db.add_shopping_item({'list_id':lid,'name':'Rice','quantity':1,'unit_price':'5'})
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'],'Open')
        with self.assertRaises(ValueError): self.db.mark_shopping_item_purchased(first,'2.50')
        self.db.mark_shopping_item_purchased(second,'5.00')
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'],'Completed')

    def test_same_name_recurring_schedules_keep_separate_templates(self):
        first=self.db.create_recurring_schedule('Same name',7,'2026-11-01',[{'name':'Milk','quantity':1,'unit_price':'2'}])
        second=self.db.create_recurring_schedule('Same name',7,'2026-11-01',[{'name':'Rice','quantity':2,'unit_price':'3'}])
        generated=self.db.generate_due_recurring_lists('2026-11-01')
        self.assertEqual(len(generated),2)
        names=[]
        for lid in generated:
            names.extend(r['name'] for r in self.db.rows('SELECT name FROM shopping_list_items WHERE list_id=?',(lid,)))
        self.assertCountEqual(names,['Milk','Rice'])


    def test_member_creation_and_expense_update(self):
        member=self.db.add_member({'name':'  Test Member  ','role':'Adult','phone':''})
        self.assertEqual(self.db.one('SELECT name FROM household_members WHERE id=?',(member,))['name'],'Test Member')
        expense=self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'10','member_id':member})
        self.db.update_expense(expense,{'date':date.today().isoformat(),'category':'Household','amount':'12.50','member_id':member})
        row=self.db.one('SELECT category,amount FROM expenses WHERE id=?',(expense,))
        self.assertEqual(row['category'],'Household'); self.assertEqual(row['amount'],'12.50')
        with self.assertRaises(ValueError): self.db.update_expense(expense,{'date':'2026-02-30','category':'Food','amount':'5'})

    def test_consumption_summary_validates_window_and_reports_stock(self):
        pid=self.product(5); self.db.consume_stock(pid,1)
        row=self.db.consumption_summary(30)[0]
        self.assertEqual(row['id'],pid); self.assertEqual(row['consumed'],1)
        for days in (0,-1,1.5,'nan',3651):
            with self.subTest(days=days), self.assertRaises(ValueError): self.db.consumption_summary(days)

    def test_stock_adjustment_preserves_batch_totals(self):
        pid=self.product(5)
        self.db.update_product(pid,{'name':'Test Milk','category':'Dairy','unit':'L','quantity':3,'min_quantity':2,'price':'2.50'})
        total=self.db.one('SELECT COALESCE(SUM(quantity),0) q FROM product_batches WHERE product_id=?',(pid,))['q']
        self.assertAlmostEqual(total,3)
        with self.assertRaises(ValueError): self.db.update_product(pid,{'name':'Test Milk','category':'Dairy','unit':'L','quantity':-1,'min_quantity':2,'price':'2.50'})

    def test_budget_alert_thresholds_and_notification(self):
        budget=self.db.add_budget({'name':'Food budget','category':'Food','amount':'100','start_date':date.today().isoformat(),'end_date':date.today().isoformat()})
        self.db.set_setting('budget_thresholds','50,75,90,100')
        self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'80'})
        self.db.generate_notifications()
        row=self.db.one("SELECT title FROM notifications WHERE related_type='budget' AND related_id=? ORDER BY id DESC LIMIT 1",(budget,))
        self.assertIsNotNone(row)
        self.assertIn('75%',row['title'])


    def test_delete_purchase_after_partial_return_removes_only_retained_stock(self):
        pid=self.product(2)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':5,'unit_price':'4'}]})
        item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        self.db.return_purchase_item(item['id'],2)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],5)
        self.db.delete_purchase(purchase)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM expenses')['n'],0)


    def test_new_database_schema_does_not_include_barcode_feature(self):
        with self.db.connect() as connection:
            columns={row['name'] for row in connection.execute('PRAGMA table_info(products)').fetchall()}
        self.assertNotIn('barcode',columns)


    def test_consumption_does_not_use_expired_batches(self):
        pid=self.db.add_product({'name':'Expired stock','category':'Food','unit':'pcs','quantity':2,'min_quantity':0,'price':'1'})
        self.db.execute("UPDATE product_batches SET expiry_date='2020-01-01' WHERE product_id=?",(pid,))
        with self.assertRaises(ValueError): self.db.consume_stock(pid,1)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)
        self.db.record_waste({'product_id':pid,'quantity':2,'reason':'Expired','date':date.today().isoformat(),'unit_cost':'1'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],0)


    def test_deleting_last_pending_shopping_item_completes_list(self):
        lid=self.db.add_shopping_list({'name':'Remove all','list_date':date.today().isoformat()})
        iid=self.db.add_shopping_item({'list_id':lid,'name':'Bread','quantity':1,'unit_price':'2'})
        self.db.delete_shopping_item(iid)
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'],'Completed')


    def test_expiry_notifications_do_not_repeat_for_each_day_in_same_level(self):
        pid=self.db.add_product({'name':'Soon food','category':'Food','unit':'pcs','quantity':1,'min_quantity':0,'price':'1','expiry_date':(date.today()+timedelta(days=2)).isoformat()})
        self.db.generate_notifications(); first=self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND title='Expiry alert'",(pid,))['n']
        self.db.generate_notifications(); second=self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_id=? AND title='Expiry alert'",(pid,))['n']
        self.assertEqual(first,1); self.assertEqual(second,1)


    def test_purchase_edit_is_blocked_after_stock_was_consumed_and_rolls_back(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':5,'unit_price':'2'}]})
        self.db.consume_stock(pid,1)
        before=self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity']
        with self.assertRaises(ValueError):
            self.db.update_purchase(purchase,{'purchase_date':date.today().isoformat(),'items':[{'product_id':pid,'quantity':3,'unit_price':'4'}]})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],before)
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'10.00')

    def test_purchase_return_cannot_exceed_unreturned_quantity(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':3,'unit_price':'2'}]})
        item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        self.db.return_purchase_item(item['id'],2)
        with self.assertRaises(ValueError): self.db.return_purchase_item(item['id'],2)
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],1)

    def test_waste_cannot_exceed_available_stock(self):
        pid=self.product(2)
        with self.assertRaises(ValueError): self.db.record_waste({'product_id':pid,'quantity':3,'reason':'Expired'})
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE id=?',(pid,))['quantity'],2)

    def test_product_with_purchase_history_cannot_be_deleted(self):
        pid=self.product(0)
        self.db.create_purchase({'items':[{'product_id':pid,'quantity':1,'unit_price':'2'}]})
        with self.assertRaises(ValueError): self.db.delete_product(pid)
        self.assertIsNotNone(self.db.one('SELECT id FROM products WHERE id=?',(pid,)))

    def test_purchased_shopping_item_cannot_be_edited_or_deleted(self):
        lid=self.db.add_shopping_list({'name':'Locked list','list_date':date.today().isoformat()})
        iid=self.db.add_shopping_item({'list_id':lid,'name':'Tea','quantity':1,'unit_price':'2'})
        self.db.mark_shopping_item_purchased(iid,'2')
        with self.assertRaises(ValueError): self.db.update_shopping_item(iid,{'name':'Tea','quantity':1,'unit_price':'2'})
        with self.assertRaises(ValueError): self.db.delete_shopping_item(iid)

    def test_foreign_keys_enabled(self):
        with self.db.connect() as c:self.assertEqual(c.execute('PRAGMA foreign_keys').fetchone()[0],1)

    def test_partial_purchase_returns_round_consistently(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[{'product_id':pid,'quantity':'1','unit_price':'0.01'}]})
        item=self.db.one('SELECT id FROM purchase_items WHERE purchase_id=?',(purchase,))
        first=self.db.return_purchase_item(item['id'],'0.5')
        second=self.db.return_purchase_item(item['id'],'0.5')
        self.assertEqual(first+second,Decimal('0.01'))
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'0.00')
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount'],'0.00')

    def test_purchase_total_equals_sum_of_rounded_line_totals(self):
        pid=self.product(0)
        purchase=self.db.create_purchase({'items':[
            {'product_id':pid,'quantity':'0.5','unit_price':'0.01'},
            {'product_id':pid,'quantity':'0.5','unit_price':'0.01'},
        ]})
        rows=self.db.rows('SELECT line_total FROM purchase_items WHERE purchase_id=?',(purchase,))
        self.assertEqual(sum((money(r['line_total']) for r in rows),Decimal('0.00')),Decimal('0.02'))
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'0.02')

    def test_product_unit_cannot_change_while_stock_exists(self):
        pid=self.product(2)
        with self.assertRaises(ValueError):
            self.db.update_product(pid,{'name':'Test Milk','category':'Dairy','unit':'pcs','quantity':2,'min_quantity':2,'price':'2.50'})
        self.assertEqual(self.db.one('SELECT unit FROM products WHERE id=?',(pid,))['unit'],'L')

    def test_atomic_shopping_item_conversion_updates_all_records(self):
        lid=self.db.add_shopping_list({'name':'To buy','list_date':date.today().isoformat()})
        item=self.db.add_shopping_item({'list_id':lid,'name':'Rice','category':'Grains','quantity':2,'unit':'kg','unit_price':'50'})
        purchase=self.db.convert_shopping_item_to_purchase(item,1.5,'48',date.today().isoformat())
        self.assertEqual(self.db.one('SELECT status FROM shopping_list_items WHERE id=?',(item,))['status'],'Purchased')
        self.assertEqual(self.db.one('SELECT quantity FROM products WHERE name=?',('Rice',))['quantity'],1.5)
        self.assertEqual(self.db.one('SELECT total FROM purchases WHERE id=?',(purchase,))['total'],'72.00')
        self.assertEqual(self.db.one('SELECT amount FROM expenses WHERE purchase_id=?',(purchase,))['amount'],'72.00')
        self.assertEqual(self.db.one('SELECT status FROM shopping_lists WHERE id=?',(lid,))['status'],'Completed')

    def test_atomic_shopping_conversion_rolls_back_on_invalid_expiry(self):
        lid=self.db.add_shopping_list({'name':'To buy','list_date':date.today().isoformat()})
        item=self.db.add_shopping_item({'list_id':lid,'name':'Rice','category':'Grains','quantity':1,'unit':'kg','unit_price':'50'})
        with self.assertRaises(ValueError):
            self.db.convert_shopping_item_to_purchase(item,1,'50',date.today().isoformat(),'2026-02-30')
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT status FROM shopping_list_items WHERE id=?',(item,))['status'],'Pending')
        self.assertIsNone(self.db.one('SELECT id FROM products WHERE name=?',('Rice',)))

    def test_price_comparison_rejects_unsupported_product_unit(self):
        pid=self.db.add_product({'name':'Mystery item','unit':'box','quantity':0,'price':'1'})
        store=self.db.add_store({'name':'Unsupported unit store'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':store,'package_quantity':1,'package_unit':'kg','price':'10','recorded_date':date.today().isoformat()})

    def test_price_comparison_uses_product_measurement_dimension(self):
        pid=self.product(0)
        store=self.db.add_store({'name':'Mass store'})
        with self.assertRaises(ValueError):
            self.db.add_price_record({'product_id':pid,'store_id':store,'package_quantity':1,'package_unit':'kg','price':'100','recorded_date':date.today().isoformat()})
        self.assertEqual(self.db.price_comparison(pid),[])

    def test_budget_per_budget_switches_are_honoured(self):
        today=date.today().isoformat()
        bid=self.db.add_budget({'name':'Food budget','category':'All','amount':'100','start_date':today,'end_date':today})
        self.db.set_budget_alert_thresholds(bid,[100])
        self.db.add_expense({'date':today,'category':'Food','amount':'80'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='budget' AND related_id=?",(bid,))['n'],0)
        self.db.add_expense({'date':today,'category':'Food','amount':'25'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='budget' AND related_id=?",(bid,))['n'],1)

    def test_stock_alert_does_not_spam_and_realerts_after_recovery(self):
        pid=self.product(1)
        self.db.generate_notifications()
        first=self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='product' AND related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n']
        self.db.generate_notifications()
        second=self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='product' AND related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n']
        self.assertEqual(first,1); self.assertEqual(second,1)
        self.db.update_product(pid,{'name':'Test Milk','category':'Dairy','unit':'L','quantity':10,'min_quantity':2,'price':'2.50'})
        self.db.generate_notifications()
        self.db.update_product(pid,{'name':'Test Milk','category':'Dairy','unit':'L','quantity':1,'min_quantity':2,'price':'2.50'})
        self.db.generate_notifications()
        self.assertEqual(self.db.one("SELECT COUNT(*) n FROM notifications WHERE related_type='product' AND related_id=? AND fingerprint LIKE 'stock:%'",(pid,))['n'],1)

    def test_recurring_schedule_rejects_empty_template(self):
        with self.assertRaises(ValueError):
            self.db.create_recurring_schedule('Empty',7,date.today().isoformat(),[])

    def test_recurring_schedule_catchup_is_bounded(self):
        sid=self.db.create_recurring_schedule('Old schedule',1,'2000-01-01',[{'name':'Rice','quantity':1,'unit':'kg','unit_price':'1'}])
        generated=self.db.generate_due_recurring_lists('2026-11-15')
        self.assertLessEqual(len(generated),50)
        next_due=self.db.one('SELECT next_due FROM recurring_shopping WHERE id=?',(sid,))['next_due']
        self.assertGreater(next_due,'2000-01-01')

    def test_invalid_optional_foreign_key_is_rejected_cleanly(self):
        with self.assertRaises(ValueError):
            self.db.add_expense({'date':date.today().isoformat(),'category':'Food','amount':'10','member_id':'1.5'})

if __name__=='__main__': unittest.main()

