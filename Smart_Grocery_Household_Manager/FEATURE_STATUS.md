# Feature status and verification

## Implemented and covered by automated tests
- SQLite persistence, foreign-key enforcement and transaction rollback.
- Inventory create/update/delete, numeric validation, stock adjustments and batch reconciliation safeguards.
- Purchase create/edit/return/delete with atomic stock, batch and linked-expense updates; cumulative partial-return rounding.
- Shopping lists and items, recurring schedules, bounded overdue catch-up and atomic conversion of shopping items into purchases.
- Manual store-price records with mass/volume/count unit compatibility checks.
- Batch expiry editing, FIFO-oriented household consumption, batch-linked consumption/wastage movements and wastage records.
- Household members and contribution summaries.
- Expenses, editable non-overlapping date-bounded budgets, global/per-budget thresholds and notification lifecycle handling.
- Dashboard, category/monthly reports, consumption and budget utilization summaries, CSV/XLSX/PDF export code, local backup and schema-validated restore code.
- Theme, currency-display, language and date-display preferences.
- Optional sample data; no demonstration records are inserted automatically.
- Barcode lookup/scanning and its dependency are not included.

## Automated verification
Run `python -m unittest discover -s tests -v` from the project folder.

- **128 automated tests passed** in the latest full run.
- Python compilation passed for the launcher, application modules and tests.
- Database statement coverage was approximately **82%** and `main.py` coverage approximately **48%** in the branch-coverage run. The full GUI is not included because the test environment cannot run CustomTkinter.
- Simulated-widget page-render tests exercise empty and populated states for the main navigation pages; CSV, XLSX and PDF export paths are also tested.
- Tests cover invalid/non-finite/negative inputs, tiny negative monetary values, invalid/future dates, purchase rollback, stock/batch integrity, partial returns, price normalization, budget overlap and alerts, shopping conversion, recurring schedules, notifications and backup validation.

## Not verified in this environment
- Full graphical rendering, mouse interactions, DPI scaling, fonts and resizing on Windows.
- Windows-specific packaging and IDLE behavior on the user's machine.

## Known limitations
- Cloud synchronization and account login are not enabled.
- Live retailer pricing is not provided; prices are entered manually.
- Currency selection changes display formatting only and does not perform exchange conversion.
- Language translations are partial.
- Existing database files from older builds may contain invalid historical records; back up and review them before reuse.

See `FIXES_APPLIED.md` for the correction log.
