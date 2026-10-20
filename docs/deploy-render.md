# Deploy on Render (free tier, ₹0)

Repo me [`render.yaml`](../render.yaml) (Render Blueprint) hai jo do services banata hai:

| Service | Type | Kya chalta hai |
|---|---|---|
| `queryhub-api` | Web service (Python, free) | FastAPI backend · build par demo data `backend/demo.db` me seed hota hai |
| `queryhub-web` | Static site (free) | React build (`frontend/dist`), har path `index.html` par rewrite |

```
GitHub push ──► GitHub Actions CI (ruff · pytest · eval smoke · seed smoke · frontend build)
                    │ sab green?
                    ▼
               Render auto-deploy (autoDeployTrigger: checksPass)
                    ├─► queryhub-api  : pip install → seed demo.db → uvicorn  (/health check)
                    └─► queryhub-web  : npm ci → npm run build → CDN
```

CI fail hua to Render deploy **nahi** karega, isliye toota hua code live nahi jaata.

## 1. Database (recommended): Supabase Postgres

Render free web service ki disk har deploy / spin-down par reset hoti hai. App tables (users, experiments,
audit log) ko bachane ke liye Supabase ka free Postgres use karo:

1. [supabase.com](https://supabase.com) → New project → strong DB password.
2. **Connect** → **Session pooler** connection string copy karo (Render IPv4 hai; direct connection IPv6-only hota hai).
   Format: `postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres`
3. Ye URL hi `DATABASE_URL` banega. `postgresql://` chalega, backend khud `psycopg` driver par map kar leta hai.
   Tables startup par Alembic se ban jaati hain.

Demo business data (orders/payments) Supabase me nahi jaata. Wo har build par `backend/demo.db` me bante hain
aur `READONLY_DATABASE_URL=sqlite:///./demo.db` se sirf read-only khulte hain.

> Supabase skip karna hai? `DATABASE_URL=sqlite:///./queryhub.db` daal do. App chalega, par har deploy /
> 15-min idle spin-down ke baad users aur experiments mit jaayenge. Aur reset ke baad jo **pehla signup**
> karega wo **admin** banega, isliye public demo ke liye Supabase hi use karo.

## 2. Render par Blueprint

1. [dashboard.render.com](https://dashboard.render.com) → **New** → **Blueprint** → GitHub repo `AI-QueryHub` connect karo.
2. Render `render.yaml` padhega aur `sync: false` wale variables poochega:

| Service | Variable | Value |
|---|---|---|
| queryhub-api | `DATABASE_URL` | Step 1 ka Supabase pooler URL |
| queryhub-api | `CORS_ORIGINS` | `https://queryhub-web.onrender.com` (comma se kai URLs) |
| queryhub-api | `GROQ_API_KEY` | console.groq.com key (optional) |
| queryhub-api | `GEMINI_API_KEY` | aistudio.google.com key (optional) |
| queryhub-api | `SUPABASE_URL` | sirf Supabase Auth / Google login ke liye |
| queryhub-api | `SENTRY_DSN` | optional |
| queryhub-web | `VITE_API_URL` | `https://queryhub-api.onrender.com` (aakhri `/` ke bina) |
| queryhub-web | `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | optional (anon key, service key **kabhi nahi**) |

`JWT_SECRET` Render khud random generate karta hai. Koi LLM key na ho to bhi app chalega: ASK ko LLM chahiye,
lekin INVESTIGATE deterministic mode me chalta hai.

3. **Apply** dabao. Pehla build ~3-5 min leta hai.
4. Agar Render ne URL me suffix laga diya (jaise `queryhub-api-x1y2.onrender.com`), to `VITE_API_URL` aur
   `CORS_ORIGINS` asli URLs se update karo aur **queryhub-web ko redeploy** karo (Vite URL build time par bake karta hai).
5. Site kholo → **Sign up**. Pehla account **admin** banta hai, baaki sab analyst. Roles baad me
   *Audit trail & RBAC* page se badal sakte ho.

## 3. Check

- `https://queryhub-api.onrender.com/health` → `{"status": "ok", ...}`
- Swagger: `https://queryhub-api.onrender.com/docs`
- Site par Workbench → LLM pill `online` (key set ho to) → Investigate: “Feb me Delhi revenue kyun gira?”

## Free tier ki limits

- Web service 15 min idle ke baad so jaata hai. Pehli request par ~30-60s cold start lagta hai.
- 512 MB RAM. Isliye Render par `requirements-rag.txt` (ChromaDB + torch) install **nahi** hota, aur schema
  RAG apne aap lexical mode me chalta hai (`SCHEMA_RAG=auto`).
- Redis / Celery worker nahi hai. Investigations background thread me chalti hain (code me fallback hai) aur
  LLM cache off rehta hai.
- Supabase free project 1 hafte inactivity ke baad pause ho sakta hai. Dashboard se resume kar lo.

## Manual deploy / rollback

- Render dashboard → service → **Manual Deploy** → *Deploy latest commit*, ya **Rollback** se purana deploy.
- GitHub Actions → CI → **Run workflow** (`workflow_dispatch`) se checks dobara chala sakte ho.
