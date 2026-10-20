# Seed data

- `seed_demo.py` — synthetic e-commerce data (Delhi / Mumbai / Pune × Electronics / Fashion / Grocery,
  Jan 2025 → Feb 2026) local SQLite (ya `DATABASE_URL`) me `orders` + `payments` tables me daalta hai.
  Feb 2026 Delhi me Electronics mix shift **planted** hai (worked example, Ch 10).
- Chinook / Northwind jaise public datasets yahan `.sql` files ki tarah rakh sakte ho.

```powershell
cd backend
python ..\database\seed_data\seed_demo.py
```
