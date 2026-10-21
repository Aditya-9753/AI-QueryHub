# Production image for the FastAPI backend (Render "AI-QueryHub" web service, Docker runtime).
# Local dev / docker-compose uses backend/Dockerfile instead (that one also installs the heavy RAG deps).
#
# - Only core requirements: ChromaDB + torch don't fit the 512 MB free tier; SCHEMA_RAG=auto falls back to lexical.
# - Demo business data (orders, payments, customers) is seeded into a separate SQLite file at build time and opened
#   read-only by the SQL firewall (READONLY_DATABASE_URL). App tables live in DATABASE_URL (Supabase Postgres
#   recommended; Alembic migrates on startup).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install -r backend/requirements.txt

COPY backend backend
COPY database database

WORKDIR /app/backend
RUN python ../database/seed_data/seed_demo.py sqlite:///./demo.db

ENV READONLY_DATABASE_URL=sqlite:///./demo.db
EXPOSE 8000
# Render sets $PORT; proxy headers so request.url / redirects use https
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
