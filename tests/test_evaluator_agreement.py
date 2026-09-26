"""Two evaluators given the same configuration must produce the same result.

This is the test the project did not have, and its absence cost two defects
that an outside reader found instead (FINDINGS, defects 9 and 10):

* `src/eval/ablation.py` used grouped cross-validation while `cv_score` in
  `src/eval/language_control.py` — used by every robustness and control check —
  used an ungrouped split. Different protocols, silently.
* `src/eval/lead_time.py` rebuilt features in memory while `ablation` read them
  from CSV. The two matrices agreed to 7e-15 and the scores did not, because
  a value on a histogram bin edge falls either side depending on its last bit.

Neither made a number look wrong. Both made one configuration report two
different numbers, which is worse: a reader cannot tell which to believe.

The invariant is cheap to state and would have caught both on the day they
were introduced. It runs on a synthetic matrix, so it needs no corpus, and it
is fast because the point is the comparison, not the model.
"""
import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

from src.data.loading import load_config
from src.eval.ablation import oof_predictions
from src.eval.language_control import cv_score
from src.eval.lead_time import evaluate
from src.eval.matrix import match_cached_precision
from src.features.feature_sets import resolve

N_UNITS = 60


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def matrix(cfg):
    """A synthetic feature matrix carrying every column the config declares.

    Values are arbitrary but deterministic, and the label is given a mild
    dependence on one feature so the folds are not scoring pure noise — an
    all-noise matrix can make two evaluators agree by both predicting nothing.
    """
    rng = np.random.default_rng(20260926)
    cols = [c for v in cfg["features"].values() if isinstance(v, list) for c in v]
    data = {c: rng.normal(size=N_UNITS) for c in cols}
    signal = data[cols[0]] + 0.5 * data[cols[1]]
    df = pd.DataFrame(data)
    df["label"] = (signal > np.median(signal)).astype(int)
    df["topic"] = [f"topic_{i:03d}" for i in range(N_UNITS)]
    return df


def _ablation_predictions(cfg, df, arm):
    cols = resolve(cfg, arm)
    return oof_predictions(cfg, df[cols].values.astype(float),
                           df["label"].values.astype(int),
                           df["topic"].values, 0, "default")


ARMS = ["volume_only", "structure_size_free", "full_fusion"]


class TestEvaluatorsAgree:
    """The invariant. One configuration, one answer, whoever asks."""

    @pytest.mark.parametrize("arm", ARMS)
    def test_ablation_and_lead_time_agree(self, cfg, matrix, arm):
        a = _ablation_predictions(cfg, matrix, arm)
        _, b = evaluate(cfg, matrix, arm)
        assert np.array_equal(a, b), (
            f"{arm}: ablation and lead_time disagree on identical inputs "
            f"(max diff {np.abs(a - b).max():.3g})")

    @pytest.mark.parametrize("arm", ARMS)
    def test_ablation_and_cv_score_agree(self, cfg, matrix, arm):
        """`cv_score` backs every robustness and language check. At
        `seed_offset=0` it must reproduce the headline exactly; this is the
        assertion that fails if anyone reverts it to an ungrouped split."""
        cols = resolve(cfg, arm)
        a = _ablation_predictions(cfg, matrix, arm)
        _, b = cv_score(cfg, matrix[cols].values.astype(float),
                        matrix["label"].values.astype(int),
                        matrix["topic"].values, 0)
        assert np.array_equal(a, b), (
            f"{arm}: cv_score disagrees with the headline protocol "
            f"(max diff {np.abs(a - b).max():.3g})")

    def test_the_three_report_one_pr_auc(self, cfg, matrix):
        y = matrix["label"].values.astype(int)
        cols = resolve(cfg, "full_fusion")
        scores = {
            "ablation": average_precision_score(
                y, _ablation_predictions(cfg, matrix, "full_fusion")),
            "lead_time": evaluate(cfg, matrix, "full_fusion")[0]["pr_auc"],
            "cv_score": cv_score(cfg, matrix[cols].values.astype(float), y,
                                 matrix["topic"].values, 0)[0]["pr_auc"],
        }
        assert len(set(scores.values())) == 1, scores

    def test_cv_score_will_not_run_ungrouped(self, cfg, matrix):
        """`groups` is positional and required. A default is what let the
        ungrouped split survive unnoticed, so its absence is the fix."""
        cols = resolve(cfg, "volume_only")
        with pytest.raises(TypeError):
            cv_score(cfg, matrix[cols].values.astype(float),
                     matrix["label"].values.astype(int))


class TestNumericPath:
    """Rebuilt features must sit on the same numeric footing as cached ones."""

    def test_round_trip_is_idempotent(self, matrix):
        once = match_cached_precision(matrix)
        twice = match_cached_precision(once)
        pd.testing.assert_frame_equal(once, twice)

    def test_round_trip_preserves_shape_and_columns(self, matrix):
        out = match_cached_precision(matrix)
        assert list(out.columns) == list(matrix.columns)
        assert len(out) == len(matrix)

    @pytest.mark.parametrize("arm", ["volume_only", "full_fusion"])
    def test_scoring_is_stable_once_round_tripped(self, cfg, matrix, arm):
        """After one round-trip the values are on the cached footing, so a
        further trip must not move the score. Before the fix, the first trip
        moved PR-AUC by up to 0.013 on real data."""
        once = match_cached_precision(matrix)
        twice = match_cached_precision(once)
        a = _ablation_predictions(cfg, once, arm)
        b = _ablation_predictions(cfg, twice, arm)
        assert np.array_equal(a, b)

    def test_last_bit_changes_can_move_the_score(self, cfg, matrix):
        """Documents defect 9 rather than guarding against it.

        Perturbing every feature by one part in 1e15 is far below any
        meaningful precision, and the model may still return different
        out-of-fold decisions. The assertion is deliberately weak — this
        records that the sensitivity exists and is not claimed to be fixed;
        matching the code paths is what removed the *inconsistency*.
        """
        arm = "full_fusion"
        cols = resolve(cfg, arm)
        nudged = matrix.copy()
        nudged[cols] = nudged[cols] * (1 + 1e-15)
        a = _ablation_predictions(cfg, matrix, arm)
        b = _ablation_predictions(cfg, nudged, arm)
        assert a.shape == b.shape
        assert np.allclose(a, b, atol=0.5), (
            "a 1e-15 perturbation inverted a prediction outright, which is "
            "beyond the instability recorded in FINDINGS defect 9")
