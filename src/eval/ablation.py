"""Ablation across every arm, with PR-AUC as the headline metric.

PR-AUC leads because emergence is the minority class here: prevalence is 0.326,
so **chance PR-AUC is 0.326 while chance ROC-AUC is 0.50**. ROC-AUC flatters
under imbalance because a large negative pool suppresses the false-positive
rate even when precision is poor (Saito & Rehmsmeier, 2015). Every ROC figure
below must be read against the PR-AUC from the same run.

Cross-validation is grouped by topic. **Each unit is one topic, so the groups
are singletons and grouped k-fold is equivalent to stratified k-fold here** —
stated rather than implied, because "grouped CV" would otherwise suggest a
constraint that is doing work it is not doing. It is kept so that the guarantee
survives if a future unit definition emits several windows per topic.

Uncertainty is reported as bootstrap CIs over out-of-fold predictions rather
than as fold standard deviations: with 129 units the folds are small and their
spread understates uncertainty.

Run:  python -m src.eval.ablation
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import StratifiedGroupKFold, cross_val_predict

from src.data.loading import load_config
from src.eval.size_audit import load_matrices
from src.features.feature_sets import resolve, validate
from src.models.fusion import build_estimator


def arm_columns(cfg: dict, spec: dict) -> tuple[list[str], int]:
    """Columns for an arm, plus how many of them get residualised.

    For a residualised arm the proxy is appended LAST and the transformer drops
    it, so volume can never re-enter as a feature.
    """
    target = spec.get("residualise")
    if not target:
        return resolve(cfg, spec["name"]), 0
    feats = list(cfg["features"][target])
    return feats + [cfg["audit"]["volume_proxy"]], len(feats)


def oof_predictions(cfg: dict, X: np.ndarray, y: np.ndarray,
                    groups: np.ndarray, n_resid: int, kind: str) -> np.ndarray:
    cv = StratifiedGroupKFold(n_splits=cfg["model"]["cv_folds"], shuffle=True,
                              random_state=cfg["seed"])
    est = build_estimator(cfg, n_residualised=n_resid, kind=kind)
    return cross_val_predict(est, X, y, cv=cv, groups=groups,
                             method="predict_proba",
                             n_jobs=cfg["model"]["n_jobs"])[:, 1]


def bootstrap_ci(y: np.ndarray, p: np.ndarray, metric, n: int, seed: int):
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        vals.append(metric(y[idx], p[idx]))
    if not vals:
        return None, None
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(lo), float(hi)


def mcnemar(y: np.ndarray, a: np.ndarray, b: np.ndarray) -> dict:
    """Exact McNemar on the discordant pairs of two arms' OOF decisions."""
    from statsmodels.stats.contingency_tables import mcnemar as sm_mcnemar
    a_ok, b_ok = (a == y), (b == y)
    n01 = int((~a_ok & b_ok).sum())     # only B correct
    n10 = int((a_ok & ~b_ok).sum())     # only A correct
    table = [[int((a_ok & b_ok).sum()), n10], [n01, int((~a_ok & ~b_ok).sum())]]
    res = sm_mcnemar(table, exact=True)
    return {"only_a_correct": n10, "only_b_correct": n01,
            "discordant": n01 + n10, "statistic": float(res.statistic),
            "p_value": float(res.pvalue)}


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    df = load_matrices(cfg)
    validate(cfg, [c for c in df.columns
                   if c not in ("topic", "label") and not c.startswith("meta_")])

    y = df["label"].values.astype(int)
    groups = df["topic"].values
    prevalence = float(y.mean())
    thr = cfg["evaluation"]["decision_threshold"]
    n_pos, n_neg = int(y.sum()), int((1 - y).sum())

    print(f"ABLATION | {len(df)} units, {n_pos} trending / {n_neg} "
          f"non-trending, prevalence {prevalence:.3f}")
    print(f"Chance PR-AUC = {prevalence:.3f}   Chance ROC-AUC = 0.500")
    print(f"CV: {cfg['model']['cv_folds']}-fold StratifiedGroupKFold grouped by "
          f"topic (groups are singletons here), seed {cfg['seed']}")
    print(f"Bootstrap: {cfg['model']['n_bootstrap']} resamples of out-of-fold "
          f"predictions, decision threshold {thr}\n")

    results, oof = {}, {}
    for spec in cfg["ablation"]:
        name = spec["name"]
        if name == "chance":
            results[name] = {"n_features": 0, "pr_auc": prevalence,
                             "roc_auc": 0.5, "f1": None, "precision": None,
                             "recall": None, "pr_auc_ci": [None, None]}
            continue
        cols, n_resid = arm_columns(cfg, spec)
        kind = spec.get("model", "default")
        X = df[cols].values.astype(float)
        p = oof_predictions(cfg, X, y, groups, n_resid, kind)
        oof[name] = p
        hard = (p >= thr).astype(int)
        n_feat = n_resid if n_resid else len(cols)
        lo, hi = bootstrap_ci(y, p, average_precision_score,
                              cfg["model"]["n_bootstrap"], cfg["seed"])
        rlo, rhi = bootstrap_ci(y, p, roc_auc_score,
                               cfg["model"]["n_bootstrap"], cfg["seed"])
        results[name] = {
            "n_features": n_feat,
            "model": kind,
            "residualised": bool(n_resid),
            "pr_auc": float(average_precision_score(y, p)),
            "pr_auc_ci": [lo, hi],
            "roc_auc": float(roc_auc_score(y, p)),
            "roc_auc_ci": [rlo, rhi],
            "f1": float(f1_score(y, hard, zero_division=0)),
            "precision": float(precision_score(y, hard, zero_division=0)),
            "recall": float(recall_score(y, hard, zero_division=0)),
        }
        print(f"  {name:<26} done ({time.time() - t0:.0f}s)")

    print(f"\n{'arm':<26}{'k':>4}{'PR-AUC':>9}{'95% CI':>16}"
          f"{'ROC-AUC':>9}{'F1':>7}{'Prec':>7}{'Rec':>7}")
    print("-" * 92)
    for spec in cfg["ablation"]:
        name = spec["name"]
        r = results[name]
        ci = r.get("pr_auc_ci", [None, None])
        cis = (f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci[0] is not None else "—")
        f1 = f"{r['f1']:.3f}" if r["f1"] is not None else "—"
        pr = f"{r['precision']:.3f}" if r["precision"] is not None else "—"
        rc = f"{r['recall']:.3f}" if r["recall"] is not None else "—"
        print(f"{name:<26}{r['n_features']:>4}{r['pr_auc']:>9.3f}{cis:>16}"
              f"{r['roc_auc']:>9.3f}{f1:>7}{pr:>7}{rc:>7}")

    print(f"\nMcNEMAR (exact, out-of-fold decisions at threshold {thr})")
    print(f"{'A vs B':<50}{'only A':>8}{'only B':>8}{'p':>9}")
    print("-" * 75)
    pairs = {}
    for a, b in cfg["evaluation"]["mcnemar_pairs"]:
        if a not in oof or b not in oof:
            continue
        m = mcnemar(y, (oof[a] >= thr).astype(int), (oof[b] >= thr).astype(int))
        pairs[f"{a}__vs__{b}"] = m
        print(f"{a + ' vs ' + b:<50}{m['only_a_correct']:>8}"
              f"{m['only_b_correct']:>8}{m['p_value']:>9.4f}")

    out = {"n_units": int(len(df)), "n_positive": n_pos, "n_negative": n_neg,
           "prevalence": prevalence, "chance_pr_auc": prevalence,
           "decision_threshold": thr, "seed": cfg["seed"],
           "cv_folds": cfg["model"]["cv_folds"],
           "n_bootstrap": cfg["model"]["n_bootstrap"],
           "arms": results, "mcnemar": pairs}
    with open(f"{cfg['paths']['tables']}/ablation_results.json", "w",
              encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    pd.DataFrame(results).T.to_csv(f"{cfg['paths']['tables']}/ablation_table.csv")
    print(f"\nWrote {cfg['paths']['tables']}/ablation_results.json")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
