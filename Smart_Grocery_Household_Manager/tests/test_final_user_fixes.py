import tempfile
import unittest
from pathlib import Path
from datetime import date, timedelta
import sys
APP = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP))
from database import Database

class FinalUserFixTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self.tmp.name) / 'test.db')
    def tearDown(self):
        self.tmp.cleanup()

    def test_product_name_rejects_punctuation_only_digit_only_and_emoji(self):
        for index, bad in enumerate(('!!!', '12345', '😀😀', 'a' * 101)):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                self.db.add_product({'name': bad, 'unit': 'pcs', 'quantity': 1, 'price': '1'})

    def test_product_name_accepts_unicode_and_common_grocery_format(self):
        pid = self.db.add_product({'name': 'பால் 1L', 'unit': 'L', 'quantity': 1, 'price': '50'})
        self.assertGreater(pid, 0)

    def test_product_name_rejects_control_and_unsupported_symbols(self):
        for bad in ('Rice\nMilk', 'Rice💥'):
            with self.subTest(name=bad), self.assertRaises(ValueError):
                self.db.add_product({'name': bad, 'unit': 'kg', 'quantity': 1, 'price': '1'})

    def test_opening_batch_expiry_must_be_after_today(self):
        for index, expiry in enumerate(('2000-01-01', date.today().isoformat())):
            with self.subTest(expiry=expiry), self.assertRaises(ValueError):
                self.db.add_product({'name': f'Expiry Test {index}', 'unit': 'pcs', 'quantity': 1, 'price': '1', 'expiry_date': expiry})

    def test_opening_batch_accepts_future_expiry(self):
        expiry = (date.today() + timedelta(days=2)).isoformat()
        pid = self.db.add_product({'name': 'Future Expiry Rice', 'unit': 'kg', 'quantity': 1, 'price': '1', 'expiry_date': expiry})
        self.assertEqual(self.db.one('SELECT expiry_date FROM product_batches WHERE product_id=?', (pid,))['expiry_date'], expiry)

    def test_purchase_batch_expiry_must_be_future(self):
        pid = self.db.add_product({'name': 'Purchase Test Rice', 'unit': 'kg', 'quantity': 0, 'price': '1'})
        with self.assertRaises(ValueError):
            self.db.create_purchase({'purchase_date': date.today().isoformat(), 'items': [{'product_id': pid, 'quantity': 1, 'unit_price': '1', 'expiry_date': date.today().isoformat()}]})

if __name__ == '__main__':
    unittest.main()
