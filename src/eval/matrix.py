"""Shared feature-matrix builder.

The lead-time sweep and the robustness checks both need to rebuild all three
channels for an arbitrary set of units. Keeping one implementation means a
change to how features are assembled cannot silently apply to one analysis and
not the other.
"""
from __future__ import annotations

import pandas as pd

from src.features.network import collect_window_tweets, features_for_unit
from src.features.sentiment import aggregate
from src.features.temporal import features_for_unit as temporal_features


def build_feature_matrix(cfg, band, units: pd.DataFrame, series: dict,
                         sent_per_topic: dict, cache: dict) -> pd.DataFrame:
    """All three channels for `units`, joined into one matrix.

    `series` and `sent_per_topic` are precomputed once by the caller so a sweep
    over parameters costs one corpus pass per setting rather than three.
    """
    recs = collect_window_tweets(cfg, band, units)
    rows = []
    for r in units.itertuples():
        row = features_for_unit(r, recs.get(r.topic, []), cfg)
        row.update({k: v for k, v in temporal_features(r, series[r.topic]).items()
                    if k not in ("topic", "label")})
        row.update(aggregate(
            [(b, k) for b, k in sent_per_topic.get(r.topic, [])
             if r.window_start_bin <= b < r.window_end_bin], cache, cfg))
        rows.append(row)
    return pd.DataFrame(rows)
