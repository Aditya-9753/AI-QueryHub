"""Step X (deterministic part): evidence se claims banana. Har sentence ka type (fact / association /
interpretation / recommendation) aur evidence_node_ids. Numbers report ki values se format hote hain,
isliye grounding by construction pass hota hai (phir bhi validator chalta hai)."""
from app.schemas.qtrace import SUPPORTED_LIKE, Claim, HypStatus
from app.services.evidence.grounding_validator import numbers_in

LABELS = {
    "days": "Calendar (din ka farq)", "orders_per_day": "Orders per day", "orders": "Total orders", "aov": "AOV",
    "placed_orders": "Placed orders", "cancel_rate": "Cancellation rate", "category_mix": "Mix shift",
    "segment_aov": "Within-segment AOV (rate)", "seasonality": "Seasonality", "data_issue": "Data issue",
    "concurrent_event": "Market-wide change", "price_change": "Price change",
}


def label_of(key: str) -> str:
    if ">" in key:
        dim, seg = key.split(">", 1)[1].split("=", 1)
        return f"'{seg}' ({dim})"
    return LABELS.get(key.split(".", 1)[-1], key)


def money(v: float, unit: str) -> str:
    if unit != "inr":
        return f"{v:,.0f}" if abs(v) >= 100 else f"{v:,.2f}"
    a = abs(v)
    sign = "-" if v < 0 else ""
    if a >= 1e7:
        return f"{sign}₹{a / 1e7:.2f} Cr"
    if a >= 1e5:
        return f"{sign}₹{a / 1e5:.2f} L"
    return f"{sign}₹{a:,.0f}"


def pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _flt(spec) -> str:
    return " ".join(spec.filters.values())


def build_claims(r, graph, cfg) -> list[Claim]:
    spec = r.spec
    m = spec.metric
    claims: list[Claim] = []
    if r.status == "data_issue":
        failed = [c for c in r.verify["health"]["checks"] if not c["passed"] and c["severity"] == "error"]
        detail = "; ".join(f"{c['check_name']} {c['observed']} (expected {c['expected']})" for c in failed)
        claims.append(Claim(sentence=f"Data health check fail hua: {detail}. Pehle data theek karo — investigation "
                                     "nahi chalayi.", claim_type="fact", evidence_node_ids=["N-verify"]))
        return claims
    gate = r.verify["gate"]
    unit = gate.get("unit", "count")
    if r.status == "within_normal":
        if gate["method"] == "ets":
            band = gate["band"]
            s = (f"{m} {_flt(spec)} {spec.period_current}: per-day {money(gate['actual'], unit)} expected band "
                 f"{money(band['low'], unit)} se {money(band['high'], unit)} ke andar hai (z = {gate['z']:.2f}) — "
                 "normal fluctuation, investigation ki zaroorat nahi.")
        else:
            s = (f"{m} {_flt(spec)} {spec.period_current}: change pichhle saal ke pattern jaisa hai "
                 f"(YoY z = {gate['z']:.2f}) — normal fluctuation, investigation ki zaroorat nahi.")
        claims.append(Claim(sentence=s, claim_type="fact", evidence_node_ids=["N-verify"]))
        return claims
    if r.status != "completed":
        claims.append(Claim(sentence=f"{spec.period_base} aur {spec.period_current} me {m} me koi change nahi.",
                            claim_type="fact", evidence_node_ids=["N-verify"]))
        return claims

    c = r.core
    direction = "gira" if c["rel_change"] < 0 else "badha"
    claims.append(Claim(
        sentence=(f"{m} {_flt(spec)} {spec.period_current} me {spec.period_base} ke mukable {pct(abs(c['rel_change']))} "
                  f"{direction} ({money(c['T0'], unit)} se {money(c['T1'], unit)})."),
        claim_type="fact", evidence_node_ids=["N-total"]))
    if cfg.per_day:
        claims.append(Claim(
            sentence=(f"Per-day basis par change {pct(c['per_day_change'])} hai ({c['days0']} vs {c['days1']} din); "
                      f"gate z = {gate['z']:.2f} ({gate['method']})."),
            claim_type="fact", evidence_node_ids=["N-total", "N-verify"]))

    by_key = {f.hypothesis_id: f for f in r.findings}
    supported = sorted([by_key[k] for k in r.frontier if by_key[k].status in SUPPORTED_LIKE],
                       key=lambda f: -f.share_of_delta)
    for f in supported:
        key = f.hypothesis_id.split(".", 1)[-1]
        verdict = f" Challenge battery: {f.status.value.upper()}." if f.challenges else ""
        lab = f" Evidence: {f.label}." if f.label else ""
        if key == "days":
            s = (f"Calendar: {f.data['d0']} vs {f.data['d1']} din — isne change ka {pct(f.share_of_delta)} "
                 f"explain kiya ({money(f.amount, unit)}).")
            ctype = "fact"
        elif key == "category_mix":
            top = next(s for s in f.data["segments"] if s["segment"] == f.data["top_segment"])
            s = (f"{f.data['dimension'].title()} mix shift: '{top['segment']}' ka order share {pct(top['s0'])} se "
                 f"{pct(top['s1'])} hua; ye change ka {pct(f.share_of_delta)} hai ({money(f.amount, unit)}).")
            ctype = "association"
        else:
            s = (f"{label_of(f.hypothesis_id)}: {pct(f.effect)} change; total change ka {pct(f.share_of_delta)} "
                 f"({money(f.amount, unit)}).")
            ctype = "association"
        claims.append(Claim(sentence=s + lab + verdict, claim_type=ctype, evidence_node_ids=[f"F:{f.hypothesis_id}"],
                            finding_key=f.hypothesis_id))
    segs = [f for f in r.findings if f.source == "drilldown" and f.status in SUPPORTED_LIKE]
    for f in sorted(segs, key=lambda f: -f.share_of_delta)[:2]:
        claims.append(Claim(sentence=f"{f.statement} (change ka {pct(f.share_of_delta)}).", claim_type="association",
                            evidence_node_ids=[f"F:{f.hypothesis_id}"], finding_key=f.hypothesis_id))
    conc = by_key.get("tpl.concurrent_event")
    if conc is not None and conc.data.get("did") is not None:
        d = conc.data
        lo, hi = d["did_ci"]
        where = "segment-specific lagta hai" if not (lo <= 0 <= hi) else "market-wide ho sakta hai"
        claims.append(Claim(
            sentence=(f"Controls ({', '.join(d['controls'])}) me per-day change {pct(d['control_change'])}; "
                      f"log DiD {d['did']:.3f} — effect {where}."),
            claim_type="association", evidence_node_ids=["F:tpl.concurrent_event"], finding_key="tpl.concurrent_event"))
    if supported:
        top = supported[0] if supported[0].hypothesis_id.split(".", 1)[-1] != "days" or len(supported) == 1 \
            else supported[1]
        claims.append(Claim(
            sentence=(f"Yeh association hai, causation nahi — {label_of(top.hypothesis_id)} kyun hua (stock, "
                      "campaign, competitor, pricing), iske liye extra data chahiye."),
            claim_type="interpretation", evidence_node_ids=[f"F:{top.hypothesis_id}"], finding_key=top.hypothesis_id))
        claims.append(Claim(
            sentence=f"Next step: {label_of(top.hypothesis_id)} ke peeche ka operational data (inventory, pricing, "
                     "campaigns) check karein.",
            claim_type="recommendation", evidence_node_ids=[f"F:{top.hypothesis_id}"], finding_key=top.hypothesis_id))
    rejected = [f for f in r.findings if f.status in (HypStatus.REJECTED, HypStatus.OVERTURNED)
                and f.source != "drilldown"]
    if rejected:
        claims.append(Claim(sentence="Rejected: " + ", ".join(label_of(f.hypothesis_id) for f in rejected) + ".",
                            claim_type="fact", evidence_node_ids=[f"F:{f.hypothesis_id}" for f in rejected]))
    untested = [h for h in r.hypotheses if h.status == HypStatus.NOT_TESTED]
    if untested:
        claims.append(Claim(sentence=f"Test nahi hue (stop rule: {r.stop_reason}): "
                                     + ", ".join(label_of(h.id) for h in untested) + ".",
                            claim_type="fact", evidence_node_ids=["N-total"]))
    claims.append(Claim(sentence=f"Explained {pct(r.explained)}, unexplained residual {pct(r.residual_share)}.",
                        claim_type="fact", evidence_node_ids=["N-total"]))
    return claims


def _walk(o, out: list[float]) -> None:
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        out.append(float(o))
    elif isinstance(o, str):
        out.extend(numbers_in(o))
    elif isinstance(o, dict):
        for v in o.values():
            _walk(v, out)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _walk(v, out)


def evidence_values(r, graph) -> list[float]:
    """Narrative ke har number ka in values (ya inke lakh/crore scale) se match hona zaroori hai."""
    raw: list[float] = []
    _walk(r.spec.model_dump(), raw)
    _walk(r.verify, raw)
    _walk(r.core, raw)
    _walk(r.decomposition, raw)
    for f in r.findings:
        _walk(f.model_dump(mode="json"), raw)
    for n in graph.nodes.values():
        _walk(n.data, raw)
    _walk([r.stop_reason, r.explained, r.residual_share], raw)
    out = []
    for v in raw:
        out += [v, v / 1e3, v / 1e5, v / 1e7]
    return out
