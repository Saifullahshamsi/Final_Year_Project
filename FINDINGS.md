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

## 2026-08-13 — Normalising a count series does not make it scale-free

Every temporal feature was divided by its own window level specifically to be
scale-free. **Twelve of them still tracked volume**, and the audit caught it
because the audit is now a measurement rather than an argument.

**The mechanism, which generalises well beyond this project.** For count data,
dividing by the mean does not remove size dependence, because the *noise* also
scales with the mean. Under a Poisson process the coefficient of variation goes
as `1/√mean`, so a "normalised dispersion" measure is a disguised inverse
volume. Sparse windows separately produce more empty bins, so every entropy,
Gini, zero-share and monotonicity measure inherits volume through the
discretisation.

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
