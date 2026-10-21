"""Env settings (Ch 20.4). Root `.env` aur `backend/.env` dono padhe jaate hain."""
import json
from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    app_name: str = "AI QueryHub"
    environment: str = "dev"

    # database
    database_url: str = "sqlite:///./queryhub.db"
    readonly_database_url: str = "sqlite:///./queryhub.db"
    auto_migrate: bool = True                # startup par `alembic upgrade head`

    # cache / jobs
    redis_url: str = "redis://localhost:6379/0"

    # LLM
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    llm_temperature: float = 0.0

    # RAG
    chroma_path: str = "./chroma"
    schema_rag: str = "auto"                 # auto (chroma installed ho to) | chroma | lexical

    # auth
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    auth_disabled: bool = False              # sirf local testing: bina token ke "dev" admin user
    # Signup roles. ADMIN_EMAILS set ho to sirf ye emails admin bante hain (public deploy par "pehla signup admin"
    # wala rule band); baaki sabko DEFAULT_SIGNUP_ROLE. Khaali ho to purana rule: pehla user admin, baaki default.
    admin_emails: Annotated[list[str], NoDecode] = []
    default_signup_role: str = "analyst"
    # Supabase Auth (optional): set ho to Supabase ke access tokens bhi accept hote hain
    supabase_url: str = ""                   # https://<project>.supabase.co  (ES256/RS256 -> JWKS)
    supabase_jwt_secret: str = ""            # legacy HS256 projects ke liye
    # env me JSON list ya comma-separated: CORS_ORIGINS=https://a.onrender.com,http://localhost:5173
    cors_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]

    # monitoring (Ch 2.5): Sentry free tier — DSN set ho to errors report hote hain
    sentry_dsn: str = ""

    # datasources: conn_secret_ref sirf isi prefix wale env vars ko point kar sakta hai
    datasource_env_prefix: str = "DS_"

    # SQL firewall
    max_rows: int = 5000
    statement_timeout_ms: int = 5000
    max_plan_cost: float = 1_000_000.0

    # ASK / ANALYZE
    ask_max_retries: int = 1                 # SQL fail hone par LLM ko error ke saath 1 aur mauka
    llm_answer: bool = True                  # result ka 1-line answer LLM se (grounding check ke saath)

    # Q-TRACE+
    qtrace_max_llm_calls: int = 15
    qtrace_max_queries: int = 40
    qtrace_explained_target: float = 0.80
    qtrace_fdr_q: float = 0.10

    @field_validator("database_url", "readonly_database_url")
    @classmethod
    def _psycopg_driver(cls, v: str) -> str:
        """Supabase/Render `postgresql://...` dete hain; SQLAlchemy uske liye psycopg2 dhoondhta hai jo install
        nahi — isliye psycopg (v3) driver par map karo."""
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    @field_validator("admin_emails", mode="before")
    @classmethod
    def _split_emails(cls, v: object) -> object:
        if isinstance(v, str):
            return [e.strip().lower() for e in v.split(",") if e.strip()]
        return [str(e).strip().lower() for e in v] if isinstance(v, list) else v

    @field_validator("default_signup_role")
    @classmethod
    def _valid_role(cls, v: str) -> str:
        if v not in ("admin", "analyst", "viewer"):
            raise ValueError("DEFAULT_SIGNUP_ROLE must be admin | analyst | viewer")
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: object) -> object:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [o.strip().rstrip("/") for o in v.split(",") if o.strip()]
        return v


@lru_cache
def get_settings() -> Settings:
    return Settings()
