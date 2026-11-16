# Final table-grid update

This update is limited to the shared table renderer in `app/main.py`.

- Strengthened Treeview outer and heading borders in both light and dark themes.
- Increased row height and cell padding for clearer spreadsheet-style reading.
- Added visible vertical cell separators to displayed values without changing the underlying row values, database records, sort order, selection behavior, or callbacks.
- Kept alternating row backgrounds and all existing columns/features.

## Verification

- `python -m py_compile run_app.py app/*.py tests/*.py`: passed.
- `python -m pytest -q`: 141 passed, 4 skipped, 52 subtests passed.
- ZIP integrity: checked after packaging.

The 4 skipped tests are the optional phone-number integration tests because their external metadata packages were unavailable in this offline build environment. A real CustomTkinter Windows GUI visual test could not be performed here; the UI should be visually checked on the target computer after installing `requirements.txt`.
