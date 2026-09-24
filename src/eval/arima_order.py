"""Justify the ARIMA order instead of asserting it.

The temporal channel fits ARIMA(1,1,1) to each unit's pre-cutoff history. That
order was chosen by convention, which is not a justification. This script
selects it against the data, and writes the evidence to a table so the report
can cite a procedure rather than a habit.

Three questions, in order:

1. **Is differencing needed at all?** ADF and KPSS on each unit's history give
   the fraction of series that look non-stationary in level. That sets `d`.
2. **Which (p, q) does the data prefer?** A grid is fitted per unit and scored
   by AIC and BIC. One order must serve every unit, because ARIMA coefficients
   are features and a feature has to mean the same thing across units — so the
   winner is the order with the best *aggregate* criterion, reported alongside
   per-unit win counts so a split decision is visible rather than hidden.
3. **Does the choice survive?** Convergence rate per order, since an order that
   fits beautifully on 60% of units and fails on the rest is not usable.

No labels are read anywhere in this script. Order selection therefore cannot
leak outcome information into the features: the outcome is never consulted, and
the selection is a property of the series alone.

Run:  python -m src.eval.arima_order
"""
from __future__ import annotations

import itertools
import json
import time
import warnings

import numpy as np
import pandas as pd

from src.data.loading import band_from_config, load_config
from src.data.units import scan_nontrending, scan_trending

MIN_HISTORY = 8


def stationarity(histories: list[np.ndarray]) -> dict:
    """ADF (H0: unit root) and KPSS (H0: stationary), on levels and on first
    differences. Agreement between the two is what makes `d` defensible."""
    from statsmodels.tsa.stattools import adfuller, kpss

    res = {"adf_level_reject": 0, "kpss_level_reject": 0,
           "adf_diff_reject": 0, "kpss_diff_reject": 0, "n": 0}
    for y in histories:
        if len(y) < 12 or np.ptp(y) == 0:
            continue
        res["n"] += 1
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for tag, s in (("level", y), ("diff", np.diff(y))):
                if len(s) < 8 or np.ptp(s) == 0:
                    continue
                try:
                    if adfuller(s, autolag="AIC")[1] < 0.05:
                        res[f"adf_{tag}_reject"] += 1
                except Exception:
                    pass
                try:
                    if kpss(s, regression="c", nlags="auto")[1] < 0.05:
                        res[f"kpss_{tag}_reject"] += 1
                except Exception:
                    pass
    return res


def fit_grid(histories: list[np.ndarray], orders: list[tuple]) -> dict:
    """Fit every order to every history.

    Aggregates are taken over the units where *every* order converged, so the
    comparison sits on a common set and is not biased by which orders quietly
    dropped the hard series.
    """
    from statsmodels.tsa.arima.model import ARIMA

    per_unit: list[dict] = []
    conv = {o: 0 for o in orders}
    for y in histories:
        row = {}
        for o in orders:
            try:
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    fit = ARIMA(y, order=o, enforce_stationarity=False,
                                enforce_invertibility=False).fit(
                                    method_kwargs={"warn_convergence": False})
                aic, bic = float(fit.aic), float(fit.bic)
                if np.isfinite(aic) and np.isfinite(bic):
                    row[o] = (aic, bic)
                    conv[o] += 1
            except Exception:
                pass
        per_unit.append(row)

    complete = [r for r in per_unit if len(r) == len(orders)]
    agg = {}
    for o in orders:
        agg[o] = {
            "converged": conv[o],
            "converged_frac": round(conv[o] / max(len(histories), 1), 4),
            "mean_aic": (round(float(np.mean([r[o][0] for r in complete])), 3)
                         if complete else None),
            "mean_bic": (round(float(np.mean([r[o][1] for r in complete])), 3)
                         if complete else None),
            "aic_wins": sum(1 for r in complete
                            if min(r, key=lambda k: r[k][0]) == o),
            "bic_wins": sum(1 for r in complete
                            if min(r, key=lambda k: r[k][1]) == o),
        }
    return {"n_histories": len(histories), "n_complete": len(complete),
            "per_order": agg}


def main() -> int:
    t0 = time.time()
    cfg = load_config()
    band = band_from_config(cfg)
    vh = cfg["validation_history"]
    full = band_from_config(cfg, hours=(vh["start_hour"], cfg["band"]["end_hour"]))
    units = pd.read_csv(f"{cfg['paths']['cache']}/units.csv")

    print(f"{len(units)} units | scanning corpus for series ...")
    pos = scan_trending(cfg, band, full)
    neg, _ = scan_nontrending(cfg, band, set(pos))
    series = {}
    for pool in (pos, neg):
        for topic, ts in pool.items():
            series[topic] = (ts.feat_counts if ts.feat_counts is not None
                             else ts.counts)
    print(f"  done ({time.time() - t0:.0f}s)")

    # Exactly the histories the feature extractor sees: band start -> cutoff.
    histories = []
    for r in units.itertuples():
        if r.topic not in series:
            continue
        y = np.asarray(series[r.topic][:r.window_end_bin], dtype=float)
        if len(y) >= MIN_HISTORY and y.sum() > 0:
            histories.append(y)
    med = int(np.median([len(h) for h in histories]))
    print(f"  {len(histories)} usable histories (median length {med} bins)\n")

    print("Stationarity tests ...")
    stat = stationarity(histories)
    n = max(stat["n"], 1)
    print(f"  on {stat['n']} series with enough length:")
    print(f"    levels      ADF rejects unit root {stat['adf_level_reject']:3d}"
          f" ({100 * stat['adf_level_reject'] / n:.1f}%) | "
          f"KPSS rejects stationarity {stat['kpss_level_reject']:3d}"
          f" ({100 * stat['kpss_level_reject'] / n:.1f}%)")
    print(f"    differenced ADF rejects unit root {stat['adf_diff_reject']:3d}"
          f" ({100 * stat['adf_diff_reject'] / n:.1f}%) | "
          f"KPSS rejects stationarity {stat['kpss_diff_reject']:3d}"
          f" ({100 * stat['kpss_diff_reject'] / n:.1f}%)\n")

    orders = [(p, d, q)
              for p, d, q in itertools.product((0, 1, 2), (0, 1), (0, 1, 2))
              if (p, q) != (0, 0)]
    print(f"Fitting {len(orders)} orders x {len(histories)} histories ...")
    grid = fit_grid(histories, orders)
    print(f"  complete on {grid['n_complete']}/{grid['n_histories']} "
          f"histories ({time.time() - t0:.0f}s)\n")

    rows = sorted(grid["per_order"].items(),
                  key=lambda kv: (kv[1]["mean_bic"]
                                  if kv[1]["mean_bic"] is not None else 1e18))
    print(f"{'order':>10}{'conv%':>8}{'mean AIC':>11}{'mean BIC':>11}"
          f"{'AIC wins':>10}{'BIC wins':>10}")
    for o, v in rows:
        mark = "  <- current" if o == (1, 1, 1) else ""
        print(f"{str(o):>10}{100 * v['converged_frac']:>7.1f}%"
              f"{v['mean_aic']:>11.2f}{v['mean_bic']:>11.2f}"
              f"{v['aic_wins']:>10d}{v['bic_wins']:>10d}{mark}")

    best_aic = min(rows, key=lambda kv: kv[1]["mean_aic"])[0]
    best_bic = min(rows, key=lambda kv: kv[1]["mean_bic"])[0]
    cur = grid["per_order"][(1, 1, 1)]
    print(f"\n  best by mean AIC: {best_aic}")
    print(f"  best by mean BIC: {best_bic}")
    print(f"  current (1, 1, 1): mean AIC {cur['mean_aic']:.2f}, "
          f"mean BIC {cur['mean_bic']:.2f}, "
          f"converged {100 * cur['converged_frac']:.1f}%")

    out = {
        "n_units": int(len(units)),
        "n_histories": grid["n_histories"],
        "n_complete": grid["n_complete"],
        "median_history_bins": med,
        "stationarity": stat,
        "current_order": [1, 1, 1],
        "best_by_mean_aic": list(best_aic),
        "best_by_mean_bic": list(best_bic),
        "orders": {str(list(o)): v for o, v in grid["per_order"].items()},
    }
    path = f"{cfg['paths']['tables']}/arima_order_selection.json"
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=2)
    print(f"\nwrote {path}  ({time.time() - t0:.0f}s total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
