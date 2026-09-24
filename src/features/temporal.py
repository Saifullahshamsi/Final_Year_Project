"""Temporal features over each unit's pre-peak window.

Shape of the volume curve plus ARIMA residual structure. Every feature is
scale-free by construction — a ratio, a bounded fraction, a normalised moment
or a fitted coefficient — because raw slope, raw variance and raw residual
magnitude all scale with window volume, and volume already has its own arm.

Two boundaries worth being explicit about:

* **Leakage.** No data at or after (peak - lead) is touched, for either the
  shape features or the ARIMA fit.
* **What each part sees.** Shape features use the fixed-length window, so they
  are comparable across units. The ARIMA fit uses *all* observed history from
  band start up to the same cutoff, because 18 bins cannot identify an ARIMA
  model. Both stop at the identical cutoff; only the amount of legal history
  differs. History length is emitted as `meta_history_bins` and is NOT a
  feature — it is a deterministic function of peak position.

No LSTM. 129 units cannot support a sequence model, gradient-boosted trees are
the designated primary fusion model, and an overfitted embedding would inflate
the fusion arm — the arm H1 is about. Recorded in FINDINGS.md in advance.

Run:  python -m src.features.temporal
"""
from __future__ import annotations

import json
import time
import warnings

import numpy as np
import pandas as pd

from src.data.loading import band_from_config, load_config
from src.data.units import scan_nontrending, scan_trending

EPS = 1e-9

# Mirrors config.yaml `arima: order:`. Present so arima_features() is callable
# without a config, and asserted equal to the config value in test_temporal.py
# so the two cannot drift.
DEFAULT_ARIMA_ORDER = (0, 1, 2)


def _gini(x: np.ndarray) -> float:
    x = np.sort(np.asarray(x, dtype=float))
    if x.sum() <= 0 or len(x) == 0:
        return 0.0
    cum = np.cumsum(x)
    return float(1 - 2 * cum.sum() / (cum[-1] * len(x)) + 1 / len(x))


def shape_features(x: np.ndarray) -> dict:
    """Curve shape over the window. Everything is divided by the window's own
    level, so doubling the volume leaves every value unchanged."""
    W = len(x)
    x = np.asarray(x, dtype=float)
    total, mean = x.sum(), x.mean()
    keys = ("slope_norm", "accel_norm", "burstiness", "peakedness",
            "bin_entropy", "bin_gini", "mass_centroid", "frac_last_quarter",
            "log_half_ratio", "monotone_up_frac", "zero_bin_frac", "acf1")
    if W < 4 or total <= 0 or mean <= 0:
        return dict.fromkeys(keys, 0.0)

    z = x / mean                                  # scale-free series
    t = np.arange(W, dtype=float)
    slope = float(np.polyfit(t, z, 1)[0])
    accel = float(np.polyfit(t, z, 2)[0]) if W >= 5 else 0.0

    p = x / total
    nz = p[p > 0]
    entropy = float(-(nz * np.log(nz)).sum() / np.log(W)) if W > 1 else 0.0

    q = max(W // 4, 1)
    half = W // 2
    first, second = x[:half].mean(), x[half:].mean()

    zc = z - z.mean()
    denom = float((zc * zc).sum())
    acf1 = float((zc[:-1] * zc[1:]).sum() / denom) if denom > EPS else 0.0

    return {
        "slope_norm": slope,
        "accel_norm": accel,
        "burstiness": float(x.std() / mean),
        "peakedness": float(x.max() / mean),
        "bin_entropy": entropy,
        "bin_gini": _gini(x),
        "mass_centroid": float((t * p).sum() / (W - 1)),
        "frac_last_quarter": float(x[-q:].sum() / total),
        "log_half_ratio": float(np.log((second + EPS) / (first + EPS))),
        "monotone_up_frac": float((np.diff(x) > 0).mean()),
        "zero_bin_frac": float((x == 0).mean()),
        "acf1": acf1,
    }


def coefficient_names(order: tuple[int, int, int]) -> list[str]:
    """Which coefficient features an order produces.

    The order determines the feature set, not the other way round: (0,1,2) has
    no AR term, so there is no `arima_ar1` to emit. Keeping a zero-filled
    `arima_ar1` around for continuity would feed the classifier a constant
    column and imply the model estimates something it does not.
    """
    p, _, q = order
    return ([f"arima_ar{i}" for i in range(1, p + 1)]
            + [f"arima_ma{i}" for i in range(1, q + 1)])


def arima_features(history: np.ndarray,
                   order: tuple[int, int, int] = DEFAULT_ARIMA_ORDER) -> dict:
    """ARIMA on all legal pre-cutoff history.

    The order is selected, not assumed — see `src/eval/arima_order.py` and the
    `arima:` block in config.yaml. The default here mirrors the config, and
    `test_temporal.py` asserts the two cannot drift apart.

    Coefficients are read out by statsmodels' own parameter names rather than by
    position, because positional indexing silently returns the wrong parameter
    the moment the order changes — which is exactly the change this function now
    has to survive.

    Residual dispersion is divided by the series level so it does not become a
    volume feature. Convergence is recorded as metadata, not modelled.
    """
    coefs = coefficient_names(order)
    out = {c: 0.0 for c in coefs}
    out.update({"arima_resid_cv": 0.0, "arima_resid_acf1": 0.0,
                "arima_forecast_ratio": 0.0, "meta_arima_converged": 0})
    y = np.asarray(history, dtype=float)
    if len(y) < 8 or y.sum() <= 0:
        return out
    level = max(y.mean(), EPS)
    try:
        from statsmodels.tsa.arima.model import ARIMA
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            fit = ARIMA(y, order=tuple(order),
                        enforce_stationarity=False,
                        enforce_invertibility=False).fit(method_kwargs={"warn_convergence": False})
            resid = np.asarray(fit.resid, dtype=float)
            named = dict(zip(fit.param_names,
                             np.asarray(fit.params, dtype=float), strict=True))
            fc = float(np.asarray(fit.forecast(1))[0])
    except Exception:
        return out

    p, _, q = order
    for i in range(1, p + 1):
        v = named.get(f"ar.L{i}", 0.0)
        out[f"arima_ar{i}"] = float(v) if np.isfinite(v) else 0.0
    for i in range(1, q + 1):
        v = named.get(f"ma.L{i}", 0.0)
        out[f"arima_ma{i}"] = float(v) if np.isfinite(v) else 0.0

    rc = resid - resid.mean()
    denom = float((rc * rc).sum())
    out.update({
        "arima_resid_cv": float(np.clip(resid.std() / level, 0, 50)),
        "arima_resid_acf1": (float((rc[:-1] * rc[1:]).sum() / denom)
                             if denom > EPS else 0.0),
        # Where the series was heading at the cutoff, relative to its own level.
        "arima_forecast_ratio": float(np.clip((fc + EPS) / (y[-1] + EPS), -10, 10)),
        "meta_arima_converged": 1,
    })
    return out


def features_for_unit(row, series,
                      order: tuple[int, int, int] = DEFAULT_ARIMA_ORDER) -> dict:
    """series = the unit's feature-language counts across the whole band."""
    s, e = row.window_start_bin, row.window_end_bin
    window = series[s:e]
    history = series[:e]                    # everything legal before the cutoff
    f = {"topic": row.topic, "label": int(row.label)}
    f.update(shape_features(window))
    f.update(arima_features(history, order))
    f["meta_history_bins"] = int(e)         # deterministic in peak position
    f["meta_window_bins"] = int(e - s)
    return f


def size_proxy_audit(df: pd.DataFrame, feats: list[str],
                     size: np.ndarray, threshold: float) -> dict:
    """Every channel so far has shipped a feature that was really a size count.

    Rather than eyeball it again, correlate each feature with window volume and
    flag anything that tracks it. Spearman, so monotone-but-nonlinear proxies
    do not slip through.
    """
    from scipy.stats import spearmanr
    audit = {}
    for c in feats:
        v = df[c].values.astype(float)
        if len(np.unique(v)) < 2:
            rho = 0.0
        else:
            rho = spearmanr(v, size).statistic
            rho = 0.0 if not np.isfinite(rho) else float(rho)
        audit[c] = {"spearman_with_volume": round(rho, 4),
                    "flagged": abs(rho) >= threshold}
    return audit


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    vh = cfg["validation_history"]
    full = band_from_config(cfg, hours=(vh["start_hour"], cfg["band"]["end_hour"]))
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")
    order = tuple(cfg["arima"]["order"])
    print(f"{len(units)} units | feature language "
          f"{cfg['language']['feature_language']!r} | ARIMA{order}\n")

    print("Scanning corpus for per-topic series ...")
    pos = scan_trending(cfg, band, full)
    neg, _ = scan_nontrending(cfg, band, set(pos))
    series = {}
    for pool in (pos, neg):
        for topic, ts in pool.items():
            series[topic] = (ts.feat_counts if ts.feat_counts is not None
                             else ts.counts)
    print(f"  done ({time.time() - t0:.0f}s)\n")

    rows = [features_for_unit(r, series[r.topic], order)
            for r in units.itertuples() if r.topic in series]
    df = pd.DataFrame(rows)
    feats = [c for c in df.columns
             if c not in ("topic", "label") and not c.startswith("meta_")]
    out = f"{cfg['paths']['cache']}/temporal_features.csv"
    df.to_csv(out, index=False)

    conv = int(df.meta_arima_converged.sum())
    print(f"TEMPORAL FEATURES: {len(df)} units x {len(feats)} features")
    print(f"  ARIMA{order} converged on {conv}/{len(df)} units "
          f"({100 * conv / len(df):.1f}%)")
    print(f"  history length: median {df.meta_history_bins.median():.0f} bins, "
          f"min {df.meta_history_bins.min():.0f}, "
          f"max {df.meta_history_bins.max():.0f}\n")

    from sklearn.metrics import roc_auc_score
    y = df["label"].values
    net = pd.read_csv(f"{cfg['paths']['cache']}/network_features.csv")
    size = net.set_index("topic").loc[df.topic, "window_tweets"].values

    thr = cfg["audit"]["size_proxy_spearman_threshold"]
    assigned_volume = set(cfg["features"]["temporal_size_dependent"])
    audit = size_proxy_audit(df, feats, size, thr)
    print(f"{'feature':<24}{'mean(+)':>10}{'mean(-)':>10}{'AUC':>7}"
          f"{'rho(vol)':>10}  arm")
    print("-" * 70)
    summary = {}
    for c in feats:
        v = df[c].values.astype(float)
        auc = (max(roc_auc_score(y, v), 1 - roc_auc_score(y, v))
               if len(np.unique(v)) > 1 else 0.5)
        rho = audit[c]["spearman_with_volume"]
        arm = "volume" if c in assigned_volume else "temporal"
        summary[c] = {"mean_trending": float(v[y == 1].mean()),
                      "mean_non_trending": float(v[y == 0].mean()),
                      "univariate_auc": float(auc),
                      "spearman_with_volume": rho, "arm": arm}
        print(f"{c:<24}{v[y == 1].mean():>10.3f}{v[y == 0].mean():>10.3f}"
              f"{auc:>7.3f}{rho:>10.3f}  {arm}")

    flagged = [c for c in feats if audit[c]["flagged"]]
    print(f"\nSIZE-PROXY AUDIT (|Spearman| with window_tweets >= {thr}): "
          f"{len(flagged)} flagged, {len(feats) - len(flagged)} clean")
    for c in flagged:
        print(f"   {c:<24} rho={audit[c]['spearman_with_volume']:+.3f}  "
              f"AUC={summary[c]['univariate_auc']:.3f}")
    if not flagged:
        print("   none")

    # The audit must agree with what config actually models, or the arms lie.
    mismatch = sorted(set(flagged) ^ assigned_volume)
    if mismatch:
        print(f"\n*** AUDIT/CONFIG MISMATCH: {mismatch} — features flagged by "
              f"the audit but not assigned to volume (or vice versa) ***")
    else:
        print(f"  audit agrees with config: all {len(flagged)} flagged features "
              f"are assigned to the volume arm")

    with open(f"{cfg['paths']['tables']}/temporal_feature_summary.json", "w",
              encoding="utf-8") as fh:
        json.dump({"n_units": len(df), "n_features": len(feats),
                   "arima_converged": conv, "features": feats,
                   "summary": summary, "size_proxy_flagged": flagged,
                   "seed": cfg["seed"]}, fh, indent=2, ensure_ascii=False)
    print(f"\nWrote {out}")
    print(f"Wrote {cfg['paths']['tables']}/temporal_feature_summary.json")
    print(f"Total {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
