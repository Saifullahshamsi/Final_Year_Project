"""Cross-channel size-proxy audit.

The network and sentiment arms were assigned by reasoning about each feature's
formula. The temporal arm was assigned by *measurement*, and measurement moved
eight features that reasoning would have kept — including the channel's single
highest-AUC feature. So the same measurement is applied to every channel here.

Correlates every modelled feature against window volume (Spearman) and reports
anything at or above the configured threshold that is still sitting in a
non-volume arm.

Run:  python -m src.eval.size_audit
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.data.loading import load_config, utf8_console

# Arms whose features are supposed to carry no volume signal.
NON_VOLUME_SETS = ("structure_size_free", "sentiment", "temporal")


def load_matrices(cfg: dict) -> pd.DataFrame:
    """Join the three channel matrices on topic."""
    cache = cfg["paths"]["cache"]
    net = pd.read_csv(f"{cache}/network_features.csv")
    sen = pd.read_csv(f"{cache}/sentiment_features.csv")
    tem = pd.read_csv(f"{cache}/temporal_features.csv")
    df = net.merge(sen.drop(columns=["label"]), on="topic")
    df = df.merge(tem.drop(columns=["label"]), on="topic")
    return df


def audit(cfg: dict, df: pd.DataFrame) -> dict:
    thr = cfg["audit"]["size_proxy_spearman_threshold"]
    size = df["window_tweets"].values.astype(float)
    rows = {}
    for set_name in NON_VOLUME_SETS:
        for c in cfg["features"][set_name]:
            if c not in df.columns:
                continue
            v = df[c].values.astype(float)
            if len(np.unique(v)) < 2:
                rho = 0.0
            else:
                r = spearmanr(v, size).statistic
                rho = 0.0 if not np.isfinite(r) else float(r)
            rows[c] = {"arm": set_name, "spearman_with_volume": round(rho, 4),
                       "flagged": abs(rho) >= thr}
    return rows


def main() -> int:
    utf8_console()
    cfg = load_config()
    thr = cfg["audit"]["size_proxy_spearman_threshold"]
    df = load_matrices(cfg)
    res = audit(cfg, df)

    print(f"CROSS-CHANNEL SIZE-PROXY AUDIT  ({len(df)} units, "
          f"threshold |rho| >= {thr})\n")
    print(f"{'feature':<28}{'arm':<22}{'rho(volume)':>12}")
    print("-" * 62)
    for c, d in sorted(res.items(), key=lambda kv: -abs(kv[1]["spearman_with_volume"])):
        mark = "  <-- FLAGGED" if d["flagged"] else ""
        print(f"{c:<28}{d['arm']:<22}{d['spearman_with_volume']:>12.3f}{mark}")

    flagged = {c: d for c, d in res.items() if d["flagged"]}
    print(f"\n{len(flagged)} of {len(res)} non-volume features exceed the "
          f"threshold.")
    for c, d in flagged.items():
        print(f"   {c} ({d['arm']}) rho={d['spearman_with_volume']:+.3f}")
    if not flagged:
        print("   none — every non-volume arm is clean at this threshold")

    with open(f"{cfg['paths']['tables']}/size_proxy_audit.json", "w",
              encoding="utf-8") as fh:
        json.dump({"threshold": thr, "n_units": int(len(df)),
                   "features": res,
                   "flagged": sorted(flagged)}, fh, indent=2)
    print(f"\nWrote {cfg['paths']['tables']}/size_proxy_audit.json")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
