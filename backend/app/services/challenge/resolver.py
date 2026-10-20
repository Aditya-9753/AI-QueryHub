"""Challenge results -> UPHELD / REVISED / OVERTURNED."""
from app.services.challenge.battery import ChallengeResult

# In checks ka fail hona finding ko galat nahi, sirf uski wording/type badalta hai
REVISABLE = {"simpson", "alternative_segment", "market_wide"}


def resolve(results: list[ChallengeResult]) -> str:
    failed = {r.type for r in results if not r.passed}
    if not failed:
        return "upheld"
    if failed <= REVISABLE:
        return "revised"
    return "overturned"


def contradiction_penalty(results: list[ChallengeResult]) -> float:
    """CP = unresolved contradictions ki max severity: 0 / 0.3 minor / 0.6 major / 1 decisive."""
    verdict = resolve(results)
    return {"upheld": 0.0, "revised": 0.3, "overturned": 0.6}[verdict]
