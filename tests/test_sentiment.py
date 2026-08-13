"""Sentiment aggregation and cache keying.

Deliberately torch-free: the model itself is pinned and benchmarked elsewhere,
but CI has neither the weights nor the corpus, so everything here runs on
hand-built probability arrays. That keeps the CI run under a minute while still
covering the logic that turns model output into features.
"""
import numpy as np
import pandas as pd
import pytest

from src.data.loading import band_from_config, load_config
from src.features.sentiment import (
    NEG,
    NEU,
    POS,
    aggregate,
    lead_sweep_bins,
    load_cache,
    save_cache,
    text_key,
)


@pytest.fixture
def cfg():
    return load_config()


def probs(*triples):
    """(p_neg, p_neu, p_pos) rows -> (records, cache) ready for aggregate()."""
    cache, records = {}, []
    for i, t in enumerate(triples):
        k = f"k{i}"
        cache[k] = np.array(t, dtype=float)
        records.append((i, k))
    return records, cache


class TestTextKey:
    def test_is_stable(self):
        assert text_key("hola mundo") == text_key("hola mundo")

    def test_differs_by_content(self):
        assert text_key("hola") != text_key("hola ")

    def test_handles_emoji_and_accents(self):
        assert len(text_key("qué pasa 🔥ñ")) == 16

    def test_key_does_not_contain_the_text(self):
        """The cache ships in no repo, but keys must not carry tweet content."""
        assert "hola" not in text_key("hola mundo")


class TestAggregate:
    def test_all_positive_gives_polarity_one(self):
        recs, cache = probs((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
        f = aggregate(recs, cache, load_config())
        assert f["sent_mean"] == pytest.approx(1.0)
        assert f["sent_pos_frac"] == 1.0
        assert f["sent_var"] == pytest.approx(0.0)

    def test_all_negative_gives_polarity_minus_one(self):
        recs, cache = probs((1.0, 0.0, 0.0))
        assert aggregate(recs, cache, load_config())["sent_mean"] == pytest.approx(-1.0)

    def test_neutral_has_zero_polarity_and_zero_intensity(self):
        recs, cache = probs((0.0, 1.0, 0.0), (0.0, 1.0, 0.0))
        f = aggregate(recs, cache, load_config())
        assert f["sent_mean"] == pytest.approx(0.0)
        assert f["sent_intensity"] == pytest.approx(0.0)
        assert f["sent_neu_frac"] == 1.0

    def test_polarisation_distinguishes_split_from_neutral(self, cfg):
        """The point of the feature: a split crowd is not a calm one."""
        split, c1 = probs((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        calm, c2 = probs((0.0, 1.0, 0.0), (0.0, 1.0, 0.0))
        a = aggregate(split, c1, cfg)
        b = aggregate(calm, c2, cfg)
        assert a["sent_mean"] == pytest.approx(b["sent_mean"], abs=1e-9)
        assert a["sent_polarisation"] == 1.0
        assert b["sent_polarisation"] == 0.0
        assert a["sent_var"] > b["sent_var"]

    def test_strong_frac_respects_the_configured_threshold(self, cfg):
        recs, cache = probs((0.0, 0.0, 1.0), (0.3, 0.4, 0.3))
        f = aggregate(recs, cache, cfg)
        assert f["sent_strong_frac"] == pytest.approx(0.5)

    def test_skew_sign_follows_the_tail(self, cfg):
        recs, cache = probs((0.5, 0.5, 0.0), (0.5, 0.5, 0.0),
                            (0.5, 0.5, 0.0), (0.0, 0.0, 1.0))
        assert aggregate(recs, cache, cfg)["sent_skew"] > 0

    def test_empty_window_returns_zeros_not_nan(self, cfg):
        f = aggregate([], {}, cfg)
        assert f["meta_sent_n"] == 0.0
        assert all(np.isfinite(v) for v in f.values())

    def test_records_missing_from_cache_are_skipped(self, cfg):
        recs, cache = probs((0.0, 0.0, 1.0))
        recs.append((9, "not_in_cache"))
        assert aggregate(recs, cache, cfg)["meta_sent_n"] == 1.0

    def test_prefix_is_applied_to_every_key(self, cfg):
        recs, cache = probs((0.0, 0.0, 1.0))
        assert all(k.startswith("es_") for k in aggregate(recs, cache, cfg, "es_"))

    def test_tweet_count_is_metadata_not_a_sentiment_feature(self, cfg):
        """meta_sent_n equals the volume feature window_tweets (AUC 0.832).
        Modelling it in the sentiment arm would credit volume to sentiment."""
        recs, cache = probs((0.0, 0.0, 1.0), (1.0, 0.0, 0.0))
        f = aggregate(recs, cache, cfg)
        assert "sent_n" not in f
        assert f["meta_sent_n"] == 2.0
        assert cfg["features"]["sentiment"] == [
            k for k in f if k.startswith("sent_")]

    def test_no_sentiment_feature_scales_with_window_size(self, cfg):
        """Same distribution, ten times the tweets: features must not move."""
        one, c1 = probs((0.1, 0.2, 0.7), (0.7, 0.2, 0.1))
        ten, c10 = probs(*([(0.1, 0.2, 0.7), (0.7, 0.2, 0.1)] * 10))
        a, b = aggregate(one, c1, cfg), aggregate(ten, c10, cfg)
        for k in cfg["features"]["sentiment"]:
            assert a[k] == pytest.approx(b[k], abs=1e-9), k

    def test_label_indices_match_the_configured_order(self, cfg):
        assert cfg["sentiment"]["labels"] == ["negative", "neutral", "positive"]
        assert (NEG, NEU, POS) == (0, 1, 2)


class TestCacheRoundTrip:
    def test_probabilities_survive_a_save_load_cycle(self, tmp_path):
        path = tmp_path / "cache.csv"
        original = {"a": np.array([0.1, 0.3, 0.6]),
                    "b": np.array([0.8, 0.15, 0.05])}
        save_cache(path, original)
        back = load_cache(path)
        assert set(back) == set(original)
        for k in original:
            assert np.allclose(back[k], original[k])

    def test_missing_cache_file_is_empty_not_an_error(self, tmp_path):
        assert load_cache(tmp_path / "nope.csv") == {}

    def test_cache_file_stores_raw_probabilities_not_aggregates(self, tmp_path):
        """Aggregates must be redefinable without re-running the model."""
        path = tmp_path / "cache.csv"
        save_cache(path, {"a": np.array([0.1, 0.3, 0.6])})
        cols = set(pd.read_csv(path).columns)
        assert {"key", "p_neg", "p_neu", "p_pos"} <= cols


class TestLeadSweepBins:
    def test_covers_every_lead_in_the_sweep(self, cfg):
        band = band_from_config(cfg)
        units = pd.DataFrame([{"topic": "t", "peak_bin": 80}])
        bins = lead_sweep_bins(units, band, cfg)["t"]
        win = band.minutes_to_bins(max(cfg["units"]["window_sweep"]))
        for lead in cfg["units"]["lead_sweep"]:
            end = 80 - band.minutes_to_bins(lead)
            assert set(range(end - win, end)) <= bins

    def test_never_reaches_the_peak(self, cfg):
        """Even the shortest lead must leave the peak unscored."""
        band = band_from_config(cfg)
        units = pd.DataFrame([{"topic": "t", "peak_bin": 80}])
        shortest = band.minutes_to_bins(min(cfg["units"]["lead_sweep"]))
        assert max(lead_sweep_bins(units, band, cfg)["t"]) < 80 - shortest + 1

    def test_clamps_at_the_band_start(self, cfg):
        band = band_from_config(cfg)
        units = pd.DataFrame([{"topic": "t", "peak_bin": 8}])
        assert min(lead_sweep_bins(units, band, cfg)["t"], default=0) >= 0
