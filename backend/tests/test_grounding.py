from app.schemas.qtrace import Claim
from app.services.evidence.claims import regenerate_or_strip, validate_claims
from app.services.evidence.grounding_validator import numeric_grounding_ok, strip_ungrounded

EVIDENCE = [-0.188, 0.489, 0.445, 0.101, 30, 24]


def test_grounded_narrative_passes():
    ok, bad = numeric_grounding_ok("Revenue fell 18.8% ... 48.9% ... 44.5%", EVIDENCE)
    assert ok and bad == []


def test_invented_number_fails():
    assert numeric_grounding_ok("Revenue fell 25%.", EVIDENCE) == (False, [25.0])


def test_strip_ungrounded():
    assert strip_ungrounded("fell 18.8%, maybe 25%", EVIDENCE) == "fell 18.8%, maybe [see evidence table]%"


def test_claims_need_evidence():
    claims = [Claim(sentence="x", claim_type="fact", evidence_node_ids=[])]
    assert validate_claims(claims)


def test_regenerate_then_strip():
    bad = [Claim(sentence="Revenue fell 25%.", claim_type="fact", evidence_node_ids=["N1"])]
    fixed = [Claim(sentence="Revenue fell 18.8%.", claim_type="fact", evidence_node_ids=["N1"])]
    assert regenerate_or_strip(bad, EVIDENCE, regenerate=lambda c, b: fixed)[0].sentence == "Revenue fell 18.8%."
    out = regenerate_or_strip(bad, EVIDENCE, regenerate=None)
    assert "25" not in out[0].sentence
