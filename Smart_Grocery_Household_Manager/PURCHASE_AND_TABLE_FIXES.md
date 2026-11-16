# Purchase workflow and table presentation fixes

## Changes
- Replaced the fragile comma-separated purchase-item text area and manually typed product/store/member IDs with product-name and store-name dropdowns.
- Added individual quantity, unit-price and optional expiry fields per purchase line, with add/remove row controls and a live estimated total.
- Removed internal purchase ID and household-member columns from the Purchase History display. Internal IDs remain attached to table rows for selection/edit/return/delete actions.
- Removed member selection from the purchase-entry form. Existing member attribution is retained when editing an older purchase by omitting `member_id` from the update payload; new purchases default to no member attribution.
- Kept database transaction logic responsible for updating stock batches, stock movements and the linked expense atomically.
- Strengthened ttk table border styling and alternating row backgrounds for a clearer spreadsheet-like appearance.

## Verification
- `python -m py_compile run_app.py app/*.py tests/*.py` — passed.
- `python -m pytest -q` — 141 passed, 52 subtests passed.
- Added purchase workflow regression tests for a purchase with no store/member and for nonexistent-product rollback.

## GUI limitation
CustomTkinter is not installed in the audit environment, so the updated desktop dialog and Windows-specific visual rendering could not be launched here. The purchase database workflow and source compilation were tested. Please run the app on Windows and verify the new dropdown dialog visually.
