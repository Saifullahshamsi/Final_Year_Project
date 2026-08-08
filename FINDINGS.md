# Findings and corrections

A dated record of what the data turned out to be, what broke against it, and
what was changed as a result. Negative results and self-corrections are kept
here deliberately — they are part of the work, not a tidy-up list.

Every number below traces to a script in this repository. Nothing is estimated.

---

## 2026-08-08 — Corpus verification

Streamed both files and checked every claim previously recorded about them.

**Confirmed:** 1,275,917 trending rows; 1,090,280 non-trending rows; English
557,748 / Spanish 361,269 in the trending pool; 88.8% Spanish in the
non-trending pool; 13.2% hashtag coverage; 84,625 distinct hashtags.

**Corrected:**

| Claim | Verified | 
|---|---|
| 323 distinct trends | **322** |
| malformed rows: `trend` holding a URL, `date = 0.0` | **0** URL rows; 3 bad dates/times trending, 1 non-trending — negligible |
| "~84,500 candidate hashtags — enough for negatives" | true only in the raw count; **negatives are the bottleneck** (below) |

**New — the trend labels are contaminated two different ways.** Of 322 raw
names: 83 end `.csv`, 137 start `#`, 25 do both. Any comparison against a
hashtag token must go through normalisation first. This is the root cause of
the leak recorded below.

**New — duplicate ids.** 11.9% of trending rows and 5.7% of non-trending rows
repeat an `id`. In the trending file these are mostly *legitimate multi-trend
membership* — one tweet carrying two trending hashtags. De-duplicating on `id`
would delete real data. The pipeline keys on `(id, topic)`.

---

## 2026-08-08 — The pools do not cover the same hours

**This invalidated the original plan to bin the whole day.**

| Hour block | Trending | Non-trending |
|---|---|---|
| 00 | 151 (all dated 2020-02-26) | 113,074 |
| 01–15 | 675,652, continuous | 8,875 total — effectively dead |
| 16–23 | 660,899 | 968,330 |

The non-trending pool was collected in **two disjoint blocks** (00:00–00:59 and
16:00–23:59); the 01–15h band runs at ~590 rows/hour against ~120,000/hour in
the live band. It is a collection-window artifact.

**Consequence:** peak detection across the full day would place every negative
topic's peak inside 16–23h *by construction*, so any cross-class comparison of
peak timing would be measuring the scraper, not the phenomenon.

**Change:** all modelling is restricted to `2020-02-25 16:00:00–23:59:59`, the
only band both pools genuinely cover. 16:00 is treated as collection start for
**both** classes so the censoring filter stays symmetric. The 151 rows dated
2020-02-26 are dropped as next-day residue.

**Cost:** an 8-hour band, against a design that assumed 24. This is the binding
constraint on sample size throughout.

---

## 2026-08-08 — Negative-pool leak in the prototype (corrected)

The prototype excluded already-trending topics from the negative pool by
testing `"#" + hashtag ∈ {raw trend names}`. Because trend names are
mixed-format, that test matched only **17** of the **182** hashtags that had in
fact trended.

**Effect on the prototype's actual sample: 6 of 125 negatives (4.8%) were
topics that did trend** — `cachitosprotovideo80`, `china`, `firstdates25f`,
`frac1`, `quéhashechocandivinity`, `tierradenadie1`.

Re-ran the prototype twice, changing **only** the exclusion test, so the
difference isolates the leak (`prototype/rerun/`):

| | frozen (as submitted) | fixed exclusion |
|---|---|---|
| topics | 265 (140/125) | 259 (140/119) |
| leaked negatives | 6 (4.8%) | **0** |
| volume-only ROC-AUC | 0.776 ± 0.064 | 0.770 ± 0.058 |
| network-only ROC-AUC | 0.772 ± 0.052 | **0.776 ± 0.066** |
| network-only PR-AUC | 0.791 ± 0.057 | **0.803 ± 0.065** |
| full ROC-AUC | 0.869 ± 0.043 | 0.870 ± 0.049 |
| full PR-AUC | 0.877 ± 0.045 | 0.883 ± 0.052 |
| permutation p (network) | 0.0099 | 0.0099 |
| network vs volume | 0.771 vs 0.771, Wilcoxon p = 0.963 | 0.772 vs 0.766, Wilcoxon p = 0.637 |
| full OOF ROC-AUC 95% CI | [0.820, 0.906] | [0.833, 0.915] |

**Interpretation.** Removing the leak moves the network channel slightly in the
expected direction — leaked negatives carried genuine trend structure, so the
leak biased *toward* the null. But **the conclusion does not change**: network
structure still does not beat volume alone. The honest negative result stands.

The frozen re-run also reproduces the originally recorded table to within
±0.002 ROC-AUC (recorded 0.774 / 0.770 / 0.868; reproduced 0.776 / 0.772 /
0.869), confirming the prototype is reproducible. The one number that moved
materially is the network-vs-volume Wilcoxon p (recorded 0.81, reproduced
0.963) — different library versions, same conclusion, nowhere near
significance either way.

---

## 2026-08-08 — Censoring filters, and how accurate they are

Left-censoring was already known to be a risk. **Right-censoring was missed in
the original design** and has been added: on a bounded band, a topic still
climbing at the final bin has its last bin mis-read as a peak.

Both filters run on band data alone and are symmetric across classes.

**The filter's own accuracy is measured, not assumed.** Trending topics retain
history from 01:00–15:59 which the filter never sees. Running the filter blind
on the 16:00+ band and scoring its verdicts against that held-out history
gives, over 199 eligible positives:

| | |
|---|---|
| accuracy | **77.4%** |
| recall of truly-censored topics | **90.0%** |
| false-negative rate (contamination let through) | **10.0%** (8 topics) |
| false-positive rate (clean topics wrongly dropped) | **31.1%** (37 topics) |
| mean pre-band volume — flagged topics | 58.6% |
| mean pre-band volume — kept topics | 15.3% |

The 58.6% vs 15.3% separation confirms the filter keys on the intended signal.

**The trade-off is deliberately conservative.** Contamination invalidates the
pre-peak claim outright; discarding a clean topic only costs sample size. A
filter that catches 9 in 10 censored topics at the price of ~31% of clean ones
is the right side of that trade.

This validation uses positives only and never feeds the filter.

---

## 2026-08-08 — Left-censoring is symmetric in rule, asymmetric in effect

At the first primary setting the left-censoring filter dropped **109 positives
and 0 negatives**.

The rule is identical for both classes. The asymmetry is real: negatives are
small hashtags that are never running hot at 16:00 relative to their own peak,
whereas positives are genuine trends that frequently already were.

**Consequence — a genuine limitation, not a bug.** The surviving positive class
is biased toward **late-starting trends**: topics whose emergence happened to
fall inside the observable band. Findings generalise to trends that begin
within the observation window, not to trends already underway when observation
starts. Stated as a limitation rather than filtered away, because filtering it
away is exactly what would make the pre-peak claim false.

---

## 2026-08-08 — The planned language control cannot be executed

The original design called for controlling the severe language confound
(trending pool multilingual, non-trending pool ~89% Spanish) by
**stratifying/matching classes by language**.

**That control is impossible on this corpus.** Across all 24 combinations of
(min topic size × lead × window) swept, the number of **English-dominant
negative topics was zero in every single one**. Maximum Spanish positives
reached 37. No setting reaches a workable balance within any single language.

**Substituted control — tweet-level language filtering.** Units are still
defined on *all* activity, because a topic's peak is a real-world event and
does not belong to one language. But window **features** are computed only from
Spanish tweets. Every unit's features are then language-homogeneous, so
language cannot carry class signal, and no topics are discarded for being
multilingual.

Cost measured: 5–14 positives fall below the window-volume threshold on Spanish
alone, depending on setting. Negatives are essentially unaffected — they were
~89% Spanish already.

A language-only negative-control classifier is retained regardless, and the
topic-level Spanish-only restriction is reported as a robustness check.

**Discovering that a planned control cannot be run, and substituting one that
can, is itself a result.** It is recorded here rather than quietly dropped.

---

## 2026-08-08 — Sample size: contingency level reached

The strict setting (1-hour lead, 60-min window, ≥100 tweets) yields **88 units**
(44/44) — below the pre-registered floor of 120 total with ≥40 per class.

Contingency **level 2** was reached: widen the window rather than shorten the
lead, because *lead time is the contribution being tested*. A 30-minute lead
reaches 149 units but buys statistical comfort by surrendering the claim.

Parameters were selected **from unit counts alone, before any classifier
existed** — no model performance was visible at selection time.

Sensitivity of the window-volume threshold, at ≥50 tweets / 60-min lead /
90-min window:

| `min_window_tweets` | positives | negatives | total |
|---|---|---|---|
| 10 | 46 | 135 | 181 |
| **15** | **42** | **87** | **129** |
| 20 | 39 | 63 | 102 |
| 25 | 37 | 42 | 79 |

Full sensitivity across 15/20/25 is reported at evaluation.
