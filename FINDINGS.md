# Findings and corrections

A dated record of what the data turned out to be, what broke against it, and
what was changed as a result. Negative results and self-corrections are kept
here deliberately — they are part of the work, not a tidy-up list.

Every number below traces to a script in this repository. Nothing is estimated.

> **Superseded numbers — read before quoting any figure below.** On
> **2026-09-24** the ARIMA order was selected against the data and changed from
> (1,1,1) to (0,1,2), and every result that depends on the temporal channel was
> re-run. Entries dated 2026-08-13 record what was true under the old order and
> are **left unedited on purpose** — this is a log, and rewriting a dated entry
> to match a later run would destroy the thing it exists to provide. For the
> current value of any number involving `temporal_only`, `volume_plus_temporal`,
> `full_fusion`, `volume_extended` or the common-support band, use
> `outputs/tables/RESULTS_SUMMARY.md`, which is now **generated** from the
> result JSONs. The final entry in this file lists every number that moved.
>
> **H1 and H2 conclusions are unchanged.** H1 remains not supported; H2 remains
> directional. Nothing in the argument below depends on the superseded values.

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
on the 16:00+ band and scoring its verdicts against that held-out history:

| | at ≥100 tweets (199 scored) | **final setting, ≥50 tweets (240 scored)** |
|---|---|---|
| accuracy | 77.4% | **75.0%** |
| recall of truly-censored topics | 90.0% | **84.0%** |
| false-negative rate (contamination let through) | 10.0% (8) | **16.0% (17)** |
| false-positive rate (clean topics wrongly dropped) | 31.1% (37) | **32.1% (43)** |
| mean pre-band volume — flagged | 58.6% | 58.2% |
| mean pre-band volume — kept | 15.3% | 19.1% |

**The numbers moved when `min_topic_tweets` dropped from 100 to 50**, and the
direction is the honest one: admitting smaller topics admits noisier volume
curves, so the filter's recall falls from 90% to 84% and contamination rises
from 10% to 16%. **The final-setting figures are the ones that describe this
pipeline.** The earlier column is kept because it was reported first and the
degradation is itself informative — filter reliability is a function of topic
size.

The ~58% vs ~19% pre-band volume separation holds in both, confirming the
filter keys on the intended signal either way.

**The trade-off is deliberately conservative.** Contamination invalidates the
pre-peak claim outright; discarding a clean topic only costs sample size. A
filter that catches 9 in 10 censored topics at the price of ~31% of clean ones
is the right side of that trade.

This validation uses positives only and never feeds the filter.

---

## 2026-08-08 — Left-censoring is symmetric in rule, asymmetric in effect

At the first primary setting the left-censoring filter dropped **109 positives
and 0 negatives**. **At the final parameters it drops 132 positives and 1
negative** — the asymmetry widened rather than resolved, and the final figures
are the ones that describe this pipeline.

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

**Cost measured — and it is asymmetric for a reason worth stating.** At the
final setting the filter removes **6 positives and 6 negatives** (48/93 →
42/87). Proportionally that is 12.5% of positives against 6.5% of negatives.

The filter is nearly free on the negative class because **the non-trending pool
was already ~89% Spanish** — there is almost nothing for a Spanish filter to
remove. It genuinely thins the positive class, which is multilingual (43.7% en,
28.3% es). So the control costs what it should cost: it bites exactly where the
confound lived.

Six positives to eliminate a confound that could otherwise have produced a
high-accuracy classifier that had learned nothing but language is cheap.

A language-only negative-control classifier is retained regardless.

**Route 1 — Spanish-majority topics — is a descriptive check, not a second
model.** Restricting to units whose window is ≥50% Spanish yields 18 positives
against 87 negatives at the final setting. That cannot support the significance
testing the evaluation requires, so it is reported as a descriptive comparison
only. It is stated here explicitly so it is not read as a suppressed arm.

**Discovering that a planned control cannot be run, and substituting one that
can, is itself a result.** It is recorded here rather than quietly dropped.

---

## 2026-08-13 — The size-proxy failure mode (the project's main methodological finding)

**The rule, stated generally:**

> On classes that differ in size, *any* quantity that scales with sample size
> will separate them — and it will do so under a name that sounds like it
> measures something else.

The trending and non-trending classes here differ in size by roughly 5× inside
the feature window (250.3 vs 51.2 graph nodes; 212.9 vs 46.2 tweets). That
difference is real, and volume is a legitimate baseline. The failure mode is
when it re-enters the model *disguised as a different construct*, so a channel
gets credit for signal it does not carry.

**Three instances, one in each of the three feature channels:**

| # | feature | channel | claimed to measure | actually measured | strength |
|---|---|---|---|---|---|
| 1 | `betweenness_exact` | network | brokerage centrality | whether node count exceeded 100 | **AUC 0.793** |
| 2 | `total_count` | network (prototype) | topic volume | tweets over the **whole day**, i.e. the peak being predicted | **RF importance 0.276** — the prototype's top feature |
| 3 | `sent_n` | sentiment | scored-tweet count | identical to `window_tweets` (212.857 vs 46.184) | **AUC 0.832** |

A fourth, milder case is structural rather than a single feature: on these
fragmented graphs `n_components` (149.6 vs 31.0), `n_communities` (151.6 vs
31.3) and `community_entropy` all track `n_nodes` (250.3 vs 51.2) closely, and
their mirror images `density`, `max_pagerank`, `largest_wcc_frac` and
`largest_community_frac` are mechanically ~1/N and therefore run *higher* for
the smaller non-trending graphs. Size with the sign flipped is still size.

**The part that matters: none of these were detectable from model performance.**

Every one of them made results look **better**. A leaderboard, a CV score, a
held-out test set — none would have flagged any of the three, because all three
raise accuracy. `total_count` survived the entire prototype, was reported as
its single strongest feature, and was only identified when the pre-peak design
forced the question of *when* each feature is measured.

They were caught by **per-feature audit**: printing every feature's class means
and univariate AUC before modelling and asking, for each one, what it is
physically measuring. That check costs one table per channel. Nothing else in
the workflow would have found them.

**Consequence for the prototype's headline result.** `total_count` was a
target-contaminated feature doing most of the work in the prototype's
volume-only baseline (ROC-AUC 0.774). That baseline was closer to a partial
oracle than to a fair volume comparator — which makes the prototype's negative
result (network does not beat volume) *more* conservative than it appeared, not
less. The prototype numbers stand as recorded; this pipeline does not repeat
the mistake.

**Consequence for this pipeline.** Feature-set assignment is explicit in
`config.yaml` and enforced by `src/features/feature_sets.py`: every column must
be assigned exactly once, and the size-free structure arm is re-checked by name
independently of config. The governing rule is that anything scaling with
tweets or nodes is volume, and **where assignment is arguable it goes to
volume**, because that is the direction that makes H1 harder to pass.

Arms: chance → volume_only (3) → structure_size_free (14) →
volume_plus_structure (17, the H1 test) → sentiment_only (9) →
volume_plus_sentiment (12) → volume_extended (21).

Guard tests exist per channel. The sentiment one feeds an identical probability
distribution at 1× and 10× the tweet count and asserts that no feature moves.

---

## 2026-08-13 — The language confound is NOT fully controlled. Read this before any other result.

The negative control was run to prove the language confound had been handled.
**It proved the opposite.** This qualifies the attribution of every result in
this study and is recorded first for that reason.

### A — how large is the confound?

A classifier given **nothing but the language mix** of each window:

| | PR-AUC | 95% CI | ROC-AUC | chance PR-AUC |
|---|---|---|---|---|
| language-only | **0.897** | [0.824, 0.958] | 0.893 | 0.326 |

**That is the best-performing model in the entire study** — better than
`full_fusion` (0.853), better than `volume_extended` (0.820). Mean Spanish
share of window: **0.483 for trending, 0.978 for non-trending.**

### B — do the modelled features still carry language? Yes.

Predicting "is this window majority Spanish" *from the modelled feature
matrices*. This was required to fail. It did not:

| arm | ROC-AUC predicting language | verdict |
|---|---|---|
| full_fusion | **0.812** | leaks |
| volume_extended | 0.769 | leaks |
| structure_size_free | 0.747 | leaks |
| temporal_only | 0.744 | leaks |
| volume_only | 0.735 | leaks |
| sentiment_only | 0.683 | borderline |

Tweet-level filtering made every feature *computed from Spanish tweets*. It did
not make them *independent of language*, because **how much Spanish activity a
topic has is itself informative**: `window_tweets` is a Spanish count, and
multilingual topics are the large ones.

### C — can we check performance within one language? No.

| Spanish share of window | trending | non-trending |
|---|---|---|
| p0 (minimum) | 0.048 | **0.824** |
| p25 | 0.193 | 0.964 |
| p50 | 0.438 | 1.000 |
| p75 | **0.814** | 1.000 |

**The least-Spanish non-trending unit (0.824) sits above the 75th percentile of
trending units (0.814).** The distributions barely overlap. At a ≥90% Spanish
threshold only 6 trending units remain against 80 non-trending. The widest
usable common-support band, [0.5, 0.99), holds 15 trending and 28 non-trending
— far too few to model.

**The planned within-language robustness check cannot be executed at all.**

### D — restriction was attempted anyway, and it demonstrates the point

The widest usable band of common language support — windows 50–99% Spanish, 15
trending against 28 non-trending — was modelled despite being underpowered,
because the alternative was leaving the possibility untested.

| model on the common-support band | PR-AUC | chance |
|---|---|---|
| volume_only | 0.442 | 0.349 |
| structure_size_free | 0.558 | 0.349 |
| volume_extended | 0.712 | 0.349 |
| full_fusion | 0.735 | 0.349 |
| **Spanish share of window, alone** | **0.716** | **0.349** |

**Inside the region selected for common language support, a classifier given
nothing but the Spanish share of the window scores 0.716 — matching
`volume_extended` at 0.712 and within noise of `full_fusion` at 0.735.**

This is the strongest single piece of evidence in the confound analysis. The
band was chosen precisely to be the slice where the two classes overlap in
language, and language still predicts the label as well as the entire feature
set does. **Restriction does not weaken the confound; it survives inside the
region built to neutralise it.** That is a demonstration rather than an
argument, and it is why no fourth control strategy is proposed.

(The H1 null also holds on this subset: full_fusion vs volume_extended,
McNemar p = 0.7744.)

### What this means

In this corpus **a trending topic essentially *is* a multilingual topic**.
Language, volume and label are close to collinear: language predicts the label
at ROC 0.893, and volume alone predicts language at ROC 0.735.

Three control strategies were available and all three are now exhausted:
topic-level matching (impossible — zero English negatives), tweet-level
filtering (implemented, insufficient), and within-language restriction
(impossible — no common support).

**Consequence for attribution.** No result in this study can cleanly separate
"this model detects trend dynamics" from "this model detects that the topic is
multilingual". The honest statement is that the classifiers work, and that
their performance has a language component that could not be removed or
bounded on this data.

### What survives the confound, and why

A reader who reaches this section will reasonably assume every result in the
study is dead. Some are. Three are not, and the reasons are different in each
case and need arguing rather than asserting.

**1. The H2 lead-time result is protected, and this is now the study's most
defensible finding.**

The nested design compares the **same 52 topics at every lead**. Each topic's
language composition is a fixed property of that topic — it does not change
when the cut-off moves from 30 minutes to 180. So across the four rows of that
comparison, **the confound is held constant while the effect varies**. Language
cannot explain why `volume_only` decays from 0.765 to 0.515 while
`volume_plus_structure` holds at 0.764, because language is identical in both
arms and at every lead.

That makes it a **within-topic contrast**, and within-topic contrasts are
immune to any confound that is constant within a topic. It is the most
defensible result in the study — not because the effect is the largest, but
because it is the only one the confound cannot reach.

**This was luck, not foresight.** The nested design was built to fix a
different problem: sample composition changing across leads, which made the raw
curve partly a plot of the survival filter. That it also neutralises the
language confound was discovered afterwards, when the negative control came
back positive. Claiming the design as a deliberate confound control would be
the one dishonest move available at this point, and it is not being made.

**2. The H1 null survives, and the logic matters.**

A confound that is present in *every* arm inflates them all in the same
direction. The language signal is available to `volume_only`, to
`structure_size_free`, to `volume_extended` and to `full_fusion` alike — all
four are built from the same units with the same language composition.

Therefore the confound can manufacture a **spurious pass** — a model looking
predictive when it is only detecting language — but it cannot manufacture a
spurious **failure to beat a baseline**. For the confound to explain H1's null
it would have to inflate `volume_extended` specifically, relative to
`full_fusion`, which it has no mechanism to do: both arms have full access to
it. If anything, a shared inflation compresses the differences between arms
towards zero, which makes detecting a genuine fusion benefit *harder*, not
easier.

The honest form is: H1 failed, and the confound is not a candidate explanation
for why.

**3. The size-proxy findings are untouched.** They are statements about
correlations between features and window volume — the label does not enter
them. `zero_bin_frac` correlates with volume at −0.858 regardless of what
language anything is in.

**What is genuinely compromised:** any absolute claim about predictive
performance, and any claim that a specific channel detects *trend dynamics* as
such rather than the multilingual character of trending topics.

### What this cost, and the counterfactual

The language-only classifier was prescribed in the project design precisely to
catch this. It was run late — after the channels, the ablation and the
lead-time sweep — and it invalidated the interpretation of work already done.
Running it earlier would not have changed the finding, but would have framed
every result correctly from the start.

All three prescribed control strategies were attempted, in the order the design
specified, and the corpus defeated each:

| strategy | outcome |
|---|---|
| topic-level language matching | **impossible** — zero English negatives in all 24 settings swept |
| tweet-level filtering | **implemented, insufficient** — features still recover language at ROC 0.74–0.81 |
| within-language restriction | **impossible** — no common support (see distribution table above) |

**Documenting an exhausted control hierarchy is itself a result.** It converts
"the confound was not controlled" from an admission into a finding about what
this corpus can and cannot support.

**The counterfactual is the part worth stating plainly: had the control not
been run, every number in this study would have looked clean and been
uninterpretable.** The ablation table, the CIs, the McNemar tests and the
lead-time curve would all have appeared exactly as they do now. Nothing in the
results would have looked wrong. The control is the only thing standing between
a language detector and a claimed trend predictor.

### Was the corpus salvageable?

Probably not for this design. The two pools were collected by different
processes — one sampling global trends, one sampling a Spanish-language stream
— so language is not a nuisance variable that happened to correlate with the
label. It is **an artifact of how the two classes were assembled**, and no
amount of downstream modelling removes it. A corpus with negatives drawn from
the same language distribution as positives is the only real fix, and that
requires re-collection, which is out of scope here.

Recorded rather than worked around. The alternative — reporting the results
without this section — would have presented a language detector as a trend
predictor.

---

## 2026-08-13 — Robustness: the conclusions are stable, the confound is not removable

**Framing.** These are sensitivity checks on a model with a confound that could
not be removed. They test whether conclusions survive parameter choices. They do
not validate a clean result, because there is no clean result to validate.

### Common support — the only slice where the classes overlap in language

Units whose window is 50–99% Spanish: **15 trending, 28 non-trending, n = 43.**
Underpowered by construction and stated as such before running.

| arm | PR-AUC | 95% CI | lift over chance (0.349) |
|---|---|---|---|
| volume_only | 0.442 | [0.296, 0.681] | +0.093 |
| structure_size_free | 0.558 | [0.332, 0.780] | +0.209 |
| volume_extended | 0.712 | [0.487, 0.906] | +0.363 |
| full_fusion | 0.735 | [0.525, 0.891] | +0.386 |

full_fusion vs volume_extended: **McNemar p = 0.7744** (7/5 discordant). The H1
null holds here too, on a fifth of the data.

**And the confound does not disappear inside the overlap band.** A classifier
given only the Spanish share of the window scores **PR-AUC 0.716** there —
essentially matching `volume_extended` (0.712) and close to `full_fusion`
(0.735). The band was selected to be the region of common language support, and
language still predicts the label as well as the full feature set does.

**This is the clearest single demonstration that the confound cannot be escaped
by restriction.** The attempt was made, the result is a null, and the null is
uninformative because the confound survives the restriction. Reported because
declining to attempt it would have left the possibility untested.

### `min_window_tweets` — the one tuned parameter

| setting | n | chance | volume_only | structure | volume_extended | full_fusion | fusion vs vol_ext |
|---|---|---|---|---|---|---|---|
| 15 | 129 | 0.326 | 0.621 | 0.671 | 0.821 | 0.868 | p = 0.286 |
| 20 | 102 | 0.382 | 0.672 | 0.603 | 0.844 | 0.871 | p = 1.000 |
| 25 | 79 | 0.468 | 0.746 | 0.802 | 0.870 | 0.894 | p = 1.000 |

Raw PR-AUC rises with the threshold only because prevalence rises with it
(0.326 → 0.468). **Lift over chance falls**: full_fusion +0.542, +0.489, +0.426.
The H1 null is unaffected at every setting. The tuned parameter did not create
the conclusion.

### Window length — drives graph sparsity

| window | n | chance | volume_only | structure | volume_extended | full_fusion | fusion vs vol_ext |
|---|---|---|---|---|---|---|---|
| 30 min | 71 | 0.521 | 0.666 | 0.664 | 0.763 | 0.879 | p = 0.359 |
| 60 min | 107 | 0.383 | 0.587 | 0.616 | 0.775 | 0.809 | p = 0.678 |
| 90 min | 129 | 0.326 | 0.621 | 0.671 | 0.821 | 0.868 | p = 0.286 |

Never significant, at any window length. The choice of 90 minutes is not what
produced the null.

### Cross-validation noise, measured

The robustness checks use a different CV seed and splitter from the headline
table, which incidentally quantifies seed sensitivity: `full_fusion` moves 0.853
→ 0.868 and `volume_only` 0.649 → 0.621 on identical data. **Roughly ±0.02–0.03
PR-AUC from the resampling choice alone** — the same order as several
differences between arms, and a further reason to read the CIs rather than the
point estimates.

### A bias caught in the robustness code itself

The first run collected sentiment texts for the primary units only. Eleven units
that survive at a 30-minute window but not at 90 were therefore scored with
all-zero sentiment features — a silent bias in exactly the arm under test. Fixed
by collecting over the union of every sweep setting's units before any sweep
runs. The corrected 30-minute figures differ (full_fusion 0.882 → 0.879, fusion
vs volume_extended p 0.824 → 0.359).

---

## 2026-08-13 — Feature importance: sanity check against theory

Permutation importance on a held-out split, `full_fusion`, PR-AUC as the
scoring. **Indicative only at n = 129** — a sanity check against theory, not a
ranking to interpret feature by feature. Every standard deviation below is
comparable to or larger than the mean it accompanies.

| feature | Δ PR-AUC when shuffled | arm |
|---|---|---|
| `arima_ar1` | +0.040 ± 0.037 | temporal |
| `tweets_per_active_bin` | +0.035 ± 0.063 | volume |
| `window_tweets` | +0.023 ± 0.026 | volume |
| `node_growth_slope` | +0.015 ± 0.022 | structure |
| `unique_users` | +0.010 ± 0.030 | volume |
| `arima_forecast_ratio` | +0.007 ± 0.027 | temporal |

**Consistent with theory, weakly.** Three of the top six are volume measures,
which matches everything else in this study. `node_growth_slope` — how fast the
interaction graph accretes nodes across the window — is the highest-ranked
structural feature, which is what Weng et al. and Cheng et al. would predict:
early *breadth* of diffusion, not depth or centrality. `arima_ar1` heading the
list is harder to interpret and may simply be noise at this sample size.

**Against theory:** none of the concentration or community measures
(`pagerank_gini`, `betweenness_gini`, `core3_frac`) carries meaningful
importance. On graphs this sparse they are near-degenerate — consistent with the
sparsity limitation already recorded, not evidence against the theory itself.

No feature's importance interval excludes zero. The honest reading is that the
ordering is suggestive and the magnitudes are not distinguishable from noise.

---

## 2026-08-13 — Running tally of defects found in this project's own work

Kept visible deliberately. The count is not an embarrassment to be minimised —
it is the evidence that the checks were actually running, and every entry below
would have produced a *better-looking* result had it gone unnoticed.

| # | defect | what it would have done | how it was caught |
|---|---|---|---|
| 1 | `betweenness_exact` emitted as a feature | a metadata flag scoring **AUC 0.793** while measuring nothing | per-feature audit before modelling |
| 2 | `total_count` inherited from the prototype | whole-day volume, i.e. the peak being predicted, as the top feature | asking when each feature is measured |
| 3 | `sent_n` in the sentiment arm | `window_tweets` under another name, **AUC 0.832**, crediting volume to sentiment | per-feature audit |
| 4 | substring match in the size-proxy validator | rejected `mean_clustering` for containing `n_` — a false positive in the checking code itself | running the validator and reading its output |
| 5 | `n_jobs=1` never reaching the model | a documented determinism guarantee that was not in force | **ruff**, as an unused-variable warning |
| 6 | sentiment texts collected for primary units only | 11 units in the 30-minute-window setting scored with **all-zero sentiment features** — silent bias in the arm under test; corrected p moved **0.824 → 0.359** | reading the sweep's own diagnostic line |
| 7 | figure palette | 4 of 5 colour-vision checks failed; two series indistinguishable | running the CVD validator |
| 8 | ARIMA order fixed at (1,1,1) by convention | an AR coefficient the data does not support, standing as the **top temporal feature** by permutation importance (+0.040) | external review asked for a justification; the selection then showed (1,1,1) wins on **0 of 129** units |

**Seven of the eight made results look better, not worse.** None was found by a
number looking wrong, because none of them made a number look wrong — that is
the defining property of this class of defect. They were found by audits that
ran regardless of whether anything seemed amiss: a per-feature size correlation,
a linter, a palette validator, and a diagnostic line printed by a sweep that
nobody was suspicious of.

**#6 is worth singling out** because it occurred in the robustness code — the
code whose entire purpose is checking other code. A check is not exempt from
needing checks, which is also the lesson of #4.

**#8 is the one this project's own audits did not catch**, and it is worth
being precise about why. Every other entry was found by a check that ran
whether or not anything looked wrong. #8 had no such check, because the size-
proxy audit asks *"does this feature track volume?"* and `arima_ar1` honestly
did not — it was a legitimate feature of a model whose **specification** was
never tested. The audit was aimed at one failure mode and found every instance
of it. An unexamined modelling assumption is a different failure mode, and it
took an outside reader to ask. That is an argument for external review as a
distinct check, not a substitute for the internal ones.

---

## 2026-08-13 — Three domains, one principle: measure what is measurable

The project produced the same lesson three times, in three unrelated places,
each time by running a check instead of forming a judgement. Collected here
because three independent instances make it a theme rather than an anecdote.

| domain | the intuition | what measurement showed |
|---|---|---|
| **feature design** | "it's a ratio, so it's scale-free" | 12 features across 3 channels tracked sample size; `zero_bin_frac` at ρ = −0.858, `sent_n` identical to `window_tweets` (AUC 0.832) |
| **model optimisation** | "int8 quantization is roughly free on CPU" | 12% faster, and **41.4% label agreement with fp32** — barely above the 33% chance rate for three classes |
| **figure design** | "this palette looks clear" | failed 4 of 5 colour-vision checks; grey ↔ teal at **ΔE 1.9** under protanopia, **9.8** with normal vision |

**The principle: a property that can be measured should never be assessed by
eye.**

What makes the three cases comparable is not that the intuitions were careless
— each is a widely held, usually reasonable heuristic. It is that in every case
a cheap, decisive check existed and the intuition was wrong anyway:

* scale-freedom → a Spearman correlation against the size variable;
* quantization safety → 400 tweets scored twice and compared;
* palette legibility → a CVD simulator run over the adjacent pairs.

Each check took minutes. Each overturned a conclusion that would otherwise have
shipped. And critically, **in none of the three would the error have announced
itself**: the ratios looked normalised, the quantized model produced plausible
sentiment scores, and the figures looked fine. All three failure modes are
silent by nature, which is exactly why the checks have to be routine rather
than triggered by suspicion.

---

## 2026-08-13 — Figures: the palette was wrong and it was checkable

The project's original figure palette — navy `#1f3a5f`, teal `#2a8a8a`, amber
`#b06b1f`, grey `#888888` — was chosen by eye and carried into the prototype
figures. Run through a colour-vision validator it fails four of five checks:

| check | result |
|---|---|
| lightness band | FAIL — navy at L 0.347, below the band |
| chroma floor | FAIL — navy, teal and grey read as gray |
| CVD separation | FAIL — grey ↔ teal **ΔE 1.9** under protanopia |
| normal-vision floor | FAIL — grey ↔ teal **ΔE 9.8**, below the floor of 15 |

**ΔE 9.8 means the two series are hard to distinguish even with full colour
vision**, and 1.9 means a protanopic reader sees one colour. Replaced with the
Okabe-Ito set (`#0072B2`, `#E69F00`, `#009E73`, `#CC79A7`), which passes, and
every series additionally carries a direct label and a distinct marker so
identity never rests on colour alone.

Recorded because it is the same lesson as the size-proxy audit in a different
domain: **a property that can be measured should not be assessed by eye.** The
palette looked fine. It was not.

---

## 2026-08-13 — Volume decays, structure persists

**The project's positive contribution.** On the 52 topics that survive at every
lead — prevalence fixed at 0.500, so PR-AUC is directly comparable down the
column:

| lead | volume_only | volume+structure |
|---|---|---|
| 30 min | 0.765 | 0.890 |
| 60 min | 0.795 | 0.888 |
| 120 min | 0.699 | **0.923** |
| 180 min | **0.515** | **0.764** |

**At a three-hour lead, engagement counts alone reach 0.515 against a chance
value of 0.500 — no better than guessing.** Volume plus network structure holds
0.764 on the same topics, the same folds, the same model.

The McNemar p-value for that comparison falls monotonically as the cut-off
moves earlier:

```
lead   30 min → p = 0.3877
lead   60 min → p = 0.2668
lead  120 min → p = 0.1185
lead  180 min → p = 0.0347
```

**The trend is the evidence, not the single significant cell.** Four tests were
run; Bonferroni-corrected α is 0.0125 and p = 0.0347 does not clear it. What
does the work is that the gap widens in the predicted direction at every step —
a pattern four independent tests would be unlikely to produce by chance in that
order, but which this study is too small to confirm formally.

### What it means

This is **the one place in the study where a non-volume channel does something
volume cannot**. Everywhere else the channels re-encode volume; here, structure
carries signal at a horizon where counts have decayed to nothing.

The mechanism is plausible and matches existing theory. Ma, Feng & Lai and Weng
et al. both argue that the *shape* of early diffusion — who is talking to whom,
across how many communities — is informative before raw counts separate. A
topic that will emerge and one that will not can look identical by volume three
hours out, while already differing in how their interaction graphs are wired.
That is exactly the pattern here: volume's discriminative power collapses with
lead time while structure's decays far more slowly.

**Stated at the strength the evidence supports:** consistent with the theory,
directionally clear, effect size large (0.515 vs 0.764), statistically
marginal, n = 52.

---

## 2026-08-13 — One phenomenon at three scales

The study's central finding appears three times, at increasing levels of
aggregation, and the three are the same thing seen from different distances:

| scale | observation | evidence |
|---|---|---|
| **feature** | features re-encode volume under other names | 12 features across 3 channels correlate with window volume above 0.4; `zero_bin_frac` at −0.858, `sent_n` identical to `window_tweets` |
| **model** | channels add nothing over a well-specified volume baseline | full_fusion vs volume_extended, p = 0.6636 |
| **lead** | the extra channels actively *hurt* at long lead | nested design: full_fusion below volume_plus_structure at every lead; p = 0.345 at 180 min where structure alone reaches 0.035 |

The third is the sharpest form. Adding sentiment and temporal features to
volume-plus-structure does not merely fail to help — it **dilutes**. On 52
units, extra features that carry no independent signal cost model capacity and
degrade the arm that would otherwise show the H2 effect most clearly.

**This coherence is what makes the study a study.** Any one of the three could
be dismissed: a feature correlation might not matter predictively, a model-level
null might be underpowering, a lead-level gap might be noise. Together they
identify one mechanism, measured three ways, each consistent with the others.

---

## 2026-08-13 — Methods: the nested lead-time design

The obvious way to draw a lead-time curve is wrong in two independent ways, and
both were only visible after the first run.

**1. Sample composition changes with the lead.** A longer lead requires the
window to start earlier, so more topics fail the "window fits inside the band"
filter: 183 units at 30 min, 129 at 60, 93 at 120, 64 at 180. A raw curve
therefore mixes *performance changing with lead time* with *which topics
survive at each lead* — and the surviving topics at 180 min are systematically
those with late peaks and long observable histories, which is not a random
subsample.

**2. PR-AUC is not comparable across leads.** Prevalence moves with the
surviving sample — 0.279, 0.326, 0.376, 0.422 — and chance PR-AUC *equals*
prevalence. A PR-AUC of 0.62 is well above chance at 30 min and barely above it
at 180. Comparing the raw values down a column compares different things.

**Fixes, both applied.** Lift over chance is reported alongside raw PR-AUC. And
the sweep is re-run on the **52 topics that survive at every lead**, holding
composition fixed so the only thing varying is the cut-off. In that design
prevalence is constant at 0.500 by construction, which also removes the second
problem.

The two designs disagree in an instructive way: on the full sample
`volume_only` looks flat (0.619 → 0.611), suggesting volume is robust to lead
time. On the nested sample it collapses (0.765 → 0.515). The full-sample
flatness was an artifact — later leads retain easier topics, which masks the
decay.

**Generalisable:** any curve plotted against a parameter that also filters the
sample needs the nested version, or it is partly a plot of the filter.

---

## 2026-08-13 — H2 result: structure extends lead time, at marginal significance

H2 claims network and sentiment features extend the achievable lead time beyond
engagement counts alone. **Directionally supported, and the effect is large —
but it reaches only marginal significance and does not survive correction for
the four tests run.**

### Two problems the naive curve has

**1. PR-AUC is not comparable across leads.** The surviving sample changes with
the lead, and so does its prevalence — 0.279 at 30 min, 0.326 at 60, 0.376 at
120, 0.422 at 180. Chance PR-AUC *equals* prevalence, so a raw PR-AUC of 0.62
means something different at each lead. Lift over chance is the comparable
quantity.

**2. The sample composition changes with the lead.** A longer lead needs the
window to start earlier, so more topics fail the "window fits in the band"
filter: 183 units at 30 min, 129 at 60, 93 at 120, 64 at 180. A raw curve
therefore confounds *performance changing with lead time* with *the surviving
topics changing with lead time*.

Both are handled: lift is reported, and the curve is re-run on the **52 topics
that survive at every lead**, which is the only way to isolate the lead effect.

### Full sample (composition varies)

| lead | n | pos | chance | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|---|---|---|
| 30 | 183 | 51 | 0.279 | 0.619 | 0.721 | 0.789 | 0.769 |
| 60 | 129 | 42 | 0.326 | 0.649 | 0.820 | 0.816 | 0.857 |
| 120 | 93 | 35 | 0.376 | 0.641 | 0.687 | 0.739 | 0.677 |
| 180 | 64 | 27 | 0.422 | 0.611 | 0.599 | 0.676 | 0.662 |

Lift over chance, which is the readable version:

| lead | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|
| 30 | +0.341 | +0.442 | +0.510 | +0.490 |
| 60 | +0.324 | +0.494 | +0.490 | +0.532 |
| 120 | +0.265 | +0.311 | +0.363 | +0.301 |
| 180 | +0.189 | +0.177 | **+0.254** | +0.240 |

### Nested comparison — the same 52 topics at every lead

Prevalence is fixed at 0.500 here, so PR-AUC is directly comparable across rows.

| lead | volume_only | volume_extended | volume+structure | full_fusion |
|---|---|---|---|---|
| 30 | 0.765 | 0.906 | 0.890 | 0.883 |
| 60 | 0.795 | 0.884 | 0.888 | 0.858 |
| 120 | 0.699 | 0.817 | **0.923** | 0.880 |
| 180 | **0.515** | 0.620 | **0.764** | 0.699 |

**This is the H2 pattern, and it is stark at three hours.** Engagement counts
alone decay to **0.515 against a chance of 0.500 — volume is dead at a 3-hour
lead.** Volume plus network structure still reaches 0.764.

### Significance, stated with its limits

McNemar, exact, on the common 52-topic subset:

| lead | volume_only vs volume+structure | discordant | volume_only vs full_fusion |
|---|---|---|---|
| 30 | p = 0.3877 | 4 / 8 | p = 0.1094 |
| 60 | p = 0.2668 | 4 / 9 | p = 0.1460 |
| 120 | p = 0.1185 | 4 / 11 | p = 0.4545 |
| 180 | **p = 0.0347** | 6 / 17 | p = 0.3449 |

**The p-value falls monotonically as the lead grows — 0.388, 0.267, 0.119,
0.035 — which is precisely the direction H2 predicts.** The gap between volume
alone and volume-plus-structure widens the earlier the cut-off is placed.

**Three qualifications, none of which should be dropped:**

1. **Four tests were run. Bonferroni-corrected α is 0.0125, and p = 0.0347 does
   not survive it.** The monotone trend across leads is more persuasive than
   the single significant cell, but the cell alone does not clear correction.
2. **It is structure, not fusion.** `volume_plus_structure` shows the effect;
   `full_fusion` does not (p = 0.345 at 180 min) and scores lower at every
   lead in the nested design. Adding sentiment and temporal features **dilutes**
   the signal rather than adding to it — consistent with the H1 finding that
   those channels largely re-encode volume.
3. **n = 52, split 26/26.** The effect size is large — 0.515 versus 0.764 is
   not a subtle difference — but the sample cannot establish it firmly.

### Verdict

**H2 is supported directionally and not statistically.** The honest statement
is that network structure appears to retain predictive signal at lead times
where engagement counts alone have decayed to chance, that the effect grows
with lead time exactly as predicted, and that this study is too small to
confirm it at conventional significance after correction.

That is a weaker claim than "H2 confirmed" and a considerably stronger one than
"no effect found". It is also the most interesting result in the project: the
one place where a non-volume channel demonstrably does something volume cannot.

---

## 2026-08-13 — Baseline specification determines the conclusion

**Same fusion model. Same data. Same metric. Same folds. Opposite conclusions.**

| comparison | PR-AUC | McNemar p | conclusion |
|---|---|---|---|
| full_fusion vs `volume_only` (3 features) | 0.853 vs 0.649 | **0.0059** | H1 supported |
| full_fusion vs `volume_extended` (33 features) | 0.853 vs 0.820 | **0.6636** | H1 not supported |

Nothing changed between those two rows except **which baseline the fused model
was asked to beat**.

**The weak comparison is the one that was originally planned.** The ablation
hierarchy specified in the project design ran chance → single-signal baselines
→ fusion, with volume represented by engagement counts. `volume_extended` did
not exist as a planned arm. It was constructed only because the size-proxy
audit had exiled twelve features from the other channels for encoding volume —
and once those features were identified as volume, the obvious question was
what volume could do if it were *given* them.

Reporting the planned comparison alone would have been **technically true and
substantively misleading**: every number correct, the test correctly executed,
and the conclusion an artifact of the opponent chosen.

### Why this generalises

A fusion claim is a claim about *marginal* contribution. Marginal to what is
not a detail — it is the entire content of the claim. An under-specified
baseline does not merely weaken a comparison; it silently changes what is being
asserted, from "these channels add information" to "these channels add
information that three hand-picked features happen to lack".

The failure is invisible from inside the result. p = 0.0059 looks like a
finding. It is a finding — about a baseline nobody would defend if it were
stated explicitly.

**Operational form of the lesson:** before running an ablation, construct the
strongest version of the baseline you are trying to beat, using every feature
you are willing to grant it. If the hypothesis only survives against the weak
version, that is the result.

This ranks second only to the size-proxy pattern among the transferable
findings here — and the two are connected: the audit that produced
`volume_extended` is the same audit that defeated H1 with it.

---

## 2026-08-13 — The size-proxy finding reappears at model level

The feature-level audit found that twelve features across three channels
encoded sample size under other names. The ablation now shows the same thing at
model level:

* each channel beats the *minimal* volume baseline (p = 0.024, 0.017, 0.029);
* no channel adds anything to a volume model that has been given the exiled
  features (p = 0.66);
* the arm built entirely from size-derived features (`volume_extended`) posts
  the best F1 in the study (0.780).

**These are not two results that happen to agree — they are one phenomenon
observed at two scales.** At feature level it looks like `reciprocity`
correlating with tweet count at ρ = 0.447. At model level it looks like a
fused model failing to beat volume. The mechanism is identical: at this window
size the channels are largely **re-encoding volume rather than adding to it**.

That mutual corroboration is what makes the conclusion credible. A model-level
null alone would be ambiguous — underpowered study, wrong model family, bad
hyperparameters. A feature-level correlation alone would be suggestive but not
decisive about predictive value. Together they identify a specific, measurable
cause.

**This is the report's central claim.**

---

## 2026-08-13 — Independent replication of the negative result

Network structure does not beat volume alone. This has now been found **twice,
by two studies that share almost nothing methodologically**:

| | prototype | this pipeline |
|---|---|---|
| unit | earliest fixed 150 tweets | pre-peak window, 1-hour lead |
| volume control | fixed by construction | measured and audited out |
| model | random forest | gradient-boosted trees |
| prevalence | 0.528 (balanced by sampling) | 0.326 (as observed) |
| negatives | 125 (6 leaked) | 87 (0 leaked) |
| test | Wilcoxon on paired folds | exact McNemar on OOF decisions |
| result | p = 0.81 (recorded), 0.96 (re-run) | **p = 1.0000**, 21 discordant each way |

Different unit definition, different volume control, different model family,
different significance test, different class balance, different negative pool.
Same conclusion.

**An independent replication of one's own negative result is stronger evidence
than either study alone.** The prototype's finding could have been an artifact
of the fixed-150 proxy, or of the leaked negatives, or of the balanced
sampling. It survives the removal of all three.

The 21-versus-21 split is worth stating precisely: the two arms disagree on 42
of 129 units and are right on exactly half each. That is not a small effect
that failed to reach significance — it is the absence of a difference in
direction.

---

## 2026-08-13 — Statistical power: what this study cannot show

**Stated prominently because it qualifies every result above, including the
ones that came out favourably.**

129 units. **42 positives.** Every confidence interval reported here is wide —
typically ±0.10 to ±0.15 PR-AUC. Effects smaller than roughly **0.1 PR-AUC are
not detectable at this sample size.**

**"Not significant" is not "no difference".** `full_fusion` (0.853) may
genuinely be better than `volume_extended` (0.820). This study cannot show it,
and the correct statement is that no difference was detected — not that none
exists.

**The reverse risk matters just as much.** With 42 positives, a comparison
would have needed an implausibly large effect to reach significance. So the
*absence* of a significant fusion benefit is correspondingly weak evidence of
absence. Both the positive and the negative readings are underpowered, and
neither should be presented as settled.

What the study can support: direction, mechanism, and the identification of a
specific confound. What it cannot support: precise effect sizes, or a claim
that fusion is worthless.

**Underpowered-but-honest is the correct framing**, and it is preferable to a
better-looking number obtained by relaxing the censoring filters, the size
audit or the baseline specification — each of which was available and each of
which was declined.

### Resampling noise, measured

The robustness checks happened to use a different CV seed and splitter from the
headline table, which quantifies how much of the ablation table is signal. On
**identical data and identical features**:

| arm | headline table | robustness run | difference |
|---|---|---|---|
| full_fusion | 0.853 | 0.868 | +0.015 |
| volume_only | 0.649 | 0.621 | −0.028 |
| volume_extended | 0.820 | 0.821 | +0.001 |

**Roughly ±0.02–0.03 PR-AUC moves from the resampling choice alone.** That is
the same order as several of the differences between arms in the main table —
`volume_extended` (0.820) versus `full_fusion` (0.853) is a 0.033 gap, barely
outside this range.

**Consequence for reading the results:** point estimates in the ablation table
should not be ranked against each other at the third decimal, and differences
below about 0.05 PR-AUC carry no interpretation. The bootstrap intervals, not
the point estimates, are the reportable quantity. This is an additional reason
the H1 comparison resolves to a null rather than a narrow win.

---

## 2026-08-13 — PR-AUC over ROC-AUC, demonstrated rather than cited

Saito & Rehmsmeier (2015) show that ROC curves are misleading under class
imbalance, because a large negative pool suppresses the false-positive rate
even when precision is poor. That principle is demonstrated directly on this
data by the `sentiment_only` arm:

| metric | sentiment_only | chance |
|---|---|---|
| ROC-AUC | **0.783** | 0.500 |
| PR-AUC | **0.564** | **0.326** |

On ROC-AUC it reads as a solid channel, comfortably above chance. Against a
chance PR-AUC of 0.326 — the actual prevalence — it is the **weakest arm in the
study**, below even the three-feature volume baseline.

The gap is not subtle and it is not hypothetical: it is the difference between
reporting sentiment as a contributing channel and reporting it as the least
informative one. A cited principle demonstrated on one's own data is worth more
than the citation alone.

---

## 2026-08-13 — A determinism guarantee that was documented but not in force

`n_jobs=1` was chosen deliberately for bit-reproducibility, recorded in
`CLAUDE.md`, and read from config at model-construction time. It was then
**silently discarded**: `HistGradientBoostingClassifier` has no `n_jobs`
parameter — it parallelises through OpenMP — so the value went nowhere.

The exposure is real. Histogram reductions are summed in thread-completion
order, so a machine with a different core count can differ in low-order bits
and, on a knife-edge split, grow a different tree. The published numbers would
not have been reproducible off this hardware.

Two details worth recording:

* **It was found by lint**, not by any result looking wrong. `ruff` flagged
  `n_jobs` as an assigned-but-unused variable. No output was incorrect, no
  score was suspicious, and no test failed.
* **Re-running with threads pinned reproduced every figure exactly.** The
  numbers were not thread-dependent on this machine. The fix therefore removes
  a **latent** reproducibility risk rather than correcting an error.

A guarantee that is documented, configured, and not actually in force is worse
than one that was never claimed — it invites exactly the trust it does not
earn.

---

## 2026-08-13 — H1 result: fusion beats a weak volume baseline, not a strong one

Full ablation, 129 units, prevalence 0.326. **Chance PR-AUC is 0.326**;
chance ROC-AUC is 0.500. Out-of-fold predictions, 5-fold stratified CV grouped
by topic, bootstrap CIs over 1,000 resamples.

| arm | k | PR-AUC | 95% CI | ROC-AUC | F1 |
|---|---|---|---|---|---|
| chance | 0 | 0.326 | — | 0.500 | — |
| volume_only | 3 | 0.649 | [0.509, 0.771] | 0.724 | 0.571 |
| sentiment_only | 9 | 0.564 | [0.435, 0.745] | 0.783 | 0.617 |
| temporal_only | 9 | 0.654 | [0.512, 0.789] | 0.764 | 0.622 |
| structure_size_free | 10 | 0.689 | [0.551, 0.804] | 0.730 | 0.561 |
| structure_residualised | 10 | 0.707 | [0.570, 0.819] | 0.802 | 0.593 |
| volume_plus_sentiment | 12 | 0.789 | [0.673, 0.882] | 0.843 | 0.692 |
| volume_plus_temporal | 12 | 0.783 | [0.669, 0.872] | 0.827 | 0.700 |
| volume_plus_structure | 13 | 0.829 | [0.719, 0.910] | 0.869 | 0.709 |
| **volume_extended** | 33 | **0.820** | [0.701, 0.912] | 0.889 | **0.780** |
| full_fusion_regularised | 31 | 0.822 | [0.723, 0.904] | 0.855 | 0.667 |
| **full_fusion** | 31 | **0.853** | [0.756, 0.927] | 0.891 | 0.727 |

### The headline is a negative result

**H1 claims the fused model significantly beats the best single-signal
baseline. It does not.**

The best single-signal baseline is **not** `volume_only`. It is
`volume_extended` — still volume alone, but given every size-derived feature
the audit exiled from the other channels. Against that opponent:

| comparison | PR-AUC | McNemar p |
|---|---|---|
| full_fusion vs **volume_only** | 0.853 vs 0.649 | **0.0059** |
| full_fusion vs **volume_extended** | 0.853 vs 0.820 | **0.6636** |
| volume_plus_structure vs volume_extended | 0.829 vs 0.820 | 0.4244 |

Fusion beats the three-feature baseline decisively and the full volume baseline
not at all. Confidence intervals overlap almost completely, and
`volume_extended` actually posts the **best F1 of any arm (0.780)**.

Reporting only the first row would have been the easy result and it would have
been misleading. Choosing a weak opponent is the most common way a fusion claim
passes.

### What *is* supported

Each channel adds to volume individually — all three paired tests clear 0.05:

| comparison | McNemar p |
|---|---|
| volume_only vs volume_plus_structure | 0.0241 |
| volume_only vs volume_plus_sentiment | 0.0169 |
| volume_only vs volume_plus_temporal | 0.0290 |

So the channels carry information the minimal volume baseline lacks. What they
do **not** carry is information beyond what a well-specified volume model
already captures. The most defensible reading: on this corpus, at this window
size, the three channels are largely **re-encoding volume** rather than adding
independent signal — which is exactly what the size-proxy audit found at the
feature level, now confirmed at the model level.

### The prototype's negative result replicates

`volume_only` vs `structure_size_free`: **21 discordant each way, p = 1.0000.**
Network structure does not beat volume alone. The prototype found the same
thing (Wilcoxon p = 0.81 as recorded, 0.96 on re-run) with a different unit
definition, a different volume control and a different model family. Two
independent designs, same conclusion.

### Robustness checks

* **Residualisation does not change the story.** `structure_residualised`
  (0.707) vs `structure_size_free` (0.689), McNemar p = 0.6776. The
  conservative exile and the less-conservative residualisation agree, so the
  conclusion is not an artifact of how the volume confound was handled. The
  residualised arm is the *less* conservative one and is not the headline.
* **Overfitting is present but not decisive.** `full_fusion` (0.853) vs
  `full_fusion_regularised` (0.822), p = 0.0923, 10 units correct only under
  the unregularised model against 3 the other way. With **31 features against
  42 positive cases — close to one parameter per positive** — the unregularised
  arm should be read with that ratio in mind. The gap is evidence about
  capacity, not about fusion.
* **PR-AUC versus ROC-AUC diverges exactly as predicted.** `sentiment_only`
  scores ROC-AUC 0.783 but PR-AUC 0.564. On ROC alone it would look like a
  solid channel; against a chance PR-AUC of 0.326 it is the weakest arm in the
  study. This is the concrete case for the headline-metric choice.

### Caveats stated rather than buried

129 units and 42 positives. Every CI is wide, the folds are small, and effects
smaller than roughly 0.1 PR-AUC are not detectable here. `full_fusion` may
genuinely be better than `volume_extended` — this study cannot show it.
"Not significant" is not "no difference".

---

## 2026-08-13 — Why the prototype's best network features do not survive here

**This single explanation links the two studies and accounts for why their
numbers differ. It belongs in the report as its own subsection.**

The prototype's two strongest network features were `reciprocity` (univariate
AUC 0.66, RF importance 0.073) and `mean_clustering` (0.64). In this pipeline
both were **removed from the structure arm** because they correlate with window
volume at ρ = +0.447 and +0.556.

They were not wrong there and right here. **They were sound there and unsound
here, and the difference is a single design choice.**

| | prototype | this pipeline |
|---|---|---|
| unit of observation | earliest **fixed 150 tweets** per topic | variable-length **pre-peak window** |
| tweets per graph | identical by construction | 15 to 1,308 |
| volume as a confound | **controlled by design** | present and must be measured out |
| pre-peak guarantee | none — "early" is a proxy | window closes at peak − lead |

Holding the tweet count fixed makes every graph the same size, so any
difference in reciprocity or clustering between two topics *cannot* be a
difference in volume. The measure is volume-controlled by construction.

A pre-peak window cannot do that. Its length is fixed in *time*, not in tweets,
because the whole point is to observe a fixed lead before the peak. Volume
therefore varies by two orders of magnitude across units, and any feature whose
value depends on graph density inherits it.

**Three consequences worth stating plainly.**

1. **The prototype's design was doing more work than it appeared to.** The
   fixed-150 choice was documented as being about comparability and about
   isolating structure. It was also, unremarked, the reason its structural
   features were interpretable at all. That is a stronger justification for the
   choice than the one originally given.
2. **The exchange was real and it had a price.** Trading fixed-K for a genuine
   pre-peak window bought the central claim of the project — prediction before
   peak rather than early detection — and cost the volume control that made the
   prototype's best structural features clean.
3. **The two sets of numbers are not comparable and must never be tabled
   together.** Different units, different volume control, different prevalence
   (0.528 balanced vs 0.326 observed). They are reported separately throughout.

---

## 2026-08-13 — Normalising a count series does not make it scale-free

Every temporal feature was divided by its own window level specifically to be
scale-free. **Twelve of them still tracked volume**, and the audit caught it
because the audit is now a measurement rather than an argument.

### The mechanism, spelled out

For a Poisson count process with rate λ per bin, the mean is λ and the variance
is **also** λ. So the standard deviation is √λ, and the coefficient of
variation is

```
CV = σ/μ = √λ / λ = 1/√λ
```

Dividing a count series by its own mean removes the *scale* but not the
*noise*, because for counts the noise is a function of the scale. A window
averaging 4 tweets per bin has an expected CV of 0.50 purely from sampling; a
window averaging 100 has 0.10. **Any "normalised dispersion" feature is
therefore a disguised measure of inverse volume**, and will separate a
large-count class from a small-count class with no underlying difference in
process whatsoever.

A second, independent route runs through discretisation: low counts produce
empty bins. Zero-share is directly a function of λ; entropy is bounded above by
the log of the number of *non-empty* bins; Gini and monotonicity are both
distorted by ties at zero. Every one of those inherits volume without any
dispersion argument at all.

Neither route is visible in the algebra. `std/mean` looks scale-free. It is
not, for counts.

### The general rule

> **A feature's algebraic form does not tell you whether it encodes sample
> size. Only its measured correlation with sample size does.**

This is the most transferable result the project has produced. It applies to
any study comparing groups that differ in sample size — which is most
observational work — and it defeats the usual defence of "but it's a ratio, so
it's normalised". Ratios of counts are not normalised with respect to counts.

The operational form is cheap: correlate every candidate feature against the
sample-size variable (Spearman, so monotone-but-nonlinear proxies are caught),
fix the threshold *before* looking, and reassign anything above it. In this
project that check moved twelve features across three channels, four of which
had already been cleared by formula-level reasoning.

Measured Spearman correlation with window volume:

| feature | ρ with volume | AUC | verdict |
|---|---|---|---|
| `zero_bin_frac` | **−0.858** | 0.741 | discretisation artifact of low counts |
| `bin_entropy` | +0.686 | 0.628 | bounded by number of non-empty bins |
| `bin_gini` | −0.593 | 0.589 | same mechanism, inverted |
| `arima_resid_cv` | −0.568 | 0.571 | Poisson dispersion |
| `burstiness` | −0.557 | 0.562 | CV of counts ~ 1/√mean |
| `monotone_up_frac` | +0.509 | 0.643 | ties at zero suppress increases |
| `acf1` | +0.470 | **0.855** | highest temporal AUC — and arguable, so volume |
| `arima_ma1` | +0.433 | 0.622 | arguable, so volume |

All eight moved to the volume arm, including `acf1`, which was the strongest
temporal feature by a wide margin. Nine survive.

**The audit was then applied to the channels that had already been assigned by
reasoning, and it moved four more.**

| feature | arm it was in | ρ with volume |
|---|---|---|
| `mean_clustering` | structure | **+0.556** |
| `core2_frac` | structure | +0.505 |
| `modularity` | structure | +0.447 |
| `reciprocity` | structure | +0.447 |

All four are bounded ratios, which is why reasoning kept them. But on graphs
this sparse — `reciprocity` is exactly zero on 85% of units, `mean_clustering`
on 80% — their value is dominated by whether the window contained enough tweets
to form a mutual edge or a triangle *at all*. They measure "big enough to have
structure", which is volume.

**This costs the structure arm the prototype's two strongest network features**
(`reciprocity` AUC 0.66, `mean_clustering` 0.64 in the prototype). The reason
they were sound there and not here is a design difference worth stating: **the
prototype built every graph from a fixed 150 tweets, which controlled volume by
construction.** A variable-length pre-peak window does not. Fixing the tweet
count was a deliberate choice to isolate structure, and this is the price of
giving it up in exchange for a real pre-peak window.

`core3_frac` sits at ρ = +0.390, just inside the threshold. It is kept, and
flagged as marginal, because the 0.4 threshold was fixed before these numbers
existed — moving it afterwards would be changing the rule to suit the result.

**Final arms:** volume_only 3 · structure_size_free 10 · sentiment 9 ·
temporal 9 · full_fusion 31 · volume_extended 33. Cross-channel audit now
reports 0 of 28 non-volume features above threshold.

**Methodological note.** The temporal channel was audited by measurement
because three previous channels had shipped a size proxy. Measurement then
overturned reasoning in *both* directions it was pointed at — eight temporal
features and four network ones that formula-level argument had cleared. The
generalisable lesson is not "check for counts" but: **a feature's algebraic
form does not tell you whether it encodes sample size; only its correlation
with sample size does.**

---

## 2026-08-13 — Decided in advance: no LSTM on 129 units

CLAUDE.md's original plan lists LSTM embeddings of the early volume curve as
part of the temporal channel. **That is not being built as a headline
component**, and the reasoning is recorded here *before* the temporal results
exist so the report shows a judgement made in advance rather than a capability
gap discovered afterwards.

1. **129 units cannot support a sequence model.** A recurrent network over
   per-unit volume curves has more parameters than the study has examples, by
   orders of magnitude.
2. **Gradient-boosted trees are already the designated primary fusion model**,
   for exactly this reason. An LSTM would not be the model under test.
3. **The failure mode is directional, and it points the wrong way.** An
   overfitted LSTM embedding would inflate whichever arm contains it — the
   fusion arm — which is the arm H1 is about. A component that flatters the
   hypothesis under test is worse than no component.

The temporal channel is therefore ARIMA residuals plus normalised shape
features. If time permits, an LSTM will be run as a **reported negative** — an
explicit demonstration that it overfits at this sample size — rather than as a
contributing feature.



## 2026-08-13 — Sparse graphs: the added structure has little to bite on

At a 90-minute window the interaction graphs are mostly disconnected star
fragments. Non-trending windows average 46 Spanish tweets.

Share of units where the feature is exactly zero:

| feature | zero |
|---|---|
| `core3_frac` | 91.5% |
| `reciprocity` | 85.3% |
| `max_betweenness` / `mean_betweenness` | 80.6% |
| `mean_clustering` | 79.8% |
| `core2_frac` | 62.8% |

**This is a constraint of the window size, not a modelling failure.** Mentions
and replies are sparse over 90 minutes for topics this small, so betweenness
(best univariate AUC 0.597) and the deeper k-core features are near-degenerate.

**The distinction matters for the report:** if the structure arm underperforms,
that is evidence about *sample geometry* — 129 small, fragmented graphs — and
not evidence that interaction structure carries no signal about emergence. The
two claims are different, and only the first is supported by this corpus. The
window-length sensitivity analysis is what separates them empirically.

---

## 2026-08-13 — The conservative assignment rule cost four features, and was applied anyway

When the size-free structure arm was defined, `density`, `max_pagerank`,
`largest_wcc_frac` and `largest_community_frac` had all been described — by me,
one step earlier — as size-independent structural features on the strength of
being ratios and bounded fractions.

They are not. On fragmented graphs all four are mechanically ~1/N, and all four
run *higher* for the smaller non-trending graphs (`density` 0.005 vs 0.014,
`max_pagerank` 0.036 vs 0.074, `largest_wcc_frac` 0.184 vs 0.249,
`largest_community_frac` 0.096 vs 0.170). Being a ratio is not the same as
being scale-free.

Under the rule — *where assignment is arguable, it goes to volume* — all four
moved out of the structure arm, taking `largest_community_frac` (AUC 0.763) and
`max_pagerank` (0.749) with them, two of the strongest apparently-structural
separators.

**That is the rule working as intended.** It makes H1 harder to pass. A
structure arm assembled from quantities that quietly encode node count could
produce "structure beats volume" arithmetically; one assembled under this rule
cannot, which is precisely what would give a positive result its value.

---

## 2026-08-13 — Three measurements that contradicted the obvious assumption

### int8 quantization would have turned the sentiment channel into noise

The standard assumption is that int8 dynamic quantization is roughly free on
CPU — large speedup, negligible accuracy cost. Benchmarked on 400 real Spanish
tweets from this corpus:

| | throughput | agreement with fp32 |
|---|---|---|
| fp32, batch 16, length-sorted | 35.2 tweets/s | — |
| int8 dynamic, batch 32, sorted | 39.5 tweets/s | **41.4%** |

**12% faster, and it agrees with the full-precision model on 41.4% of labels —
barely above the 33% chance rate for three classes.** Dynamic quantization
destroys this model.

**Counterfactual, and the reason this is worth recording:** had the assumption
been taken rather than tested, every sentiment feature in the fusion model
would have been noise, and nothing downstream would have looked wrong. The
channel would simply have failed to contribute, and that failure would have
been reported as a finding about sentiment rather than a bug in the pipeline.
Rejected on measurement.

### Length-sorting beats batching, and the bigger batch is slower

| config | tweets/s |
|---|---|
| batch 16, unsorted | 26.1 |
| **batch 16, length-sorted** | **35.2** |
| batch 32, unsorted | 22.8 |
| batch 32, length-sorted | 29.3 |

Sorting by length before batching gives **+35%**, because padding is charged
per batch and mixed-length batches pad short tweets up to the longest one.
Doubling the batch size makes throughput *worse* — the opposite of the usual
expectation — since wider batches gather a broader length spread and pad more.
Small sorted batches win.

### A substring bug in my own validator

The check that keeps raw counts out of the size-free structure arm matched
banned names by substring. `mean_clustering` contains `n_`, so the validator
rejected a legitimate scale-free feature. Fixed to prefix matching plus an
explicit name list.

This is the **second defect found in checking code rather than in the pipeline**
— the first being `betweenness_exact`, a metadata flag emitted as a feature.
Both were caught by running the checks and reading the output rather than
trusting that a guard works because it exists.

---


## 2026-08-13 — Sentiment signal is real but weak; the strongest is disagreement

XLM-T over 20,505 distinct Spanish tweets, 100% window coverage (median 30
tweets per window, min 15, max 1,308).

| feature | trending | non-trending | AUC |
|---|---|---|---|
| `sent_polarisation` | 0.318 | 0.215 | **0.673** |
| `sent_var` | 0.236 | 0.187 | **0.670** |
| `sent_neg_frac` | 0.314 | 0.275 | 0.596 |
| `sent_mean` | −0.078 | −0.020 | 0.588 |
| `sent_intensity` | 0.566 | 0.535 | 0.579 |
| `sent_neu_frac` | 0.464 | 0.511 | 0.578 |
| `sent_skew` | −0.127 | −0.105 | 0.528 |

**The two strongest features measure disagreement, not mood.** `sent_var` and
`sent_polarisation` (the share of the window in the smaller of the positive and
negative camps, doubled) both beat every measure of average sentiment.
Emerging topics are more *contested*, not simply more negative — though they
are slightly more negative too.

**Mechanism.** Mean polarity cannot distinguish a split crowd from a calm one,
because both average to zero. A window in which half the tweets are strongly
positive and half strongly negative has the same `sent_mean` as a window of
uniform indifference. Variance and polarisation are the only features in the
set that separate those two situations, and they are the two that discriminate
best — which is the reason `sent_polarisation` was defined at all.

**This is a substantive result for the report, not just a feature ranking.**
Stieglitz & Dang-Xuan (2013) established that emotionally charged messages are
shared more than neutral ones — charge drives diffusion. The result here points
somewhere more specific: within charged content, what marks *emergence* is
**disagreement rather than valence**. Emerging topics are not
systematically more positive or more negative; they are more contested. That
extends the existing finding rather than reproducing it, and it is directly
testable — it predicts that a valence-only sentiment feature set should
underperform one containing dispersion measures, which the ablation will show
either way.

Caveat kept in view: no individual sentiment feature is strong (best 0.673).
Whether the channel contributes is an ablation question, not a univariate one,
and the mechanism above is a hypothesis the ablation can support or fail to
support — not something these AUCs establish on their own.

---

## 2026-08-13 — VADER covers too few negatives to be an arm

VADER was specified as an English-subset baseline. It cannot serve as one here,
and the reason is not thin coverage but **confounded coverage**: which units
VADER can score is itself determined by the label.

The trending pool is multilingual (43.7% English); the non-trending pool is
88.8% Spanish. So English presence in a window is a *marker of the positive
class*. VADER's covered subset is **77% positive against a corpus prevalence of
0.326** — a classifier that predicted "trending" purely from "this unit has
enough English to score" would already beat chance. Any VADER-based arm would
be measuring that, not sentiment.

This is why the check is descriptive. It is not a caveat attached to an
otherwise valid baseline.

Measured coverage over the final 129 units:

| | |
|---|---|
| units with any English tweet in window | **44 of 129** |
| — trending | 34 |
| — **non-trending** | **10** |
| English tweets scored | 19,148 |
| median English tweets per covered unit | 47.5 |

**Ten negative units could not support an ablation arm even without the
confound.**

Worth being precise about what VADER is scoring: the main channel is filtered
to Spanish, so VADER is not a second opinion on the same tweets. It scores a
**different tweet population, in a different language, drawn disproportionately
from the positive class.** It is reported as a descriptive check on the English
remainder, never as a baseline the fusion model is compared against.

---

## 2026-08-13 — Sentiment model pinned to an exact revision

`cardiffnlp/twitter-xlm-roberta-base-sentiment`, revision
**`f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8`**, recorded in `config.yaml`.

HuggingFace `main` can move at any time. Unpinned, a re-run months later could
produce different sentiment numbers for identical inputs with nothing in the
repository to explain the change. Pinning costs nothing and makes every
sentiment figure traceable to one model version.

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

**Final setting: ≥50 tweets, 60-min lead, 90-min window, ≥15 window tweets →
129 units (42 trending / 87 non-trending).** Floor cleared. Full decision record
in [`outputs/tables/parameter_decision.md`](outputs/tables/parameter_decision.md);
sensitivity across 15/20/25 is reported at evaluation.

---

## 2026-08-08 — Prevalence is 0.326, and that settles the headline metric

The prototype was **artificially balanced** — 140 trending against 125
non-trending, prevalence 0.528, because both classes were sampled to a target
size. This pipeline is not balanced. Negatives are what the corpus yields after
censoring, so the real class split is **42 / 87 — prevalence 0.326**.

**Consequence: PR-AUC is the correct headline metric here as a matter of fact,
not of taste.**

- **Chance PR-AUC is 0.326**, not 0.5. Any PR-AUC must be read against that
  baseline, and a model scoring 0.33 has learned nothing.
- Chance ROC-AUC remains 0.5 regardless of prevalence. That is exactly why ROC
  misleads under imbalance (Saito & Rehmsmeier, 2015): the larger negative pool
  suppresses false-positive rate, so ROC-AUC stays flattering while precision
  quietly degrades.
- **Every ROC number reported in this project must be read against a PR-AUC
  from the same run.** ROC-AUC alone overstates performance on a 0.326-
  prevalence problem.

This also means the prototype's ROC figures and this pipeline's ROC figures are
**not directly comparable** — different prevalence, different unit definition.
They are reported separately and never merged into one table.

---

## 2026-09-24 — The ARIMA order was never justified, and the data rejects it

External review of the draft asked why the temporal channel uses ARIMA(1,1,1).
There was no answer. The order was chosen by convention and hardcoded in
`src/features/temporal.py`, in a project whose own rule is that no magic
numbers live in code. The reviewer was right to ask, and the result is worse
than "unjustified".

### What the selection shows

`src/eval/arima_order.py` fits a 16-order grid to all 129 pre-cutoff histories
— the exact series the feature extractor sees — and scores AIC and BIC over the
units where every order converged. All 129 converged under every order, so the
comparison rests on the full sample. The procedure reads **no labels**, so it
cannot leak outcome information into the features.

**Differencing is justified.** ADF and KPSS disagree on the levels and agree
after first differences, which is the pattern that supports `d = 1`:

| test | on levels | on first differences |
|---|---|---|
| ADF rejects unit root | 51.9% | **84.5%** |
| KPSS rejects stationarity | 54.3% | **10.9%** |

**The order was not.**

| order | mean AIC | mean BIC | AIC wins | BIC wins |
|---|---|---|---|---|
| **(0,1,2)** | **192.13** | **197.33** | 34 | **52** |
| (0,1,1) | 195.69 | 199.21 | 2 | 35 |
| (1,1,2) | 192.86 | 199.80 | 12 | 9 |
| **(1,1,1)** — the order in use | 195.76 | 201.04 | **0** | **0** |

(1,1,1) is not merely suboptimal. It wins on **zero of 129 units** under either
criterion. The data prefers **no AR term at all**.

That matters more than a model-fit statistic, because the AR coefficient was
not just fitted — it was a *feature*. `arima_ar1` stood at the top of the
permutation-importance table for `full_fusion` (+0.040 ± 0.037). The model's
most informative temporal input was a coefficient estimating something the
series does not contain.

### What changed when (0,1,2) was adopted

The order determines which coefficients exist, so the feature set changes with
it. `coefficient_names()` now derives the columns from the order, and the
coefficients are read out by statsmodels' own parameter names rather than by
position — positional indexing returns a different parameter the moment the
order moves, which is precisely the change the code now has to survive.

| | under (1,1,1) | under (0,1,2) |
|---|---|---|
| coefficients emitted | `arima_ar1`, `arima_ma1` | `arima_ma1`, `arima_ma2` |
| assigned to temporal | `arima_ar1` | `arima_ma2` (rho −0.112) |
| assigned to volume | `arima_ma1` (rho +0.433) | `arima_ma1` (rho **+0.557**) |
| temporal channel size | 9 features | 9 features |

The audit was re-run, not assumed. `arima_ma1` fails it harder under the new
order (rho +0.433 → +0.557, AUC 0.810), and `arima_ma2` passes cleanly. The
conservative rule was applied exactly as before, and the channel happens to
contribute the same number of features, so every arm's feature count is
unchanged and the ablation remains comparable.

### Every number that moved

Only arms that touch the temporal channel moved. The rest are bit-identical,
which is itself the check that the change was surgical rather than diffuse.

| arm | (1,1,1) | (0,1,2) | Δ |
|---|---|---|---|
| volume_only | 0.649 | 0.649 | — |
| structure_size_free | 0.689 | 0.689 | — |
| sentiment_only | 0.564 | 0.564 | — |
| volume_plus_structure | 0.829 | 0.829 | — |
| volume_plus_sentiment | 0.789 | 0.789 | — |
| structure_residualised | 0.707 | 0.707 | — |
| **temporal_only** | 0.654 | **0.565** | **−0.089** |
| **volume_plus_temporal** | 0.783 | **0.747** | **−0.036** |
| full_fusion | 0.853 | 0.856 | +0.003 |
| full_fusion_regularised | 0.822 | 0.820 | −0.002 |
| volume_extended | 0.820 | 0.805 | −0.014 |

**The temporal channel is weaker than it looked.** Standing alone it drops from
0.654 to 0.565 — from clearly above the 3-feature volume baseline to level with
sentiment, the weakest channel. Nearly all of the temporal channel's apparent
standalone signal was carried by a coefficient the data does not support.

Fusion is unmoved (+0.003), which is the expected shape: a 31-feature
gradient-boosted model does not depend on any single input, and what `arima_ar1`
was contributing is recoverable from the other 30 columns.

### Effect on the hypotheses

**H1 — still not supported, and the test is now cleaner.**

| | (1,1,1) | (0,1,2) |
|---|---|---|
| full_fusion vs volume_extended | 0.853 vs 0.820 | 0.856 vs 0.805 |
| McNemar | 9 / 12 discordant, p = 0.6636 | **10 / 10 discordant, p = 1.0000** |

The PR-AUC gap widened to 0.051 while the decision-level test moved to a perfect
tie. Those two facts are not in tension: PR-AUC scores the *ranking*, McNemar
scores the *decisions at threshold 0.5*, and at this sample size a 0.05 ranking
difference is inside the ±0.02–0.03 resampling noise already recorded. The two
models are wrong about a different case exactly ten times each. **Where the two
disagree, the decision-level test is the one to quote**, because it is paired on
identical units and makes no distributional assumption.

**H2 — completely unchanged.** Every nested lead-time number and every H2
p-value is identical to four decimal places (0.3877, 0.2668, 0.1185, 0.0347),
because neither `volume_only` nor `volume_plus_structure` contains a temporal
feature. The H2 evidence never depended on the ARIMA specification. That is a
property of the arms chosen for the test, not luck this time.

**The language confound — one number flipped, the conclusion did not.** Inside
the common-support band (n = 43), `volume_extended` moved 0.712 → **0.811**,
so the previously recorded framing — *"language (0.716) matches
`volume_extended` (0.712)"* — no longer holds. The correct statement is the
weaker and more defensible one: **language alone still scores 0.716 in the band
built to neutralise it, a lift of +0.367 over the 0.349 chance rate.** At n = 43
nothing separates 0.716 from 0.811, and it was always a mistake to lean on a
rank ordering between two arms in a 43-unit sample. The confound surviving
restriction is the finding; which arm leads inside the restriction is noise.

### Two process changes

**`RESULTS_SUMMARY.md` is now generated, not typed.** Every number is read from
the result JSONs by `src/eval/results_summary.py`. The re-run above is exactly
the event that would previously have left a hand-maintained summary half-updated
— which is the inconsistency the draft review flagged. A generated file cannot
drift from the run that produced it, and cannot be partially corrected.

**The Spanish-share quantiles are now saved, not printed.** The class overlap in
language is the entire argument for why within-language restriction is
impossible, and a number that only ever reached a console could not be checked
against the report.

### What this says about the review

The internal audits in this project were aimed at one failure mode — features
that track volume — and they caught every instance of it, including four in
checking code. They could not catch this, because `arima_ar1` was not a volume
proxy. It was an honest feature of a model whose specification nobody had
tested. Different failure mode, different check required, and the check came
from outside. That is an argument for external review as a distinct instrument
rather than a backstop for the internal one.
