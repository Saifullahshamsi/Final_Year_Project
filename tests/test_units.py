"""Unit construction: peak detection, censoring, and — load-bearing — the
guarantee that no feature window ever sees data at or after its cut-off.

If leakage is ever introduced, `TestNoLeakage` fails.
"""
import numpy as np
import pytest

from src.data.loading import band_from_config, load_config
from src.data.units import (
    TopicSeries,
    build_units,
    detect_peak,
    make_unit,
    scan_nontrending,
    scan_trending,
    smooth,
)


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def band(cfg):
    return band_from_config(cfg)


def series(counts, label=1, feat=None):
    arr = np.array(counts, dtype=np.int32)
    return TopicSeries(topic="t", label=label, counts=arr, total=int(arr.sum()),
                       feat_counts=None if feat is None else np.array(feat, dtype=np.int32))


class TestSmoothing:
    def test_preserves_length(self):
        x = np.arange(96)
        assert len(smooth(x, 3)) == 96
        assert len(smooth(x, 5)) == 96

    def test_k1_is_identity(self):
        x = np.array([1, 5, 2])
        assert np.allclose(smooth(x, 1), x)

    def test_even_k_is_made_odd_and_still_preserves_length(self):
        assert len(smooth(np.arange(20), 4)) == 20


class TestPeakDetection:
    def test_finds_the_maximum(self, band):
        c = np.zeros(96, dtype=np.int32)
        c[40] = 100
        peak, height = detect_peak(c, 1)
        assert peak == 40 and height == 100

    def test_ties_resolve_to_the_earliest_bin(self):
        c = np.zeros(20, dtype=np.int32)
        c[5] = c[15] = 10
        peak, _ = detect_peak(c, 1)
        assert peak == 5

    def test_smoothing_suppresses_a_lone_spike(self):
        """A single noisy bin must not outrank a sustained burst."""
        c = np.zeros(60, dtype=np.int32)
        c[10] = 20                      # lone spike
        c[38:46] = 9                    # sustained burst
        assert detect_peak(c, 5)[0] > 30


class TestCensoring:
    """The filters run on band data alone and are symmetric across classes."""

    def test_left_censored_topic_is_dropped(self, band, cfg):
        c = np.zeros(96, dtype=np.int32)
        c[0:5] = 15                     # already at full volume at 16:00
        c[5:40] = 2
        unit, reason = make_unit(series(c), band, cfg, 60, 90,
                                 min_topic=10, min_window=1)
        assert unit is None and reason == "left_censored"

    def test_right_censored_topic_is_dropped(self, band, cfg):
        c = np.zeros(96, dtype=np.int32)
        c[60:96] = np.arange(1, 37)     # still climbing at the band edge
        unit, reason = make_unit(series(c), band, cfg, 60, 90,
                                 min_topic=10, min_window=1)
        assert unit is None and reason.startswith("right_censored")

    def test_peak_without_observed_decay_is_dropped(self, band, cfg):
        """A plateau is not a peak: volume must actually fall afterwards."""
        c = np.zeros(96, dtype=np.int32)
        c[20:40] = 1
        c[40:70] = 20                   # rises, then stays flat
        unit, reason = make_unit(series(c), band, cfg, 60, 90,
                                 min_topic=10, min_window=1)
        assert unit is None and reason.startswith("right_censored")

    def test_clean_topic_survives(self, band, cfg):
        c = np.zeros(96, dtype=np.int32)
        c[18:48] = 3
        c[48:51] = 30
        c[51:75] = 1
        unit, reason = make_unit(series(c), band, cfg, 60, 90,
                                 min_topic=10, min_window=1)
        assert reason == "kept" and unit is not None

    def test_topic_below_min_size_is_dropped_first(self, band, cfg):
        unit, reason = make_unit(series(np.ones(96)), band, cfg, 60, 90,
                                 min_topic=1000, min_window=1)
        assert unit is None and reason == "too_small"


class TestNoLeakage:
    """THE critical guarantee: features never see the outcome."""

    @pytest.fixture
    def clean(self):
        c = np.zeros(96, dtype=np.int32)
        c[10:48] = 4
        c[48:51] = 40
        c[51:80] = 1
        return series(c)

    @pytest.mark.parametrize("lead,window", [(30, 30), (60, 60), (60, 90),
                                             (120, 60), (180, 90)])
    def test_window_closes_before_the_lead_cutoff(self, clean, band, cfg,
                                                  lead, window):
        unit, reason = make_unit(clean, band, cfg, lead, window,
                                 min_topic=10, min_window=1)
        if unit is None:
            pytest.skip(f"setting infeasible for this fixture: {reason}")
        lead_bins = band.minutes_to_bins(lead)
        assert unit["window_end_bin"] == unit["peak_bin"] - lead_bins
        assert unit["window_end_bin"] < unit["peak_bin"]
        assert unit["window_start_bin"] < unit["window_end_bin"]
        assert unit["window_start_bin"] >= 0

    def test_window_length_matches_configuration(self, clean, band, cfg):
        unit, _ = make_unit(clean, band, cfg, 60, 90, min_topic=10, min_window=1)
        assert (unit["window_end_bin"] - unit["window_start_bin"]
                == band.minutes_to_bins(90))

    def test_window_tweet_count_excludes_everything_from_the_cutoff_on(
            self, clean, band, cfg):
        """Counted volume must come only from [start, end) — never the peak."""
        unit, _ = make_unit(clean, band, cfg, 60, 90, min_topic=10, min_window=1)
        s, e = unit["window_start_bin"], unit["window_end_bin"]
        assert unit["n_window_tweets_all_langs"] == int(clean.counts[s:e].sum())
        assert unit["n_window_tweets_all_langs"] != int(clean.counts[s:e + 1].sum())

    def test_window_starting_before_the_band_is_rejected(self, band, cfg):
        """No unit may borrow data from before collection started."""
        c = np.zeros(96, dtype=np.int32)
        c[0:3] = 1
        c[3:6] = 20                     # peak too early for any pre-peak window
        c[6:40] = 1
        unit, reason = make_unit(series(c), band, cfg, 180, 90,
                                 min_topic=10, min_window=1)
        assert unit is None and reason in ("window_before_band_start",
                                           "left_censored")


class TestLanguageFilter:
    """Tweet-level control: units are defined on all activity, features are
    counted on one language only."""

    @pytest.fixture
    def mixed(self):
        c = np.zeros(96, dtype=np.int32)
        c[10:48] = 10
        c[48:51] = 60
        c[51:80] = 1
        es = np.zeros(96, dtype=np.int32)
        es[10:48] = 2                   # only a fifth of the window is Spanish
        return series(c, feat=es)

    def test_peak_uses_all_activity_not_just_the_feature_language(
            self, mixed, band, cfg):
        unit, _ = make_unit(mixed, band, cfg, 60, 90, min_topic=10, min_window=1)
        assert unit["peak_bin"] >= 48   # the all-language peak, not the es one

    def test_window_volume_is_counted_in_the_feature_language(
            self, mixed, band, cfg):
        unit, _ = make_unit(mixed, band, cfg, 60, 90, min_topic=10, min_window=1)
        assert unit["n_window_tweets"] < unit["n_window_tweets_all_langs"]
        assert 0 < unit["feature_language_frac"] < 1

    def test_sparse_in_feature_language_is_dropped(self, mixed, band, cfg):
        unit, reason = make_unit(mixed, band, cfg, 60, 90,
                                 min_topic=10, min_window=1000)
        assert unit is None and reason == "window_too_sparse"

    def test_disabling_the_filter_uses_all_languages(self, mixed, band, cfg):
        unit, _ = make_unit(mixed, band, cfg, 60, 90, min_topic=10,
                            min_window=1, use_feature_language=False)
        assert unit["n_window_tweets"] == unit["n_window_tweets_all_langs"]


class TestCorpusScan:
    """End to end over synthetic CSVs carrying the real schema and quirks."""

    def test_labels_are_normalised_across_all_three_forms(self, synthetic_corpus,
                                                          band):
        cfg = synthetic_corpus
        full = band_from_config(cfg, hours=(cfg["validation_history"]["start_hour"],
                                            cfg["band"]["end_hour"]))
        pos = scan_trending(cfg, band, full)
        assert {"cleantopic", "leftcensored", "rightcensored"} <= set(pos)

    def test_shared_id_counts_once_per_topic_and_duplicate_row_collapses(
            self, synthetic_corpus, band):
        """De-dup keys on (id, topic). One tweet in two trends is real data."""
        cfg = synthetic_corpus
        full = band_from_config(cfg, hours=(cfg["validation_history"]["start_hour"],
                                            cfg["band"]["end_hour"]))
        pos = scan_trending(cfg, band, full)
        # bin 20 of CleanTopic: 3 from the profile + 1 shared id (dup collapsed)
        assert pos["cleantopic"].counts[20] == 4
        # the same shared id also lands in the other topic
        assert pos["leftcensored"].counts[20] == 2 + 1
        # bin 21: 3 from the profile + 1 from the duplicated pair, not 2
        assert pos["cleantopic"].counts[21] == 4

    def test_hashtags_that_trended_are_excluded_from_negatives(
            self, synthetic_corpus, band):
        """The prototype's leak, as a regression test."""
        cfg = synthetic_corpus
        full = band_from_config(cfg, hours=(cfg["validation_history"]["start_hour"],
                                            cfg["band"]["end_hour"]))
        pos = scan_trending(cfg, band, full)
        neg, n_excluded = scan_nontrending(cfg, band, set(pos))
        assert "cleantopic" not in neg
        assert n_excluded >= 1
        assert "cleanneg" in neg          # untrended hashtags still survive

    def test_censored_fixtures_are_dropped_end_to_end(self, synthetic_corpus,
                                                      band):
        cfg = synthetic_corpus
        full = band_from_config(cfg, hours=(cfg["validation_history"]["start_hour"],
                                            cfg["band"]["end_hour"]))
        pos = scan_trending(cfg, band, full)
        units, drops, verdicts = build_units(pos, band, cfg, 60, 90,
                                             min_topic=10, min_window=1)
        assert verdicts["leftcensored"] == "left_censored"
        assert verdicts["rightcensored"].startswith("right_censored")
        assert verdicts["cleantopic"] == "kept"
        kept = {u["topic"] for u in units}
        assert "leftcensored" not in kept and "rightcensored" not in kept

    def test_no_produced_unit_leaks_post_cutoff_data(self, synthetic_corpus,
                                                     band):
        """Whole-pipeline leakage guard."""
        cfg = synthetic_corpus
        full = band_from_config(cfg, hours=(cfg["validation_history"]["start_hour"],
                                            cfg["band"]["end_hour"]))
        pos = scan_trending(cfg, band, full)
        neg, _ = scan_nontrending(cfg, band, set(pos))
        lead_bins = band.minutes_to_bins(60)
        for pool in (pos, neg):
            units, _, _ = build_units(pool, band, cfg, 60, 90,
                                      min_topic=10, min_window=1)
            for u in units:
                assert u["window_end_bin"] == u["peak_bin"] - lead_bins
                assert u["window_end_bin"] < u["peak_bin"]
                assert u["window_start_bin"] >= 0
