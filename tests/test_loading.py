"""Field parsing and binning — the layer every downstream number depends on."""
import pytest

from src.data.loading import (
    Band,
    band_from_config,
    clean_topic,
    load_config,
    parse_hashtags,
    parse_screen_names,
    time_to_seconds,
)


class TestCleanTopic:
    """Trend labels arrive in three contaminated forms. Comparing raw forms is
    what leaked trended topics into the negative pool."""

    @pytest.mark.parametrize("raw,expected", [
        ("Bayern.csv", "bayern"),          # .csv suffix
        ("#BTSonFallon", "btsonfallon"),   # # prefix
        ("#Askelarre.csv", "askelarre"),   # both
        ("Gaga", "gaga"),                  # bare
        ("  #Mixed.CSV  ", "mixed"),       # whitespace + case
        ("cleantopic", "cleantopic"),      # already clean, idempotent
    ])
    def test_normalises_every_label_form(self, raw, expected):
        assert clean_topic(raw) == expected

    def test_is_idempotent(self):
        assert clean_topic(clean_topic("#Bayern.csv")) == clean_topic("#Bayern.csv")

    def test_hashtag_matches_its_trend_label(self):
        """The leak in one assertion: a bare hashtag must equal the cleaned
        trend name it corresponds to."""
        assert clean_topic("cleantopic") == clean_topic("CleanTopic.csv")

    @pytest.mark.parametrize("bad", [None, 3.5, float("nan")])
    def test_survives_non_strings(self, bad):
        assert clean_topic(bad) == ""


class TestParsing:
    def test_hashtags_from_stringified_list(self):
        assert parse_hashtags("['grande', 'AndaLevanta']") == ["grande", "andalevanta"]

    @pytest.mark.parametrize("cell", ["", "[]", "nan", None, "not a list", "{'a': 1}"])
    def test_hashtags_reject_junk(self, cell):
        assert parse_hashtags(cell) == []

    def test_screen_names_from_stringified_dicts(self):
        cell = ("[{'screen_name': 'MonicaNaranjo', 'name': 'm', 'id': '1'}, "
                "{'screen_name': 'GloriaTrevi', 'name': 'g', 'id': '2'}]")
        assert parse_screen_names(cell) == ["monicanaranjo", "gloriatrevi"]

    def test_screen_names_skip_entries_without_the_key(self):
        assert parse_screen_names("[{'name': 'no screen name'}]") == []

    @pytest.mark.parametrize("cell", ["", "[]", "nan", None, "["])
    def test_screen_names_reject_junk(self, cell):
        assert parse_screen_names(cell) == []


class TestTime:
    def test_parses_valid_clock(self):
        assert time_to_seconds("16:05:30") == 16 * 3600 + 5 * 60 + 30

    @pytest.mark.parametrize("bad", ["0.0", "", None, "9:34:40", "16:05", 12345])
    def test_rejects_malformed(self, bad):
        assert time_to_seconds(bad) is None


class TestBand:
    @pytest.fixture
    def band(self):
        return Band("2020-02-25", 16, 23, 5, drop_dates=["2020-02-26"])

    def test_bin_count_covers_the_whole_band(self, band):
        assert band.n_bins == 96                     # 8 hours / 5 min

    def test_first_and_last_bin(self, band):
        assert band.bin_of("2020-02-25", "16:00:00") == 0
        assert band.bin_of("2020-02-25", "23:59:59") == 95

    @pytest.mark.parametrize("time_str", ["15:59:59", "00:30:00", "09:34:40"])
    def test_rejects_times_outside_the_band(self, band, time_str):
        assert band.bin_of("2020-02-25", time_str) is None

    def test_rejects_the_next_day_residue(self, band):
        """151 rows are dated 2020-02-26 and must never enter the grid."""
        assert band.bin_of("2020-02-26", "16:30:00") is None

    def test_rejects_malformed_rows(self, band):
        assert band.bin_of("0.0", "16:30:00") is None
        assert band.bin_of("2020-02-25", "0.0") is None

    def test_minutes_to_bins(self, band):
        assert band.minutes_to_bins(60) == 12
        assert band.minutes_to_bins(90) == 18

    def test_bin_to_clock_round_trips(self, band):
        assert band.bin_to_clock(0) == "16:00"
        assert band.bin_to_clock(12) == "17:00"


def test_config_paths_resolve_absolutely():
    cfg = load_config()
    assert cfg["paths"]["trending_csv"].endswith("tweets_25_tendencia_raw.csv")
    band = band_from_config(cfg)
    assert band.n_bins > 0
