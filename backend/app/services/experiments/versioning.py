"""Dataset / semantic layer / model versions — replay ke liye (Ch 17)."""
import hashlib
from datetime import datetime


def dataset_version(as_of: datetime, data_through: str | None) -> str:
    return f"asof={as_of.isoformat(timespec='seconds')}|data_through={data_through or 'unknown'}"


def model_version(llm_calls: list) -> str:
    models = sorted({getattr(resp, "model", "?") for _, _, resp in llm_calls})
    return ",".join(models) if models else "deterministic (no LLM)"


def schema_snapshot_hash(schema: list[dict]) -> str:
    blob = "|".join(f"{t['table']}:{','.join(c['name'] for c in t['columns'])}"
                    for t in sorted(schema, key=lambda t: t["table"]))
    return hashlib.sha256(blob.encode()).hexdigest()[:16]
