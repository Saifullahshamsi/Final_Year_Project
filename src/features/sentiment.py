"""Sentiment features over each unit's pre-peak window.

XLM-T (`cardiffnlp/twitter-xlm-roberta-base-sentiment`) at a pinned revision,
scoring the Spanish tweets inside each window.

Decisions here are measured, not assumed (see FINDINGS.md):

* fp32. int8 dynamic quantization is 12% faster and agrees with fp32 on 41.4%
  of labels — barely above chance for three classes. It would have turned this
  entire channel into noise while looking fine.
* batch 16, length-sorted. Sorting is worth +35%; batch 32 is *slower* than 16
  because wider batches gather a broader length spread and pad more.
* truncate at 128 tokens — only 0.3% of tweets reach it.

The cache stores **raw three-class probabilities** keyed by text hash, over the
union of every lead-sweep window rather than just the primary one. Aggregates
can then be redefined, and the lead-time curve re-cut, without re-running the
model.

Run:  python -m src.features.sentiment
"""
from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.loading import (
    band_from_config,
    clean_topic,
    load_config,
    parse_hashtags,
    stream,
)

NEG, NEU, POS = 0, 1, 2


def text_key(text: str) -> str:
    """Stable cache key. Hash rather than the text itself so the cache file
    carries no tweet content."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Collect the texts that need scoring
# ---------------------------------------------------------------------------
def lead_sweep_bins(units: pd.DataFrame, band, cfg) -> dict[str, set[int]]:
    """Union of the bins every lead in the sweep would need, at the widest
    window. Scoring this once means the lead-time curve costs nothing extra."""
    win_b = band.minutes_to_bins(max(cfg["units"]["window_sweep"]))
    out: dict[str, set[int]] = {}
    for r in units.itertuples():
        bins: set[int] = set()
        for lead in cfg["units"]["lead_sweep"]:
            end = r.peak_bin - band.minutes_to_bins(lead)
            bins |= set(range(max(end - win_b, 0), max(end, 0)))
        out[r.topic] = bins
    return out


def collect_texts(cfg: dict, band, units: pd.DataFrame, language: str,
                  bins_needed: dict[str, set[int]]):
    """topic -> [(bin, text_key)], plus text_key -> text for anything unscored.

    Filtered to `language`; de-duplicated on (id, topic).
    """
    primary = {r.topic: r.label for r in units.itertuples()}
    pos = {t for t, lb in primary.items() if lb == 1}
    neg = {t for t, lb in primary.items() if lb == 0}
    per_topic: dict[str, list[tuple[int, str]]] = defaultdict(list)
    texts: dict[str, str] = {}
    seen: set[tuple[str, str]] = set()

    def take(topic, tweet_id, b, tw):
        if b not in bins_needed.get(topic, ()):
            return
        if (tweet_id, topic) in seen:
            return
        seen.add((tweet_id, topic))
        tw = tw if isinstance(tw, str) else ""
        if not tw.strip():
            return
        k = text_key(tw)
        texts[k] = tw
        per_topic[topic].append((b, k))

    if pos:
        for ch in stream(cfg["paths"]["trending_csv"],
                         ["id", "trend", "date", "time", "language", "tweet"], cfg):
            for i, t, d, tm, lg, tw in zip(
                    ch["id"].values, ch["trend"].values, ch["date"].values,
                    ch["time"].values, ch["language"].values,
                    ch["tweet"].values, strict=False):
                if lg != language:
                    continue
                topic = clean_topic(t)
                if topic not in pos:
                    continue
                b = band.bin_of(d, tm)
                if b is not None:
                    take(topic, i, b, tw)

    if neg:
        for ch in stream(cfg["paths"]["nontrending_csv"],
                         ["id", "date", "time", "language", "hashtags", "tweet"], cfg):
            for i, d, tm, lg, hs, tw in zip(
                    ch["id"].values, ch["date"].values, ch["time"].values,
                    ch["language"].values, ch["hashtags"].values,
                    ch["tweet"].values, strict=False):
                if lg != language:
                    continue
                b = band.bin_of(d, tm)
                if b is None:
                    continue
                for topic in parse_hashtags(hs):
                    if topic in neg:
                        take(topic, i, b, tw)

    return per_topic, texts


# ---------------------------------------------------------------------------
# Scoring + cache
# ---------------------------------------------------------------------------
def load_cache(path: Path) -> dict[str, np.ndarray]:
    if not path.exists():
        return {}
    df = pd.read_csv(path)
    return {r.key: np.array([r.p_neg, r.p_neu, r.p_pos])
            for r in df.itertuples()}


def save_cache(path: Path, cache: dict[str, np.ndarray]) -> None:
    pd.DataFrame([{"key": k, "p_neg": v[0], "p_neu": v[1], "p_pos": v[2]}
                  for k, v in cache.items()]).to_csv(path, index=False)


def score_texts(texts: dict[str, str], cache: dict[str, np.ndarray],
                cfg: dict) -> dict[str, np.ndarray]:
    """Score whatever is not already cached. Returns the updated cache."""
    todo = [k for k in texts if k not in cache]
    if not todo:
        print("  all texts already cached")
        return cache

    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    sc = cfg["sentiment"]
    print(f"  scoring {len(todo):,} uncached texts "
          f"({len(texts) - len(todo):,} cache hits)")
    tok = AutoTokenizer.from_pretrained(sc["model"], revision=sc["revision"])
    model = AutoModelForSequenceClassification.from_pretrained(
        sc["model"], revision=sc["revision"])
    model.eval()

    # Length-sorted: padding is charged per batch, so mixed-length batches
    # waste compute padding short tweets up to the longest.
    if sc["sort_by_length"]:
        todo = sorted(todo, key=lambda k: len(texts[k]))

    bs = sc["batch_size"]
    t0 = time.time()
    with torch.no_grad():
        for i in range(0, len(todo), bs):
            keys = todo[i:i + bs]
            enc = tok([texts[k] for k in keys], padding=True, truncation=True,
                      max_length=sc["max_length"], return_tensors="pt")
            probs = torch.softmax(model(**enc).logits, dim=-1).numpy()
            for k, p in zip(keys, probs, strict=True):
                cache[k] = p
            if i and i % (bs * 100) == 0:
                done = i + len(keys)
                print(f"    {done:,}/{len(todo):,}  "
                      f"({done / (time.time() - t0):.1f} tweets/s)")
    print(f"  scored in {time.time() - t0:.0f}s "
          f"({len(todo) / max(time.time() - t0, 1e-9):.1f} tweets/s)")
    return cache


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------
def aggregate(records, cache, cfg: dict, prefix: str = "") -> dict:
    """Per-window aggregates from raw probabilities.

    polarity = p(pos) - p(neg) in [-1, 1]; intensity = 1 - p(neutral).

    Every feature here is an average, a fraction or a moment — nothing scales
    with the number of tweets. The count is emitted as `meta_sent_n` and is NOT
    a sentiment feature: it is numerically identical to the volume feature
    `window_tweets` (means 212.9 vs 46.2, AUC 0.832), so modelling it in the
    sentiment arm would credit volume to sentiment.
    """
    thr = cfg["sentiment"]["strong_threshold"]
    if not records:
        return {f"{prefix}{k}": 0.0 for k in
                ("sent_mean", "sent_var", "sent_intensity", "sent_strong_frac",
                 "sent_pos_frac", "sent_neg_frac", "sent_neu_frac",
                 "sent_skew", "sent_polarisation", "meta_sent_n")}
    P = np.array([cache[k] for _b, k in records if k in cache])
    if len(P) == 0:
        return aggregate([], cache, cfg, prefix)
    polarity = P[:, POS] - P[:, NEG]
    intensity = 1.0 - P[:, NEU]
    lab = P.argmax(axis=1)
    pos_f = float((lab == POS).mean())
    neg_f = float((lab == NEG).mean())
    sd = float(polarity.std())
    return {
        f"{prefix}sent_mean": float(polarity.mean()),
        f"{prefix}sent_var": float(polarity.var()),
        f"{prefix}sent_intensity": float(intensity.mean()),
        f"{prefix}sent_strong_frac": float((np.abs(polarity) >= thr).mean()),
        f"{prefix}sent_pos_frac": pos_f,
        f"{prefix}sent_neg_frac": neg_f,
        f"{prefix}sent_neu_frac": float((lab == NEU).mean()),
        # Third standardised moment: is the tail positive or negative?
        f"{prefix}sent_skew": (float(((polarity - polarity.mean()) ** 3).mean()
                                     / (sd ** 3)) if sd > 1e-9 else 0.0),
        # Disagreement rather than average mood: both camps present at once.
        f"{prefix}sent_polarisation": 2 * min(pos_f, neg_f),
        f"{prefix}meta_sent_n": float(len(P)),   # diagnostics only, not a feature
    }


def vader_features(cfg: dict, band, units: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """English-subset VADER baseline.

    Route 2 filters modelled features to Spanish, so VADER scores a *different*
    tweet population from the main channel. Coverage is reported precisely; if
    it is thin, this is a descriptive check and not an ablation arm.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:
        return pd.DataFrame(), {"available": False,
                                "reason": "vaderSentiment not installed"}
    bins = lead_sweep_bins(units, band, cfg)
    per_topic, texts = collect_texts(cfg, band, units, cfg["sentiment"]["vader"]["language"], bins)
    an = SentimentIntensityAnalyzer()
    scored = {k: an.polarity_scores(v)["compound"] for k, v in texts.items()}
    primary = {r.topic: (r.window_start_bin, r.window_end_bin, r.label)
               for r in units.itertuples()}
    rows = []
    for topic, (s, e, label) in primary.items():
        vals = [scored[k] for b, k in per_topic.get(topic, []) if s <= b < e]
        if not vals:
            continue
        v = np.array(vals)
        rows.append({"topic": topic, "label": label,
                     "vader_mean": float(v.mean()), "vader_var": float(v.var()),
                     "vader_strong_frac": float((np.abs(v) >= 0.5).mean()),
                     "vader_n": float(len(v))})
    df = pd.DataFrame(rows)
    cov = {"available": True, "units_with_any_english": int(len(df)),
           "units_total": int(len(units)),
           "english_tweets_scored": int(len(texts))}
    if len(df):
        cov["units_trending"] = int(df.label.sum())
        cov["units_non_trending"] = int((1 - df.label).sum())
        cov["median_english_tweets_per_unit"] = float(df.vader_n.median())
    return df, cov


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    sc = cfg["sentiment"]
    lang = cfg["language"]["feature_language"]
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")
    print(f"{len(units)} units | model {sc['model']}")
    print(f"revision {sc['revision']}")
    print(f"feature language {lang!r} | fp32 batch {sc['batch_size']} "
          f"length-sorted={sc['sort_by_length']}\n")

    bins = (lead_sweep_bins(units, band, cfg) if sc["cache_over_lead_sweep"]
            else {r.topic: set(range(r.window_start_bin, r.window_end_bin))
                  for r in units.itertuples()})
    print("Collecting window texts ...")
    per_topic, texts = collect_texts(cfg, band, units, lang, bins)
    print(f"  {sum(len(v) for v in per_topic.values()):,} tweet slots, "
          f"{len(texts):,} distinct texts ({time.time() - t0:.0f}s)\n")

    cache_path = Path(cfg["paths"]["cache"]) / sc["cache_file"].replace(
        ".parquet", ".csv")
    cache = load_cache(cache_path)
    print(f"Scoring (cache: {cache_path.name}, {len(cache):,} entries) ...")
    cache = score_texts(texts, cache, cfg)
    save_cache(cache_path, cache)
    print(f"  cache now {len(cache):,} entries\n")

    rows = []
    for r in units.itertuples():
        recs = [(b, k) for b, k in per_topic.get(r.topic, [])
                if r.window_start_bin <= b < r.window_end_bin]
        f = {"topic": r.topic, "label": int(r.label)}
        f.update(aggregate(recs, cache, cfg))
        rows.append(f)
    df = pd.DataFrame(rows)
    out = f"{cfg['paths']['cache']}/sentiment_features.csv"
    df.to_csv(out, index=False)

    covered = int((df.meta_sent_n > 0).sum())
    print(f"SENTIMENT FEATURES: {len(df)} units, {covered} with >=1 scored "
          f"tweet ({100 * covered / len(df):.1f}% coverage)")
    print(f"  tweets per window: median {df.meta_sent_n.median():.0f}, "
          f"min {df.meta_sent_n.min():.0f}, max {df.meta_sent_n.max():.0f}\n")

    feats = [c for c in df.columns
             if c.startswith("sent_") and not c.startswith("meta_")]
    from sklearn.metrics import roc_auc_score
    y = df["label"].values
    print(f"{'feature':<24}{'mean(+)':>10}{'mean(-)':>10}{'AUC':>8}")
    print("-" * 52)
    summary = {}
    for c in feats:
        v = df[c].values.astype(float)
        auc = (max(roc_auc_score(y, v), 1 - roc_auc_score(y, v))
               if len(np.unique(v)) > 1 else 0.5)
        summary[c] = {"mean_trending": float(v[y == 1].mean()),
                      "mean_non_trending": float(v[y == 0].mean()),
                      "univariate_auc": float(auc)}
        print(f"{c:<24}{v[y == 1].mean():>10.3f}{v[y == 0].mean():>10.3f}"
              f"{auc:>8.3f}")

    print("\nVADER (English-subset baseline) ...")
    vdf, vcov = vader_features(cfg, band, units)
    for k, v in vcov.items():
        print(f"  {k:<34} {v}")
    if len(vdf):
        vdf.to_csv(f"{cfg['paths']['cache']}/vader_features.csv", index=False)

    with open(f"{cfg['paths']['tables']}/sentiment_feature_summary.json", "w",
              encoding="utf-8") as fh:
        json.dump({"model": sc["model"], "revision": sc["revision"],
                   "feature_language": lang, "n_units": len(df),
                   "units_with_scores": covered,
                   "distinct_texts_scored": len(texts),
                   "cache_entries": len(cache),
                   "summary": summary, "vader_coverage": vcov,
                   "seed": cfg["seed"]}, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {out}")
    print(f"Wrote {cfg['paths']['tables']}/sentiment_feature_summary.json")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
