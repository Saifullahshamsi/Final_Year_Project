"""Shared feature-matrix builder.

The lead-time sweep and the robustness checks both need to rebuild all three
channels for an arbitrary set of units. Keeping one implementation means a
change to how features are assembled cannot silently apply to one analysis and
not the other.
"""
from __future__ import annotations

import io

import pandas as pd

from src.features.network import collect_window_tweets, features_for_unit
from src.features.sentiment import aggregate
from src.features.temporal import features_for_unit as temporal_features


def match_cached_precision(df: pd.DataFrame) -> pd.DataFrame:
    """Put rebuilt features through the same CSV round-trip the cached ones took.

    `src/eval/ablation.py` reads features from the cached CSVs, where every
    value has been written to text and re-parsed. Anything rebuilt here has
    not, and the two differ by up to ~7e-15 per cell.

    That is enough to matter. `HistGradientBoostingClassifier` bins each
    feature into 255 buckets; a value sitting on a bin edge falls either side
    depending on its last bit, and one flipped split cascades through every
    later split. Measured on this data, it moved PR-AUC by up to 0.013 and made
    the primary configuration report two different numbers depending on which
    script printed it.

    Round-tripping costs a fraction of a second and makes the numeric path
    identical everywhere. It does NOT remove the underlying sensitivity, which
    is recorded in FINDINGS.md as defect 9: a result that moves by 0.013 on the
    last bit of a float is a fact about this study's resolution, not a bug to
    paper over.
    """
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return pd.read_csv(buf)


def build_feature_matrix(cfg, band, units: pd.DataFrame, series: dict,
                         sent_per_topic: dict, cache: dict) -> pd.DataFrame:
    """All three channels for `units`, joined into one matrix.

    `series` and `sent_per_topic` are precomputed once by the caller so a sweep
    over parameters costs one corpus pass per setting rather than three.

    Every rebuild path goes through here, and every one leaves through
    `match_cached_precision`, so no analysis can end up on a different numeric
    footing from the headline by accident.
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
    return match_cached_precision(pd.DataFrame(rows))
