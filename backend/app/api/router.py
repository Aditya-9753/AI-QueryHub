from fastapi import APIRouter

from app.api.routes import (
    admin,
    auth,
    challenges,
    datasource,
    eval,
    evidence,
    experiments,
    hypotheses,
    llm,
    metrics,
    query,
    reports,
    saved_queries,
    schema,
)

api_router = APIRouter()
for module in (query, saved_queries, auth, datasource, schema, reports, experiments, hypotheses, challenges,
               evidence, metrics, eval, llm, admin):
    api_router.include_router(module.router)
