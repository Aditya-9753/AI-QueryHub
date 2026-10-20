Alembic migrations (base + innovation + v3 tables). Config: `backend/alembic.ini`.

```
cd backend
alembic upgrade head
alembic revision --autogenerate -m "message"
```
