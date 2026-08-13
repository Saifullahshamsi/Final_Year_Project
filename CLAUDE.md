# Project: Predictive Modelling of Social Media Trend Emergence

## What this project is

Final-year data science project. Predict **topic-level trend emergence on Twitter 1–3 hours before peak**, not detect trends after they appear.

Core contribution is **signal fusion**: combine three feature channels that the literature studies in isolation, and measure each one's marginal contribution via ablation.

| Channel | Content | Status |
|---|---|---|
| Network | mention/reply interaction graph structure | **DONE** (prototype validated) |
| Temporal | ARIMA + LSTM on volume curves | TODO |
| Sentiment | XLM-T multilingual polarity | TODO |

Research question: *Can fusing early temporal, sentiment and network-diffusion signals predict, 1–3h before peak, whether a topic will emerge as a trend, more accurately than single-signal baselines?*

- **H1**: fused model significantly beats best single-signal baseline.
- **H2**: network + sentiment features extend achievable lead time beyond engagement counts alone.

This is an **offline** project on a static historical corpus. No real-time system, no dashboard required. Do not build a web UI.

---

## Data

Two CSVs (~1.2 GB total, scraped with `twint`):

```
dataset/tweets_25_tendencia_raw.csv      # 668 MB — TRENDING   — 1,275,917 rows
dataset/tweets_25_notendencias_raw.csv   # 558 MB — NON-TRENDING — ~1,080,000 rows
```

Columns (twint schema): `id, conversation_id, created_at, date, time, timezone, user_id, username, name, place, tweet, language, mentions, urls, photos, replies_count, retweets_count, likes_count, hashtags, cashtags, link, retweet, quote_url, video, thumbnail, near, geo, source, user_rt_id, user_rt, retweet_id, reply_to, retweet_date, translate, trans_src, trans_dest`

Relevant columns only: `trend, time, created_at, username, tweet, language, mentions, reply_to, hashtags, retweets_count, replies_count, likes_count`

### Data gotchas — READ BEFORE WRITING ANY LOADER

1. **`trend` labels are contaminated**, in *two* different ways — verified 2026-08-08. Of 322 distinct raw names: 83 carry a `.csv` suffix (`Bayern.csv`), 137 carry a `#` prefix (`#BTSonFallon`), 25 carry both, the rest are bare. Normalise all three: strip `.csv`, strip leading `#`, lowercase. Cleaning collapses no two topics together, so it is safe. **Comparing a raw trend name against a hashtag token is a bug** — it silently leaks trended topics into the negative pool (see §Known corrections).
2. **Whole corpus is a single day (2020-02-25).** Any topic already peaking at collection start is **left-censored** — its emergence phase was never recorded. Must filter these out, or the "pre-peak" claim is false.
3. **`mentions` / `reply_to` are stringified Python lists of dicts** — parse with `ast.literal_eval`, then read `screen_name`. Lowercase all screen names.
4. **Retweet capture is broken.** `retweet` / `retweet_id` / `user_rt` are mostly empty. **Do NOT build retweet cascades.** Build the graph from `mentions` + `reply_to`. This is a deliberate design decision, justified in the report (Weng et al. 2013 show the predictive structures are clustering/community, computable from any interaction graph; Cheng et al. 2014 show early breadth matters more than cascade depth).
5. **SEVERE language confound.** Trending pool is multilingual (EN ~558k, ES ~361k, plus PT/FR/IT/JA). Non-trending pool is **~90% Spanish** (968k/1.08M). A classifier can hit high accuracy by detecting *language*, learning nothing about trend dynamics. **Every model run must control for this** — stratify/match classes by language, and run a language-only classifier as a negative control.
6. **Trending file is NOT grouped by trend** — rows are interleaved, across **322** distinct trends (verified; an earlier note said 323). Two-pass streaming needed; don't assume you can groupby in one sequential sweep.
7. **Negatives are the bottleneck, not positives.** Non-trending hashtag coverage is 13.2% of rows and there are 84,625 distinct hashtags — but almost all are tiny. **Inside the usable band, only ~174 non-trending hashtags reach ≥100 tweets and ~103 reach ≥150** (against 199 / 182 trending). Sample size is set by the negative class. This is why `min_topic_tweets` is **100**, not 150.
8. **Malformed rows are negligible** — verified, and milder than an earlier note claimed: 0 rows with `trend` holding a URL, 3 bad dates/times in the trending file, 1 in the non-trending file. Keep `on_bad_lines="skip"` and drop them, but do not expect a meaningful loss.
9. **De-duplicate on `(id, topic)`, never on `id` alone.** Raw duplicate-`id` rates are 11.9% (trending) and 5.7% (non-trending), but in the trending file a repeated id is mostly **legitimate multi-trend membership** — one tweet carrying two trending hashtags. De-duplicating by `id` would delete real topic memberships.

### Usable collection band — the pools do NOT cover the same hours

Verified 2026-08-08. The two files were collected over **different windows**:

| Hour block | Trending rows | Non-trending rows |
|---|---|---|
| 00 | 151 (all dated **2020-02-26**) | 113,074 |
| 01–15 | 675,652 (continuous) | 8,875 total — effectively dead |
| 16–23 | 660,899 | 968,330 |

The non-trending pool was collected in **two disjoint blocks** (00:00–00:59 and 16:00–23:59); the 01–15h band is residue at ~590 rows/hour against ~120,000/hour in the live band.

**Consequence: binning the full day makes cross-class peak comparison invalid** — every negative topic's "peak" would land in 16–23h by collection artifact rather than behaviour.

**Decision: all modelling is restricted to `2020-02-25 16:00:00–23:59:59`** — the only band both pools genuinely cover. The 151 rows dated 2020-02-26 are dropped as next-day residue. The censoring filters treat **16:00 as collection start for both classes**; the filter must stay symmetric or the comparison breaks.

### Known corrections (documented in the report)

- **Negative-pool leak in the prototype.** The prototype excluded trended topics by testing `"#" + hashtag ∈ {raw trend names}`. Because trend names are mixed-format, that test matched only 17 of the 182 hashtags that had actually trended. Result: **6 of the prototype's 125 negatives (4.8%) were topics that did trend.** This biases *toward* the null, but cannot be claimed to explain the network-vs-volume result (p = 0.81 is nowhere near marginal). Corrected test: compare against **cleaned** trend names.
- The prototype under `prototype/` is **frozen** as a reference. Its numbers are reproduced by re-running it with path edits only. The new pipeline reports its own numbers separately. **Do not tune toward 0.868.**

### Memory / compute constraints

Files are too big to load whole. **Always stream with `pd.read_csv(..., chunksize=300_000, usecols=[...], dtype=str)`,** and cache expensive intermediates to disk (especially sentiment scores). Streaming is about the 1.2 GB files, not about the machine, so it stays regardless.

**Hardware — corrected 2026-08-13.** An earlier note assumed ~4 GB RAM and possibly 1 CPU core. Verified actual spec: **Intel i9-13900H, 14 cores / 20 threads, 15.6 GB RAM, 255 GB free disk.** A full streaming pass over either CSV takes ~8 s; XLM-T scores 35.2 tweets/s. Runtime is not a binding constraint on this project.

**`n_jobs=1` stays — as a deliberate choice, not a hardware necessity.** Reasons, in order:
1. **Determinism.** Parallel folds can reorder floating-point reductions, and CV results must be bit-reproducible for the report.
2. **Nothing to gain.** 129 units and a ~10-minute sentiment pass; parallelism buys no time worth the reproducibility cost.
3. **CI honesty.** The workflow runs on a small shared runner, so tests must assume modest hardware regardless of the development machine.

A wrong stated constraint is worse than no stated constraint — the original note would have justified rejecting XLM-T on a cost estimate that was an order of magnitude too pessimistic.

---

## Prototype: what's already built and proven

Two working scripts (in `prototype/`):
- `prototype_extract.py` — streams corpus, builds per-topic early interaction graph, computes 16 features → `topic_features.csv`
- `prototype_eval.py` — full ML evaluation → `proto_results.json` + 4 figures

### Prototype method
- Unit = **one topic** (a hashtag). Trending = labelled trends. Non-trending = hashtags in the non-trending pool that never trended.
- Sample: **265 topics (140 trending / 125 non-trending)**, restricted to topics with ≥150 total tweets.
- Early-stage proxy: **each topic's earliest 150 tweets by timestamp** (kept via bounded max-heaps). Chosen *deliberately* over a fixed time window because (a) comparable graph size across topics, (b) controls for raw volume so structure is isolated. A first attempt using a fixed 60-min window produced too sparse a sample because of left-censoring — that failure is documented in the report.
- Graph: directed, author → each mentioned/replied-to account, parallel edges weighted.
- Features: 14 network (`density, edges_per_tweet, max_in_degree, mean_in_degree, max_out_degree, n_components, largest_wcc_frac, mean_component_size, reciprocity, pagerank_gini, max_pagerank, mean_clustering, n_nodes, n_edges`) + 2 volume (`total_count, unique_users`).

### Prototype results (must be reproducible / not regressed)

| Model | ROC-AUC | PR-AUC | F1 |
|---|---|---|---|
| Chance | 0.50 | 0.53 | — |
| Volume only | 0.774 ± 0.059 | 0.825 ± 0.051 | 0.705 |
| Network only | 0.770 ± 0.051 | 0.790 ± 0.052 | 0.709 |
| **Full (volume + network)** | **0.868 ± 0.040** | **0.872 ± 0.043** | **0.800** |

- Permutation test, network-only: observed ROC-AUC 0.779, **p = 0.0099** (100 shuffles) → structure carries real signal.
- Network vs volume, Wilcoxon on paired folds: **p = 0.81** → **structure does NOT beat volume alone.** Honest negative result. Keep it. Value is in *combination*, which supports the fusion thesis.
- Full model OOF ROC-AUC bootstrap 95% CI: **[0.808, 0.899]**.
- Top univariate discriminators: `reciprocity` AUC 0.66 (p≈1.6e-9), `mean_clustering` 0.64, `pagerank_gini` 0.61, `max_pagerank` 0.59.
- RF importance: `total_count` 0.276, `unique_users` 0.084, `reciprocity` 0.073, `pagerank_gini` 0.062, `mean_clustering` 0.056.

**Do not silently change the prototype's numbers.** If a refactor moves them, say so explicitly and explain why.

---

## Target architecture

```
raw corpus
  → cleaning (strip .csv labels, de-dup, parse timestamps)
  → language balancing (kill the confound)
  → topic–time-window units (peak detection; DROP left-censored topics)
  → 3 parallel feature channels: temporal | sentiment | network
  → feature fusion
  → models: fusion classifier vs single-signal baselines
  → evaluation: PR-AUC, F1, lead-time curve, ablation, significance tests
```

### Suggested repo layout
```
src/
  data/    loading.py  cleaning.py  units.py       # streaming, peak detection, censoring filter
  features/ temporal.py  sentiment.py  network.py  # network.py = refactored prototype
  models/   baselines.py  fusion.py
  eval/     metrics.py  ablation.py  significance.py  figures.py
config.yaml            # windows, lead times, thresholds, seeds — NO magic numbers in code
tests/
outputs/   figures/  tables/  cache/
prototype/             # keep as-is for reference
```

---

## Implementation priorities, in order

1. **`units.py` — the critical path.** Replace the earliest-150-tweets proxy with real peak detection and a genuine pre-peak window. Bin each topic's activity, find its max-volume bin = peak, extract features from a window ending 1–3h *before* peak, and **exclude any topic whose onset isn't observed inside the collection window**. Nothing downstream is credible until this exists.
2. **Language balancing** in `cleaning.py`, plus a language-only negative-control classifier in `eval/`.
3. **`network.py`** — refactor prototype extractor; add betweenness centrality, k-core, community detection (Louvain/greedy modularity), and graph growth rate over the window.
4. **`sentiment.py`** — XLM-T (`cardiffnlp/twitter-xlm-roberta-base-sentiment`). Batch, cache to disk, aggregate per window (mean/variance/intensity/share strongly-affective). Keep VADER as an English-subset baseline.
5. **`temporal.py`** — volume slope/acceleration, ARIMA residuals, LSTM embeddings of the early curve.
6. **`baselines.py` + `fusion.py`** — ablation hierarchy: chance → ARIMA-only → engagement-only LSTM → engagement+network → engagement+sentiment → full fusion. **Gradient-boosted trees are the primary fusion model** (an end-to-end LSTM will likely overfit on one day of data).
7. **`eval/`** — see below.

---

## Evaluation requirements (non-negotiable — these are marked)

- **PR-AUC is the headline metric**, not accuracy, not ROC-AUC alone. Emergence is rare; Saito & Rehmsmeier (2015) show ROC misleads under imbalance because a large negative pool suppresses FPR even when precision is bad. Report ROC-AUC, F1, precision, recall alongside.
- **Group k-fold CV split by topic.** A topic must never appear in both train and test folds.
- **Ablation** across the full hierarchy — the point is to isolate each channel's marginal contribution.
- **Significance testing**: McNemar for paired classifiers, bootstrap CIs for PR-AUC/F1, report effect sizes not just p-values.
- **Lead-time curve**: performance as a function of how far before peak the cut-off sits. This is what evidences H2.
- **Robustness**: (a) language-confound test — performance holds within a single language AND a language-only classifier fails; (b) sensitivity to window length and lead time; (c) feature importance / SHAP sanity-check against theory.
- Set and record **random seeds** everywhere. Results must reproduce.

---

## Contingency

Policy for when too few topics survive the censoring filters in `units.py`.
Apply **in order**, and state explicitly which level was reached.

1. **Keep the strict 1–3 h pre-peak window.** Preferred; the headline claim rests on it.
2. **If too few topics survive:** widen the feature window and/or shorten the lead to 30–60 min. **Report the lead time achieved, not the lead time assumed.**
3. **If still too few:** define the peak relative to each topic's *observed span* rather than absolute clock time, keeping both censoring filters in place.
4. **Last resort:** reframe the task as *early-escalation vs non-escalation*. This weakens the pre-peak claim, so **only with explicit approval** — never adopt it silently.

**Hard floor:** below ~120 usable topics, or either class below 40, **stop and report**. The sample will not support the significance testing the evaluation section requires.

---

## Working style

- Small, verifiable steps. Run the thing, show output, then move on.
- Every stage writes a small summary (row counts, class balance, per-language breakdown) so problems surface early rather than at model time.
- **Report honest negative results.** The prototype's "structure doesn't beat volume alone" finding is valuable and stays in. If fusion turns out not to help, that's a finding, not a failure — say so.
- No fabricated numbers, ever. Every figure in the report must trace to a script that produced it.
- Flag it loudly if a design assumption breaks against the data. That already happened once (fixed time window → left-censoring) and it improved the project.

## Out of scope
Real-time streaming, dashboards, web UI, deployment, live Twitter/X API collection.
