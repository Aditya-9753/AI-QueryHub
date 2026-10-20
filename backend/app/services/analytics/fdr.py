"""F19: Benjamini-Hochberg FDR (Ch 9.5, code Ch 13.4)."""


def benjamini_hochberg(pvalues: dict, q: float = 0.10) -> dict:
    """Returns {hypothesis_id: (q_value, significant)}.
    Controls the expected share of false discoveries at q."""
    items = sorted(pvalues.items(), key=lambda kv: kv[1])
    m = len(items)
    # largest k with p_(k) <= k/m * q
    k_max = 0
    for k, (_, p) in enumerate(items, start=1):
        if p <= k / m * q:
            k_max = k
    # adjusted q-values (monotone from the end)
    qvals, running = {}, 1.0
    for k in range(m, 0, -1):
        hid, p = items[k - 1]
        running = min(running, p * m / k)
        qvals[hid] = running
    return {hid: (qvals[hid], rank <= k_max)
            for rank, (hid, _) in enumerate(items, start=1)}
