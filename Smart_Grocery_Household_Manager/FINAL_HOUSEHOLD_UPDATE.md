
# Household members update

- Removed the internal database ID from the Household Members table while retaining IDs internally for selection and edit/delete operations.
- Removed the Current Month Member Contributions table from the Household Members page. Purchase/expense attribution and contribution data remain stored and available to other existing features; no schema or transaction history was deleted.
- Replaced the free-text phone field with a country/region selector and national-number input. The selected country displays its calling code (for example, India +91). The phone number is validated against the selected country's numbering plan using Google's libphonenumber metadata and stored in E.164 format.
- The database service also validates E.164 phone values, so callers cannot bypass validation by avoiding the GUI.
- Added `phonenumbers` and `pycountry` dependencies. Run `python -m pip install -r requirements.txt` after extracting this version.

## Verification

- Python compilation: passed.
- Automated suite: 141 passed, 4 skipped, 52 subtests passed.
- The four country-phone integration tests were skipped in this build environment because outbound package installation was unavailable and `phonenumbers` / `pycountry` could not be installed here. They run after installing the new requirements on the target computer.
- The GUI was not launched in this environment; country selector layout and live entry behavior require confirmation on Windows.

Phone-number validation confirms that a number is valid under the selected country's numbering plan. It cannot establish that a number is currently assigned, reachable, or belongs to a particular city/locality; that requires an SMS/voice verification service.
