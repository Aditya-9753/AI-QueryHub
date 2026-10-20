# Setup guide

## 1. Backend (Windows)

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-rag.txt      # optional (ChromaDB + sentence-transformers, ~2 GB torch)
copy ..\.env.example ..\.env            # keys bharo
python ..\database\seed_data\seed_demo.py
uvicorn app.main:app --reload
```

- Swagger docs: http://localhost:8000/docs
- Tests: `pytest`

## 2. Frontend

```powershell
cd frontend
npm install
npm run dev
```

`/api` requests Vite proxy se `http://localhost:8000` par jaati hain (`vite.config.ts`).

## 3. Postgres / Supabase

1. `database/schema.sql` chalao (demo business tables + `queryhub_ro` read-only role).
2. `.env` me `DATABASE_URL` / `READONLY_DATABASE_URL` set karo (`postgresql+psycopg://...`), `AUTO_CREATE_TABLES=false`.
3. `cd backend && alembic upgrade head` (app + innovation + v3 tables).

## 4. New migration

```powershell
cd backend
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
