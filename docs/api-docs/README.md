# API docs

Live OpenAPI docs: `http://localhost:8000/docs` (FastAPI auto-generated).

| Method + path | Kaam |
|---|---|
| POST /api/query | ASK / ANALYZE: question (+ dev ke liye `sql`) → firewall → result |
| POST /api/experiments | Naya investigation |
| POST /api/experiments/{id}/run | Q-TRACE+ run (Celery) |
| GET /api/experiments/{id} | Status + summary |
| GET /api/experiments/{id}/timeline | experiment_steps |
| POST /api/hypotheses/generate | Deterministic hypotheses preview |
| GET /api/experiments/{id}/hypotheses | Hypothesis tree |
| POST /api/hypotheses/{id}/approve | Ungrounded LLM idea approve |
| GET /api/experiments/{id}/decomposition | Waterfall data |
| GET /api/findings/{id}/evidence | Evidence graph |
| POST /api/challenges | Custom challenge |
| GET /api/findings/{id}/challenges | Battery + user challenges |
| POST /api/experiments/{id}/replay | exact / rederive |
| GET /api/experiments/{id}/export | JSON export |
| GET/POST /api/metrics | Semantic layer |
| GET /api/admin/audit | Audit log (admin) |
