# AI QueryHub — PRD (short)

**Problem:** Text-to-SQL tools number de dete hain, lekin "kyun?" wale sawaal par galat ya unverified
explanation dete hain.

**Product:** ₹0-budget NL→SQL tool + AI Data Experiment Engine (Q-TRACE+).

| Mode | Example |
|---|---|
| ASK | "Feb me Delhi ka revenue kitna tha?" |
| ANALYZE | "Delhi revenue category-wise, Jan vs Feb" |
| INVESTIGATE | "Feb me Delhi revenue kyun gira?" |

**Golden rule:** LLM sirf orchestrate aur explain karta hai; har number SQL + scipy/statsmodels se aata hai,
aur numeric grounding validator isse prove karta hai.

**Success metrics:** Ch 18 (SQL accuracy, Recall@k, attribution error, calibration, grounding violations = 0).

Detailed design: `AI_QueryHub_Master_Blueprint_v3_QTRACE_Plus.pdf`.
