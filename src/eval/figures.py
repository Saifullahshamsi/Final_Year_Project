"""Report figures.

Palette is Okabe-Ito, validated for colour-vision deficiency rather than chosen
by eye — the project's original navy/teal/amber set failed adjacent-pair
separation badly (grey vs teal ΔE 1.9 under protanopia, 9.8 even with normal
vision). Every series also carries a direct label and a distinct marker, so
identity never rests on colour alone.

One chart per question, no dual axes, recessive grid, chance lines drawn
explicitly because PR-AUC chance is prevalence and moves between panels.

Run:  python -m src.eval.figures
"""
from __future__ import annotations

import json
import time

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (  # noqa: E402
    StratifiedGroupKFold,
    cross_val_predict,
    train_test_split,
)

from src.data.loading import band_from_config, load_config  # noqa: E402
from src.eval.language_control import window_language_mix  # noqa: E402
from src.eval.size_audit import load_matrices  # noqa: E402
from src.features.feature_sets import resolve  # noqa: E402
from src.models.fusion import build_estimator, single_threaded  # noqa: E402

BLUE, ORANGE, GREEN, PINK = "#0072B2", "#E69F00", "#009E73", "#CC79A7"
INK, MUTED, GRID = "#1a1a1a", "#6b6b6b", "#dcdcdc"
ARM_COLOUR = {"full_fusion": BLUE, "volume_only": ORANGE,
              "volume_plus_structure": GREEN, "volume_extended": PINK}
ARM_MARKER = {"full_fusion": "o", "volume_only": "s",
              "volume_plus_structure": "^", "volume_extended": "D"}


def _style(ax, title, xlabel, ylabel):
    ax.set_title(title, fontsize=11, color=INK, pad=12)
    ax.set_xlabel(xlabel, fontsize=9, color=MUTED)
    ax.set_ylabel(ylabel, fontsize=9, color=MUTED)
    ax.tick_params(labelsize=8, colors=MUTED, length=0)
    ax.grid(True, color=GRID, lw=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)


def fig_lead_time_nested(cfg, out):
    """Nested design: the same 52 topics at every lead, so the language mix is
    held constant and only the cut-off moves."""
    data = json.load(open(f"{cfg['paths']['tables']}/lead_time_results.json",
                          encoding="utf-8"))
    nested = data.get("nested", {})
    if not nested:
        return
    leads = sorted(int(k) for k in nested)
    fig, ax = plt.subplots(figsize=(7.4, 4.8), dpi=200)
    for arm in ("full_fusion", "volume_plus_structure", "volume_extended",
                "volume_only"):
        v = [nested[str(ld)]["arms"][arm]["pr_auc"] for ld in leads]
        ax.plot(leads, v, marker=ARM_MARKER[arm], ms=7, lw=2,
                color=ARM_COLOUR[arm], label=arm, zorder=3,
                markeredgecolor="white", markeredgewidth=1.2)
        ax.annotate(arm.replace("_", " "), (leads[-1], v[-1]),
                    xytext=(8, 0), textcoords="offset points", va="center",
                    fontsize=8, color=INK)
    n = nested[str(leads[0])]["n_units"]
    ax.axhline(0.5, color=MUTED, ls="--", lw=1, zorder=1)
    ax.annotate(f"chance = 0.500  (n={n}, 26+/26−, fixed at every lead)",
                (leads[0], 0.5), xytext=(0, -14), textcoords="offset points",
                fontsize=8, color=MUTED)
    ax.set_xticks(leads)
    ax.set_xlim(leads[0] - 8, leads[-1] + 58)
    ax.set_ylim(0.4, 1.0)
    _style(ax, "Volume decays, structure persists — same 52 topics at every lead",
           "Lead time before peak (minutes)", "PR-AUC (out-of-fold)")
    fig.tight_layout()
    fig.savefig(f"{out}/fig_lead_time_nested.png", facecolor="white",
                bbox_inches="tight")
    plt.close(fig)


def fig_ablation(cfg, out):
    res = json.load(open(f"{cfg['paths']['tables']}/ablation_results.json",
                         encoding="utf-8"))
    chance = res["prevalence"]
    arms = [(k, v) for k, v in res["arms"].items() if k != "chance"]
    arms.sort(key=lambda kv: kv[1]["pr_auc"])
    names = [k for k, _ in arms]
    vals = np.array([v["pr_auc"] for _, v in arms])
    lo = np.array([v["pr_auc_ci"][0] for _, v in arms])
    hi = np.array([v["pr_auc_ci"][1] for _, v in arms])
    ks = [v["n_features"] for _, v in arms]

    fig, ax = plt.subplots(figsize=(7.6, 5.2), dpi=200)
    y = np.arange(len(names))
    colours = [ARM_COLOUR.get(n, "#8c8c8c") for n in names]
    ax.barh(y, vals, height=0.62, color=colours, zorder=3)
    ax.errorbar(vals, y, xerr=[vals - lo, hi - vals], fmt="none",
                ecolor=INK, elinewidth=1.1, capsize=3, zorder=4)
    for i, (v, k) in enumerate(zip(vals, ks, strict=True)):
        ax.text(hi[i] + 0.015, i, f"{v:.3f}  (k={k})", va="center",
                fontsize=8, color=INK)
    ax.axvline(chance, color=MUTED, ls="--", lw=1.2, zorder=5)
    ax.annotate(f"chance PR-AUC = {chance:.3f}", (chance, len(names) - 0.3),
                xytext=(6, 0), textcoords="offset points", fontsize=8,
                color=MUTED)
    ax.set_yticks(y)
    ax.set_yticklabels([n.replace("_", " ") for n in names], fontsize=8.5)
    ax.set_xlim(0, 1.12)
    _style(ax, "Ablation — PR-AUC with bootstrap 95% CI (k = feature count)",
           "PR-AUC (out-of-fold, 129 units, 42 positive)", "")
    fig.tight_layout()
    fig.savefig(f"{out}/fig_ablation.png", facecolor="white", bbox_inches="tight")
    plt.close(fig)


def fig_pr_vs_roc(cfg, df, out):
    """Why PR-AUC is the headline: the same predictions, two verdicts."""
    y = df["label"].values.astype(int)
    cols = resolve(cfg, "sentiment_only")
    cv = StratifiedGroupKFold(n_splits=cfg["model"]["cv_folds"], shuffle=True,
                              random_state=cfg["seed"])
    with single_threaded(cfg):
        p = cross_val_predict(build_estimator(cfg), df[cols].values.astype(float),
                              y, cv=cv, groups=df["topic"].values,
                              method="predict_proba",
                              n_jobs=cfg["model"]["n_jobs"])[:, 1]
    prev = y.mean()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.4), dpi=200)

    fpr, tpr, _ = roc_curve(y, p)
    axes[0].plot(fpr, tpr, color=BLUE, lw=2, zorder=3)
    axes[0].plot([0, 1], [0, 1], color=MUTED, ls="--", lw=1)
    axes[0].annotate(f"ROC-AUC = {roc_auc_score(y, p):.3f}", (0.45, 0.18),
                     fontsize=10, color=INK)
    axes[0].annotate("chance = 0.500", (0.55, 0.44), fontsize=8, color=MUTED,
                     rotation=32)
    _style(axes[0], "ROC — looks like a solid channel",
           "False positive rate", "True positive rate")

    pr, rc, _ = precision_recall_curve(y, p)
    axes[1].plot(rc, pr, color=ORANGE, lw=2, zorder=3)
    axes[1].axhline(prev, color=MUTED, ls="--", lw=1)
    axes[1].annotate(f"PR-AUC = {average_precision_score(y, p):.3f}",
                     (0.36, 0.90), fontsize=10, color=INK)
    axes[1].annotate(f"chance = {prev:.3f}", (0.02, prev + 0.03), fontsize=8,
                     color=MUTED)
    axes[1].set_ylim(0, 1)
    _style(axes[1], "Precision–recall — the weakest arm in the study",
           "Recall", "Precision")

    fig.suptitle("sentiment_only: identical predictions, opposite readings "
                 "(Saito & Rehmsmeier, 2015)", fontsize=11, color=INK)
    fig.tight_layout()
    fig.savefig(f"{out}/fig_pr_vs_roc_sentiment.png", facecolor="white",
                bbox_inches="tight")
    plt.close(fig)


def fig_size_proxy(cfg, df, out):
    """Every feature's Spearman correlation with window volume, with the
    pre-registered 0.4 threshold drawn."""
    from scipy.stats import spearmanr
    sets = cfg["features"]
    volume_sets = {"volume_baseline", "size_dependent", "temporal_size_dependent"}
    size = df[cfg["audit"]["volume_proxy"]].values.astype(float)
    rows = []
    for set_name, cols in sets.items():
        for c in cols:
            if c not in df.columns or c == cfg["audit"]["volume_proxy"]:
                continue
            v = df[c].values.astype(float)
            rho = 0.0 if len(np.unique(v)) < 2 else spearmanr(v, size).statistic
            rows.append({"feature": c, "rho": abs(float(rho)),
                         "volume_arm": set_name in volume_sets})
    d = pd.DataFrame(rows).sort_values("rho")
    thr = cfg["audit"]["size_proxy_spearman_threshold"]

    fig, ax = plt.subplots(figsize=(7.4, 11), dpi=200)
    colours = [PINK if v else BLUE for v in d.volume_arm]
    ax.barh(np.arange(len(d)), d.rho, color=colours, height=0.68, zorder=3)
    ax.axvline(thr, color=INK, ls="--", lw=1.3, zorder=5)
    ax.annotate(f"threshold {thr}\n(fixed before measuring)", (thr, len(d) - 4),
                xytext=(6, 0), textcoords="offset points", fontsize=8, color=INK)
    ax.set_yticks(np.arange(len(d)))
    ax.set_yticklabels(d.feature, fontsize=7)
    ax.set_xlim(0, 1)
    ax.legend(handles=[Line2D([], [], color=PINK, lw=6, label="assigned to volume"),
                       Line2D([], [], color=BLUE, lw=6, label="non-volume arm")],
              fontsize=8, loc="lower right", frameon=False)
    _style(ax, "Size-proxy audit — |Spearman| of each feature with window volume",
           "|ρ| with window_tweets", "")
    fig.tight_layout()
    fig.savefig(f"{out}/fig_size_proxy_audit.png", facecolor="white",
                bbox_inches="tight")
    plt.close(fig)


def fig_language_overlap(cfg, band, df, out):
    """The chart behind the study's central limitation."""
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")
    mix, _ = window_language_mix(cfg, band, units)
    mix = mix.set_index("topic").loc[df.topic].reset_index()
    y = df["label"].values.astype(int)
    es = mix["lang_es_frac"].values

    fig, axes = plt.subplots(2, 1, figsize=(7.4, 5.6), dpi=200,
                             gridspec_kw={"height_ratios": [3, 1]}, sharex=True)
    bins = np.linspace(0, 1, 26)
    axes[0].hist(es[y == 1], bins=bins, color=BLUE, alpha=0.85, label="trending",
                 zorder=3)
    axes[0].hist(es[y == 0], bins=bins, color=ORANGE, alpha=0.85,
                 label="non-trending", zorder=3)
    axes[0].axvline(es[y == 0].min(), color=INK, ls="--", lw=1.2, zorder=5)
    axes[0].annotate(f"least-Spanish non-trending unit = {es[y==0].min():.3f}\n"
                     f"(above the 75th percentile of trending, "
                     f"{np.percentile(es[y==1], 75):.3f})",
                     (es[y == 0].min(), axes[0].get_ylim()[1] * 0.55),
                     xytext=(-10, 0), textcoords="offset points", ha="right",
                     fontsize=8, color=INK)
    axes[0].legend(fontsize=8, frameon=False, loc="upper left")
    _style(axes[0], "The classes barely overlap in language — the confound "
           "that could not be controlled", "", "units")

    for cls, colour, lab in ((1, BLUE, "trending"), (0, ORANGE, "non-trending")):
        v = es[y == cls]
        axes[1].scatter(v, np.full(len(v), 1 if cls else 0), s=14, color=colour,
                        alpha=0.55, zorder=3, edgecolors="none")
        axes[1].annotate(lab, (0.01, 1 if cls else 0), xytext=(0, 8),
                         textcoords="offset points", fontsize=8, color=colour)
    axes[1].set_yticks([])
    axes[1].set_ylim(-0.6, 1.6)
    _style(axes[1], "", "Spanish share of the unit's feature window", "")
    fig.tight_layout()
    fig.savefig(f"{out}/fig_language_overlap.png", facecolor="white",
                bbox_inches="tight")
    plt.close(fig)


def fig_importance(cfg, df, out):
    """Permutation importance for full_fusion.

    Computed on a held-out split, not on training data. With 129 units this is
    indicative only — it is a sanity check against theory, not a ranking to
    interpret feature by feature.
    """
    from sklearn.inspection import permutation_importance
    cols = resolve(cfg, "full_fusion")
    X = df[cols].values.astype(float)
    y = df["label"].values.astype(int)
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y,
                                          random_state=cfg["seed"])
    with single_threaded(cfg):
        model = build_estimator(cfg).fit(Xtr, ytr)
        imp = permutation_importance(model, Xte, yte, n_repeats=30,
                                     random_state=cfg["seed"],
                                     scoring="average_precision")
    d = pd.DataFrame({"feature": cols, "mean": imp.importances_mean,
                      "std": imp.importances_std}).sort_values("mean")
    d = d.tail(18)
    sets = cfg["features"]

    def arm_of(c):
        for k in ("volume_baseline", "structure_size_free", "sentiment", "temporal"):
            if c in sets[k]:
                return k
        return "other"

    palette = {"volume_baseline": ORANGE, "structure_size_free": GREEN,
               "sentiment": PINK, "temporal": BLUE, "other": MUTED}
    fig, ax = plt.subplots(figsize=(7.4, 6.4), dpi=200)
    colours = [palette[arm_of(c)] for c in d.feature]
    ax.barh(np.arange(len(d)), d["mean"], xerr=d["std"], color=colours,
            height=0.68, zorder=3, error_kw=dict(ecolor=INK, elinewidth=0.9))
    ax.axvline(0, color=MUTED, lw=1)
    ax.set_yticks(np.arange(len(d)))
    ax.set_yticklabels(d.feature, fontsize=8)
    ax.legend(handles=[Line2D([], [], color=palette[k], lw=6,
                              label=k.replace("_", " "))
                       for k in ("volume_baseline", "structure_size_free",
                                 "sentiment", "temporal")],
              fontsize=8, loc="lower right", frameon=False)
    _style(ax, "Permutation importance, full_fusion (held-out split, "
           "indicative at n=129)", "Drop in PR-AUC when the feature is shuffled", "")
    fig.tight_layout()
    fig.savefig(f"{out}/fig_feature_importance.png", facecolor="white",
                bbox_inches="tight")
    plt.close(fig)
    d.sort_values("mean", ascending=False).to_csv(
        f"{cfg['paths']['tables']}/permutation_importance.csv", index=False)
    return d.sort_values("mean", ascending=False)


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    out = cfg["paths"]["figures"]
    df = load_matrices(cfg)

    for name, fn in (("fig_lead_time_nested", lambda: fig_lead_time_nested(cfg, out)),
                     ("fig_ablation", lambda: fig_ablation(cfg, out)),
                     ("fig_pr_vs_roc_sentiment", lambda: fig_pr_vs_roc(cfg, df, out)),
                     ("fig_size_proxy_audit", lambda: fig_size_proxy(cfg, df, out)),
                     ("fig_language_overlap",
                      lambda: fig_language_overlap(cfg, band, df, out))):
        fn()
        print(f"  {name}")
    top = fig_importance(cfg, df, out)
    print("  fig_feature_importance")

    # `mean` and `std` collide with DataFrame methods under itertuples.
    print("\nTop permutation importances (full_fusion, held-out split):")
    sets = cfg["features"]
    for _, r in top.head(12).iterrows():
        arm = next((k for k in ("volume_baseline", "structure_size_free",
                                "sentiment", "temporal") if r["feature"] in sets[k]),
                   "other")
        print(f"  {r['feature']:<28}{r['mean']:+.4f} ± {r['std']:.4f}   {arm}")
    print(f"\nWrote 6 figures to {out}")
    print(f"Total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
