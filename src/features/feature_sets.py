"""Feature-set assignment and the ablation hierarchy.

The whole point of this module is that the ablation arms cannot quietly drift.
On these fragmented graphs several structural-sounding features are node counts
(`n_components` 149.6 vs 31.0 tracks `n_nodes` 250.3 vs 51.2), so if assignment
were done ad hoc in modelling code, "structure beats volume" could be produced
by putting a count in the structure arm.

Rules enforced here:

* every feature column belongs to exactly one set — no gaps, no overlaps;
* the size-free structure arm contains no raw counts, checked by name pattern
  as well as by config;
* arguable features live in volume, because that is the assignment that makes
  H1 harder to pass.
"""
from __future__ import annotations

import pandas as pd

# Independent check on the structure arm, by name rather than by config, so a
# careless config edit cannot smuggle a count in. Substring matching is not
# safe here — "mean_clustering" contains "n_" — so this is prefix plus an
# explicit list of the count-valued names in this feature matrix.
_COUNT_PREFIXES = ("n_",)
_COUNT_NAMES = frozenset({
    "window_tweets", "unique_users", "tweets_per_active_bin",
    "max_in_degree", "mean_in_degree", "max_out_degree",
    "max_core", "mean_core", "mean_component_size", "community_entropy",
})


class FeatureSetError(ValueError):
    """Raised when the config and the feature matrix disagree."""


def _sets(cfg: dict) -> dict[str, list[str]]:
    return cfg["features"]


def validate(cfg: dict, columns: list[str]) -> None:
    """Fail loudly if assignment is incomplete, overlapping, or unsound."""
    sets = _sets(cfg)
    assigned: list[str] = []
    for cols in sets.values():
        assigned.extend(cols)

    dupes = {c for c in assigned if assigned.count(c) > 1}
    if dupes:
        raise FeatureSetError(f"features assigned to more than one set: {sorted(dupes)}")

    missing = sorted(set(columns) - set(assigned))
    if missing:
        raise FeatureSetError(
            f"feature columns not assigned to any set: {missing}. "
            "Add them to config.yaml `features:`; if the assignment is "
            "arguable, put them in size_dependent.")

    unknown = sorted(set(assigned) - set(columns))
    if unknown:
        raise FeatureSetError(
            f"config names features that the matrix does not have: {unknown}")

    # The structure arm must not contain raw counts, config notwithstanding.
    offenders = [c for c in sets["structure_size_free"]
                 if c in _COUNT_NAMES or c.startswith(_COUNT_PREFIXES)]
    if offenders:
        raise FeatureSetError(
            f"size-free structure arm contains count-like features: {offenders}")


def resolve(cfg: dict, arm: str) -> list[str]:
    """Column list for one ablation arm."""
    sets = _sets(cfg)
    for spec in cfg["ablation"]:
        if spec["name"] == arm:
            cols: list[str] = []
            for key in spec["sets"]:
                if key not in sets:
                    raise FeatureSetError(f"arm {arm!r} names unknown set {key!r}")
                cols.extend(sets[key])
            return cols
    raise FeatureSetError(f"unknown ablation arm: {arm!r}")


def arms(cfg: dict) -> list[str]:
    return [spec["name"] for spec in cfg["ablation"]]


def describe(cfg: dict, df: pd.DataFrame | None = None) -> str:
    """Human-readable summary of the hierarchy, for logs and the report."""
    lines = ["Ablation hierarchy:"]
    for arm in arms(cfg):
        cols = resolve(cfg, arm)
        lines.append(f"  {arm:<24} {len(cols):>2} features")
        if cols:
            lines.append(f"      {', '.join(cols)}")
    if df is not None:
        lines.append(f"\nMatrix: {len(df)} units, prevalence {df.label.mean():.3f}")
    return "\n".join(lines)


def main() -> int:
    from src.data.loading import load_config
    from src.features.network import feature_columns

    cfg = load_config()
    df = pd.read_csv(f"{cfg['paths']['cache']}/network_features.csv")
    cols = feature_columns(df)
    validate(cfg, cols)
    print(f"Validated {len(cols)} feature columns against config.\n")
    print(describe(cfg, df))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
