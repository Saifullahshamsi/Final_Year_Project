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
  ↓  features       ┌─ temporal   volume slope/acceleration, ARIMA residuals, LSTM embeddings
  ↓                 ├─ sentiment  XLM-T multilingual polarity, VADER (English baseline)
  ↓                 └─ network    mention/reply interaction-graph structure
  ↓  fusion         gradient-boosted trees over the concatenated channels
  ↓  evaluation     PR-AUC (headline), grouped CV, ablation, lead-time curve, significance
```

| Channel | Content | Status |
|---|---|---|
| Network | mention/reply interaction graph structure | **validated as prototype** |
| Temporal | ARIMA + LSTM on volume curves | in progress |
| Sentiment | XLM-T multilingual polarity | in progress |

## Status

| Stage | State |
|---|---|
| Corpus verification | done — see [FINDINGS.md](FINDINGS.md) |
| `src/data/loading.py` — streaming, parsing, binning | done |
| `src/data/units.py` — peak detection, censoring, windows | done |
| Language control (tweet-level) | done |
| Network channel | prototype validated; refactor pending |
| Sentiment channel | not started |
| Temporal channel | not started |
| Fusion + evaluation | not started |

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

### Where output lands

| Path | Contents | Committed? |
|---|---|---|
| `outputs/tables/` | result JSONs, summary tables | yes — no tweet text |
| `outputs/figures/` | figures for the report | yes |
| `outputs/cache/` | regenerable intermediates (`units.csv`, feature CSVs) | no |
| `dataset/` | the raw corpus | **no — never** |

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
- **Ablation** across the full hierarchy: chance → ARIMA-only → engagement-only
  → engagement+network → engagement+sentiment → full fusion.
- **Significance**: bootstrap CIs, permutation tests, McNemar for paired
  classifiers; effect sizes reported alongside p-values.
- **Lead-time curve** — performance as a function of how far before peak the
  cut-off sits. This is the evidence for H2.
- **Robustness** — language control (a language-only classifier must *fail*),
  sensitivity to window length, lead time and thresholds, and feature
  importance checked against theory.
- Seeds are set and recorded everywhere.

## Results

*To be completed once the fusion model runs.*

| Model | PR-AUC | ROC-AUC | F1 |
|---|---|---|---|
| Chance | — | 0.50 | — |
| Temporal only | | | |
| Sentiment only | | | |
| Network only | | | |
| **Full fusion** | | | |

The validated prototype result for the network channel, and the correction
applied to it, are recorded in [FINDINGS.md](FINDINGS.md).

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
