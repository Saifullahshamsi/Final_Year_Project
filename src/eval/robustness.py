"""Robustness checks.

**Framing.** These are sensitivity checks on a model with a confound that could
not be removed (see the language-control section of FINDINGS.md). They test
whether conclusions are stable under parameter choices. They do **not**
validate a clean result, because there is no clean result to validate.

Three checks:

1. **Common-support ablation.** The only slice of the corpus where the two
   classes overlap in language at all. Badly underpowered — 15 trending against
   28 non-trending — and will not reach significance. Run anyway, because
   attempting the one comparison the confound does not dominate, and reporting
   that it resolves nothing, is more informative than declining to try.
2. **`min_window_tweets` 15 / 20 / 25.** This was the one tuned parameter, so it
   carries the highest risk of the result being an artifact of its value.
3. **Window length 30 / 60 / 90 min.** Window length drives graph sparsity,
   which is what pushed four structural features into the volume arm.

Run:  python -m src.eval.robustness
"""
from __future__ import annotations

import json
import time

import pandas as pd

from src.data.loading import band_from_config, load_config, utf8_console
from src.data.units import build_units, scan_nontrending, scan_trending
from src.eval.ablation import mcnemar
from src.eval.language_control import cv_score, window_language_mix
from src.eval.matrix import build_feature_matrix
from src.eval.size_audit import load_matrices
from src.features.feature_sets import resolve
from src.features.sentiment import collect_texts, lead_sweep_bins, load_cache

ARMS = ["volume_only", "structure_size_free", "full_fusion", "volume_extended"]


def run_arms(cfg, df, arms=ARMS, seed_offset=0):
    y = df["label"].values.astype(int)
    out, preds = {}, {}
    for arm in arms:
        cols = resolve(cfg, arm)
        out[arm], preds[arm] = cv_score(cfg, df[cols].values.astype(float), y,
                                        seed_offset)
    return out, preds, y


def main() -> int:
    utf8_console()
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    vh = cfg["validation_history"]
    full = band_from_config(cfg, hours=(vh["start_hour"], cfg["band"]["end_hour"]))
    results = {}

    # ------------------------------------------------------------------
    # 1. Common-support ablation
    # ------------------------------------------------------------------
    print("=" * 74)
    print("1 — COMMON-SUPPORT ABLATION (the only language overlap between classes)")
    print("=" * 74)
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")
    feats = load_matrices(cfg)
    mix, _ = window_language_mix(cfg, band, units)
    mix = mix.set_index("topic").loc[feats.topic].reset_index()
    es = mix["lang_es_frac"].values
    lo, hi = 0.5, 0.99
    keep = (es >= lo) & (es < hi)
    sub = feats[keep].reset_index(drop=True)
    ysub = sub["label"].values.astype(int)
    n_pos, n_neg = int(ysub.sum()), int((1 - ysub).sum())
    print(f"  band: Spanish share in [{lo}, {hi})")
    print(f"  units: {len(sub)} ({n_pos} trending / {n_neg} non-trending, "
          f"prevalence {ysub.mean():.3f})")
    print("  UNDERPOWERED BY CONSTRUCTION — reported for completeness, not as "
          "a test that can settle anything\n")
    cs = {"band": [lo, hi], "n_units": int(len(sub)), "n_positive": n_pos,
          "n_negative": n_neg, "prevalence": float(ysub.mean())}
    if n_pos >= 10 and n_neg >= 10:
        res, preds, _ = run_arms(cfg, sub, seed_offset=3)
        for arm, r in res.items():
            print(f"  {arm:<24} PR-AUC {r['pr_auc']:.3f} "
                  f"[{r['pr_auc_ci'][0]:.3f}, {r['pr_auc_ci'][1]:.3f}]  "
                  f"chance {r['chance_pr_auc']:.3f}  "
                  f"lift {r['pr_auc'] - r['chance_pr_auc']:+.3f}")
        thr = cfg["evaluation"]["decision_threshold"]
        m = mcnemar(ysub, (preds["full_fusion"] >= thr).astype(int),
                    (preds["volume_extended"] >= thr).astype(int))
        print(f"\n  full_fusion vs volume_extended: McNemar p={m['p_value']:.4f} "
              f"({m['only_a_correct']}/{m['only_b_correct']} discordant)")
        # Does the language signal survive inside the overlap band?
        lang_r, _ = cv_score(cfg, mix[keep][["lang_es_frac"]].values, ysub, 4)
        print(f"  language-only inside the band: PR-AUC {lang_r['pr_auc']:.3f} "
              f"(chance {lang_r['chance_pr_auc']:.3f})")
        cs.update({"arms": res, "fusion_vs_volume_extended": m,
                   "language_only_in_band": lang_r})
    else:
        print("  too few per class even to attempt")
    results["common_support"] = cs

    # ------------------------------------------------------------------
    # Shared inputs for the parameter sweeps
    # ------------------------------------------------------------------
    print(f"\nScanning corpus for the parameter sweeps ({time.time()-t0:.0f}s) ...")
    pos = scan_trending(cfg, band, full)
    neg, _ = scan_nontrending(cfg, band, set(pos))
    series = {t: (ts.feat_counts if ts.feat_counts is not None else ts.counts)
              for pool in (pos, neg) for t, ts in pool.items()}
    # Every setting's units are built FIRST, then the sentiment texts are
    # collected over the union. Collecting for the primary units alone left 11
    # units in the 30-minute-window setting with no cached texts and therefore
    # all-zero sentiment features — a silent bias in exactly the arm being
    # tested.
    lead = cfg["units"]["lead_minutes"]
    win = cfg["units"]["window_minutes"]
    settings_mw = [(f"min_window={mw}",
                    build_units(pos, band, cfg, lead, win, min_window=mw)[0],
                    build_units(neg, band, cfg, lead, win, min_window=mw)[0])
                   for mw in (15, 20, 25)]
    settings_win = [(f"window={w}min",
                     build_units(pos, band, cfg, lead, w)[0],
                     build_units(neg, band, cfg, lead, w)[0])
                    for w in cfg["units"]["window_sweep"]]

    all_units = pd.concat(
        [units] + [pd.DataFrame(up + un) for _, up, un in settings_mw + settings_win]
    ).drop_duplicates("topic").reset_index(drop=True)
    print(f"  sentiment texts collected over {len(all_units)} distinct topics "
          "across every sweep setting")
    sent_per_topic, _ = collect_texts(cfg, band, all_units,
                                      cfg["language"]["feature_language"],
                                      lead_sweep_bins(all_units, band, cfg))
    cache = load_cache(pd.io.common.Path(cfg["paths"]["cache"])
                       / cfg["sentiment"]["cache_file"].replace(".parquet", ".csv"))
    print(f"  done ({time.time()-t0:.0f}s)\n")

    def sweep(name, header, settings, build):
        print("=" * 74)
        print(header)
        print("=" * 74)
        rows = {}
        for label, up, un in settings:
            u = pd.DataFrame(up + un)
            n_p, n_n = int(u.label.sum()), int((1 - u.label).sum())
            if len(u) < 40 or n_p < 12 or n_n < 12:
                print(f"  {label}: {len(u)} units — too few, not modelled")
                rows[label] = {"n_units": len(u), "modelled": False}
                continue
            missing = [t for t in u.topic if t not in sent_per_topic]
            df = build(u)
            res, preds, y = run_arms(cfg, df, seed_offset=5)
            print(f"  {label}: {len(u)} units ({n_p}+/{n_n}-), "
                  f"chance {u.label.mean():.3f}"
                  + (f"  [{len(missing)} units outside the sentiment cache]"
                     if missing else ""))
            for arm, r in res.items():
                print(f"      {arm:<24} PR-AUC {r['pr_auc']:.3f} "
                      f"lift {r['pr_auc'] - r['chance_pr_auc']:+.3f}")
            thr = cfg["evaluation"]["decision_threshold"]
            m = mcnemar(y, (preds["full_fusion"] >= thr).astype(int),
                        (preds["volume_extended"] >= thr).astype(int))
            print(f"      fusion vs volume_extended p={m['p_value']:.4f}")
            rows[label] = {"n_units": int(len(u)), "n_positive": n_p,
                           "n_negative": n_n, "modelled": True,
                           "prevalence": float(u.label.mean()), "arms": res,
                           "fusion_vs_volume_extended": m}
        results[name] = rows
        print()

    sweep("min_window_tweets",
          "2 — min_window_tweets SENSITIVITY (the one tuned parameter)",
          settings_mw,
          lambda u: build_feature_matrix(cfg, band, u, series, sent_per_topic, cache))

    sweep("window_minutes",
          "3 — WINDOW-LENGTH SENSITIVITY (drives graph sparsity)",
          settings_win,
          lambda u: build_feature_matrix(cfg, band, u, series, sent_per_topic, cache))

    with open(f"{cfg['paths']['tables']}/robustness.json", "w",
              encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=float)
    print(f"Wrote {cfg['paths']['tables']}/robustness.json")
    print(f"Total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
