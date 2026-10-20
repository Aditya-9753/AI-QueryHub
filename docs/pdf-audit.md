# Blueprint v3.0 (Q-TRACE+) — chapter-wise audit

Status: ✅ = implemented + tested · 🟡 = implemented, lekin limited / alag tarike se (reason diya hai) · ❌ = nahi hai.
Last audit: 2026-10-18 · backend 98 tests · ruff clean · frontend build OK.

| Ch | Requirement | Status | Kahan / proof |
|---|---|---|---|
| 0 | Q-TRACE+ 10 steps V→Q→T→R→A→C→Ch→E→X→Rec | ✅ | `orchestrator/qtrace.py`; timeline me har phase (`test_qtrace_pipeline`, benchmark completion 100%) |
| 0.1 | audit_log, llm_calls + replay modes, priority vs evidence_score, benchmark early | ✅ | models/v3.py, replay.py |
| 1 | ASK / ANALYZE / INVESTIGATE modes, golden rule (numbers sirf SQL/maths se) | ✅ | grounding validator; benchmark grounding violations 0 |
| 2.1 | React+Vite, Tailwind, Zustand, TanStack, Recharts (waterfall), React Flow, Monaco | ✅ | frontend/ |
| 2.1 | Vercel/Netlify hosting | 🟡 | static build (`npm run build`) deploy-ready; hosting account user ka |
| 2.2 | FastAPI, SQLAlchemy+Alembic, Pydantic v2, scipy/statsmodels, sqlglot, Celery+Redis | ✅ | Redis down ho to background thread fallback |
| 2.3 | Postgres + `queryhub_ro`, SQLite, ChromaDB, storage watch-item | ✅ | schema.sql; raw rows store nahi hote (sirf aggregates + SHA-256) |
| 2.4 | Groq→Gemini→Ollama, Sentence-Transformers, Redis cache (prompt_hash, model), temp 0 | ✅ | llm/fallback.py, rag/retriever.py (`SCHEMA_RAG=auto`) |
| 2.5 | Supabase Auth / JWT / RBAC, CI, Docker, Sentry, UptimeRobot (`/health`) | ✅ | MFA Supabase dashboard ka setting hai |
| 5 | Router → do raaste → ek firewall → executor → record | ✅ | docs/architecture-diagram.png |
| 6.1 | Hypothesis object (saare fields + source/prior/priority/parent/depth) | ✅ | `_describe()`; test_hypothesis_fields_and_shapley |
| 6.2 | Evidence node: query_id, dataset version, schema snapshot, metric def, filters, window, duration, checksum, method, claim IDs | ✅ | evidence/provenance.py; test_provenance_and_dataset_version |
| 6.3 | Challenge runs alag store, original overwrite nahi | ✅ | challenges table + experiment_steps |
| 7.1 | 15 kamiyon ke fixes | ✅ | sab niche ke rows me |
| 8.2 | Data health (completeness, freshness, null, duplicates, volume) + anomaly gate (ETS / YoY < 24 mo) | ✅ | gate sigma me sampling SE jodha — docs/algorithm-notes.md §1 |
| 8.3 | QuestionSpec, per-day, controls (corr ≥ 0.8, size 0.5–2x) | ✅ | rule parser + LLM fallback |
| 8.4 | 4 sources + priors (0.5/0.4/0.4/0.3), grounding → UNGROUNDED | ✅ | |
| 8.5 | Priority = prior×ExpShare/Cost, stop rule, drill-down (EP + JS), stop_reason saved | ✅ | algorithm-notes §2–5 |
| 8.6 | Cross-check, reconciliation ±10%, Simpson, 7-check battery, user challenge | ✅ | |
| 8.7 | Labels, claim types, LLM ko sirf evidence JSON, regenerate ≤ 2 → strip | ✅ | |
| 8.9 | Budget ≤ 15 LLM / ≤ 40 queries | ✅ | avg 6.6 queries (benchmark) |
| 9 | F1–F33 | ✅ | unit tests; F5 Shapley cross-check `core.shapley`; F15 outlier check |
| 9.4 | Welch t / Mann-Whitney / trend-ETS (question patterns) | 🟡 | `analytics/statistics.py`, `forecasting.py` me functions + tests; Q-TRACE+ ke tests bootstrap/permutation/chi2 use karte hain (doc ki daily-data recommendation), isliye ye pipeline me wired nahi |
| 10 | Worked example numbers | ✅ | `python -m tests.eval_suite.worked_example` — 48.9/1.7/49.4%, −440/−48, DiD −0.086 |
| 11 | Saari tables + v3 columns + 6 nayi tables, Pydantic models | ✅ | 3 Alembic migrations |
| 11 | `metric_definitions` = semantic layer | ✅ | DB edits pipeline use karti hai (`load_semantic_layer`); formula firewall se validate |
| 12 | Folder tree | ✅ | saari files maujood; R step `orchestrator/data_access.py` me (planner.py preview helper hai) |
| 13 | Tested core code | ✅ | |
| 14 | Saare endpoints + 14.1 response shape | ✅ | test_doc_response_shape |
| 15 | 10 screens, claim-type badges, live timeline, decomposition view, alerts | ✅ | |
| 16 | 4 security layers, audit, secrets LLM se door, prompt injection quoting | ✅ | safety eval 25/25 blocked |
| 17 | Exact vs re-derive, temp 0, llm_calls, checksum, **as_of filter + max(updated_at)**, semantic version warning | ✅ | test_exact_replay…, test_metric_edit…_replay_warning |
| 18 | Benchmark metrics | 🟡 | ✅ Recall@k, attribution error, false alarm, calibration, grounding, safety, completion, evidence coverage, reproducibility, latency; ⏳ SQL execution accuracy + schema grounding + intent (LLM key chahiye — `run_golden.py`); ❌ Contradiction Detection / Challenge Success / Insufficient Precision ke liye seeded scenarios abhi nahi |
| 18.2 | Planted-cause generator, scenarios/ + ground_truth/ (expected share) | ✅ | 50 scenarios disk par, benchmark 200 |
| 18.3 | Ablation | 🟡 | −Verify, −Normalization, −Decomposition, −FDR, −Challenge ✅; Baseline (LLM Text-to-SQL) aur LLM-only scoring LLM key ke bina n/a |
| 19 | Roadmap phases | ✅ | README |
| 20 | Setup, requirements, .env.example, docker-compose | 🟡 | `docker compose config` valid; images build Docker Desktop band hone se verify nahi hue |
| 21 | Demo flow 1–8, what-not-to-claim | 🟡 | steps 2–8 bina LLM chalte hain; step 1 (NL→SQL) ke liye key |
| 12 | seed_data: Chinook / Northwind | ❌ | sirf synthetic e-commerce seed; public datasets optional |
| — | Scheduled reports (Celery beat) | ❌ | `reports.py` TODO; 5-phase plan me nahi |

Evaluation numbers aur algorithm decisions: [algorithm-notes.md](algorithm-notes.md).
