"""Evidence node kya store karta hai (Ch 6.2): query_id, dataset id + version, schema snapshot,
metric definition, filters, time window, execution time, result checksum, analysis method, linked claim IDs."""


def build_provenance(record, *, dataset_version: str | None, schema_snapshot: str | None,
                     method: str | None = None) -> dict:
    """record: orchestrator.data_access.QueryRecord. claim_ids explain step ke baad jodte hain."""
    return {
        "query_id": record.id,
        "purpose": record.purpose,
        "table": record.table,
        "dataset_version": dataset_version,
        "schema_snapshot": schema_snapshot,
        "metric": record.metric,
        "metric_definition": record.metric_definition,
        "filters": record.filters,
        "time_window": record.time_window,
        "group_by": record.group_by,
        "sql": record.sql,
        "sql_hash": record.sql_hash,
        "duration_ms": record.duration_ms,
        "row_count": record.row_count,
        "checksum": record.checksum,
        "analysis_method": method or record.purpose.split(":")[0],
        "hypothesis": record.hypothesis_key,
    }
