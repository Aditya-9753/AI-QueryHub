# Q-TRACE+ — implementation notes (blueprint v3.0 se kahan aur kyun alag)

Blueprint ke saare formulas (F1–F33) jaise ke taise implement hain aur unit tests me doc ke numbers se match
karte hain. Jahan doc ka rule *ambiguous* tha ya synthetic benchmark par galat result de raha tha, wahan neeche
diye gaye decisions liye gaye. Har decision ke saath woh evidence hai jisne use justify kiya.

Code: `backend/app/services/orchestrator/qtrace.py` (pipeline), `analytics/` (formulas), `evidence/`, `challenge/`.

## 1. Anomaly gate ka sigma (F9)

| | Noise-only scenarios par false alarm |
|---|---|
| Doc: `sigma = std(ETS residuals)` (25–36 monthly points) | **11–22%** (nominal 5% hona chahiye) |
| v3 impl: `sigma^2 = resid_sd^2 + SE(current month per-day mean)^2` | **4–5%** |
| YoY gate (history < 24 months): `z = (ln this-yr change - ln last-yr change) / SE` | **1%** |

Forecast error = model error + "actual" month ka apna sampling noise. In-sample residuals chhoti history par
overfit hote hain. (Experiment script: 40 seeds x 2 cities, `tests/eval_suite/generator.py` data.)

## 2. Top-level metric-tree factors hamesha test hote hain

Doc F28 "explained >= 80% to ruko" ko seedha lagane par calendar (53%) + AOV (30%) ke baad hi loop ruk gaya aur
orders/day test hi nahi hua. Top-level factors F2 decomposition ka hissa hain (shares ka sum 100%),
**0 extra query** lagti hai, isliye ye hamesha test hote hain; stop rule templates / LLM extras par lagta hai.

## 3. Stop rule me "explained" calendar hata kar

Har Feb-vs-Jan sawaal me calendar akela 50–90% "explain" kar deta hai (pure arithmetic: 28 vs 31 din).
Stop rule ke liye `explained_per_day = sum(non-calendar supported shares) / (1 - calendar share)`.
Report me doc wala total `explained` aur `residual = 1 - explained` hi dikhta hai.
Worked example: (44.5% + 4.9%) / 51.1% = 97% — doc ke result par koi asar nahi.

## 4. Drill-down: sirf share se (significance shart nahi)

Doc 8.5: "share > 30% aur depth < 2". Pehli implementation me maine "parent supported ho" bhi joda tha —
benchmark me cancellation spikes miss hue: orders/day ka daily bootstrap low-power hai (CI +-6%), jabki uska
child (cancel rate, chi-square on counts) bahut powerful hai (p ~ 1e-34). Shart hatane par Recall@3
(detected) **15% -> 62%**. Share threshold calendar hata kar (`share / (1 - calendar)`) lagta hai.

## 5. AOV drill-down ka dimension = jahan mix effect sabse zyada

Revenue-delta par EP (Adtributor) ne `channel` chuna (EP 1.24 > category 1.08) aur nateeja aaya "app channel ka
AOV gira" — jabki planted cause category mix tha. AOV ko todne ka sawaal hi "composition ya rate?" hai, isliye
dimension = max `mix / Delta-A` (>= 0.5); koi dimension mix-dominant na ho to EP + JS (F29) fallback.

## 6. Seasonality challenge finding-level par

Battery ka seasonality check metric-level YoY se karne par cancellation finding galat tarike se OVERTURNED hui.
Ab har finding apne factor ka last-year change compare karti hai (cancel rate ka delta, segment share ka delta,
orders/day ka log change), apne standard error ke saath: survive if `|excess| >= 1.96 * SE`.

## 7. Doc 8.4 "Drill-down" source: dimension concentration hypotheses

T step par har (unfiltered) dimension ke liye hypothesis: "change kisi ek segment me concentrated hai".
- Concentration = `contribution - baseline size` (bada segment uniform change me bhi bada contribution deta hai).
- Test: `segment per-day change - total per-day change` (7-day block bootstrap CI) + composition chi-square + BH.
- Share: model `dR_seg = shock + size * dR_common` se `shock share = excess / (1 - size)`.
Ye tab bhi planted segment pakadta hai jab AOV/orders factors underpowered hon (benchmark: localization 83%).

## 8. Parallel-trends check = pre-period slope test

`mean |growth_T - growth_C|` noise level (~3%) par hi fail ho raha tha. Ab pre-period `ln(T) - ln(C)` par
linear regression: slope significant (p < 0.05) aur > 0.5%/month ho tabhi "not parallel" (CP 0.3).

## 9. Kuch defaults jo doc me open the

| Parameter | Value | Kyun |
|---|---|---|
| MDE (relative effects) | 10% | per-day / AOV change jo business ke liye matter kare |
| MDE (shares) | 5 pts | doc example: Electronics 2,160 orders -> SA = 1.0 isi se aata hai |
| MDE (cancel rate) | 2 pts | |
| Bootstrap | 7-day blocks, B = 2000, seed = crc32(hypothesis id) | re-derive deterministic |
| Freshness | data period ke aakhri din tak | doc "period end + lag" ko lag = -1 day |
| Controls | corr >= 0.8, size 0.5–2x (doc), filter dimension ke doosre values | |

## 10. Evaluation (asli runs, `tests/eval_suite/`)

200 planted-cause scenarios (`benchmark.py`), 60 for ablation, LLM ke bina (deterministic pipeline):

| Metric | Full |
|---|---|
| False alarm (noise-only) | 0% |
| Data-issue detection (missing days) | 100% |
| Recall@3 (gate fired) | 86% |
| Planted segment localized | 83% |
| Attribution error (F32) | 0.107 |
| Brier / ECE (F31) | 0.085 / 0.121 |
| Grounding violations (F33) | 0 |
| Investigation completion / Evidence coverage / Reproducibility | 100% / 100% / 100% |
| Detection (gate fired on planted) | 51% |

Detection 51% gate ki statistical power limit hai: chhote planted effects (e.g. cancel 5% -> 8%, ya kam AOV
wali category) monthly per-day noise ke andar hote hain — ye design se hai (noise ka peecha nahi karna).

Ablation (60 scenarios): -Normalization attribution error 0.088 -> 1.18; -Verify false alarm 0 -> 6.7% aur
data-issue detection 100% -> 0%; -FDR false findings 0 -> 0.033; -Decomposition / -Challenge ka is data par
measurable asar nahi.

Calibration (F30): fitted weights sirf SS aur ES ko weight dete hain, lekin 5-fold CV Brier equal weights se
behtar nahi (0.0886 vs 0.0852) — isliye `WEIGHTS` equal rakhe gaye.

Known limitation: FDR q = 0.10 ka matlab ~10% discoveries galat ho sakti hain. Demo DB me "app channel share
60.9% -> 57.0%" aisi hi ek ~3 sigma random fluctuation hai jo statistically significant hai — isliye UI har
finding ko *association* bolta hai aur challenge / human review ka option deta hai.
