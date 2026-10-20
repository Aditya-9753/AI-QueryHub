# AI QueryHub

> Business questions ko safe, evidence-driven aur reproducible data experiments me badalta hai —
> blindly generated SQL return karne ki jagah.

Blueprint: **Master Blueprint v3.0 · Q-TRACE+ Edition**.
Workflow: **ASK → ANALYZE → INVESTIGATE → CHALLENGE → REPLAY**.

## Folder structure

| Folder | Kya hai |
|---|---|
| `frontend/` | React + Vite + Tailwind + Zustand + TanStack Query + Recharts + React Flow + Monaco |
| `backend/` | FastAPI app, Q-TRACE+ services, tests, eval suite |
| `backend/app/services/` | verify, orchestrator, hypothesis_engine, experiment_planner, analytics, evidence, challenge, experiments, sql_validator, query_executor, rag, llm |
| `database/` | Alembic migrations, demo business schema (`schema.sql`), seed data |
| `docs/` | PRD, setup guide, API docs |

## Quick start (local, bina Docker)

```bash
# backend
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows   (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
pip install -r requirements-rag.txt   # optional: ChromaDB + sentence-transformers (heavy)
python ../database/seed_data/seed_demo.py   # demo orders/payments data (SQLite)
uvicorn app.main:app --reload       # http://localhost:8000/docs
pytest

# frontend (naya terminal)
cd frontend
npm install
npm run dev                          # http://localhost:5173
```

Ya poora stack: `docker-compose up --build`.

## Implementation status (5-phase build plan)

| Phase | Done when | Status / proof |
|---|---|---|
| 1. Foundation + Safe SQL | ASK mode 20 sawaalon par chale | Auth (local JWT + **Supabase**), RBAC, 4-layer firewall, LLM chain + Redis cache, schema RAG (lexical / **ChromaDB + Sentence-Transformers**), semantic layer, ASK/ANALYZE UI. 100 golden questions ready — accuracy ke liye LLM key chahiye: `python -m tests.eval_suite.run_golden` |
| 2. Data + Verify | Noise-only par early exit | `test_qtrace_pipeline.py::test_noise_only_exits_early`; benchmark false alarm **0%**, data-issue detection **100%** |
| 3. Hypotheses + Analytics | Ch 13.8 jaisa output | `python -m tests.eval_suite.worked_example` — poora pipeline SQL se 48.9 / 1.7 / 49.4%, mix −440 / rate −48, DiD −0.086, score 0.915 / 0.888 |
| 4. Trust layer | Grounding violations = 0, exact replay checksum match | `test_investigate_api.py` (replay 100% match, re-derive stable, PDF export, user challenge) |
| 5. Product UI + Eval + Demo | Demo end-to-end + ablation/calibration published | Investigation / Evidence / Challenge / Record / Eval pages asli API par; `benchmark.py`, `run_ablation.py`, `calibrate.py`, `safety.py` |

Algorithm decisions + evaluation numbers: **[docs/algorithm-notes.md](docs/algorithm-notes.md)** · PDF ke saath chapter-wise audit: **[docs/pdf-audit.md](docs/pdf-audit.md)** · Architecture: [docs/architecture-diagram.png](docs/architecture-diagram.png).

```bash
cd backend
pytest -q -p no:warnings                                  # 98 tests
python -m tests.eval_suite.worked_example                 # Ch 10 worked example, live pipeline
python -m tests.eval_suite.benchmark --scenarios 200      # planted-cause benchmark
python -m tests.eval_suite.run_ablation --scenarios 60
python -m tests.eval_suite.calibrate                      # benchmark ke baad
python -m tests.eval_suite.safety
python -m tests.eval_suite.run_golden                     # LLM key chahiye (100 NL->SQL questions)
```

LLM optional hai: key na ho to INVESTIGATE poori tarah deterministic chalta hai (rule-based question parse +
template narrative). Key ho to question parse fallback, extra hypotheses aur narrative LLM se — har number
grounding validator (F33) se check hota hai.
