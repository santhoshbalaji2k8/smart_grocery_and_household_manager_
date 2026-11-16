import tempfile
import unittest
from pathlib import Path
import sys
APP = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP))
from database import Database

class PurchaseWorkflowRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / 'purchase-flow.db')
        self.product_id = self.db.add_product({'name':'Purchase Flow Rice','unit':'kg','quantity':0,'price':'60'})

    def tearDown(self):
        self.tmp.cleanup()

    def test_purchase_without_store_or_member_updates_stock_and_expense(self):
        purchase_id = self.db.create_purchase({
            'purchase_date':'2026-11-15', 'payment_method':'Cash', 'notes':'UI workflow regression',
            'items':[{'product_id':self.product_id,'quantity':'2.5','unit_price':'60','expiry_date':None}]
        })
        self.assertGreater(purchase_id, 0)
        product = self.db.one('SELECT quantity FROM products WHERE id=?',(self.product_id,))
        purchase = self.db.one('SELECT total,member_id FROM purchases WHERE id=?',(purchase_id,))
        expense = self.db.one('SELECT amount,purchase_id FROM expenses WHERE purchase_id=?',(purchase_id,))
        self.assertAlmostEqual(product['quantity'], 2.5)
        self.assertEqual(str(purchase['total']), '150.00')
        self.assertIsNone(purchase['member_id'])
        self.assertEqual(str(expense['amount']), '150.00')
        self.assertEqual(expense['purchase_id'], purchase_id)

    def test_purchase_rejects_nonexistent_product_without_partial_records(self):
        with self.assertRaises(ValueError):
            self.db.create_purchase({'purchase_date':'2026-11-15','items':[{'product_id':999999,'quantity':1,'unit_price':'10'}]})
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM purchases')['n'],0)
        self.assertEqual(self.db.one('SELECT COUNT(*) n FROM expenses')['n'],0)

if __name__ == '__main__': unittest.main()
