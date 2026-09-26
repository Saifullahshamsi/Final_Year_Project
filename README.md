# Predictive Modelling of Social Media Trend Emergence

[![CI](https://github.com/OWNER/REPO/actions/workflows/ci.yml/badge.svg)](https://github.com/OWNER/REPO/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)

> Final-year undergraduate data science project. Offline study on a static
> historical corpus — no real-time system, no deployment.

## What this does

Predicts **topic-level trend emergence on Twitter 1 hour before peak** — a
forecasting task, not post-hoc trend detection. The unit of analysis is a
*topic* (a hashtag), and features are extracted from a window that closes
strictly before the topic's peak, so the model never sees the outcome it is
predicting.

**Research question.** Can fusing early temporal, sentiment and
network-diffusion signals predict, ahead of peak, whether a topic will emerge
as a trend, more accurately than single-signal baselines?

- **H1** — the fused model significantly beats the best single-signal baseline.
- **H2** — network and sentiment features extend achievable lead time beyond
  engagement counts alone.

The contribution is **signal fusion**: three feature channels that the
literature studies in isolation, combined, with each channel's marginal
contribution isolated by ablation.

## Architecture

```
raw corpus (2 CSVs, ~1.2 GB, 2020-02-25)
  ↓  clean          strip .csv / # from labels, de-dup on (id, topic), parse timestamps
  ↓  restrict       16:00–23:59 — the only band both pools cover
  ↓  units          bin activity → detect peak → drop left- and right-censored topics
  ↓                 → emit windows ending a fixed lead before peak
  ↓  features       ┌─ temporal   normalised curve shape + ARIMA(0,1,2) residual features
  ↓                 ├─ sentiment  XLM-T multilingual polarity, VADER (English baseline)
  ↓                 └─ network    mention/reply interaction-graph structure
  ↓  audit          size-proxy audit: |Spearman| vs window_tweets >= 0.4 reassigned to volume
  ↓  fusion         gradient-boosted trees over the concatenated channels
  ↓  evaluation     PR-AUC (headline), grouped CV, ablation, lead-time curve, significance
```

| Channel | Content | Features kept after audit | Status |
|---|---|---|---|
| Network | mention/reply interaction-graph structure | 10 size-free of 32 | done |
| Temporal | normalised shape + ARIMA(0,1,2) residuals | 9 size-free of 17 | done |
| Sentiment | XLM-T multilingual polarity | 9 | done |

No LSTM. With 129 units and 42 positives a sequence model would overfit the
arm under test; the decision was taken before any model ran and the rationale
is recorded in [FINDINGS.md](FINDINGS.md).

## Status

| Stage | State |
|---|---|
| Corpus verification | done — see [FINDINGS.md](FINDINGS.md) |
| `src/data/loading.py` — streaming, parsing, binning | done |
| `src/data/units.py` — peak detection, censoring, windows | done |
| Language control (tweet-level) | done — **the control fails; see Results** |
| Network channel | done |
| Sentiment channel | done |
| Temporal channel | done |
| Fusion + ablation | done — 12 arms |
| Lead-time sweep, robustness, figures | done |

The pipeline is complete end to end. 182 tests pass, lint is clean, and every
number below traces to a script in this repository.

## Setup

Requires Python 3.12.

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -r requirements.txt
```

On Linux/macOS use `.venv/bin/python` throughout.

## Get the data

The corpus is **not in this repository** — it is ~1.2 GB, and republishing raw
tweet text would breach the terms it was collected under. Full instructions,
schema, and the quirks the loaders handle are in
[`scripts/get_data.md`](scripts/get_data.md). Place the two CSVs under
`dataset/` and everything else resolves from [`config.yaml`](config.yaml).

## Run the pipeline

Every tunable lives in [`config.yaml`](config.yaml) — bin size, lead time,
window length, thresholds, seeds, paths. There are no magic numbers in code.

```bash
.venv/Scripts/python -m src.data.units --sweep
```

Parameter grid over (min topic size × lead × window), with and without the
language filter. Writes `outputs/tables/units_sweep.json`.

```bash
.venv/Scripts/python -m src.data.units
```

Builds the units at the configured primary setting. Prints per-filter
attrition, class balance, and the censoring filter's measured accuracy. Writes
`outputs/cache/units.csv` and `outputs/tables/units_summary.json`.

Reproduce the frozen prototype, and the same prototype with the negative-pool
leak corrected:

```bash
.venv/Scripts/python prototype/rerun/extract.py --mode frozen --out outputs/cache/proto_frozen_features.csv
```

```bash
.venv/Scripts/python prototype/rerun/evaluate.py --features outputs/cache/proto_frozen_features.csv --out outputs/tables/proto_frozen_results.json --tag frozen
```

Swap `--mode fixed` and the matching filenames for the corrected run.

### Regenerating every result from a clean checkout

Given the dataset in `dataset/`, run these in order. Each depends on the
previous one's cached output; nothing is hand-edited at any stage.

```bash
.venv/Scripts/python -m src.data.units
```
```bash
.venv/Scripts/python -m src.features.network
```
```bash
.venv/Scripts/python -m pip install -r requirements-sentiment.txt
```
```bash
.venv/Scripts/python -m src.features.sentiment
```
```bash
.venv/Scripts/python -m src.eval.arima_order
```
```bash
.venv/Scripts/python -m src.features.temporal
```
```bash
.venv/Scripts/python -m src.eval.size_audit
```
```bash
.venv/Scripts/python -m src.eval.ablation
```
```bash
.venv/Scripts/python -m src.eval.lead_time
```
```bash
.venv/Scripts/python -m src.eval.language_control
```
```bash
.venv/Scripts/python -m src.eval.robustness
```
```bash
.venv/Scripts/python -m src.eval.figures
```
```bash
.venv/Scripts/python -m src.eval.results_summary
```

`results_summary` must run last: it reads the JSONs every earlier step
writes, and regenerates
[`outputs/tables/RESULTS_SUMMARY.md`](outputs/tables/RESULTS_SUMMARY.md) from
them. That file is **generated, never edited by hand** — which is what stops
it drifting away from the run it describes.

The sentiment step is the only slow one (~11 min on first run, ~30 s
thereafter — it caches raw model probabilities by text hash). Everything else
completes in seconds to a couple of minutes.

### Figures and the scripts that produce them

| figure | produced by | reads |
|---|---|---|
| `fig_ablation.png` | `src/eval/figures.py` | `ablation_results.json` |
| `fig_lead_time_nested.png` | `src/eval/figures.py` | `lead_time_results.json` |
| `fig_pr_vs_roc_sentiment.png` | `src/eval/figures.py` | feature matrices |
| `fig_size_proxy_audit.png` | `src/eval/figures.py` | feature matrices |
| `fig_language_overlap.png` | `src/eval/figures.py` | corpus + `units.csv` |
| `fig_feature_importance.png` | `src/eval/figures.py` | feature matrices |
| `lead_time_curve.png` | `src/eval/lead_time.py` | computed in-run |

Consolidated numbers for the report:
[`outputs/tables/RESULTS_SUMMARY.md`](outputs/tables/RESULTS_SUMMARY.md).
Findings, corrections and limitations: [`FINDINGS.md`](FINDINGS.md).

### Where output lands

| Path | Contents | Committed? |
|---|---|---|
| `outputs/tables/` | result JSONs, summary tables | yes — no tweet text |
| `outputs/figures/` | figures for the report | yes |
| `outputs/cache/` | regenerable intermediates (`units.csv`, feature CSVs) | no |
| `dataset/` | the raw corpus | **no — never** |

## Parameters and hyperparameters

Every data and evaluation parameter lives in [`config.yaml`](config.yaml).

| Parameter | Value | Meaning |
|---|---|---|
| `bin_minutes` | 5 | activity bin width |
| `smooth_bins` | 3 | moving-average width before peak detection |
| `min_topic_tweets` | 50 | minimum tweets for a topic to be considered |
| `window_minutes` | 90 | feature-window length |
| `lead_minutes` | 60 | gap between window close and peak |
| `min_window_tweets` | 15 | minimum tweets inside the window |
| `left_censor_frac` | 0.25 | onset must be below this fraction of peak at band start |
| `min_post_peak_bins` | 12 | bins of post-peak history required |
| `post_peak_decay_frac` | 0.70 | decay required after peak to call it a peak |
| `size_proxy_spearman_threshold` | 0.4 | \|Spearman\| vs `window_tweets` above which a feature is reassigned to volume |
| `volume_proxy` | `window_tweets` | the declared volume proxy |
| `arima.order` | `[0, 1, 2]` | **selected, not assumed** — see below |
| `seed` | 42 | every stochastic component |
| `cv_folds` | 5 | `StratifiedGroupKFold`, run **once** — there are no repeats |
| `n_bootstrap` | 1000 | bootstrap resamples for CIs |
| `n_permutations` | 100 | permutation test / importance |

`min_window_tweets` was lowered from 20 to 15 to reach a usable sample. It was
set from unit counts alone, before any classifier ran — recorded in
[`outputs/tables/parameter_decision.md`](outputs/tables/parameter_decision.md).

**The ARIMA order is selected against the data, not assumed.**
`python -m src.eval.arima_order` fits a 16-order grid to all 129 pre-cutoff
histories and scores AIC and BIC over the units where every order converged
(all 129 did). Differencing is justified: ADF rejection of a unit root rises
from 51.9% of series to 84.5% after first differences, and KPSS rejection of
stationarity falls from 54.3% to 10.9%, so both tests agree on `d = 1`.
(0,1,2) then wins on mean AIC (192.13) and mean BIC (197.33). The order used
previously, (1,1,1), sits at 195.76 / 201.04 and wins on **zero** of 129
units under either criterion — the data prefers no AR term at all. Selection
reads no labels, so it cannot leak outcome information into the features.
Evidence: [`outputs/tables/arima_order_selection.json`](outputs/tables/arima_order_selection.json).

**Classifier.** `HistGradientBoostingClassifier`, defined in
[`src/models/fusion.py`](src/models/fusion.py):

| | default arm | regularised arm |
|---|---|---|
| `max_iter` | 250 | 120 |
| `learning_rate` | 0.1 | 0.05 |
| `max_leaf_nodes` | 31 | 4 |
| `max_depth` | none | 3 |
| `min_samples_leaf` | 5 | 15 |
| `l2_regularization` | 0.0 | 1.0 |
| `class_weight` | balanced | balanced |
| `early_stopping` | off | off |

The regularised arm exists to separate overfitting from genuine fusion benefit:
with 31 features and 42 positives the study runs near one feature per positive
case, so the two arms are reported together.

Hyperparameters were **not** tuned. There is no inner tuning loop, so no
selection effect inflates any arm; with 129 units a nested search would consume
the sample the hypotheses are tested on.

**Determinism.** `n_jobs: 1` is a deliberate choice, not a hardware limit.
`HistGradientBoostingClassifier` has no `n_jobs` parameter — it parallelises
through OpenMP — so thread count is pinned at the call site with
`threadpool_limits`. Passing `n_jobs` to the estimator would be silently
ignored, which it was, until a lint pass caught it (see [FINDINGS.md](FINDINGS.md)).

**Sentiment model.** `cardiffnlp/twitter-xlm-roberta-base-sentiment`, pinned at
revision `f2f1202b1bdeb07342385c3f807f9c07cd8f5cf8`, fp32, batch 16, truncation
at 128 tokens, inputs length-sorted. Raw three-class probabilities are cached by
SHA1 of the tweet text.

## Tests

```bash
.venv/Scripts/python -m pytest -q
```

Tests run on **synthetic fixtures built in code** — they need no dataset, which
is what lets CI run them. The fixtures reproduce the real schema and the known
data quirks: stringified-dict `mentions`, `.csv`-suffixed and `#`-prefixed
trend names, ids duplicated across topics, plus a left-censored, a
right-censored and a clean topic.

The load-bearing test asserts **no feature window contains data at or after its
cut-off**, and that the censoring filters drop the censored fixtures. If
leakage is ever introduced, that test fails.

## Evaluation approach

- **PR-AUC is the headline metric.** Emergence is rare; ROC-AUC misleads under
  imbalance (Saito & Rehmsmeier, 2015). ROC-AUC, F1, precision and recall are
  reported alongside.
- **Grouped cross-validation by topic** — a topic never appears in both train
  and test folds.
- **Ablation** over 12 arms: chance, three single-channel arms, three
  volume-plus-one-channel arms, a residualised structure arm, full fusion,
  a regularised full fusion, and `volume_extended`.
- **`volume_extended` is the baseline H1 must beat.** It is volume plus every
  feature the size-proxy audit disqualified from the other channels — 33
  features against full fusion's 31. Comparing fusion against the 3-feature
  `volume_only` arm would make H1 pass for the wrong reason, because most of
  what fusion adds over three features is re-encoded volume.
- **Significance**: bootstrap CIs over out-of-fold predictions, exact McNemar
  on paired out-of-fold decisions, Bonferroni correction where a family of
  comparisons is tested; effect sizes reported alongside p-values.
- **Lead-time curve** — performance against how far before peak the cut-off
  sits, evaluated on a *nested* design: the same 52 topics at every lead, so
  the lead effect is not confounded with sample composition. Evidence for H2.
- **Robustness** — a language-only negative control (which **fails**; see
  Results), sensitivity to window length, lead time and `min_window_tweets`,
  and permutation feature importance checked against theory.
- Seeds are set and recorded everywhere.

## Results

129 units — 42 trending, 87 non-trending. **Chance PR-AUC = prevalence =
0.326**, not 0.5. Grouped 5-fold CV, seed 42.

**Every number, in one generated table:**
[`outputs/tables/RESULTS_SUMMARY.md`](outputs/tables/RESULTS_SUMMARY.md) — all
12 ablation arms with confidence intervals, every McNemar comparison, the
lead-time sweep, the language control and both sensitivity analyses.

No results table is reproduced here on purpose. It would be a hand-maintained
copy of a generated file, and the first re-run that moved a number would leave
the two disagreeing with nothing to catch it — which is the failure this
project has already been through once, and the reason the summary is generated
at all. The headline conclusions follow; the numbers behind them live in one
place.

### H1 — not supported

Full fusion beats `volume_only` (0.856 vs 0.649, McNemar p = 0.0041). It does
**not** beat `volume_extended`: **0.856 vs 0.805, p = 1.0000** — the two
models are wrong about a different case exactly ten times each — and
`volume_extended` still has the higher F1 and recall. Most of fusion's apparent
advantage over a three-feature baseline is volume re-encoded through other
channels, which is why the audit and the extended baseline exist.

Note that the PR-AUC gap (0.051) and the decision-level test disagree. Ranking
improves slightly; the binary decisions at threshold 0.5 do not. With
resampling noise at ±0.02–0.03 a gap of 0.05 is at the edge of what this
sample can resolve, so the McNemar result is the one to trust.

### H2 — supported directionally, not statistically

Nested sweep, the same 52 topics at every lead (prevalence 0.5 here, so chance
PR-AUC is 0.5, **not** 0.326):

| Lead | n | Volume only | Volume + structure | p (McNemar) |
|---|---|---|---|---|
| 30 min | 52 | 0.765 | 0.892 | 0.1094 |
| 60 min | 52 | 0.795 | 0.890 | 0.2668 |
| 120 min | 52 | 0.699 | 0.925 | 0.1185 |
| 180 min | 52 | **0.515** | **0.765** | **0.0169** |

Volume decays to near chance at a three-hour lead; structure holds. The
smallest p does not survive Bonferroni correction across four leads
(α = 0.0125), so the claim is **directional**.

**Read the effect sizes, not the p-values.** The gap between the two arms is
stable to the third decimal across every correction this pipeline has been
through. The p-values are not: they come from McNemar on 52 units, where one
flipped out-of-fold decision moves a p-value by a factor of two. At the
180-minute lead a 7e-15 change in the feature values took the discordant split
from 6/17 to 5/17 and the p-value from 0.0347 to 0.0169 — see
[FINDINGS.md](FINDINGS.md), defect 9. An earlier version of this table reported
a monotone p-trend; that monotonicity did not survive, and it was never the
evidence.

### The language control fails — and this qualifies everything above

The negative control was specified to fail. It does not.

| Classifier | PR-AUC |
|---|---|
| Spanish-share alone | **0.897** |
| Full fusion | 0.853 |

**A single feature — what fraction of a topic's tweets are Spanish — outscores
every model in this study.** The cause is collection, not modelling: the
trending pool is multilingual while the non-trending pool is ~90% Spanish, so
language separates the classes before any dynamics are measured.

All three standard controls were attempted and all three are impossible on this
corpus: topic-level language matching (no English negatives exist), tweet-level
filtering (the strongest arms still recover language at ROC 0.75–0.79), and
within-language restriction (the non-trending minimum Spanish share, 0.824,
exceeds the trending 75th percentile, 0.814 — the distributions barely
overlap). Restricting to the common-support band does not neutralise it
either: with n = 43 and chance at 0.349, language alone still scores 0.642
there — a lift of +0.293 over chance inside the region built to remove it,
against `volume_extended`'s 0.689 on the same 43 units. Nothing at that sample
size separates those two, and the arm ordering inside the band has already
moved once under a protocol correction, which is itself the reason not to lean
on it. The finding is that the confound **survives the restriction**, not which
arm leads inside it.

**What survives.** H2 is a within-topic contrast — the same 52 topics at every
lead, so the confound is constant while the effect varies. That is a fortunate
consequence of a design choice made for a different reason, not foresight. The
H1 null also survives: a shared confound can manufacture a spurious *pass*, but
it cannot manufacture a spurious *failure* to beat a baseline that carries the
same confound. The size-proxy findings are internal to the feature matrix and
are unaffected.

Resampling noise is ±0.02–0.03 PR-AUC, so differences below ~0.05 carry no
interpretation. With 42 positives this study is underpowered; a null here is
weak evidence of no effect, and the reverse risk holds too.

Full numbers: [`outputs/tables/RESULTS_SUMMARY.md`](outputs/tables/RESULTS_SUMMARY.md).
Corrections, defects and limitations: [FINDINGS.md](FINDINGS.md). The frozen
prototype result for the network channel, and the negative-pool leak corrected
in it, are recorded there too.

## Honest reporting

This project reports negative results. The prototype's finding that network
structure **does not** beat volume alone is kept, not buried — the value is in
the combination, which is what the fusion thesis actually claims. Design
assumptions that broke against the data, and controls that turned out to be
impossible to run, are documented in [FINDINGS.md](FINDINGS.md) rather than
quietly dropped.

## Licence and citation

Code is MIT licensed — see [LICENSE](LICENSE). The licence covers this code
only; the tweet corpus is not distributed here.

Citation metadata is in [CITATION.cff](CITATION.cff).
