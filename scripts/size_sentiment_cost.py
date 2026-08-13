"""Measure the XLM-T workload BEFORE installing torch.

Counts exactly how many tweets the sentiment channel must score, how long they
are, and how much of the work de-duplicates away, so the CPU cost can be
estimated rather than discovered halfway through a run on a 4 GB / 1-core box.

Measures workload only. Throughput is estimated separately and is stated as an
estimate until a real benchmark is run.

Run:  python -m scripts.size_sentiment_cost
"""
from __future__ import annotations

import json
from collections import defaultdict

import numpy as np
import pandas as pd

from src.data.loading import band_from_config, clean_topic, load_config, parse_hashtags, stream


def windows_for_leads(units: pd.DataFrame, band, cfg) -> dict[str, set[int]]:
    """Bins each unit needs across every lead in the sweep, at the widest window.

    The lead-time curve re-cuts the window per lead, so the sentiment cache has
    to cover the union or it will be recomputed four times.
    """
    win_b = band.minutes_to_bins(max(cfg["units"]["window_sweep"]))
    need: dict[str, set[int]] = {}
    for r in units.itertuples():
        bins: set[int] = set()
        for lead in cfg["units"]["lead_sweep"]:
            end = r.peak_bin - band.minutes_to_bins(lead)
            start = end - win_b
            bins |= {b for b in range(max(start, 0), max(end, 0))}
        need[r.topic] = bins
    return need


def main() -> int:
    cfg = load_config()
    band = band_from_config(cfg)
    lang = cfg["language"]["feature_language"]
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")

    primary = {r.topic: (r.window_start_bin, r.window_end_bin, r.label)
               for r in units.itertuples()}
    sweep = windows_for_leads(units, band, cfg)
    pos = {t for t, w in primary.items() if w[2] == 1}
    neg = {t for t, w in primary.items() if w[2] == 0}

    n_primary = n_sweep = 0
    chars_primary: list[int] = []
    texts_primary: set[str] = set()
    texts_sweep: set[str] = set()
    per_class = defaultdict(int)
    seen: set[tuple[str, str]] = set()

    def take(topic, tweet_id, b, text, label):
        nonlocal n_primary, n_sweep
        if (tweet_id, topic) in seen:
            return
        seen.add((tweet_id, topic))
        s, e, _ = primary[topic]
        txt = text if isinstance(text, str) else ""
        if b in sweep[topic]:
            n_sweep += 1
            texts_sweep.add(txt)
        if s <= b < e:
            n_primary += 1
            per_class[label] += 1
            chars_primary.append(len(txt))
            texts_primary.add(txt)

    for ch in stream(cfg["paths"]["trending_csv"],
                     ["id", "trend", "date", "time", "language", "tweet"], cfg):
        for i, t, d, tm, lg, tw in zip(ch["id"].values, ch["trend"].values,
                                       ch["date"].values, ch["time"].values,
                                       ch["language"].values, ch["tweet"].values,
                                       strict=False):
            if lang and lg != lang:
                continue
            topic = clean_topic(t)
            if topic not in pos:
                continue
            b = band.bin_of(d, tm)
            if b is not None:
                take(topic, i, b, tw, 1)

    for ch in stream(cfg["paths"]["nontrending_csv"],
                     ["id", "date", "time", "language", "hashtags", "tweet"], cfg):
        for i, d, tm, lg, hs, tw in zip(ch["id"].values, ch["date"].values,
                                        ch["time"].values, ch["language"].values,
                                        ch["hashtags"].values, ch["tweet"].values,
                                        strict=False):
            if lang and lg != lang:
                continue
            b = band.bin_of(d, tm)
            if b is None:
                continue
            for topic in parse_hashtags(hs):
                if topic in neg:
                    take(topic, i, b, tw, 0)

    chars = np.array(chars_primary) if chars_primary else np.array([0])
    # XLM-R sentencepiece on Spanish runs roughly 3.2-4.0 characters per token.
    # Both ends are reported; nothing here depends on a single point estimate.
    tok_hi = chars / 3.2
    tok_lo = chars / 4.0

    print(f"SENTIMENT WORKLOAD  (feature language: {lang!r})\n")
    print(f"  units                              {len(units)}")
    print(f"  tweets to score, primary window    {n_primary:,}")
    print(f"    trending / non-trending          {per_class[1]:,} / {per_class[0]:,}")
    print(f"    distinct texts                   {len(texts_primary):,} "
          f"({100*len(texts_primary)/max(n_primary,1):.1f}% of rows)")
    print(f"  tweets to score, union over lead   {n_sweep:,}")
    print(f"    sweep {cfg['units']['lead_sweep']} at window "
          f"{max(cfg['units']['window_sweep'])} min")
    print(f"    distinct texts                   {len(texts_sweep):,}\n")

    print("  tweet length (characters, primary window)")
    for q in (50, 75, 90, 95, 99, 100):
        print(f"    p{q:<3}                             {int(np.percentile(chars, q))}")
    print(f"    mean                             {chars.mean():.0f}")
    print("\n  estimated tokens/tweet (3.2-4.0 chars per token)")
    print(f"    mean                             {tok_lo.mean():.0f} - {tok_hi.mean():.0f}")
    print(f"    p95                              {int(np.percentile(tok_lo,95))} - "
          f"{int(np.percentile(tok_hi,95))}")
    print(f"    share over 128 tokens            "
          f"{100*(tok_hi > 128).mean():.1f}% (would be truncated)")

    out = {
        "feature_language": lang,
        "n_units": int(len(units)),
        "tweets_primary_window": n_primary,
        "tweets_primary_by_class": {"trending": per_class[1],
                                    "non_trending": per_class[0]},
        "distinct_texts_primary": len(texts_primary),
        "tweets_lead_sweep_union": n_sweep,
        "distinct_texts_lead_sweep": len(texts_sweep),
        "chars_mean": float(chars.mean()),
        "chars_p95": float(np.percentile(chars, 95)),
        "chars_max": int(chars.max()),
        "est_tokens_mean_low": float(tok_lo.mean()),
        "est_tokens_mean_high": float(tok_hi.mean()),
        "frac_over_128_tokens": float((tok_hi > 128).mean()),
    }
    with open(f"{cfg['paths']['tables']}/sentiment_cost.json", "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {cfg['paths']['tables']}/sentiment_cost.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
