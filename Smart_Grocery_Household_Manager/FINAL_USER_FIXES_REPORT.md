# Final User-Reported Fixes — Audit Report

## Source reviewed
The uploaded `Smart_Grocery_Household_Manager_Deep_Audit_Final(1).zip` archive was extracted and modified. Existing modules, navigation pages, database operations, tests, and barcode-free design were retained.

## Changes made

1. **Product-name validation**
   - Product names must be 2–100 characters and contain at least one Unicode letter.
   - Allows normal grocery names with numbers, spaces, common punctuation, and non-English scripts (including combining marks used by Tamil and other scripts).
   - Rejects punctuation-only, digits-only, emoji-only, control-character, unsupported-symbol, and excessively long names.
   - Enforced in both UI validation and database methods, so bypassing the form does not bypass the rule.

2. **Expiry-date validation**
   - New opening batches and new purchase batches accept only real ISO calendar dates strictly after today's date.
   - Past dates and today's date are rejected.
   - Invalid dates such as 2026-02-30 are rejected.
   - Existing historical expired batches remain readable and can still be corrected; changing a batch expiry requires a future date.

3. **Dark-mode Tcl error**
   - The previous implementation changed CustomTkinter's global appearance mode while old scrollable-frame canvases and their Tcl callbacks were still alive. This could cause `invalid command name ...ctkcanvas` on Windows.
   - Theme switching is now deferred until the option-menu callback has returned. Existing page and sidebar widgets are destroyed before the global appearance mode changes, then the current page is rebuilt.
   - This is a code-level correction; a real Windows GUI launch still needs confirmation on the user's machine because this environment has no CustomTkinter installation/display.

4. **Action-button alignment**
   - The purchase history's edit, return, and delete controls are grouped in a centered action row.
   - Household member edit/delete controls are grouped in a centered action row.

5. **Table appearance**
   - Added solid table and heading borders, increased row height, and alternating row backgrounds to improve row separation and readability while retaining native Treeview selection behavior.

## Verification

- `python -m py_compile run_app.py app/*.py tests/*.py` — passed.
- `python -m unittest discover -s tests` — **139 tests passed**.
- Added regression tests for invalid product names, Unicode grocery names, past/today/future expiry dates, and purchase-batch expiry validation.
- An existing expired-stock test now seeds an expired legacy batch directly in the database, reflecting the real-world case of historical data rather than allowing a new expired batch through the application.

## Remaining verification limitation

CustomTkinter is not installed in the build environment and there is no interactive Windows desktop here. Therefore the Tk/CustomTkinter theme-switch behavior and final pixel-level table appearance cannot be honestly described as visually tested in this environment. Please launch the app on Windows and switch Light → Dark → Light once; the new code specifically addresses the invalid-canvas callback shown in the supplied screenshot.
