# Smart Grocery & Household Manager — Final User Fixes Build

This build is based on the exact archive uploaded with the screenshot. Existing application modules and the barcode-free version have been retained.

## User-reported fixes
- Product names now require meaningful Unicode letters and are limited to 2–100 characters. Common grocery formats such as `Aashirvaad Atta 5kg`, `3M Scotch Brite`, and Tamil-script names are accepted. Punctuation-only, number-only, emoji-only, control-character and unsupported-symbol names are rejected.
- New product opening-batch and purchase-batch expiry dates must be valid calendar dates strictly later than today. Past dates and today are rejected. Existing expired stock remains visible as historical inventory; unchanged historical dates are not erased during unrelated corrections.
- Dark-mode switching now waits until the option-menu callback has returned, destroys the old scrollable page canvases before changing CustomTkinter's global appearance mode, then rebuilds the current page. This directly addresses the supplied `invalid command name ...ctkcanvas` failure pattern.
- Purchase edit/return/delete controls and household member edit/delete controls are grouped in centered action rows.
- Tables now use solid outer and heading borders, improved row height, and alternating row backgrounds. Native Treeview selection and sorting behavior is preserved.

## Test and build verification
- Python compilation: passed.
- Unit/integration suite: 139 tests passed.
- Coverage run with branch measurement: database module 82%; main application module 47%; combined statement coverage 65%.
- ZIP archive integrity: checked after packaging.

## Not yet verified in this environment
The current environment does not have CustomTkinter installed and does not provide an interactive Windows desktop. Therefore, the real Windows dark/light transition and exact visual placement must be confirmed on the user's PC. Automated page-render tests and source-level checks are not a substitute for a GUI session.
