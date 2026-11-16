# Local timestamp display correction

## Problem
SQLite `CURRENT_TIMESTAMP` stores timestamps in UTC. The application was displaying the stored timestamp text directly in the spreadsheet table, so the date appeared correct while the clock time was several hours behind the computer's local time.

## Correction
- Keep timestamps stored in UTC in SQLite; do not rewrite existing records or alter database relationships.
- Convert `created_at` and `updated_at` values from UTC to the computer's configured local timezone only when rendering table cells.
- Respect explicit timezone offsets when present.
- Apply the user's configured date format and retain 24-hour time with seconds.
- Leave invalid legacy timestamp strings visible as-is rather than failing the page render.

## Verification
- Added five regression tests covering SQLite naive UTC timestamps, explicit `Z`, explicit offsets, empty values, and malformed legacy values.
- Full test suite: 150 passed, 4 optional phone-number tests skipped because `phonenumbers`/`pycountry` are not installed in the test environment.
- Python compilation passed.

Existing database timestamps are not modified. The displayed local time follows the Windows time zone configured on the computer running the application.
