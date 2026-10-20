"""Schema -> ChromaDB index (Schema RAG). Optional deps: pip install -r requirements-rag.txt"""
from sqlalchemy import inspect
from sqlalchemy.engine import Engine

from app.core.config import get_settings

COLLECTION = "schema"
EMBED_MODEL = "all-MiniLM-L6-v2"


def describe_schema(engine: Engine, include: set[str] | None = None) -> list[dict]:
    insp = inspect(engine)
    out = []
    for table in insp.get_table_names():
        if include and table not in include:
            continue
        cols = [{"name": c["name"], "type": str(c["type"])} for c in insp.get_columns(table)]
        out.append({"table": table, "columns": cols})
    return out


def table_document(t: dict) -> str:
    cols = ", ".join(f"{c['name']} ({c['type']})" for c in t["columns"])
    return f"table {t['table']}: {cols}"


def get_collection(path: str | None = None):
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    client = chromadb.PersistentClient(path=path or get_settings().chroma_path)
    return client.get_or_create_collection(
        COLLECTION, embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL))


def index_schema(engine: Engine, include: set[str] | None = None) -> int:
    schema = describe_schema(engine, include)
    col = get_collection()
    col.upsert(ids=[t["table"] for t in schema],
               documents=[table_document(t) for t in schema],
               metadatas=[{"table": t["table"]} for t in schema])
    return len(schema)
