"""Build (topic, pre-peak window) units — the critical path.

Replaces the prototype's "earliest 150 tweets" proxy with real peak detection
and a genuine pre-peak window, and drops topics whose emergence phase was
never observed.

Design constraints that are NOT negotiable here:

* All work happens inside the verified collection band (config `band`), the
  only hours both pools cover. 16:00 is treated as collection start for BOTH
  classes; the censoring filter must stay symmetric or the cross-class
  comparison is meaningless.
* Features may never see data at or after (peak - lead). The window is
  [peak - lead - length, peak - lead), half-open at the late end.
* De-duplication keys on (id, topic), never id alone: one tweet legitimately
  belongs to several trends.
* Trending history from 01:00-15:59 is used ONLY to score the censoring
  filter after the fact. It is never an input to the filter and is never
  applied to negatives.
* Language control is TWEET-LEVEL (config `language.feature_language`).
  Units are defined on all activity, because a topic's peak is a real-world
  event and does not belong to one language. Window FEATURES are counted on
  the chosen language alone, so language cannot carry class signal. The
  topic-level matching that CLAUDE.md gotcha #5 prescribes is impossible
  here — the negative pool contains zero English topics at any usable size.

Run:  python -m src.data.units            # primary setting
      python -m src.data.units --sweep    # grid over min x lead x window
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.data.loading import (
    Band,
    band_from_config,
    clean_topic,
    load_config,
    parse_hashtags,
    stream,
)

# Ordered drop reasons — also the order attrition is reported in.
DROP_ORDER = ["too_small", "left_censored", "right_censored_no_tail",
              "right_censored_no_decay", "window_before_band_start",
              "window_too_sparse"]


@dataclass
class TopicSeries:
    """One topic's activity on the band grid.

    counts       — all tweets, used for peak detection and censoring
    feat_counts  — tweets in feature_language, used for window feature volume
    full_counts  — 01:00-23:59 grid, positives only, validation of the filter
    """
    topic: str
    label: int
    counts: np.ndarray
    total: int
    feat_counts: np.ndarray | None = None
    full_counts: np.ndarray | None = None
    band_offset: int = 0


def _to_array(counter: Counter, n_bins: int) -> np.ndarray:
    arr = np.zeros(n_bins, dtype=np.int32)
    for b, c in counter.items():
        if 0 <= b < n_bins:
            arr[b] = c
    return arr


# ---------------------------------------------------------------------------
# Corpus scans
# ---------------------------------------------------------------------------
def scan_trending(cfg: dict, band: Band, full: Band) -> dict[str, TopicSeries]:
    """One pass over the trending file on the FULL 01:00-23:59 grid.

    The modelling band is a slice of that grid, so positives and negatives sit
    on an identical bin lattice while pre-band history stays available for
    filter validation.
    """
    feat_lang = cfg["language"]["feature_language"]
    per_topic: dict[str, Counter] = defaultdict(Counter)
    per_lang: dict[str, Counter] = defaultdict(Counter)
    topic_idx: dict[str, int] = {}
    seen: set[int] = set()
    rows = 0

    for ch in stream(cfg["paths"]["trending_csv"],
                     ["id", "trend", "date", "time", "language"], cfg):
        rows += len(ch)
        for i, t, d, tm, lg in zip(ch["id"].values, ch["trend"].values,
                                   ch["date"].values, ch["time"].values,
                                   ch["language"].values, strict=False):
            b = full.bin_of(d, tm)
            if b is None:
                continue
            topic = clean_topic(t)
            if not topic:
                continue
            idx = topic_idx.setdefault(topic, len(topic_idx))
            try:
                key = (int(i) << 20) | idx          # de-dup on (id, topic)
            except (TypeError, ValueError):
                continue
            if key in seen:
                continue
            seen.add(key)
            per_topic[topic][b] += 1
            if feat_lang and lg == feat_lang:
                per_lang[topic][b] += 1

    offset = (band.start_sec - full.start_sec) // full.bin_sec
    out = {}
    for topic, cnt in per_topic.items():
        fc = _to_array(cnt, full.n_bins)
        bc = fc[offset:offset + band.n_bins]
        lc = (_to_array(per_lang[topic], full.n_bins)[offset:offset + band.n_bins]
              if feat_lang else None)
        out[topic] = TopicSeries(topic=topic, label=1, counts=bc,
                                 total=int(bc.sum()), feat_counts=lc,
                                 full_counts=fc, band_offset=offset)
    print(f"  trending: {rows:,} rows scanned, {len(out):,} topics on grid",
          file=sys.stderr)
    return out


def scan_nontrending(cfg: dict, band: Band, trend_names: set[str]):
    """One pass over the non-trending file, band only.

    Any hashtag matching a CLEANED trend name is excluded — this is the fix for
    the prototype's negative-pool leak.
    """
    feat_lang = cfg["language"]["feature_language"]
    per_topic: dict[str, Counter] = defaultdict(Counter)
    per_lang: dict[str, Counter] = defaultdict(Counter)
    topic_idx: dict[str, int] = {}
    seen: set[int] = set()
    rows = 0
    excluded: set[str] = set()

    for ch in stream(cfg["paths"]["nontrending_csv"],
                     ["id", "date", "time", "language", "hashtags"], cfg):
        rows += len(ch)
        for i, d, tm, lg, hs in zip(ch["id"].values, ch["date"].values,
                                    ch["time"].values, ch["language"].values,
                                    ch["hashtags"].values, strict=False):
            b = band.bin_of(d, tm)
            if b is None:
                continue
            for topic in parse_hashtags(hs):
                if topic in trend_names:
                    excluded.add(topic)
                    continue
                idx = topic_idx.setdefault(topic, len(topic_idx))
                try:
                    key = (int(i) << 20) | idx
                except (TypeError, ValueError):
                    continue
                if key in seen:
                    continue
                seen.add(key)
                per_topic[topic][b] += 1
                if feat_lang and lg == feat_lang:
                    per_lang[topic][b] += 1

    out = {t: TopicSeries(topic=t, label=0, counts=_to_array(c, band.n_bins),
                          total=int(sum(c.values())),
                          feat_counts=(_to_array(per_lang[t], band.n_bins)
                                       if feat_lang else None))
           for t, c in per_topic.items()}
    print(f"  non-trending: {rows:,} rows scanned, {len(out):,} candidate "
          f"hashtags on grid, {len(excluded):,} excluded for having trended",
          file=sys.stderr)
    return out, len(excluded)


# ---------------------------------------------------------------------------
# Peak detection + censoring
# ---------------------------------------------------------------------------
def smooth(x: np.ndarray, k: int) -> np.ndarray:
    """Centred moving average, length preserved, edges replicated."""
    if k <= 1:
        return x.astype(float)
    if k % 2 == 0:
        k += 1
    pad = k // 2
    xp = np.pad(x.astype(float), pad, mode="edge")
    return np.convolve(xp, np.ones(k) / k, mode="valid")


def detect_peak(counts: np.ndarray, smooth_bins: int) -> tuple[int, float]:
    """Peak bin = argmax of the smoothed curve; ties resolve to the earliest."""
    sm = smooth(counts, smooth_bins)
    b = int(np.argmax(sm))
    return b, float(sm[b])


def censor_reason(sm: np.ndarray, peak_bin: int, peak_h: float,
                  cfg: dict) -> str | None:
    """Censoring verdict from band data ALONE. Symmetric across classes."""
    c = cfg["censoring"]
    # LEFT: already running hot at collection start -> rise never recorded.
    if peak_h > 0 and sm[0] >= c["left_censor_frac"] * peak_h:
        return "left_censored"
    # RIGHT: not enough post-peak data to confirm the peak is a peak.
    need = c["min_post_peak_bins"]
    if peak_bin > len(sm) - 1 - need:
        return "right_censored_no_tail"
    tail = sm[peak_bin + 1: peak_bin + 1 + need]
    if peak_h > 0 and float(tail.mean()) >= c["post_peak_decay_frac"] * peak_h:
        return "right_censored_no_decay"
    return None


def make_unit(ts: TopicSeries, band: Band, cfg: dict, lead_minutes: int,
              window_minutes: int, min_topic: int | None = None,
              min_window: int | None = None,
              use_feature_language: bool = True) -> tuple[dict | None, str]:
    """Apply the full filter chain to one topic. Returns (unit_or_None, reason)."""
    u = cfg["units"]
    min_topic = u["min_topic_tweets"] if min_topic is None else min_topic
    min_window = u["min_window_tweets"] if min_window is None else min_window

    if ts.total < min_topic:
        return None, "too_small"

    # Peak and censoring always use ALL activity: the peak is a real-world
    # event, not a property of one language.
    peak_bin, peak_h = detect_peak(ts.counts, u["smooth_bins"])
    sm = smooth(ts.counts, u["smooth_bins"])
    reason = censor_reason(sm, peak_bin, peak_h, cfg)
    if reason:
        return None, reason

    lead_b = band.minutes_to_bins(lead_minutes)
    win_b = band.minutes_to_bins(window_minutes)
    win_end = peak_bin - lead_b            # exclusive: no post-cutoff data
    win_start = win_end - win_b
    if win_start < 0:
        return None, "window_before_band_start"

    n_all = int(ts.counts[win_start:win_end].sum())
    feat = ts.feat_counts if (use_feature_language and ts.feat_counts is not None) \
        else ts.counts
    n_feat = int(feat[win_start:win_end].sum())
    if n_feat < min_window:
        return None, "window_too_sparse"

    return {
        "topic": ts.topic,
        "label": ts.label,
        "total_band_tweets": ts.total,
        "peak_bin": peak_bin,
        "peak_clock": band.bin_to_clock(peak_bin),
        "peak_height_smoothed": round(peak_h, 3),
        "window_start_bin": win_start,
        "window_end_bin": win_end,
        "window_start_clock": band.bin_to_clock(win_start),
        "window_end_clock": band.bin_to_clock(win_end),
        "lead_minutes": lead_minutes,
        "window_minutes": window_minutes,
        "n_window_tweets": n_feat,
        "n_window_tweets_all_langs": n_all,
        "feature_language_frac": round(n_feat / n_all, 4) if n_all else 0.0,
    }, "kept"


def build_units(series: dict[str, TopicSeries], band: Band, cfg: dict,
                lead_minutes: int, window_minutes: int, **kw):
    units, drops, verdicts = [], Counter(), {}
    for ts in series.values():
        unit, reason = make_unit(ts, band, cfg, lead_minutes, window_minutes, **kw)
        verdicts[ts.topic] = reason
        if unit is None:
            drops[reason] += 1
        else:
            units.append(unit)
    return units, drops, verdicts


# ---------------------------------------------------------------------------
# Censoring-filter validation (positives only, never an input to the filter)
# ---------------------------------------------------------------------------
def validate_censoring(series: dict[str, TopicSeries], cfg: dict,
                       verdicts: dict[str, str], min_topic: int) -> dict:
    """Score the left-censoring filter against pre-band ground truth.

    Filter-positive = "flagged left_censored".
      FN = truly censored, filter let it through  -> contamination
      FP = not censored,   filter dropped it      -> data lost
    """
    k = cfg["units"]["smooth_bins"]
    tp = fp = fn = tn = 0
    frac_flagged, frac_kept = [], []
    for ts in series.values():
        if ts.full_counts is None or ts.total < min_topic:
            continue
        true_peak = int(np.argmax(smooth(ts.full_counts, k)))
        truly_censored = true_peak < ts.band_offset
        flagged = verdicts.get(ts.topic) == "left_censored"

        total_vol = int(ts.full_counts.sum())
        frac = int(ts.full_counts[:ts.band_offset].sum()) / total_vol if total_vol else 0.0
        (frac_flagged if flagged else frac_kept).append(frac)

        if flagged and truly_censored:
            tp += 1
        elif flagged:
            fp += 1
        elif truly_censored:
            fn += 1
        else:
            tn += 1

    n = tp + fp + fn + tn
    return {
        "n_scored": n,
        "true_positives": tp, "false_positives": fp,
        "false_negatives": fn, "true_negatives": tn,
        "accuracy": round((tp + tn) / n, 4) if n else None,
        "recall_of_censored": round(tp / (tp + fn), 4) if (tp + fn) else None,
        "precision_of_flag": round(tp / (tp + fp), 4) if (tp + fp) else None,
        "false_negative_rate": round(fn / (tp + fn), 4) if (tp + fn) else None,
        "false_positive_rate": round(fp / (fp + tn), 4) if (fp + tn) else None,
        "mean_pre_band_volume_frac_flagged":
            round(float(np.mean(frac_flagged)), 4) if frac_flagged else None,
        "mean_pre_band_volume_frac_kept":
            round(float(np.mean(frac_kept)), 4) if frac_kept else None,
        "ground_truth_rule": "true peak (01:00-23:59 grid) falls before 16:00",
    }


# ---------------------------------------------------------------------------
# Reporting helpers
# ---------------------------------------------------------------------------
def attrition_rows(n_on_grid: int, drops: Counter, n_kept: int):
    remaining = n_on_grid
    rows = [("topics on grid", 0, remaining)]
    for reason in DROP_ORDER:
        d = drops.get(reason, 0)
        remaining -= d
        rows.append((reason, d, remaining))
    rows.append(("SURVIVING", 0, n_kept))
    return rows


def print_attrition(name, n_on_grid, drops, n_kept):
    print(f"--- {name}: attrition ---")
    print(f"{'stage':<28} {'dropped':>9} {'remaining':>10}")
    for stage, d, rem in attrition_rows(n_on_grid, drops, n_kept):
        print(f"{stage:<28} {d:>9,} {rem:>10,}")
    print()


def run_sweep(pos, neg, band, cfg):
    """Grid over min_topic x lead x window, with and without the language
    filter, so the cost of the language control is visible."""
    u = cfg["units"]
    lang = cfg["language"]["feature_language"]
    thr = cfg["language"]["es_majority_threshold"]
    print(f"\nSWEEP — feature_language={lang!r}. 'all' = no language filter, "
          f"'{lang}' = tweet-level filter.")
    print(f"'lost' = positives that survive on all languages but fall below "
          f"min_window_tweets on {lang} alone.")
    print(f"'route1' = surviving units whose window is >={thr:.0%} {lang} "
          f"(topic-level check, robustness only).\n")
    print(f"{'min':>4} {'lead':>5} {'win':>4} | {'pos':>4} {'neg':>4} {'tot':>5} "
          f"| {'posAll':>7} {'negAll':>7} | {'lost':>5} | {'r1pos':>6} {'r1neg':>6} "
          f"| floor")
    print("-" * 88)
    grid = {}
    for min_topic in u["min_topic_tweets_sweep"]:
        for lead in u["lead_sweep"]:
            for win in u["window_sweep"]:
                kw = dict(min_topic=min_topic)
                up, _, _ = build_units(pos, band, cfg, lead, win, **kw)
                un, _, _ = build_units(neg, band, cfg, lead, win, **kw)
                up_all, _, _ = build_units(pos, band, cfg, lead, win,
                                           use_feature_language=False, **kw)
                un_all, _, _ = build_units(neg, band, cfg, lead, win,
                                           use_feature_language=False, **kw)
                r1p = sum(1 for x in up if x["feature_language_frac"] >= thr)
                r1n = sum(1 for x in un if x["feature_language_frac"] >= thr)
                p, n = len(up), len(un)
                lost = len(up_all) - p
                ok = "OK" if (p + n >= 120 and p >= 40 and n >= 40) else "below"
                grid[f"min{min_topic}_lead{lead}_win{win}"] = {
                    "pos": p, "neg": n, "total": p + n,
                    "pos_all_langs": len(up_all), "neg_all_langs": len(un_all),
                    "positives_lost_to_language_filter": lost,
                    "route1_pos": r1p, "route1_neg": r1n}
                print(f"{min_topic:>4} {lead:>5} {win:>4} | {p:>4} {n:>4} {p+n:>5} "
                      f"| {len(up_all):>7} {len(un_all):>7} | {lost:>5} "
                      f"| {r1p:>6} {r1n:>6} | {ok}")
    return grid


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sweep", action="store_true",
                    help="print the parameter grid instead of writing units")
    args = ap.parse_args()

    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    vh = cfg["validation_history"]
    full = band_from_config(cfg, hours=(vh["start_hour"], cfg["band"]["end_hour"]))

    print(f"Band: {cfg['band']['date']} {cfg['band']['start_hour']:02d}:00-"
          f"{cfg['band']['end_hour']:02d}:59 | {cfg['units']['bin_minutes']}-min "
          f"bins -> {band.n_bins} bins")
    print(f"Feature language (tweet-level control): "
          f"{cfg['language']['feature_language']!r}\n")

    print("Scanning corpus ...")
    pos = scan_trending(cfg, band, full)
    neg, n_excluded = scan_nontrending(cfg, band, set(pos))
    print(f"  scan done ({time.time()-t0:.0f}s)")

    if args.sweep:
        grid = run_sweep(pos, neg, band, cfg)
        with open(f"{cfg['paths']['tables']}/units_sweep.json", "w",
                  encoding="utf-8") as fh:
            json.dump(grid, fh, indent=2)
        print(f"\nWrote {cfg['paths']['tables']}/units_sweep.json "
              f"({time.time()-t0:.0f}s)")
        return 0

    lead, window = cfg["units"]["lead_minutes"], cfg["units"]["window_minutes"]
    min_topic = cfg["units"]["min_topic_tweets"]
    pos_units, pos_drops, pos_verdicts = build_units(pos, band, cfg, lead, window)
    neg_units, neg_drops, _ = build_units(neg, band, cfg, lead, window)
    units = pos_units + neg_units
    n_pos, n_neg = len(pos_units), len(neg_units)

    print(f"\nPRIMARY: lead={lead} min, window={window} min, "
          f"min_topic_tweets={min_topic}, "
          f"min_window_tweets={cfg['units']['min_window_tweets']}\n")
    print_attrition("TRENDING (positives)", len(pos), pos_drops, n_pos)
    print_attrition("NON-TRENDING (negatives)", len(neg), neg_drops, n_neg)

    print(f"USABLE UNITS: {n_pos + n_neg}  ({n_pos} trending / {n_neg} non-trending)")
    if units:
        print(f"  positive prevalence: {n_pos/(n_pos+n_neg):.3f}")
    print(f"  negatives excluded for having trended: {n_excluded:,}\n")

    print("--- censoring-filter validation (positives only, held-out history) ---")
    val = validate_censoring(pos, cfg, pos_verdicts, min_topic)
    for k, v in val.items():
        print(f"  {k:<38} {v}")
    print()

    out_csv = f"{cfg['paths']['cache']}/units.csv"
    pd.DataFrame(units).to_csv(out_csv, index=False)
    summary = {
        "config": {"band": cfg["band"], "units": cfg["units"],
                   "censoring": cfg["censoring"], "language": cfg["language"]},
        "n_units": len(units), "n_positive": n_pos, "n_negative": n_neg,
        "negatives_excluded_for_trending": n_excluded,
        "topics_on_grid": {"positive": len(pos), "negative": len(neg)},
        "attrition_positive": {r: pos_drops.get(r, 0) for r in DROP_ORDER},
        "attrition_negative": {r: neg_drops.get(r, 0) for r in DROP_ORDER},
        "censoring_validation": val,
        "seed": cfg["seed"],
    }
    with open(f"{cfg['paths']['tables']}/units_summary.json", "w",
              encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, ensure_ascii=False)
    print(f"Wrote {out_csv}\nWrote {cfg['paths']['tables']}/units_summary.json")
    print(f"Total {time.time()-t0:.0f}s")

    if len(units) < 120 or n_pos < 40 or n_neg < 40:
        print("\n*** BELOW CONTINGENCY HARD FLOOR (120 total, 40/class) — "
              "floor is BREACHED, not ignored: bootstrap CIs become the primary "
              "uncertainty statement and small effects are undetectable. ***")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
