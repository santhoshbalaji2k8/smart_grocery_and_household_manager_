# Smart Grocery & Household Manager

A Python desktop application for organizing household groceries, monitoring inventory, recording purchases, planning shopping, tracking expiry dates, comparing store prices, and managing household expenses and budgets.

The application is built with **Python, CustomTkinter and SQLite**. It is designed for local use: your records are stored in a SQLite database on your computer.

---

## Table of contents

- [Overview](#overview)
- [Features](#features)
- [Technology stack](#technology-stack)
- [Application structure](#application-structure)
- [Requirements](#requirements)
- [Installation](#installation)
- [Run the application](#run-the-application)
- [First launch and sample data](#first-launch-and-sample-data)
- [Run the tests](#run-the-tests)
- [Data storage and backup](#data-storage-and-backup)
- [Validation and data integrity](#validation-and-data-integrity)
- [Known limitations](#known-limitations)
- [Future improvements](#future-improvements)

## Overview

Managing household groceries involves more than keeping a list of products. It also means knowing what is in stock, what needs to be purchased, which items are nearing expiry, how much has been spent, and whether spending is within a planned budget.

**Smart Grocery & Household Manager** brings these activities together in one desktop application. It links purchase records with inventory and expenses, maintains stock-batch information, and provides reports and alerts to help users understand household grocery activity.

The application opens on the **Inventory** page. A new installation starts with an empty database; sample records are optional and are never inserted automatically.

## Features

### 1. Dashboard

- Summary cards for total products, low-stock items, out-of-stock items and top category.
- Overview of household inventory and activity.

### 2. Inventory management

- Add, edit, view and delete eligible product records.
- Track product category, brand, description, unit, current stock, minimum stock and price.
- Search and filter inventory records.
- Monitor stock status and make stock adjustments.
- Export inventory data to CSV and Excel (XLSX).
- Spreadsheet-style tables with visible cell gridlines and centred cell content.

### 3. Orders and purchases

- Record purchases containing multiple products.
- Select products by name in the purchase form rather than entering product IDs manually.
- Calculate purchase totals from item quantities and unit prices.
- Associate purchases with a store and, where applicable, a household member and payment method.
- Update inventory, stock batches and the linked expense as part of the purchase transaction.
- Edit eligible purchases, record item returns, and delete purchases when stock-integrity rules allow it.

### 4. Household members

- Add, edit and remove household member records.
- Select a country/region and validate a phone number against its numbering-plan metadata.
- Store valid phone numbers in international E.164 format.
- Keep member relationships for purchase and expense records.

### 5. Shopping lists

- Create and manage multiple shopping lists.
- Add, edit, remove and mark shopping-list items as purchased.
- Convert eligible shopping items into purchases.
- Create recurring shopping schedules, pause or resume them, and generate due lists.
- Limit overdue schedule catch-up per visit so an old schedule does not generate an unbounded number of lists at once.

### 6. Store price comparison

- Maintain stores and manually entered product price observations.
- Compare prices using compatible mass, volume or count units.
- Normalize supported package sizes to make like-for-like comparisons easier.

> Store prices are entered by the user. The application does not fetch or scrape live retailer prices.

### 7. Expiry and stock-batch tracking

- Track stock in batches with purchase and expiry dates.
- Review and edit eligible batch information.
- Record household consumption using non-expired stock in FIFO-oriented order.
- Record wastage against available stock batches.
- Keep stock movements and batch quantities linked for inventory history.

### 8. Expenses and budgets

- Record, edit and delete manual household expenses.
- Associate expenses with household members when applicable.
- Create date-bounded budgets and track spending by category or across all categories.
- Configure budget alert thresholds.
- View budget utilization and remaining amounts for active overall budgets.
- Purchase transactions create linked expense records; purchase returns and eligible reversals adjust those records.

### 9. Smart Assistant and notifications

- Provide offline, rule-based suggestions based on stock, expiry and spending information.
- Generate notifications for relevant stock and expiry conditions and budget thresholds.
- Review notifications and mark them as read.

### 10. Reports and exports

- Review category spending, monthly spending trends and stock by category.
- View consumption and active-budget utilization summaries.
- Export supported information to CSV, Excel (XLSX) and PDF.

### 11. Settings and database tools

- Switch between light and dark appearance.
- Choose a currency display symbol/code. This changes formatting only; it does not convert exchange rates.
- Select the available interface language option and date display format.
- Configure budget alert thresholds.
- Create and restore local SQLite database backups, subject to database validation.
- Load optional sample data for an empty inventory.

---

## Technology stack

| Technology / library | Purpose |
|---|---|
| Python | Application logic |
| CustomTkinter | Desktop graphical user interface |
| SQLite (`sqlite3`) | Local relational database and transactions |
| Matplotlib | Charts and report visualizations |
| OpenPyXL | Excel workbook export |
| ReportLab | PDF report generation |
| `phonenumbers` | Country-aware phone-number validation |
| `pycountry` | Country and region options for the phone form |
| Python `unittest` | Automated tests |

## Application structure

```text
Smart_Grocery_Household_Manager_Deep_Audit_Final/
│
├── app/
│   ├── __init__.py
│   ├── main.py                 # CustomTkinter interface and page workflows
│   ├── database.py             # SQLite schema, queries and business operations
│   └── phone_utils.py          # Country-aware phone validation helpers
│
├── tests/
│   ├── test_database.py
│   ├── test_datetime_display.py
│   ├── test_final_user_fixes.py
│   ├── test_phone_validation.py
│   ├── test_purchase_ui_workflow_regression.py
│   ├── test_regressions.py
│   └── test_ui_validation.py
│
├── run_app.py                  # Main application entry point
├── requirements.txt            # Python package dependencies
├── launch_windows.bat          # Windows launcher
├── launch_unix.sh              # Unix-like launcher
├── IDLE_INSTRUCTIONS.txt       # Additional Windows / IDLE instructions
├── FEATURE_STATUS.md           # Feature and verification notes
├── FIXES_APPLIED.md             # Correction log
├── README.md
└── .gitignore
```

## Requirements

- Python **3.10 or newer**.
- Windows is the primary documented desktop setup. The repository also includes a Unix-like launch script, but platform-specific GUI behavior should be checked on the target system.
- Internet access is needed to install the Python dependencies. Normal application records are stored locally; live retailer data and cloud services are not required.

## Installation

### Windows

1. Download or clone this repository and open its project folder (the folder containing `run_app.py`).
2. Open Command Prompt in that folder.
3. Install the required packages:

   ```bash
   python -m pip install -r requirements.txt
   ```

If the `python` command is not available on your Windows installation, try:

```bash
py -m pip install -r requirements.txt
```

## Run the application

### Option A: Python IDLE

1. Open Python IDLE.
2. Select **File → Open**.
3. Open `run_app.py` from the project folder.
4. Press **F5** or select **Run → Run Module**.
5. Keep the IDLE Shell open while using the application so diagnostic messages remain available.

### Option B: Command Prompt

From the project folder, run:

```bash
python run_app.py
```

Or on Windows:

```bash
py run_app.py
```

### Option C: Windows launcher

Double-click `launch_windows.bat`. It installs the listed requirements and then starts the application using the Windows Python launcher.

## First launch and sample data

- The application creates `smart_grocery.db` in the project folder when it first initializes the database.
- A new database starts empty. No demonstration products, expenses or dashboard totals are inserted automatically.
- To preview the application with example records, open **Settings → Load Optional Sample Data**. Sample data is intended for an empty inventory.
- Use your own records for normal operation. Do not commit your personal database or database backups to a public GitHub repository.

## Run the tests

Run the automated test suite from the project folder:

```bash
python -m unittest discover -s tests -v
```

The test suite in this uploaded project version was run during README preparation:

- **151 tests passed**.
- **4 phone-validation tests were skipped** because the `phonenumbers` / `pycountry` dependencies were not installed in the test environment at that time. Install all packages from `requirements.txt` and rerun the command to execute the optional phone-validation tests.
- Python compilation of the launcher, application modules and test modules completed successfully.

The tests cover database workflows, validation, transaction rollback, purchase and return behavior, stock/batch consistency, recurring shopping schedules, budget alerts, timestamp display helpers, exports and simulated page-render logic.

Automated tests do not replace a full manual test of the graphical application on the target operating system. See [`FEATURE_STATUS.md`](FEATURE_STATUS.md) for additional verification notes.

## Data storage and backup

- The local database is named `smart_grocery.db` and is created in the project root.
- The application includes database backup and restore functions under **Settings**.
- Back up the database before replacing the project folder, changing versions or restoring another database.
- The repository `.gitignore` excludes SQLite database files, backup folders, logs, Python bytecode and common build artifacts. Keep these exclusions in place when publishing the project.

## Validation and data integrity

The application applies validation in the interface and database layer for important operations. Examples include:

- Product names must contain meaningful letters and meet the application's length and character rules.
- Quantities must be finite and non-negative where zero is allowed, and positive for purchase, consumption, shopping and wastage operations.
- Prices and costs cannot be negative; invalid or non-finite numeric values are rejected.
- Dates must be real calendar dates in the expected ISO format for database operations. Purchase, expense, price-record and wastage dates cannot be in the future.
- New expiry dates must be after the current date, and a purchase-batch expiry date cannot precede its purchase date. Historical expired batches remain available for tracking.
- Purchase creation, editing, returns and shopping-list conversion use database transactions so related stock, batch and expense changes succeed or roll back together.
- Stock depletion and wastage are checked against available stock. Batch and stock-movement records are maintained together where supported.
- Product units cannot be changed after stock or relevant product history exists, preventing incompatible historical quantities.
- Backup restore checks database integrity and required data relationships before replacing the active database.

## Known limitations

- **No cloud synchronization:** data is stored in a local SQLite database.
- **No user login or multi-account authentication:** the current interface uses a local Admin User presentation, not a secure account system.
- **No live retailer price feed:** store prices are manually entered by the user.
- **No currency conversion:** changing the currency setting changes display formatting only. Do not mix amounts in different currencies in one database.
- **Partial translations:** English, Tamil, Hindi, Telugu and Kannada options are available, but some descriptions, dialogs, table values and report text may remain in English.
- **Phone validation is not ownership verification:** country metadata checks the number's numbering-plan validity. It cannot confirm that a number is active, belongs to the entered person or is assigned to a particular locality. That requires a separate SMS or voice verification service.
- **GUI verification:** automated tests include simulated widget/page checks, but do not automate every real mouse interaction, Windows DPI setting, font, resize behavior or full graphical workflow. Run the application on the target computer and verify the screens and workflows there.
- **Older database files:** back up an older `smart_grocery.db` before reuse. Historical records from previous versions may need review; do not assume every legacy database is automatically repaired.

## Future improvements

Possible future extensions include secure local user accounts and roles, optional cloud synchronization, authorized retailer integrations, complete translations, expanded configurable reports and broader automated end-to-end GUI tests.

---

## Project status

This is a student-developed Python desktop project. The repository includes its application source, SQLite data layer, automated tests, dependency list and setup documentation. Contributions, bug reports and suggestions are welcome.
