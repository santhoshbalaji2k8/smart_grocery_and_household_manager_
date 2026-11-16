# Deep audit and correction log

This build was re-audited against the previous Logic Fixed ZIP. The earlier 54-test pass did not exercise all cross-feature behavior. Additional defects were found and corrected.

## Corrections made in this pass

### Validation and dates
- Validate monetary input before rounding, so small negative values such as `-0.001` cannot become an accepted `-0.00`.
- Reject non-finite, negative, zero-when-not-allowed, overflow and underflow numeric inputs.
- Require real ISO calendar dates; reject future purchase, expense, price-record and wastage dates.
- Require purchase-batch expiry to be on or after the purchase date.
- Keep past expiry dates available for opening stock records so already-expired household stock can be identified and written off.
- Require positive budget/expense values to remain at least one minor currency unit after rounding.

### Inventory, batches and purchases
- Prevent changing a product's unit while stock or batch quantities remain.
- Record manual stock adjustments, consumption and wastage against affected batches.
- Keep consumption reporting separate from wastage reporting.
- Keep purchase totals equal to the sum of rounded line totals.
- Calculate partial purchase refunds cumulatively to avoid rounding-cent over-refunds.
- Block unsafe return/delete/edit operations for legacy purchase rows without traceable batch records.
- Validate optional foreign-key IDs and report missing products/stores/members clearly.

### Shopping and recurring schedules
- Fix shopping-list estimated totals so currency-formatted display strings are never parsed back as raw money values.
- Convert a shopping item into a product/purchase/stock batch/expense and mark it purchased in one database transaction.
- Roll back the entire conversion if any validation or database operation fails.
- Require at least one recurring template item and strict four-field item syntax in the UI.
- Limit recurring catch-up to 50 occurrences per schedule per page visit to prevent long pauses after a schedule has been dormant for years.

### Prices, budgets and notifications
- Enforce price package units compatible with the product's measurement dimension.
- Prevent mass and volume price comparisons from being mixed or selected based on record order.
- Prevent overlapping budgets for the same category/date range.
- Apply per-budget alert switches as well as the global supported thresholds.
- Refresh notification text as conditions change, avoid repeated active stock alerts, close obsolete alerts after recovery and refresh expiry alerts as their state changes.

### UI, reports and backup
- Stop inserting sample/demo data automatically. Sample data is now an explicit opt-in action in Settings.
- Apply the saved date-display format to table date columns.
- Add empty-state messages for key lists.
- Add 30-day consumption and active budget-utilization summaries to Reports and PDF output.
- Sanitize unsupported PDF glyphs rather than allowing a Unicode character in a product name to abort the entire PDF export.
- Add an application-level page-render/callback error boundary and log unexpected exceptions when the project folder is writable.
- Validate restored backups for SQLite integrity, foreign keys, required tables and required columns; restore through a temporary file after validation.
- Barcode code and barcode-related dependencies remain removed.

### Additional edge-case corrections
- Set a documented minimum non-zero quantity resolution of `1e-9` and use a tighter `1e-12` stock reconciliation tolerance to avoid silently losing tiny stock changes.
- Add a user-facing Record Consumption action; only non-expired batches can be consumed, while expired stock must be recorded as wastage.
- Add safe batch expiry/cost editing and budget editing with overlap checks.
- Clamp floating-point residue close to zero after stock depletion, returns and wastage.
- Preserve batch quantity and price fields when updating only part of a batch record; add an Edit Batch action to the expiry page.
- Prevent product-unit changes after any stock, purchase, price or wastage history exists, even when current stock has reached zero.
- Prevent deletion of products with remaining stock or transaction/price history; close active alerts when an unused product is deleted.
- Resolve budget notifications when spending drops below thresholds or a budget period ends; refresh the current threshold alert rather than leaving stale warnings active.
- Validate purchase line totals against the exact quantity representation stored by SQLite and use Decimal accumulation for split returns.
- Validate restored backups for stock/batch equality, purchase totals, linked expense equality, returned quantities, date validity, money validity, unit compatibility and overlapping budgets.
- Add SQLite triggers as a second line of defense for invalid dates and non-finite/too-small quantities.
- Test empty and populated render logic for the main data pages using simulated widgets; add real CSV, XLSX and PDF export workflow tests.

## Latest verification
- `python -m py_compile run_app.py app/*.py tests/*.py` — passed.
- `python -m unittest discover -s tests -v` — **128 tests passed** in the latest full run.
- Branch coverage run: approximately **82% statement coverage for `app/database.py`** and **47% for `app/main.py`**. Simulated-widget page rendering is tested, but actual CustomTkinter rendering and mouse behavior are not covered.

## Important limitation
The build environment did not have CustomTkinter installed and could not fetch it from the package index. Therefore the actual Windows graphical interface has not been launched or visually regression-tested here. The GUI must still be opened on the target Windows computer. This report does not claim that no future bugs are possible.

## Additional user-reported fixes (2026-11-15)
- Enforced meaningful Unicode product names at UI and database layers.
- New expiry dates must be real future dates (strictly after today); historical expired batches remain supported for existing stock records.
- Reworked theme switching to destroy old scrollable canvases before changing CustomTkinter's global appearance mode and defer the rebuild until the option-menu callback finishes.
- Centered purchase and household-member action controls.
- Improved Treeview borders, header separators, row height and alternating row backgrounds.
- Added regression coverage; see `FINAL_USER_FIXES_REPORT.md`.
