"""Language-confound negative control.

The corpus has a severe language confound: the trending pool is multilingual
(43.7% English) while the non-trending pool is 88.8% Spanish. A classifier can
therefore score well by detecting language and learning nothing about trend
dynamics. The pipeline controls this at tweet level — features are computed
only from Spanish tweets — because topic-level matching is impossible here
(zero English negatives at any usable size).

Three tests, and it matters which is expected to pass and which to fail:

* **A — confound magnitude.** Classify the label from the window's *raw
  language mix* alone. This SHOULD succeed. It measures how large the confound
  is, and is the justification for controlling it. A weak result here would
  mean the control was unnecessary.

* **B — leakage into the features.** Try to predict each unit's language
  composition FROM the modelled feature matrix. This MUST fail. If the features
  can recover language, they carry it, and every conclusion resting on them is
  unsafe.

* **C — survival within one language.** Re-run the main arms on the subset of
  units that are almost entirely Spanish. If performance holds there, it was
  not language driving it.

Run:  python -m src.eval.language_control
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict

import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from src.data.loading import band_from_config, clean_topic, load_config, parse_hashtags, stream
from src.eval.ablation import bootstrap_ci
from src.eval.size_audit import load_matrices
from src.features.feature_sets import resolve
from src.models.fusion import build_estimator, single_threaded

ARMS = ["volume_only", "structure_size_free", "sentiment_only", "temporal_only",
        "full_fusion", "volume_extended"]


def window_language_mix(cfg, band, units) -> pd.DataFrame:
    """Language counts inside each unit's own window, ALL languages."""
    win = {r.topic: (r.window_start_bin, r.window_end_bin, r.label)
           for r in units.itertuples()}
    pos = {t for t, w in win.items() if w[2] == 1}
    neg = {t for t, w in win.items() if w[2] == 0}
    langs: dict[str, Counter] = defaultdict(Counter)
    seen: set[tuple[str, str]] = set()

    def take(topic, tid, b, lg):
        s, e, _ = win[topic]
        if not (s <= b < e) or (tid, topic) in seen:
            return
        seen.add((tid, topic))
        langs[topic][lg if isinstance(lg, str) else "unk"] += 1

    for ch in stream(cfg["paths"]["trending_csv"],
                     ["id", "trend", "date", "time", "language"], cfg):
        for i, t, d, tm, lg in zip(ch["id"].values, ch["trend"].values,
                                   ch["date"].values, ch["time"].values,
                                   ch["language"].values, strict=False):
            topic = clean_topic(t)
            if topic in pos:
                b = band.bin_of(d, tm)
                if b is not None:
                    take(topic, i, b, lg)
    for ch in stream(cfg["paths"]["nontrending_csv"],
                     ["id", "date", "time", "language", "hashtags"], cfg):
        for i, d, tm, lg, hs in zip(ch["id"].values, ch["date"].values,
                                    ch["time"].values, ch["language"].values,
                                    ch["hashtags"].values, strict=False):
            b = band.bin_of(d, tm)
            if b is None:
                continue
            for topic in parse_hashtags(hs):
                if topic in neg:
                    take(topic, i, b, lg)

    top = [lg for lg, _ in Counter(
        {k: sum(v.values()) for k, v in langs.items()} and
        Counter([lg for c in langs.values() for lg in c.elements()])).most_common(10)]
    rows = []
    for r in units.itertuples():
        c = langs.get(r.topic, Counter())
        tot = max(sum(c.values()), 1)
        row = {"topic": r.topic, "label": int(r.label), "lang_total": sum(c.values())}
        for lg in top:
            row[f"lang_{lg}"] = c.get(lg, 0) / tot
        row["lang_n_distinct"] = len(c)
        row["lang_es_frac"] = c.get("es", 0) / tot
        rows.append(row)
    return pd.DataFrame(rows), top


def cv_score(cfg, X, y, seed_offset=0):
    cv = StratifiedKFold(n_splits=cfg["model"]["cv_folds"], shuffle=True,
                         random_state=cfg["seed"] + seed_offset)
    with single_threaded(cfg):
        p = cross_val_predict(build_estimator(cfg), X, y, cv=cv,
                              method="predict_proba",
                              n_jobs=cfg["model"]["n_jobs"])[:, 1]
    lo, hi = bootstrap_ci(y, p, average_precision_score,
                          cfg["model"]["n_bootstrap"], cfg["seed"])
    return {"pr_auc": float(average_precision_score(y, p)),
            "pr_auc_ci": [lo, hi], "roc_auc": float(roc_auc_score(y, p)),
            "chance_pr_auc": float(y.mean())}, p


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")
    feats = load_matrices(cfg)
    y = feats["label"].values.astype(int)

    print("Collecting window language mix (all languages) ...")
    mix, top_langs = window_language_mix(cfg, band, units)
    mix = mix.set_index("topic").loc[feats.topic].reset_index()
    lang_cols = [c for c in mix.columns if c.startswith("lang_")
                 and c != "lang_total"]
    print(f"  languages tracked: {top_langs}")
    print(f"  done ({time.time() - t0:.0f}s)\n")

    out = {}

    # ---- A: how big is the confound? (expected to SUCCEED) ----
    print("=" * 72)
    print("A — LANGUAGE-ONLY CLASSIFIER (expected to succeed: measures the")
    print("    confound this pipeline exists to control)")
    print("=" * 72)
    a, _ = cv_score(cfg, mix[lang_cols].values.astype(float), y)
    print(f"  features: {lang_cols}")
    print(f"  PR-AUC {a['pr_auc']:.3f} [{a['pr_auc_ci'][0]:.3f}, "
          f"{a['pr_auc_ci'][1]:.3f}]   ROC-AUC {a['roc_auc']:.3f}   "
          f"chance {a['chance_pr_auc']:.3f}")
    print(f"  mean Spanish share — trending {mix.lang_es_frac[y == 1].mean():.3f}, "
          f"non-trending {mix.lang_es_frac[y == 0].mean():.3f}")
    out["A_language_only"] = a
    # Saved, not only printed: the class overlap in Spanish share is the whole
    # argument for why within-language restriction is impossible, and a number
    # that only ever reaches a console cannot be checked against the report.
    qs = [0.0, 0.25, 0.5, 0.75, 1.0]
    out["spanish_share"] = {
        "mean_trending": round(float(mix.lang_es_frac[y == 1].mean()), 4),
        "mean_non_trending": round(float(mix.lang_es_frac[y == 0].mean()), 4),
        "quantiles": {
            lab: {
                "trending": round(float(mix.lang_es_frac[y == 1].quantile(q)), 4),
                "non_trending": round(float(mix.lang_es_frac[y == 0].quantile(q)), 4),
            }
            for lab, q in zip(("min", "p25", "p50", "p75", "max"), qs, strict=True)
        },
    }

    # ---- B: can the modelled features recover language? (MUST FAIL) ----
    print("\n" + "=" * 72)
    print("B — CAN THE MODELLED FEATURES RECOVER LANGUAGE? (must fail)")
    print("=" * 72)
    es_major = (mix["lang_es_frac"].values >= 0.5).astype(int)
    print(f"  target: window is majority Spanish "
          f"({es_major.sum()}/{len(es_major)} units)")
    out["B_language_from_features"] = {}
    for arm in ARMS:
        cols = resolve(cfg, arm)
        r, _ = cv_score(cfg, feats[cols].values.astype(float), es_major, 1)
        out["B_language_from_features"][arm] = r
        verdict = "LEAKS LANGUAGE" if r["roc_auc"] >= 0.70 else "ok"
        print(f"  {arm:<24} ROC-AUC {r['roc_auc']:.3f}  "
              f"PR-AUC {r['pr_auc']:.3f} (chance {r['chance_pr_auc']:.3f})  "
              f"{verdict}")

    # ---- C: does performance survive inside one language? ----
    print("\n" + "=" * 72)
    print("C — PERFORMANCE WITHIN NEARLY-MONOLINGUAL SPANISH UNITS")
    print("=" * 72)
    thr = 0.9
    keep = mix["lang_es_frac"].values >= thr
    sub = feats[keep].reset_index(drop=True)
    ysub = y[keep]
    n_pos, n_neg = int(ysub.sum()), int((1 - ysub).sum())
    print(f"  units with >={thr:.0%} Spanish in window: {keep.sum()} "
          f"({n_pos} trending / {n_neg} non-trending, "
          f"prevalence {ysub.mean():.3f})")
    out["C_monolingual_subset"] = {"threshold": thr, "n_units": int(keep.sum()),
                                   "n_positive": n_pos, "n_negative": n_neg}
    if n_pos >= 12 and n_neg >= 12:
        out["C_monolingual_subset"]["arms"] = {}
        for arm in ARMS:
            cols = resolve(cfg, arm)
            r, _ = cv_score(cfg, sub[cols].values.astype(float), ysub, 2)
            out["C_monolingual_subset"]["arms"][arm] = r
            print(f"  {arm:<24} PR-AUC {r['pr_auc']:.3f} "
                  f"[{r['pr_auc_ci'][0]:.3f}, {r['pr_auc_ci'][1]:.3f}]  "
                  f"chance {r['chance_pr_auc']:.3f}  "
                  f"lift {r['pr_auc'] - r['chance_pr_auc']:+.3f}")
    else:
        print("  too few units per class — reported as such, not modelled")

    with open(f"{cfg['paths']['tables']}/language_control.json", "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nWrote {cfg['paths']['tables']}/language_control.json")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
