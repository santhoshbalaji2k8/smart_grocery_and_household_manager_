"""Regression tests for local-time display of SQLite UTC timestamps."""
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / 'app'
sys.path.insert(0, str(APP_DIR))
if 'customtkinter' not in sys.modules:
    stub = types.ModuleType('customtkinter')
    stub.CTk = type('CTk', (), {})
    sys.modules['customtkinter'] = stub

spec = importlib.util.spec_from_file_location('grocery_main_for_datetime_tests', APP_DIR / 'main.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
format_datetime_value = module.format_datetime_value


class LocalDateTimeDisplayTests(unittest.TestCase):
    def test_sqlite_naive_timestamp_is_interpreted_as_utc(self):
        raw = '2026-11-15 17:04:26'
        expected_dt = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc).astimezone()
        expected = expected_dt.strftime('%d-%m-%Y %H:%M:%S')
        self.assertEqual(format_datetime_value(raw, '%d-%m-%Y'), expected)

    def test_explicit_utc_suffix_is_converted(self):
        raw = '2026-11-15T17:04:26Z'
        expected_dt = datetime.fromisoformat('2026-11-15T17:04:26+00:00').astimezone()
        self.assertEqual(format_datetime_value(raw, '%Y-%m-%d'), expected_dt.strftime('%Y-%m-%d %H:%M:%S'))

    def test_explicit_offset_is_respected(self):
        raw = '2026-11-15T22:34:26+05:30'
        expected_dt = datetime.fromisoformat(raw).astimezone()
        self.assertEqual(format_datetime_value(raw, '%Y-%m-%d'), expected_dt.strftime('%Y-%m-%d %H:%M:%S'))

    def test_empty_value_stays_empty(self):
        self.assertEqual(format_datetime_value('', '%d-%m-%Y'), '')
        self.assertEqual(format_datetime_value(None, '%d-%m-%Y'), '')

    def test_invalid_legacy_value_does_not_crash(self):
        self.assertEqual(format_datetime_value('not-a-timestamp', '%d-%m-%Y'), 'not-a-timestamp')


if __name__ == '__main__':
    unittest.main()
