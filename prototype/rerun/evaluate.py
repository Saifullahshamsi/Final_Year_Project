#!/usr/bin/env python3
"""Re-run of prototype_eval.py — same methodology, parametrised paths.

Figures are skipped; only the numbers matter for the frozen-vs-fixed
comparison. Seeds are unchanged from the original so the frozen run should
reproduce the recorded prototype table.
"""
import argparse
import json

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu, wilcoxon
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import (
    RepeatedStratifiedKFold,
    StratifiedKFold,
    cross_val_predict,
    cross_val_score,
    permutation_test_score,
)

np.random.seed(42)

ap = argparse.ArgumentParser()
ap.add_argument("--features", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--tag", required=True)
args = ap.parse_args()

df = pd.read_csv(args.features)
y = df["label"].values
prev = y.mean()
print(f"[{args.tag}] {len(df)} topics | trending prevalence = {prev:.3f}")

VOLUME = ["total_count", "unique_users"]
NETWORK = ["density", "edges_per_tweet", "max_in_degree", "mean_in_degree",
           "max_out_degree", "n_components", "largest_wcc_frac",
           "mean_component_size", "reciprocity", "pagerank_gini",
           "max_pagerank", "mean_clustering", "n_nodes", "n_edges"]
ALL = VOLUME + NETWORK


def model():
    return RandomForestClassifier(n_estimators=120, class_weight="balanced",
                                  random_state=0, n_jobs=1)


def cv_scores(cols, scoring, n_splits=5, n_repeats=8, seed=0):
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats,
                                 random_state=seed)
    return cross_val_score(model(), df[cols].values, y, scoring=scoring,
                           cv=cv, n_jobs=1)


results = {"n_topics": int(len(df)), "prevalence": float(prev)}
for name, cols in [("volume_only", VOLUME), ("network_only", NETWORK),
                   ("full", ALL)]:
    roc = cv_scores(cols, "roc_auc")
    pr = cv_scores(cols, "average_precision")
    f1 = cv_scores(cols, "f1")
    results[name] = {"roc_auc": float(roc.mean()), "roc_auc_std": float(roc.std()),
                     "pr_auc": float(pr.mean()), "pr_auc_std": float(pr.std()),
                     "f1": float(f1.mean())}
    print(f"[{args.tag}] {name:13s} ROC-AUC {roc.mean():.3f}±{roc.std():.3f}   "
          f"PR-AUC {pr.mean():.3f}±{pr.std():.3f}   F1 {f1.mean():.3f}")

cvp = StratifiedKFold(5, shuffle=True, random_state=0)
score, perm, pval = permutation_test_score(
    model(), df[NETWORK].values, y, scoring="roc_auc", cv=cvp,
    n_permutations=100, random_state=0, n_jobs=1)
print(f"[{args.tag}] permutation (network_only): observed={score:.3f}, p={pval:.4f}")
results["permutation"] = {"observed_roc_auc": float(score), "p_value": float(pval),
                          "n_permutations": 100}

cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=8, random_state=7)
net_fold, vol_fold = [], []
X = df[ALL].values
for tr, te in cv.split(X, y):
    m1 = model().fit(df[NETWORK].values[tr], y[tr])
    m2 = model().fit(df[VOLUME].values[tr], y[tr])
    net_fold.append(roc_auc_score(y[te], m1.predict_proba(df[NETWORK].values[te])[:, 1]))
    vol_fold.append(roc_auc_score(y[te], m2.predict_proba(df[VOLUME].values[te])[:, 1]))
net_fold, vol_fold = np.array(net_fold), np.array(vol_fold)
wstat, wp = wilcoxon(net_fold, vol_fold)
print(f"[{args.tag}] network vs volume ROC-AUC: {net_fold.mean():.3f} vs "
      f"{vol_fold.mean():.3f} (Wilcoxon p={wp:.4f})")
results["network_vs_volume"] = {"network_mean": float(net_fold.mean()),
                                "volume_mean": float(vol_fold.mean()),
                                "wilcoxon_p": float(wp)}

oof = cross_val_predict(model(), df[ALL].values, y,
                        cv=StratifiedKFold(5, shuffle=True, random_state=1),
                        method="predict_proba", n_jobs=1)[:, 1]
rng = np.random.default_rng(0)
boots = []
for _ in range(1000):
    s = rng.integers(0, len(y), len(y))
    if len(np.unique(y[s])) < 2:
        continue
    boots.append(roc_auc_score(y[s], oof[s]))
lo, hi = np.percentile(boots, [2.5, 97.5])
print(f"[{args.tag}] full OOF ROC-AUC bootstrap 95% CI: [{lo:.3f}, {hi:.3f}]")
results["full_bootstrap_ci"] = [float(lo), float(hi)]

uni = {}
for c in NETWORK:
    v = df[c].values
    a = roc_auc_score(y, v)
    a = max(a, 1 - a)
    try:
        _, p = mannwhitneyu(v[y == 1], v[y == 0], alternative="two-sided")
    except Exception:
        p = 1.0
    uni[c] = {"auc": float(a), "mwu_p": float(p)}
results["univariate"] = uni
print(f"[{args.tag}] top univariate: " + ", ".join(
    f"{c} {d['auc']:.3f}" for c, d in sorted(uni.items(),
                                             key=lambda kv: -kv[1]["auc"])[:4]))

json.dump(results, open(args.out, "w"), indent=2)
print(f"[{args.tag}] wrote {args.out}\n")
