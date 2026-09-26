"""The two reporting scripts: `results_summary` and `arima_order`.

Neither had any coverage, and both are the kind of code that fails quietly. A
summary generator that silently drops a section still writes a plausible file;
an order-selection grid that silently fails to converge still returns a
winner. Those are exactly the failures nobody notices by reading the output.

Dataset-free, like the rest of the suite. `results_summary` is exercised
against the committed result JSONs (they carry no tweet text, so they are in
the repository and CI can read them). `arima_order` needs the corpus for its
`main()`, so its two pure functions are tested on synthetic series instead —
which is the part with the actual statistics in it.
"""
import json
import pathlib

import numpy as np
import pytest

from src.data.loading import load_config
from src.eval.arima_order import fit_grid, stationarity
from src.eval.results_summary import build

TABLES = pathlib.Path("outputs/tables")
REQUIRED_JSONS = [
    "ablation_results.json", "lead_time_results.json", "language_control.json",
    "robustness.json", "units_summary.json", "size_proxy_audit.json",
    "arima_order_selection.json", "proto_frozen_results.json",
    "proto_fixed_results.json",
]

# Every section the report cites. If one is renamed or dropped, say so loudly
# rather than shipping a summary that is quietly missing a result.
EXPECTED_SECTIONS = [
    "## 1. Primary ablation",
    "## 2. Lead-time curve",
    "## 3. Lead-time curve",
    "## 4. Language control",
    "## 5. Common-support ablation",
    "## 6. Sensitivity",
    "## 7. Sensitivity",
    "## 8. Unit construction",
    "## 9. Prototype",
    "## 10. Permutation importance",
    "## 11. Feature-set assignment",
]

have_results = all((TABLES / f).exists() for f in REQUIRED_JSONS) and \
    (TABLES / "permutation_importance.csv").exists()
needs_results = pytest.mark.skipif(
    not have_results, reason="result tables not present in this checkout")


@pytest.fixture
def cfg():
    return load_config()


@needs_results
class TestResultsSummary:
    def test_builds_without_writing_anything(self, cfg):
        before = (TABLES / "RESULTS_SUMMARY.md").read_bytes() \
            if (TABLES / "RESULTS_SUMMARY.md").exists() else None
        text = build(cfg)
        assert len(text) > 4000
        after = (TABLES / "RESULTS_SUMMARY.md").read_bytes() \
            if (TABLES / "RESULTS_SUMMARY.md").exists() else None
        assert before == after, "build() must not touch the tracked file"

    def test_emits_every_section(self, cfg):
        text = build(cfg)
        missing = [s for s in EXPECTED_SECTIONS if s not in text]
        assert not missing, f"missing sections: {missing}"

    def test_section_numbering_is_contiguous(self, cfg):
        """A dropped section would otherwise show up only as a gap in the
        numbering that a reader is unlikely to notice."""
        nums = [int(line.split(".")[0][3:])
                for line in build(cfg).splitlines()
                if line.startswith("## ") and line[3].isdigit()]
        assert nums == list(range(1, 12)), nums

    def test_is_deterministic(self, cfg):
        assert build(cfg) == build(cfg)

    def test_carries_the_three_standing_warnings(self, cfg):
        """Chance differs between tables, resampling noise, and the
        uncontrolled language confound. Every one of them changes how a number
        below should be read, so none may be dropped silently."""
        text = build(cfg)
        assert "chance PR-AUC = prevalence" in text
        assert "±0.02–0.03" in text
        assert "not controlled" in text

    def test_reports_the_h1_test_and_names_it(self, cfg):
        text = build(cfg)
        assert "H1 not supported" in text
        assert "the H1 test" in text
        assert "volume_extended" in text

    def test_states_the_selected_arima_order(self, cfg):
        order = tuple(load_config()["arima"]["order"])
        assert f"Order **{order}**" in build(cfg)

    def test_no_unresolved_format_artifacts(self, cfg):
        """Guards the f-string plumbing: a None slipping into a table renders
        as 'None' or 'nan' and looks like a result."""
        text = build(cfg)
        for bad in ("None", "nan", "{", "}"):
            assert bad not in text, f"{bad!r} leaked into the summary"

    def test_feature_counts_sum_to_the_configured_total(self, cfg):
        total = sum(len(v) for v in cfg["features"].values()
                    if isinstance(v, list))
        assert f"| **total** | **{total}** |" in build(cfg)


class TestArimaOrderSelection:
    """`stationarity` and `fit_grid` on series with known behaviour."""

    def test_differencing_makes_a_random_walk_look_stationary(self):
        rng = np.random.default_rng(0)
        walks = [np.cumsum(rng.normal(0, 1, 80)) + 50 for _ in range(12)]
        res = stationarity(walks)
        assert res["n"] == 12
        # A random walk has a unit root: ADF should mostly fail to reject on
        # levels and mostly reject after differencing. That direction is the
        # whole justification for d = 1.
        assert res["adf_diff_reject"] > res["adf_level_reject"]
        # KPSS runs the opposite way round - it rejects stationarity.
        assert res["kpss_diff_reject"] <= res["kpss_level_reject"]

    def test_stationarity_skips_degenerate_series_instead_of_crashing(self):
        flat = [np.full(40, 7.0), np.zeros(40), np.array([1.0, 2.0])]
        res = stationarity(flat)
        assert res["n"] == 0

    def test_grid_scores_every_order_it_is_given(self):
        rng = np.random.default_rng(1)
        series = [np.cumsum(rng.normal(2, 1, 50)).clip(0) for _ in range(4)]
        orders = [(0, 1, 1), (0, 1, 2), (1, 1, 1)]
        grid = fit_grid(series, orders)

        assert grid["n_histories"] == 4
        assert set(grid["per_order"]) == set(orders)
        for o in orders:
            v = grid["per_order"][o]
            assert v["mean_aic"] is not None and np.isfinite(v["mean_aic"])
            assert v["mean_bic"] is not None and np.isfinite(v["mean_bic"])
            assert 0 <= v["converged_frac"] <= 1

    def test_win_counts_are_conserved(self):
        """Every complete history votes exactly once under each criterion. If
        the totals do not add up, the winner is being chosen from a different
        denominator than the means are."""
        rng = np.random.default_rng(2)
        series = [np.cumsum(rng.normal(2, 1, 50)).clip(0) for _ in range(5)]
        orders = [(0, 1, 1), (0, 1, 2), (1, 1, 1)]
        grid = fit_grid(series, orders)
        n = grid["n_complete"]
        assert sum(v["aic_wins"] for v in grid["per_order"].values()) == n
        assert sum(v["bic_wins"] for v in grid["per_order"].values()) == n

    @pytest.mark.filterwarnings("ignore:divide by zero encountered in log")
    @pytest.mark.filterwarnings("ignore:invalid value encountered in log")
    def test_aggregates_are_taken_on_a_common_set(self):
        """A history too short to fit must not be averaged for some orders and
        skipped for others - that would compare orders on different samples.

        The degenerate series is the point of the test, so statsmodels' log
        warnings on it are expected and silenced here rather than globally.
        """
        rng = np.random.default_rng(3)
        series = [np.cumsum(rng.normal(2, 1, 50)).clip(0) for _ in range(3)]
        series.append(np.array([1.0, 2.0, 3.0]))        # too short to fit
        grid = fit_grid(series, [(0, 1, 1), (0, 1, 2)])
        assert grid["n_histories"] == 4
        assert grid["n_complete"] <= 3


@needs_results
class TestCommittedSelectionTable:
    """The committed selection result must still say what config acts on."""

    def test_config_order_is_the_one_the_selection_chose(self, cfg):
        sel = json.loads((TABLES / "arima_order_selection.json")
                         .read_text(encoding="utf-8"))
        assert tuple(cfg["arima"]["order"]) == tuple(sel["best_by_mean_bic"]), \
            "config.yaml no longer uses the order the selection table picked"

    def test_every_order_converged_on_every_history(self, cfg):
        sel = json.loads((TABLES / "arima_order_selection.json")
                         .read_text(encoding="utf-8"))
        assert sel["n_complete"] == sel["n_histories"]
