# Parameter decision record

Auditable record of how the unit-construction parameters were chosen. Written
at the point of decision, not reconstructed afterwards.

**Every number here was produced by `python -m src.data.units --sweep` before
any classifier existed. No model performance was visible at selection time,
and none had been computed.**

---

## Final parameters

```yaml
min_topic_tweets:  50
lead_minutes:      60
window_minutes:    90
min_window_tweets: 15
feature_language:  es
```

**Yield: 129 units — 42 trending / 87 non-trending. Positive prevalence 0.326.**

Clears the pre-registered floor (≥120 total, ≥40 per class).

---

## The constraint that drove everything

**Negatives are the binding constraint, not positives.** Inside the usable
16:00–23:59 band there are 76,705 candidate non-trending hashtags, but almost
all are tiny: only 431 reach 50 tweets, 174 reach 100, and 103 reach 150. The
trending pool is comparatively healthy (240 / 199 / 182 at the same
thresholds).

Every parameter below is a negotiation against that ceiling.

---

## Level 1 — attempted, and why it failed

The preferred setting keeps the strict pre-peak window: **60-minute lead,
60-minute window, ≥100 tweets per topic, ≥20 tweets in the window.**

| | positives | negatives | total |
|---|---|---|---|
| Level 1 as specified | 44 | 44 | **88** |

**88 units against a floor of 120.** Both classes cleared 40, but the total did
not. Level 1 is not viable.

The attrition is not evenly distributed. At that setting the left-censoring
filter alone removed 109 positives — see "asymmetry" in `FINDINGS.md`.

---

## The grid considered

Swept `min_topic_tweets × lead × window` (36 cells, full results in
`units_sweep.json`), with and without the tweet-level language filter. The
lead-60 rows are the ones that preserve the claim:

| min | lead | win | pos/neg (es features) | no filter | total |
|---|---|---|---|---|---|
| 50 | 60 | 60 | 38 / 44 | 44 / 44 | 82 |
| **50** | **60** | **90** | **39 / 63** | 46 / 65 | 102 |
| 100 | 60 | 90 | 39 / 51 | 46 / 53 | 90 |
| 150 | 60 | 90 | 39 / 34 | 45 / 35 | 73 |

Shortening the lead instead reaches the floor comfortably:

| min | lead | win | pos/neg | total |
|---|---|---|---|---|
| 50 | 30 | 90 | 56 / 93 | **149** |
| 100 | 30 | 90 | 53 / 75 | **128** |

And lengthening it collapses the sample:

| min | lead | win | pos/neg | total |
|---|---|---|---|---|
| 50 | 120 | 90 | 31 / 38 | 69 |
| 50 | 180 | 90 | 20 / 23 | 43 |

---

## What was chosen, and why

**Contingency level 2, taken in the widen-the-window direction rather than the
shorten-the-lead direction.**

A 30-minute lead reaches 149 units. It was rejected. **Lead time is the
contribution being tested** — the project claims prediction 1–3 hours before
peak, and buying statistical comfort by dropping to 30 minutes surrenders the
thing under test. 129 units at a genuine 1-hour lead is worth more than 149 at
30 minutes.

`min_topic_tweets` moved 100 → 50 because at 100 the total caps at 112 for a
60-minute lead — below the floor regardless of any other choice. This widens
the negative pool from 174 to 431 candidates before censoring.

The full lead sweep (30 / 60 / 120 / 180) still runs at evaluation as the
**lead-time curve**, which is the evidence for H2. n shrinks and confidence
intervals widen at the longer leads; that is reported, not hidden.

---

## The one tuned parameter

`min_window_tweets` was relaxed from 20 to 15. This is the only parameter that
was tuned to reach the floor, and it is declared as such.

At min 50 / lead 60 / window 90:

| `min_window_tweets` | positives | negatives | total | floor |
|---|---|---|---|---|
| 10 | 46 | 135 | 181 | clears |
| **15** | **42** | **87** | **129** | **clears** |
| 20 | 39 | 63 | 102 | below |
| 25 | 37 | 42 | 79 | below |

15 was chosen over 10 because 10 admits interaction graphs too sparse to carry
meaningful structure — the network channel needs enough edges to compute
clustering, reciprocity and community structure at all. Sensitivity across
15 / 20 / 25 is reported at evaluation.

**Provenance:** selected on the unit counts in this table. At the time of
selection `src/models/` and `src/eval/` were empty and no classifier had been
run against these units.

---

## Language control

Topic-level language matching — the control originally specified — is
impossible here: **zero English-dominant negative topics in all 24 settings
swept.** Substituted with tweet-level filtering (units defined on all activity,
window features counted on Spanish tweets only).

Cost at the final setting: **6 positives and 6 negatives** fall below the
window threshold on Spanish alone (48/93 → 42/87).

The cost is asymmetric in principle but small in practice on the negative side,
because the non-trending pool was already ~89% Spanish — the filter removes
almost nothing there, while it genuinely thins the multilingual positive pool.

Route 1 (restricting to Spanish-majority *topics*) yields 18 positives / 87
negatives at this setting. **That is a descriptive robustness check only, not a
second model** — 18 positives cannot support the significance testing, and it
is reported as such rather than as a suppressed arm.

---

## Attrition at the final setting

| Stage | Trending | Non-trending |
|---|---|---|
| topics on grid | 322 | 76,705 |
| − too_small | −82 → 240 | −76,274 → 431 |
| − left_censored | −132 → 108 | −1 → 430 |
| − right_censored_no_tail | −9 → 99 | −41 → 389 |
| − right_censored_no_decay | −4 → 95 | −12 → 377 |
| − window_before_band_start | −20 → 75 | −169 → 208 |
| − window_too_sparse | −33 → **42** | −121 → **87** |

---

## Floor status

**Cleared.** 129 ≥ 120, and 42 / 87 both ≥ 40.

The margin is thin and the positive class sits 2 above its minimum. Evaluation
therefore treats bootstrap confidence intervals as the primary uncertainty
statement, prefers permutation tests over parametric ones, and states
explicitly that effects below a certain size are undetectable at this n.
