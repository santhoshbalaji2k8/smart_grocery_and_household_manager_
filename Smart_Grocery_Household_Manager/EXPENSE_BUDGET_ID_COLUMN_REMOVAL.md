# Expense & Budget ID Column Removal

- Removed the visible `id` column from the Active Budget Tracking table.
- Removed the visible `id` column from the Household Expenses table.
- Kept database IDs in each row's underlying data. The shared spreadsheet table uses those IDs as hidden selection metadata, so Edit Selected Budget, Configure Selected Budget Alerts, Edit Expense, and Delete Expense continue to target the correct records.
- No database schema, stored records, calculations, or other application modules were changed.

Verification: Python compilation and the project's automated test suite were run after this change. See the accompanying delivery message for the observed results.
