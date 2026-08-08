#!/usr/bin/env python3
"""Evaluate whether early interaction-graph structure discriminates trending
from non-trending topics, using ML-appropriate methodology."""
import json, numpy as np, pandas as pd
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (RepeatedStratifiedKFold, cross_val_score,
                                     cross_val_predict, permutation_test_score,
                                     StratifiedKFold)
from sklearn.metrics import (roc_auc_score, average_precision_score, f1_score,
                             roc_curve, precision_recall_curve)
from scipy.stats import wilcoxon, mannwhitneyu
np.random.seed(42)

df = pd.read_csv("/tmp/topic_features.csv")
y = df["label"].values
prev = y.mean()
print(f"{len(df)} topics | trending prevalence = {prev:.3f}")

VOLUME  = ["total_count", "unique_users"]
NETWORK = ["density", "edges_per_tweet", "max_in_degree", "mean_in_degree",
           "max_out_degree", "n_components", "largest_wcc_frac",
           "mean_component_size", "reciprocity", "pagerank_gini",
           "max_pagerank", "mean_clustering", "n_nodes", "n_edges"]
ALL = VOLUME + NETWORK

def model():
    return RandomForestClassifier(n_estimators=120, class_weight="balanced",
                                  random_state=0, n_jobs=1)

def cv_scores(cols, scoring, n_splits=5, n_repeats=8, seed=0):
    cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=seed)
    return cross_val_score(model(), df[cols].values, y, scoring=scoring, cv=cv, n_jobs=1)

results = {}
for name, cols in [("chance", None), ("volume_only", VOLUME),
                   ("network_only", NETWORK), ("full", ALL)]:
    if name == "chance":
        results[name] = {"roc_auc": 0.5, "roc_auc_std": 0.0,
                         "pr_auc": float(prev), "pr_auc_std": 0.0, "f1": 0.0}
        continue
    roc = cv_scores(cols, "roc_auc")
    pr  = cv_scores(cols, "average_precision")
    f1  = cv_scores(cols, "f1")
    results[name] = {"roc_auc": float(roc.mean()), "roc_auc_std": float(roc.std()),
                     "pr_auc": float(pr.mean()), "pr_auc_std": float(pr.std()),
                     "f1": float(f1.mean())}
    print(f"{name:13s}  ROC-AUC {roc.mean():.3f}±{roc.std():.3f}   "
          f"PR-AUC {pr.mean():.3f}±{pr.std():.3f}   F1 {f1.mean():.3f}")

# ---- permutation test: is network-only better than chance? ----
cvp = StratifiedKFold(5, shuffle=True, random_state=0)
score, perm, pval = permutation_test_score(
    model(), df[NETWORK].values, y, scoring="roc_auc", cv=cvp,
    n_permutations=100, random_state=0, n_jobs=1)
print(f"\nPermutation test (network_only ROC-AUC): observed={score:.3f}, p={pval:.4f}")
results["permutation"] = {"observed_roc_auc": float(score), "p_value": float(pval),
                          "n_permutations": 100}

# ---- paired comparison: network_only vs volume_only across identical folds ----
cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=8, random_state=7)
net_fold, vol_fold = [], []
X = df[ALL].values
idx_net = [ALL.index(c) for c in NETWORK]
idx_vol = [ALL.index(c) for c in VOLUME]
for tr, te in cv.split(X, y):
    m1 = model().fit(df[NETWORK].values[tr], y[tr])
    m2 = model().fit(df[VOLUME].values[tr], y[tr])
    net_fold.append(roc_auc_score(y[te], m1.predict_proba(df[NETWORK].values[te])[:, 1]))
    vol_fold.append(roc_auc_score(y[te], m2.predict_proba(df[VOLUME].values[te])[:, 1]))
net_fold, vol_fold = np.array(net_fold), np.array(vol_fold)
wstat, wp = wilcoxon(net_fold, vol_fold)
print(f"Network vs Volume ROC-AUC: {net_fold.mean():.3f} vs {vol_fold.mean():.3f}  "
      f"(Wilcoxon p={wp:.4f})")
results["network_vs_volume"] = {"network_mean": float(net_fold.mean()),
                                "volume_mean": float(vol_fold.mean()),
                                "wilcoxon_p": float(wp)}

# ---- bootstrap CI for full-model ROC-AUC (out-of-fold predictions) ----
oof = cross_val_predict(model(), df[ALL].values, y, cv=StratifiedKFold(5, shuffle=True, random_state=1),
                        method="predict_proba", n_jobs=1)[:, 1]
rng = np.random.default_rng(0)
boots = []
for _ in range(1000):
    s = rng.integers(0, len(y), len(y))
    if len(np.unique(y[s])) < 2:
        continue
    boots.append(roc_auc_score(y[s], oof[s]))
lo, hi = np.percentile(boots, [2.5, 97.5])
print(f"Full model OOF ROC-AUC bootstrap 95% CI: [{lo:.3f}, {hi:.3f}]")
results["full_bootstrap_ci"] = [float(lo), float(hi)]

# ---- univariate discriminative power of each network feature ----
uni = {}
for c in NETWORK:
    v = df[c].values
    a = roc_auc_score(y, v)
    a = max(a, 1 - a)  # direction-agnostic
    try:
        _, p = mannwhitneyu(v[y == 1], v[y == 0], alternative="two-sided")
    except Exception:
        p = 1.0
    uni[c] = {"auc": float(a), "mwu_p": float(p)}
uni_sorted = sorted(uni.items(), key=lambda kv: -kv[1]["auc"])
print("\nTop discriminative network features (univariate AUC):")
for c, d in uni_sorted[:6]:
    print(f"   {c:20s} AUC={d['auc']:.3f}  p={d['mwu_p']:.2e}")
results["univariate"] = uni

# ---- feature importance (full model) ----
imp_model = model().fit(df[ALL].values, y)
imp = sorted(zip(ALL, imp_model.feature_importances_), key=lambda x: -x[1])
results["importance"] = {k: float(v) for k, v in imp}

json.dump(results, open("/tmp/proto_results.json", "w"), indent=2)

# ============ FIGURES ============
navy="#1f3a5f"; teal="#2a8a8a"; amber="#b06b1f"; grey="#888"

# Fig A: ROC curves (mean over folds) for the three models
plt.figure(figsize=(5.2,5.0), dpi=200)
for cols, name, col in [(VOLUME,"Volume only",grey),(NETWORK,"Network only",teal),(ALL,"Full",navy)]:
    p = cross_val_predict(model(), df[cols].values, y,
                          cv=StratifiedKFold(5,shuffle=True,random_state=1),
                          method="predict_proba", n_jobs=1)[:,1]
    fpr,tpr,_ = roc_curve(y,p); auc=roc_auc_score(y,p)
    plt.plot(fpr,tpr,color=col,lw=2,label=f"{name} (AUC={auc:.2f})")
plt.plot([0,1],[0,1],'--',color="#bbb",lw=1)
plt.xlabel("False positive rate"); plt.ylabel("True positive rate")
plt.title("ROC: discriminating trending vs non-trending")
plt.legend(loc="lower right",fontsize=9); plt.tight_layout()
plt.savefig("/tmp/proto_roc.png",facecolor="white",bbox_inches="tight"); plt.close()

# Fig B: model comparison bars (ROC-AUC & PR-AUC with std)
names=["chance","volume_only","network_only","full"]
labels=["Chance","Volume\nonly","Network\nonly","Full"]
roc_m=[results[n]["roc_auc"] for n in names]; roc_s=[results[n]["roc_auc_std"] for n in names]
pr_m=[results[n]["pr_auc"] for n in names]; pr_s=[results[n]["pr_auc_std"] for n in names]
x=np.arange(len(names)); w=0.38
plt.figure(figsize=(6.4,4.2), dpi=200)
plt.bar(x-w/2,roc_m,w,yerr=roc_s,capsize=3,color=navy,label="ROC-AUC")
plt.bar(x+w/2,pr_m,w,yerr=pr_s,capsize=3,color=amber,label="PR-AUC")
plt.axhline(0.5,ls=':',color=grey,lw=1)
plt.xticks(x,labels); plt.ylim(0,1.0); plt.ylabel("Score (mean ± SD, repeated 5-fold CV)")
plt.title("Model comparison")
plt.legend(fontsize=9); plt.tight_layout()
plt.savefig("/tmp/proto_bars.png",facecolor="white",bbox_inches="tight"); plt.close()

# Fig C: top discriminative features by class (boxplots)
top4=[c for c,_ in uni_sorted[:4]]
fig,axes=plt.subplots(1,4,figsize=(9.6,3.2),dpi=200)
for ax,c in zip(axes,top4):
    data=[df[df.label==0][c].values, df[df.label==1][c].values]
    bp=ax.boxplot(data,labels=["non-tr","trend"],patch_artist=True,widths=0.6,showfliers=False)
    for patch,col in zip(bp['boxes'],[grey,teal]): patch.set_facecolor(col); patch.set_alpha(.6)
    ax.set_title(f"{c}\nAUC={uni[c]['auc']:.2f}",fontsize=8.5)
    ax.tick_params(labelsize=8)
plt.suptitle("Most discriminative early-graph features",fontsize=10)
plt.tight_layout(); plt.savefig("/tmp/proto_features.png",facecolor="white",bbox_inches="tight"); plt.close()

# Fig D: feature importance
plt.figure(figsize=(6.4,4.6), dpi=200)
ks=[k for k,_ in imp][:10][::-1]; vs=[dict(imp)[k] for k in ks]
cols=[amber if k in VOLUME else teal for k in ks]
plt.barh(ks,vs,color=cols)
plt.xlabel("Random-forest importance"); plt.title("Feature importance (full model)")
from matplotlib.patches import Patch
plt.legend(handles=[Patch(color=teal,label="network"),Patch(color=amber,label="volume")],fontsize=8)
plt.tight_layout(); plt.savefig("/tmp/proto_importance.png",facecolor="white",bbox_inches="tight"); plt.close()

print("\nSaved: proto_results.json, proto_roc.png, proto_bars.png, proto_features.png, proto_importance.png")
