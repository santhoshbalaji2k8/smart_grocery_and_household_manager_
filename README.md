\# 🛒 Smart Grocery \& Household Manager



A Python-based desktop application designed to simplify grocery inventory management, household purchases, expiry tracking, shopping lists, store price comparison, and expense and budget management.



The application brings essential household grocery activities together in one place, helping users manage their inventory, monitor spending, and keep track of everyday household needs.



\---



\## 📌 Project Overview



Managing household groceries involves keeping track of available products, recording purchases, monitoring expiry dates, planning shopping lists, and controlling expenses.



The \*\*Smart Grocery \& Household Manager\*\* provides an integrated desktop solution for these activities.



Built using Python, CustomTkinter, and SQLite, the application provides a graphical interface with locally stored data, inventory tracking, purchase management, budget monitoring, reports, and other useful household management features.



\---



\## ✨ Key Features



\### 1. Dashboard

\- Overview of household inventory.

\- Total products and stock status.

\- Low-stock and out-of-stock information.

\- Top product category.

\- Quick access to important application modules.



\### 2. Inventory Management

\- Add, edit, view, and delete products.

\- Manage product names, categories, brands, units, prices, and quantities.

\- Set minimum stock levels.

\- Search and filter inventory.

\- Monitor available stock.

\- Export inventory information to CSV and Excel.

\- Spreadsheet-style tables with gridlines and centred cell contents.



\### 3. Orders \& Purchases

\- Record purchases containing multiple products.

\- Select products by name.

\- Calculate purchase totals automatically.

\- Maintain purchase history.

\- Associate purchases with stores and payment methods.

\- Automatically update inventory and linked expenses.

\- Edit eligible purchases.

\- Record purchase returns.

\- Delete purchases when stock-integrity conditions allow it.



\### 4. Household Members Management

\- Add, edit, and delete household members.

\- Select country or region while entering phone numbers.

\- Validate phone numbers using country-specific numbering information.

\- Store valid phone numbers in international format.

\- Maintain household member relationships with relevant records.



\### 5. Shopping List

\- Create multiple shopping lists.

\- Add, edit, and remove shopping items.

\- Mark items as purchased.

\- Convert eligible shopping-list items into purchases.

\- Create and manage recurring shopping schedules.



\### 6. Store Price Comparison

\- Maintain store information.

\- Record product prices from different stores.

\- Compare prices for compatible units.

\- Normalize supported mass, volume, and count measurements.

\- Identify more economical purchasing options.



\*Note: Store prices are entered manually. Live retailer price fetching is not included.\*



\### 7. Expiry Tracker

\- Track product purchase and expiry dates.

\- Maintain stock-batch information.

\- Identify expired and near-expiry products.

\- Manage batch information.

\- Record household consumption.

\- Track product wastage.

\- Use FIFO-oriented stock handling.



\### 8. Expenses \& Budget Management

\- Record and manage household expenses.

\- Edit and delete eligible expense records.

\- Create budgets with date ranges.

\- Monitor spending against budget limits.

\- Configure budget alert thresholds.

\- View budget utilization and remaining amounts.

\- Automatically link eligible purchase expenses.



\### 9. Smart Assistant \& Notifications

\- Offline, rule-based recommendations.

\- Stock-related suggestions.

\- Expiry-related alerts.

\- Budget threshold notifications.

\- Notification management.



\### 10. Reports \& Analytics

\- Monthly spending reports.

\- Category-wise expense analysis.

\- Stock distribution by category.

\- Consumption summaries.

\- Budget utilization reports.

\- Export supported reports to CSV, Excel, and PDF.



\### 11. Settings \& Data Management

\- Light and dark themes.

\- Currency display preferences.

\- Available language options.

\- Date display format settings.

\- Budget alert configuration.

\- Database backup and restore.

\- Optional sample data loading.



\---



\## 🛠️ Technologies Used



| Technology | Purpose |

|---|---|

| Python | Core application development |

| CustomTkinter | Desktop graphical user interface |

| SQLite | Local database management |

| Matplotlib | Charts and visual reports |

| OpenPyXL | Excel export |

| ReportLab | PDF report generation |

| phonenumbers | Country-aware phone number validation |

| pycountry | Country and region information |

| unittest | Automated testing |



\---



\## 📂 Project Structure



```text

smart\_grocery\_and\_household\_manager/

│

├── app/

│   ├── \_\_init\_\_.py

│   ├── main.py

│   ├── database.py

│   └── phone\_utils.py

│

├── tests/

│   ├── test\_database.py

│   ├── test\_datetime\_display.py

│   ├── test\_final\_user\_fixes.py

│   ├── test\_phone\_validation.py

│   ├── test\_purchase\_ui\_workflow\_regression.py

│   ├── test\_regressions.py

│   └── test\_ui\_validation.py

│

├── assets/

│

├── run\_app.py

├── requirements.txt

├── README.md

├── .gitignore

├── FEATURE\_STATUS.md

├── FIXES\_APPLIED.md

└── IDLE\_INSTRUCTIONS.txt

```



\---



\## ⚙️ Installation \& Setup



\### Prerequisites



\- Python 3.10 or newer.

\- Windows is the primary documented desktop environment.

\- Internet connection for installing the required Python packages.



\### Step 1: Clone the Repository



```bash

git clone https://github.com/YOUR-USERNAME/smart\_grocery\_and\_household\_manager.git

```



Replace `YOUR-USERNAME` with your GitHub username.



\### Step 2: Open the Project Folder



```bash

cd smart\_grocery\_and\_household\_manager

```



\### Step 3: Install Dependencies



```bash

python -m pip install -r requirements.txt

```



If `python` does not work on Windows, try:



```bash

py -m pip install -r requirements.txt

```



\---



\## ▶️ How to Run the Application



\### Method 1: Using Command Prompt



From the project directory, execute:



```bash

python run\_app.py

```



\### Method 2: Using Python IDLE



1\. Open Python IDLE.

2\. Select \*\*File → Open\*\*.

3\. Open `run\_app.py`.

4\. Press \*\*F5\*\* to execute the application.



\### Method 3: Using the Windows Launcher



Double-click:



```text

launch\_windows.bat

```



\---



\## 🗄️ Database Information



\- The application uses SQLite for local data storage.

\- The database file is named `smart\_grocery.db`.

\- The database is created automatically during the first launch.

\- Data is stored locally on the user's computer.

\- Database backup and restore options are available in Settings.



A new installation starts with an empty database. Optional sample data can be loaded through the application settings.



\*\*Important:\*\* Personal database files and backups should not be uploaded to a public GitHub repository.



\---



\## 🧪 Running Automated Tests



The project includes automated tests for database operations, validation, purchases, inventory, shopping lists, budget operations, phone validation, timestamps, and other workflows.



Run the tests from the project directory:



```bash

python -m unittest discover -s tests -v

```



The tests are intended to check important application workflows, input validation, database integrity, and regression cases.



Automated tests do not replace manual testing of the graphical interface on the target computer.



\---



\## 🔒 Data Validation \& Reliability



The application includes validation and data-integrity checks for important operations, including:



\- Invalid product names.

\- Negative and non-finite quantities.

\- Negative prices and expenses.

\- Invalid calendar dates.

\- Past expiry dates for new batches.

\- Invalid phone numbers according to country numbering metadata.

\- Purchase and return calculations.

\- Stock and batch consistency.

\- Database transaction rollback.

\- Backup and restore validation.



Related purchase, stock, batch, and expense operations use database transactions to help prevent partial updates.



\---



\## ⚠️ Current Limitations



\- The application currently uses local SQLite storage; cloud synchronization is not implemented.

\- Secure user login and multi-account authentication are not implemented.

\- Live retailer price fetching is not available; prices are entered manually.

\- Currency selection changes display formatting only and does not perform exchange-rate conversion.

\- Some interface translations may remain in English.

\- Phone-number validation checks numbering-plan validity but does not verify ownership or whether a number is active.

\- Full graphical behavior should be tested on the target Windows computer.



\---



\## 🚀 Future Improvements



Possible future enhancements include:



\- Secure user authentication and role management.

\- Cloud database synchronization.

\- Live price integrations with authorized retailers.

\- Complete multilingual support.

\- Advanced analytics and customizable reports.

\- Expanded automated graphical interface testing.



\---



\## 🎓 Project Information



\*\*Project Name:\*\* Smart Grocery \& Household Manager  

\*\*Project Type:\*\* Python Desktop Application  

\*\*Programming Language:\*\* Python  

\*\*Database:\*\* SQLite  



Developed as a Computer Science and Engineering student project to apply Python programming, database management, graphical user interface development, data validation, and software testing concepts to a practical household management problem.



\---



\## 📄 License



No open-source license has been selected for this repository yet. Please contact the repository owner before reusing or redistributing the project.



\---



\## ⭐ Feedback



Suggestions, feedback, and bug reports are welcome.



Thank you for visiting the \*\*Smart Grocery \& Household Manager\*\* project!

