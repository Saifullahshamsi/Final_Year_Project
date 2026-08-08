"""Synthetic corpus fixtures.

CI has no dataset, so every test builds its own corpus in code. The fixtures
reproduce the REAL twint schema and the real data quirks:

  * `trend` labels in all three contaminated forms (.csv, #, bare)
  * `mentions` / `reply_to` as stringified lists of dicts
  * one id shared across two topics (legitimate multi-trend membership)
  * one exactly duplicated row (must collapse)
  * a hashtag in the non-trending pool that also trended (must be excluded)
  * a left-censored, a right-censored and a clean topic
  * mixed languages, so the tweet-level language filter is exercised
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.loading import load_config

DATE = "2020-02-25"
BAND_START_HOUR = 16
BIN_MINUTES = 5

TREND_COLUMNS = [
    "Unnamed: 0.1", "id", "conversation_id", "created_at", "date", "time",
    "timezone", "user_id", "username", "name", "place", "tweet", "language",
    "mentions", "urls", "photos", "replies_count", "retweets_count",
    "likes_count", "hashtags", "cashtags", "link", "retweet", "quote_url",
    "video", "thumbnail", "near", "geo", "source", "user_rt_id", "user_rt",
    "retweet_id", "reply_to", "retweet_date", "translate", "trans_src",
    "trans_dest", "trend", "Unnamed: 0",
]
# The real non-trending file has no `trend` column and orders the index-like
# columns differently. Both quirks are reproduced.
NONTREND_COLUMNS = (["Unnamed: 0.1", "Unnamed: 0"]
                    + [c for c in TREND_COLUMNS
                       if c not in ("Unnamed: 0.1", "Unnamed: 0", "trend")])

MENTIONS = ("[{'screen_name': 'AliceX', 'name': 'alice', 'id': '1'}, "
            "{'screen_name': 'BobY', 'name': 'bob', 'id': '2'}]")
REPLY_TO = "[{'screen_name': 'CarolZ', 'name': 'carol', 'id': '3'}]"


def clock(bin_index: int) -> str:
    """Bin index -> 'HH:MM:SS' on the band grid."""
    total = BAND_START_HOUR * 3600 + bin_index * BIN_MINUTES * 60
    return f"{total // 3600:02d}:{(total % 3600) // 60:02d}:00"


def _row(tweet_id: int, bin_index: int, *, trend=None, hashtags="[]",
         language="es", username="user"):
    return {
        "Unnamed: 0.1": 0, "Unnamed: 0": 0,
        "id": str(tweet_id), "conversation_id": str(tweet_id),
        "created_at": f"{DATE} {clock(bin_index)} Romance Standard Time",
        "date": DATE, "time": clock(bin_index), "timezone": "100.0",
        "user_id": "999", "username": username, "name": username,
        "place": "", "tweet": "synthetic text", "language": language,
        "mentions": MENTIONS, "urls": "[]", "photos": "[]",
        "replies_count": "0", "retweets_count": "0", "likes_count": "0",
        "hashtags": hashtags, "cashtags": "[]", "link": "", "retweet": "",
        "quote_url": "", "video": "0", "thumbnail": "", "near": "", "geo": "",
        "source": "", "user_rt_id": "", "user_rt": "", "retweet_id": "",
        "reply_to": REPLY_TO, "retweet_date": "", "translate": "",
        "trans_src": "", "trans_dest": "", "trend": trend,
    }


def _profile(bins_and_counts):
    """[(bin, count), ...] -> flat list of bin indices."""
    out = []
    for b, n in bins_and_counts:
        out.extend([b] * n)
    return out


# Activity profiles, in bins of the 96-bin band grid.
# Clean: quiet rise, sharp peak mid-band, observed decay after it.
CLEAN = _profile([(b, 3) for b in range(18, 36)]
                 + [(b, 2) for b in range(36, 48)]
                 + [(b, 12) for b in range(48, 51)]
                 + [(b, 1) for b in range(51, 72)])
# Left-censored: already at full volume in the very first bin.
LEFT_CENSORED = _profile([(b, 15) for b in range(0, 5)]
                         + [(b, 2) for b in range(5, 40)])
# Right-censored: still climbing when the band ends.
RIGHT_CENSORED = _profile([(b, 2) for b in range(40, 80)]
                          + [(b, n) for n, b in enumerate(range(80, 96), start=3)])


@pytest.fixture
def synthetic_corpus(tmp_path):
    """Write both CSVs and return (cfg, paths) with cfg pointed at them."""
    tid = iter(range(10_000_000, 20_000_000))

    trend_rows = []
    # Three contaminated label forms, one per censoring behaviour.
    for label, profile, lang in [("CleanTopic.csv", CLEAN, "es"),
                                 ("#LeftCensored", LEFT_CENSORED, "es"),
                                 ("RightCensored", RIGHT_CENSORED, "es")]:
        for b in profile:
            trend_rows.append(_row(next(tid), b, trend=label, language=lang))

    # An English-dominant clean topic: survives without the language filter,
    # should thin out under it.
    for b in CLEAN:
        trend_rows.append(_row(next(tid), b, trend="EnglishTopic.csv",
                               language="en"))

    # One tweet belonging to TWO trends — must be counted once per topic, and
    # must NOT be collapsed by de-duplication.
    shared = next(tid)
    trend_rows.append(_row(shared, 20, trend="CleanTopic.csv"))
    trend_rows.append(_row(shared, 20, trend="#LeftCensored"))
    # An exact duplicate row — same (id, topic) — must collapse to one.
    dup = next(tid)
    trend_rows.append(_row(dup, 21, trend="CleanTopic.csv"))
    trend_rows.append(_row(dup, 21, trend="CleanTopic.csv"))

    nontrend_rows = []
    for b in CLEAN:
        nontrend_rows.append(_row(next(tid), b, hashtags="['cleanneg']"))
    for b in LEFT_CENSORED:
        nontrend_rows.append(_row(next(tid), b, hashtags="['leftneg']"))
    # A hashtag that DID trend — the leak the prototype missed. Note the raw
    # trend label was 'CleanTopic.csv', so only cleaned-name comparison catches it.
    for b in CLEAN:
        nontrend_rows.append(_row(next(tid), b, hashtags="['cleantopic']"))

    tr = tmp_path / "trending.csv"
    nt = tmp_path / "nontrending.csv"
    pd.DataFrame(trend_rows)[TREND_COLUMNS].to_csv(tr, index=False)
    pd.DataFrame(nontrend_rows)[NONTREND_COLUMNS].to_csv(nt, index=False)

    cfg = load_config()
    cfg["paths"]["trending_csv"] = str(tr)
    cfg["paths"]["nontrending_csv"] = str(nt)
    cfg["io"]["chunksize"] = 100          # force multi-chunk streaming
    return cfg
