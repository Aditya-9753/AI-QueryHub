"""Challenge ke liye counter-queries (semantic layer se)."""
from app.services.rag.semantic_layer import SemanticLayer, month_bounds, shift_period
from app.services.verify.data_health import health_queries


def shift_year(period: str, years: int = -1) -> str:
    return shift_period(period, 12 * years)


def seasonality_queries(layer: SemanticLayer, metric: str, filters: dict, period_base: str,
                        period_current: str) -> dict[str, str]:
    """Last year same months ka per-day series."""
    out = {}
    for label, period in (("ly_base", shift_year(period_base)), ("ly_current", shift_year(period_current))):
        start, end = month_bounds(period)
        out[label] = layer.render(metric, filters=filters, start=start, end=end, per_day=True)
    return out


def segment_health_queries(layer: SemanticLayer, metric: str, filters: dict, period: str) -> dict[str, str]:
    start, end = month_bounds(period)
    return health_queries(layer.get(metric), start, end, filters)
