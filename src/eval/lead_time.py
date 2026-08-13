"""Lead-time curve — the evidence for H2.

H2 claims network and sentiment features extend the achievable lead time beyond
engagement counts alone. The test is whether the gap between the fused model
and volume *widens* as the cut-off moves earlier.

The sample shrinks at every step, because a longer lead requires the window to
start earlier and more topics fail the "window fits inside the band" filter. So
**n is reported at every lead and drawn on the figure**, not relegated to the
text: a curve that rises at 180 minutes on 40 units says something very
different from one that rises on 129.

Everything is rebuilt per lead — units, censoring, windows and all three
feature channels — because changing the lead changes which topics survive, not
merely which tweets are counted. The sentiment cache already covers the union
of every lead-sweep window, so no tweet is scored twice.

Run:  python -m src.eval.lead_time
"""
from __future__ import annotations

import json
import time

import pandas as pd
from sklearn.metrics import average_precision_score, f1_score, roc_auc_score
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict

from src.data.loading import band_from_config, load_config
from src.data.units import build_units, scan_nontrending, scan_trending
from src.eval.ablation import bootstrap_ci, mcnemar
from src.features.feature_sets import resolve
from src.features.network import collect_window_tweets, features_for_unit
from src.features.sentiment import aggregate, collect_texts, lead_sweep_bins, load_cache
from src.features.temporal import features_for_unit as temporal_features
from src.models.fusion import build_estimator, single_threaded

# Kept deliberately small: H2 is about volume versus fusion as the lead grows,
# and every extra arm costs sample-size-limited statistical clarity.
ARMS = ["volume_only", "volume_extended", "volume_plus_structure", "full_fusion"]


def evaluate(cfg, df, arm):
    cols = resolve(cfg, arm)
    X = df[cols].values.astype(float)
    y = df["label"].values.astype(int)
    cv = StratifiedGroupKFold(n_splits=cfg["model"]["cv_folds"], shuffle=True,
                              random_state=cfg["seed"])
    with single_threaded(cfg):
        p = cross_val_predict(build_estimator(cfg), X, y, cv=cv,
                              groups=df["topic"].values, method="predict_proba",
                              n_jobs=cfg["model"]["n_jobs"])[:, 1]
    lo, hi = bootstrap_ci(y, p, average_precision_score,
                          cfg["model"]["n_bootstrap"], cfg["seed"])
    hard = (p >= cfg["evaluation"]["decision_threshold"]).astype(int)
    return {"pr_auc": float(average_precision_score(y, p)),
            "pr_auc_ci": [lo, hi],
            "roc_auc": float(roc_auc_score(y, p)),
            "f1": float(f1_score(y, hard, zero_division=0)),
            "n_features": len(cols)}, p


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    vh = cfg["validation_history"]
    full = band_from_config(cfg, hours=(vh["start_hour"], cfg["band"]["end_hour"]))
    window = cfg["units"]["window_minutes"]
    leads = cfg["units"]["lead_sweep"]

    print(f"LEAD-TIME SWEEP  leads {leads} min, window {window} min\n")
    print("Scanning corpus ...")
    pos = scan_trending(cfg, band, full)
    neg, _ = scan_nontrending(cfg, band, set(pos))
    series = {t: (ts.feat_counts if ts.feat_counts is not None else ts.counts)
              for pool in (pos, neg) for t, ts in pool.items()}
    print(f"  done ({time.time() - t0:.0f}s)\n")

    # Units per lead, then one sentiment collection over the union.
    per_lead_units = {}
    for lead in leads:
        up, _, _ = build_units(pos, band, cfg, lead, window)
        un, _, _ = build_units(neg, band, cfg, lead, window)
        per_lead_units[lead] = pd.DataFrame(up + un)

    union = pd.concat(per_lead_units.values()).drop_duplicates("topic")
    sent_bins = lead_sweep_bins(union, band, cfg)
    print("Collecting sentiment texts over the lead-sweep union ...")
    sent_per_topic, _ = collect_texts(cfg, band, union,
                                      cfg["language"]["feature_language"],
                                      sent_bins)
    cache = load_cache(pd.io.common.Path(cfg["paths"]["cache"])
                       / cfg["sentiment"]["cache_file"].replace(".parquet", ".csv"))
    print(f"  {len(cache):,} cached scores ({time.time() - t0:.0f}s)\n")

    results, curves = {}, {}
    for lead in leads:
        units = per_lead_units[lead]
        n_pos = int(units.label.sum())
        n_neg = int((1 - units.label).sum())
        print(f"--- lead {lead} min: {len(units)} units "
              f"({n_pos} trending / {n_neg} non-trending, "
              f"prevalence {units.label.mean():.3f}) ---")
        if len(units) < 40 or n_pos < 12 or n_neg < 12:
            print("    too few units to model at this lead — reported as such\n")
            results[lead] = {"n_units": len(units), "n_positive": n_pos,
                             "n_negative": n_neg, "modelled": False}
            continue

        recs = collect_window_tweets(cfg, band, units)
        rows = []
        for r in units.itertuples():
            net = features_for_unit(r, recs.get(r.topic, []), cfg)
            tem = temporal_features(r, series[r.topic])
            sent = aggregate([(b, k) for b, k in sent_per_topic.get(r.topic, [])
                              if r.window_start_bin <= b < r.window_end_bin],
                             cache, cfg)
            net.update({k: v for k, v in tem.items()
                        if k not in ("topic", "label")})
            net.update(sent)
            rows.append(net)
        df = pd.DataFrame(rows)

        preds, arm_res = {}, {}
        for arm in ARMS:
            arm_res[arm], preds[arm] = evaluate(cfg, df, arm)
            r = arm_res[arm]
            print(f"    {arm:<24} PR-AUC {r['pr_auc']:.3f} "
                  f"[{r['pr_auc_ci'][0]:.3f}, {r['pr_auc_ci'][1]:.3f}]  "
                  f"ROC {r['roc_auc']:.3f}")

        thr = cfg["evaluation"]["decision_threshold"]
        y = df["label"].values.astype(int)
        m = mcnemar(y, (preds["full_fusion"] >= thr).astype(int),
                    (preds["volume_extended"] >= thr).astype(int))
        print(f"    full_fusion vs volume_extended: McNemar p={m['p_value']:.4f}\n")

        results[lead] = {"n_units": int(len(units)), "n_positive": n_pos,
                         "n_negative": n_neg,
                         "prevalence": float(units.label.mean()),
                         "modelled": True, "arms": arm_res,
                         "fusion_vs_volume_extended": m}
        curves[lead] = arm_res

    # ---- figure: PR-AUC vs lead, CI bands, n annotated on the axis ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    modelled = [ld for ld in leads if results[ld].get("modelled")]
    colours = {"volume_only": "#888888", "volume_extended": "#b06b1f",
               "volume_plus_structure": "#2a8a8a", "full_fusion": "#1f3a5f"}
    fig, ax = plt.subplots(figsize=(7.2, 4.8), dpi=200)
    for arm in ARMS:
        m = [curves[ld][arm]["pr_auc"] for ld in modelled]
        lo = [curves[ld][arm]["pr_auc_ci"][0] for ld in modelled]
        hi = [curves[ld][arm]["pr_auc_ci"][1] for ld in modelled]
        ax.plot(modelled, m, "o-", color=colours[arm], lw=2, label=arm)
        ax.fill_between(modelled, lo, hi, color=colours[arm], alpha=0.12)
    for ld in modelled:
        ax.axhline(results[ld]["prevalence"], color="#cccccc", ls=":", lw=0.8)
    ax.set_xticks(modelled)
    ax.set_xticklabels([f"{ld}\nn={results[ld]['n_units']}\n"
                        f"({results[ld]['n_positive']}+/"
                        f"{results[ld]['n_negative']}-)" for ld in modelled])
    ax.set_xlabel("Lead time before peak (minutes) — sample size shown per point")
    ax.set_ylabel("PR-AUC (out-of-fold, shaded = bootstrap 95% CI)")
    ax.set_title("Lead-time curve: performance as the cut-off moves earlier")
    ax.set_ylim(0, 1)
    ax.legend(fontsize=8, loc="lower left")
    fig.tight_layout()
    fig.savefig(f"{cfg['paths']['figures']}/lead_time_curve.png",
                facecolor="white", bbox_inches="tight")
    plt.close(fig)

    # PR-AUC is NOT comparable across leads: prevalence changes with the
    # surviving sample (0.279 -> 0.422), and chance PR-AUC equals prevalence.
    # Lift over chance is the comparable quantity.
    print(f"\n{'lead':>6}{'n':>6}{'pos':>5}{'chance':>8}"
          f"{'vol_only':>10}{'vol_ext':>10}{'vol+str':>10}{'fusion':>10}"
          f"{'p(f vs ve)':>12}")
    print("-" * 77)
    for ld in leads:
        r = results[ld]
        if not r.get("modelled"):
            print(f"{ld:>6}{r['n_units']:>6}{r['n_positive']:>5}"
                  f"{'— not modelled —':>50}")
            continue
        a = r["arms"]
        print(f"{ld:>6}{r['n_units']:>6}{r['n_positive']:>5}"
              f"{r['prevalence']:>8.3f}"
              f"{a['volume_only']['pr_auc']:>10.3f}"
              f"{a['volume_extended']['pr_auc']:>10.3f}"
              f"{a['volume_plus_structure']['pr_auc']:>10.3f}"
              f"{a['full_fusion']['pr_auc']:>10.3f}"
              f"{r['fusion_vs_volume_extended']['p_value']:>12.4f}")

    print("\nLIFT OVER CHANCE (PR-AUC minus prevalence) — the comparable figure")
    print(f"{'lead':>6}{'vol_only':>10}{'vol_ext':>10}{'vol+str':>10}"
          f"{'fusion':>10}")
    print("-" * 46)
    for ld in leads:
        r = results[ld]
        if not r.get("modelled"):
            continue
        c, a = r["prevalence"], r["arms"]
        r["lift"] = {k: round(a[k]["pr_auc"] - c, 4) for k in ARMS}
        print(f"{ld:>6}" + "".join(f"{r['lift'][k]:>10.3f}" for k in ARMS))

    # ---- nested comparison on the topics that survive at EVERY lead ----
    # The curve above confounds two things: performance changing with lead
    # time, and the surviving sample changing with lead time. Only topics that
    # survive at all leads can separate them.
    common = set.intersection(*(set(per_lead_units[ld].topic) for ld in leads))
    print(f"\nNESTED COMPARISON — {len(common)} topics survive at every lead")
    nested = {}
    if len(common) >= 40:
        for ld in leads:
            units = per_lead_units[ld]
            units = units[units.topic.isin(common)].reset_index(drop=True)
            n_pos = int(units.label.sum())
            if n_pos < 12 or len(units) - n_pos < 12:
                print(f"  lead {ld}: too few per class in the common subset")
                continue
            recs = collect_window_tweets(cfg, band, units)
            rows = []
            for r in units.itertuples():
                net = features_for_unit(r, recs.get(r.topic, []), cfg)
                tem = temporal_features(r, series[r.topic])
                net.update({k: v for k, v in tem.items()
                            if k not in ("topic", "label")})
                net.update(aggregate(
                    [(b, k) for b, k in sent_per_topic.get(r.topic, [])
                     if r.window_start_bin <= b < r.window_end_bin], cache, cfg))
                rows.append(net)
            d = pd.DataFrame(rows)
            prev = float(d.label.mean())
            res, pred = {}, {}
            for a in ARMS:
                res[a], pred[a] = evaluate(cfg, d, a)
            # H2 in one test: do the extra channels keep signal alive at long
            # lead where engagement counts alone do not?
            thr = cfg["evaluation"]["decision_threshold"]
            yy = d["label"].values.astype(int)
            tests = {
                "volume_only__vs__volume_plus_structure": mcnemar(
                    yy, (pred["volume_only"] >= thr).astype(int),
                    (pred["volume_plus_structure"] >= thr).astype(int)),
                "volume_only__vs__full_fusion": mcnemar(
                    yy, (pred["volume_only"] >= thr).astype(int),
                    (pred["full_fusion"] >= thr).astype(int)),
            }
            nested[ld] = {"n_units": int(len(d)), "prevalence": prev,
                          "arms": res, "mcnemar": tests,
                          "lift": {a: round(res[a]["pr_auc"] - prev, 4)
                                   for a in ARMS}}
        if nested:
            print(f"  {'lead':>6}{'n':>5}{'chance':>8}" +
                  "".join(f"{a[:9]:>10}" for a in ARMS) + "   (lift in brackets)")
            for ld, r in nested.items():
                cells = "".join(
                    f"{r['arms'][a]['pr_auc']:>10.3f}" for a in ARMS)
                lifts = " ".join(f"{r['lift'][a]:+.2f}" for a in ARMS)
                print(f"  {ld:>6}{r['n_units']:>5}{r['prevalence']:>8.3f}"
                      f"{cells}   [{lifts}]")
            print("\n  H2 test on the common subset (McNemar, exact):")
            print(f"  {'lead':>6}{'vol_only vs vol+structure':>30}"
                  f"{'vol_only vs full_fusion':>28}")
            for ld, r in nested.items():
                a = r["mcnemar"]["volume_only__vs__volume_plus_structure"]
                b = r["mcnemar"]["volume_only__vs__full_fusion"]
                print(f"  {ld:>6}   p={a['p_value']:<7.4f} "
                      f"({a['only_a_correct']}/{a['only_b_correct']} discordant)"
                      f"   p={b['p_value']:<7.4f} "
                      f"({b['only_a_correct']}/{b['only_b_correct']})")
    else:
        print("  fewer than 40 common topics — nested comparison not run")

    with open(f"{cfg['paths']['tables']}/lead_time_results.json", "w",
              encoding="utf-8") as fh:
        json.dump({"window_minutes": window, "leads": leads,
                   "seed": cfg["seed"],
                   "results": {str(k): v for k, v in results.items()},
                   "nested_common_topics": sorted(common),
                   "nested": {str(k): v for k, v in nested.items()}},
                  fh, indent=2)
    print(f"\nWrote {cfg['paths']['tables']}/lead_time_results.json")
    print(f"Wrote {cfg['paths']['figures']}/lead_time_curve.png")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
