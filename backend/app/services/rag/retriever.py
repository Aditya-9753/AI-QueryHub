"""Question -> relevant tables (Schema RAG).

Default: lexical ranking (zero dependency). `SCHEMA_RAG=chroma` + `pip install -r requirements-rag.txt`
par ChromaDB + sentence-transformers. Chhoti schema (<= 8 tables) me saari tables bhej do.
"""
import re

from app.core.config import get_settings

SMALL_SCHEMA = 8
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(s: str) -> set[str]:
    return set(_TOKEN.findall(s.lower()))


def lexical_rank(question: str, docs: dict[str, str], k: int) -> list[str]:
    q = _tokens(question)
    return sorted(docs, key=lambda name: (-len(q & _tokens(name + " " + docs[name])), name))[:k]


def _chroma_rank(question: str, docs: dict[str, str], k: int) -> list[str]:
    from app.services.rag.schema_indexer import get_collection

    col = get_collection()
    col.upsert(ids=list(docs), documents=list(docs.values()), metadatas=[{"table": t} for t in docs])
    res = col.query(query_texts=[question], n_results=min(k, len(docs)))
    return [m["table"] for m in res["metadatas"][0]]


def retrieve(question: str, docs: dict[str, str], k: int = 6) -> list[str]:
    """docs: {table_name: table document}. Returns chosen table names."""
    if len(docs) <= SMALL_SCHEMA:
        return list(docs)
    mode = get_settings().schema_rag
    if mode in ("auto", "chroma"):
        try:
            return _chroma_rank(question, docs, k)
        except Exception:  # chromadb / sentence-transformers installed nahi ya model load fail
            if mode == "chroma":
                raise
    return lexical_rank(question, docs, k)
