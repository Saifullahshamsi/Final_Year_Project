# Results summary

Every number in one place, for pulling into the report without re-reading logs.
All figures are out-of-fold predictions under 5-fold stratified cross-validation
grouped by topic, seed 42, bootstrap CIs over 1,000 resamples.

**Read this first:** `chance PR-AUC = prevalence`, and prevalence differs
between tables. A PR-AUC of 0.62 is well above chance at prevalence 0.279 and
barely above it at 0.422. Never compare PR-AUC across tables without the chance
line.

**Second:** resampling noise is **±0.02–0.03 PR-AUC** on identical data
(measured — see FINDINGS). Differences below ~0.05 carry no interpretation.
Report the intervals, not the point estimates.

**Third:** the language confound is **not controlled**. See
`FINDINGS.md § The language confound is NOT fully controlled`. Absolute
performance figures below are not attributable to trend dynamics alone.

Source files: `ablation_results.json`, `lead_time_results.json`,
`robustness.json`, `language_control.json`, `size_proxy_audit.json`,
`units_summary.json`, `permutation_importance.csv`.

---

## 1. Primary ablation

**n = 129 units — 42 trending / 87 non-trending. Prevalence 0.326.**
**Chance PR-AUC = 0.326. Chance ROC-AUC = 0.500.**

| arm | k | PR-AUC | 95% CI | lift | ROC-AUC | F1 | Prec | Rec |
|---|---|---|---|---|---|---|---|---|
| chance | 0 | 0.326 | — | — | 0.500 | — | — | — |
| sentiment_only | 9 | 0.564 | [0.435, 0.745] | +0.238 | 0.783 | 0.617 | 0.641 | 0.595 |
| volume_only | 3 | 0.649 | [0.509, 0.771] | +0.323 | 0.724 | 0.571 | 0.571 | 0.571 |
| temporal_only | 9 | 0.654 | [0.512, 0.789] | +0.328 | 0.764 | 0.622 | 0.719 | 0.548 |
| structure_size_free | 10 | 0.689 | [0.551, 0.804] | +0.363 | 0.730 | 0.561 | 0.575 | 0.548 |
| structure_residualised | 10 | 0.707 | [0.570, 0.819] | +0.381 | 0.802 | 0.593 | 0.615 | 0.571 |
| volume_plus_temporal | 12 | 0.783 | [0.669, 0.872] | +0.457 | 0.827 | 0.700 | 0.737 | 0.667 |
| volume_plus_sentiment | 12 | 0.789 | [0.673, 0.882] | +0.463 | 0.843 | 0.692 | 0.750 | 0.643 |
| volume_extended | 33 | 0.820 | [0.701, 0.912] | +0.494 | 0.889 | **0.780** | 0.800 | 0.762 |
| full_fusion_regularised | 31 | 0.822 | [0.723, 0.904] | +0.496 | 0.855 | 0.667 | 0.667 | 0.667 |
| volume_plus_structure | 13 | 0.829 | [0.719, 0.910] | +0.503 | 0.869 | 0.709 | 0.757 | 0.667 |
| **full_fusion** | 31 | **0.853** | [0.756, 0.927] | +0.527 | 0.891 | 0.727 | 0.800 | 0.667 |

`k` = feature count. `structure_residualised` is the **less conservative** arm
(volume regressed out per fold rather than features exiled) and is not the
headline. `full_fusion` carries **31 features against 42 positive cases**.

### Paired comparisons (exact McNemar, out-of-fold decisions at threshold 0.5)

| A vs B | only A | only B | p |
|---|---|---|---|
| volume_only vs structure_size_free | 21 | 21 | **1.0000** |
| volume_only vs sentiment_only | 17 | 22 | 0.5224 |
| volume_only vs temporal_only | 17 | 25 | 0.2800 |
| volume_only vs volume_plus_sentiment | 5 | 17 | **0.0169** |
| volume_only vs volume_plus_structure | 8 | 21 | **0.0241** |
| volume_only vs volume_plus_temporal | 7 | 19 | **0.0290** |
| volume_only vs full_fusion | 6 | 21 | **0.0059** |
| volume_only vs volume_extended | 6 | 24 | **0.0014** |
| structure_size_free vs structure_residualised | 10 | 13 | 0.6776 |
| full_fusion vs full_fusion_regularised | 10 | 3 | 0.0923 |
| volume_plus_structure vs volume_extended | 10 | 15 | 0.4244 |
| **full_fusion vs volume_extended** *(the H1 test)* | 9 | 12 | **0.6636** |

**H1 not supported.** The best single-signal baseline is `volume_extended`, not
`volume_only`.

---

## 2. Lead-time curve — full sample

Composition varies with the lead; prevalence varies with it too. Use lift.

| lead | n | pos | neg | chance | volume_only | volume_extended | volume+structure | full_fusion | fusion vs vol_ext |
|---|---|---|---|---|---|---|---|---|---|
| 30 min | 183 | 51 | 132 | 0.279 | 0.619 | 0.721 | 0.789 | 0.769 | p = 1.0000 |
| 60 min | 129 | 42 | 87 | 0.326 | 0.649 | 0.820 | 0.816 | 0.857 | p = 0.8238 |
| 120 min | 93 | 35 | 58 | 0.376 | 0.641 | 0.687 | 0.739 | 0.677 | p = 0.6476 |
| 180 min | 64 | 27 | 37 | 0.422 | 0.611 | 0.599 | 0.676 | 0.662 | p = 0.4244 |

Lift over chance:

| lead | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|
| 30 | +0.341 | +0.442 | +0.510 | +0.490 |
| 60 | +0.324 | +0.494 | +0.490 | +0.532 |
| 120 | +0.265 | +0.311 | +0.363 | +0.301 |
| 180 | +0.189 | +0.177 | **+0.254** | +0.240 |

---

## 3. Lead-time curve — nested (the H2 evidence)

**The same 52 topics at every lead — 26 trending / 26 non-trending.**
**Prevalence fixed at 0.500, so PR-AUC is directly comparable down each column.**
Each topic's language mix is constant across these rows, which is why this
comparison is not reachable by the language confound.

| lead | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|
| 30 min | 0.765 | 0.906 | 0.890 | 0.883 |
| 60 min | 0.795 | 0.884 | 0.888 | 0.858 |
| 120 min | 0.699 | 0.817 | **0.923** | 0.880 |
| 180 min | **0.515** | 0.620 | **0.764** | 0.699 |

Lift over chance (0.500):

| lead | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|
| 30 | +0.27 | +0.41 | +0.39 | +0.38 |
| 60 | +0.29 | +0.38 | +0.39 | +0.36 |
| 120 | +0.20 | +0.32 | +0.42 | +0.38 |
| 180 | **+0.02** | +0.12 | **+0.26** | +0.20 |

### H2 significance (exact McNemar, common subset)

| lead | volume_only vs volume+structure | discordant | volume_only vs full_fusion | discordant |
|---|---|---|---|---|
| 30 min | p = 0.3877 | 4 / 8 | p = 0.1094 | 2 / 8 |
| 60 min | p = 0.2668 | 4 / 9 | p = 0.1460 | 3 / 9 |
| 120 min | p = 0.1185 | 4 / 11 | p = 0.4545 | 6 / 10 |
| 180 min | **p = 0.0347** | 6 / 17 | p = 0.3449 | 11 / 17 |

**H2 supported directionally, not statistically.** Four tests; Bonferroni α =
0.0125; p = 0.0347 does not survive it. The monotone trend is the evidence, not
the single cell. The effect belongs to `volume_plus_structure`, **not** to
`full_fusion` — sentiment and temporal dilute.

---

## 4. Language control

| test | result |
|---|---|
| **A** language-only classifier | PR-AUC **0.897** [0.824, 0.958], ROC 0.893, chance 0.326 |
| mean Spanish share of window | trending **0.483**, non-trending **0.978** |
| **B** predicting language *from features* (ROC-AUC) | full_fusion 0.812 · volume_extended 0.769 · structure 0.747 · temporal 0.744 · volume_only 0.735 · sentiment 0.683 |
| **C** within-language subset | **impossible** — at ≥90% Spanish: 6 trending vs 80 non-trending |

Spanish share of window, by class:

| percentile | trending | non-trending |
|---|---|---|
| min | 0.048 | **0.824** |
| p25 | 0.193 | 0.964 |
| p50 | 0.438 | 1.000 |
| p75 | **0.814** | 1.000 |
| max | 1.000 | 1.000 |

---

## 5. Common-support ablation

**Windows 50–99% Spanish. n = 43 — 15 trending / 28 non-trending. Prevalence
0.349. Underpowered by construction.**

| arm | PR-AUC | 95% CI | lift |
|---|---|---|---|
| volume_only | 0.442 | [0.296, 0.681] | +0.093 |
| structure_size_free | 0.558 | [0.332, 0.780] | +0.209 |
| volume_extended | 0.712 | [0.487, 0.906] | +0.363 |
| full_fusion | 0.735 | [0.525, 0.891] | +0.386 |
| **Spanish share alone** | **0.716** | — | **+0.367** |

full_fusion vs volume_extended: McNemar p = 0.7744 (7 / 5 discordant).

**Language scores 0.716 inside the band selected for common language support,
matching volume_extended's 0.712.** Restriction does not remove the confound.

---

## 6. Sensitivity — `min_window_tweets` (the tuned parameter)

| setting | n | pos | neg | chance | volume_only | structure | volume_extended | full_fusion | fusion vs vol_ext |
|---|---|---|---|---|---|---|---|---|---|
| 15 *(primary)* | 129 | 42 | 87 | 0.326 | 0.621 | 0.671 | 0.821 | 0.868 | p = 0.2863 |
| 20 | 102 | 39 | 63 | 0.382 | 0.672 | 0.603 | 0.844 | 0.871 | p = 1.0000 |
| 25 | 79 | 37 | 42 | 0.468 | 0.746 | 0.802 | 0.870 | 0.894 | p = 1.0000 |

full_fusion lift falls as the threshold rises: **+0.542, +0.489, +0.426**. Raw
PR-AUC rises only because prevalence does.

## 7. Sensitivity — window length

| window | n | pos | neg | chance | volume_only | structure | volume_extended | full_fusion | fusion vs vol_ext |
|---|---|---|---|---|---|---|---|---|---|
| 30 min | 71 | 37 | 34 | 0.521 | 0.666 | 0.664 | 0.763 | 0.879 | p = 0.3593 |
| 60 min | 107 | 41 | 66 | 0.383 | 0.587 | 0.616 | 0.775 | 0.809 | p = 0.6776 |
| 90 min *(primary)* | 129 | 42 | 87 | 0.326 | 0.621 | 0.671 | 0.821 | 0.868 | p = 0.2863 |

**Never significant at any setting.** Neither tuned parameter produced the null.

---

## 8. Unit construction

**Band: 2020-02-25 16:00–23:59. Lead 60 min, window 90 min, ≥50 tweets per
topic, ≥15 Spanish tweets per window, features from Spanish tweets only.**

| stage | trending | non-trending |
|---|---|---|
| topics on grid | 322 | 76,705 |
| − too_small | −82 → 240 | −76,274 → 431 |
| − left_censored | −132 → 108 | −1 → 430 |
| − right_censored_no_tail | −9 → 99 | −41 → 389 |
| − right_censored_no_decay | −4 → 95 | −12 → 377 |
| − window_before_band_start | −20 → 75 | −169 → 208 |
| − window_too_sparse | −33 → **42** | −121 → **87** |

165 negative topics excluded for having trended (the corrected leak test).

### Censoring-filter accuracy, measured against held-out pre-band history

| | ≥100 tweets (199 scored) | **final setting, ≥50 (240 scored)** |
|---|---|---|
| accuracy | 77.4% | **75.0%** |
| recall of truly-censored | 90.0% | **84.0%** |
| false-negative rate | 10.0% | **16.0%** |
| false-positive rate | 31.1% | **32.1%** |

---

## 9. Prototype, frozen vs leak-corrected

**Not comparable to the tables above** — different unit definition, volume
controlled by construction, prevalence 0.528 vs 0.326.

| | frozen (as submitted) | fixed exclusion |
|---|---|---|
| topics | 265 (140 / 125) | 259 (140 / 119) |
| leaked negatives | 6 (4.8%) | **0** |
| volume-only ROC-AUC | 0.776 ± 0.064 | 0.770 ± 0.058 |
| network-only ROC-AUC | 0.772 ± 0.052 | 0.776 ± 0.066 |
| full ROC-AUC | 0.869 ± 0.043 | 0.870 ± 0.049 |
| full PR-AUC | 0.877 ± 0.045 | 0.883 ± 0.052 |
| permutation p (network) | 0.0099 | 0.0099 |
| network vs volume | p = 0.963 | p = 0.637 |

Recorded prototype table: 0.774 / 0.770 / 0.868 — reproduced to within ±0.002.

---

## 10. Permutation importance — `full_fusion`

Held-out split, PR-AUC scoring, **indicative only at n = 129**. No interval
excludes zero.

| feature | Δ PR-AUC when shuffled | arm |
|---|---|---|
| `arima_ar1` | +0.0402 ± 0.0373 | temporal |
| `tweets_per_active_bin` | +0.0347 ± 0.0633 | volume |
| `window_tweets` | +0.0230 ± 0.0258 | volume |
| `node_growth_slope` | +0.0151 ± 0.0222 | structure |
| `unique_users` | +0.0103 ± 0.0303 | volume |
| `arima_forecast_ratio` | +0.0072 ± 0.0274 | temporal |

---

## 11. Feature-set assignment

| set | k | in which arms |
|---|---|---|
| volume_baseline | 3 | volume_only, and every `volume_plus_*` |
| size_dependent | 22 | volume_extended |
| temporal_size_dependent | 8 | volume_extended |
| structure_size_free | 10 | structure_size_free, volume_plus_structure, full_fusion |
| sentiment | 9 | sentiment_only, volume_plus_sentiment, full_fusion |
| temporal | 9 | temporal_only, volume_plus_temporal, full_fusion |

Cross-channel size-proxy audit: **0 of 28 non-volume features** exceed
|Spearman| 0.4 against window volume.
