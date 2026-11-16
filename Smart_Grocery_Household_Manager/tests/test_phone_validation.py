import importlib.util
import sys
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))

try:
    import phonenumbers  # noqa: F401
    import pycountry  # noqa: F401
    from phone_utils import normalize_phone, country_options
    PHONE_LIBS_AVAILABLE = True
except ImportError:
    PHONE_LIBS_AVAILABLE = False


@unittest.skipUnless(PHONE_LIBS_AVAILABLE, 'Install requirements.txt for libphonenumber country validation tests')
class CountryPhoneValidationTests(unittest.TestCase):
    def test_indian_mobile_number_normalizes_to_e164(self):
        self.assertEqual(normalize_phone('9876543210', 'IN'), '+919876543210')

    def test_rejects_short_indian_number(self):
        with self.assertRaises(ValueError):
            normalize_phone('12345', 'IN')

    def test_rejects_country_code_entered_twice(self):
        with self.assertRaises(ValueError):
            normalize_phone('+919876543210', 'IN')

    def test_country_options_include_india_and_calling_code(self):
        self.assertIn(('India (+91)', 'IN', 91), country_options())


if __name__ == '__main__':
    unittest.main()
