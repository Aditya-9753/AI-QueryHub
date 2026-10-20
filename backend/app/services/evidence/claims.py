"""Narrative claims: har sentence ek claim, provenance (evidence_node_ids) zaroori; numbers grounded."""
from collections.abc import Callable

from app.schemas.qtrace import Claim
from app.services.evidence.grounding_validator import numeric_grounding_ok, strip_ungrounded

MAX_REGENERATE = 2


def validate_claims(claims: list[Claim]) -> list[str]:
    return [f"claim without evidence: {c.sentence!r}" for c in claims if not c.evidence_node_ids]


def claims_grounded(claims: list[Claim], evidence_values: list[float]) -> tuple[bool, list[float]]:
    return numeric_grounding_ok(" ".join(c.sentence for c in claims), evidence_values)


def regenerate_or_strip(claims: list[Claim], evidence_values: list[float],
                        regenerate: Callable[[list[Claim], list[float]], list[Claim]] | None = None,
                        max_retries: int = MAX_REGENERATE) -> list[Claim]:
    """Fail -> regenerate (max 2) -> phir ungrounded numbers hata kar 'see evidence table'."""
    claims = [c for c in claims if c.evidence_node_ids]
    ok, bad = claims_grounded(claims, evidence_values)
    attempts = 0
    while not ok and regenerate is not None and attempts < max_retries:
        claims = [c for c in regenerate(claims, bad) if c.evidence_node_ids]
        ok, bad = claims_grounded(claims, evidence_values)
        attempts += 1
    if ok:
        return claims
    return [c.model_copy(update={"sentence": strip_ungrounded(c.sentence, evidence_values)}) for c in claims]
