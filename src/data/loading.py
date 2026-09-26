"""Streaming loaders and field-parsing helpers for the twint corpus.

Everything here is chunked; no function loads a whole CSV. All tunables come
from config.yaml — see load_config.
"""
from __future__ import annotations

import ast
import re
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path

import pandas as pd
import yaml

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TIME_RE = re.compile(r"^\d{2}:\d{2}:\d{2}$")

_NULLISH = ("", "[]", "nan", "None")


def repo_root() -> Path:
    """Repo root, resolved from this file's location (src/data/loading.py)."""
    return Path(__file__).resolve().parents[2]


def utf8_console() -> None:
    """Make stdout and stderr UTF-8 so console output renders as written.

    Windows consoles default to cp1252, which turns every em dash, arrow and
    Greek letter this pipeline prints into a literal '?'. The text is correct
    and the files on disk are fine; only the terminal rendering is wrong. It
    still matters twice over: a run being demonstrated should not look broken,
    and in an audit table a '?' where a rho was is genuinely ambiguous.

    Two steps, because they fix different halves of the problem.
    `reconfigure` changes how Python encodes what it writes;
    `SetConsoleOutputCP` changes what the Windows console decodes. Doing only
    the first still mojibakes on a legacy console.

    Every failure path here is non-fatal by design: a redirected stream, a
    stream with no `reconfigure`, or any non-Windows platform simply leaves
    things as they were. Console encoding is never worth crashing a run over.
    """
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
        except Exception:  # noqa: BLE001 - cosmetic only; never fail a run
            pass
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


def load_config(path: str | Path | None = None) -> dict:
    path = Path(path) if path else repo_root() / "config.yaml"
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh)
    # Resolve every path relative to the repo root so scripts can run anywhere.
    root = repo_root()
    cfg["paths"] = {k: str(root / v) for k, v in cfg["paths"].items()}
    return cfg


# --------------------------------------------------------------------------
# Field parsing
# --------------------------------------------------------------------------
def clean_topic(raw: str) -> str:
    """Normalise a trend name or hashtag into one comparable topic key.

    Trend labels arrive in three mixed forms (gotcha #1): '.csv'-suffixed,
    '#'-prefixed, both, or bare. Hashtags arrive bare. Comparing the raw forms
    is what leaked trended topics into the negative pool, so every comparison
    must go through this function.
    """
    if not isinstance(raw, str):
        return ""
    s = raw.strip()
    if s.lower().endswith(".csv"):
        s = s[:-4]
    return s.lstrip("#").strip().lower()


def parse_hashtags(cell) -> list[str]:
    """twint 'hashtags' cell -> list of cleaned tag strings."""
    if not isinstance(cell, str) or cell in _NULLISH:
        return []
    try:
        tags = ast.literal_eval(cell)
    except Exception:
        return []
    if not isinstance(tags, list):
        return []
    return [t for t in (clean_topic(str(x)) for x in tags) if t]


def parse_screen_names(cell) -> list[str]:
    """twint 'mentions'/'reply_to' cell -> list of lowercased screen names."""
    if not isinstance(cell, str) or cell in _NULLISH:
        return []
    try:
        lst = ast.literal_eval(cell)
    except Exception:
        return []
    out = []
    if isinstance(lst, list):
        for d in lst:
            if isinstance(d, dict) and d.get("screen_name"):
                out.append(str(d["screen_name"]).strip().lower())
    return out


def time_to_seconds(t) -> int | None:
    """'HH:MM:SS' -> seconds since midnight, or None if malformed."""
    if not isinstance(t, str) or not TIME_RE.match(t):
        return None
    return int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])


# --------------------------------------------------------------------------
# Band / binning
# --------------------------------------------------------------------------
class Band:
    """The window of clock time a pass is allowed to see, and its bin grid."""

    def __init__(self, date: str, start_hour: int, end_hour: int,
                 bin_minutes: int, drop_dates: Iterable[str] = ()):
        self.date = date
        self.start_sec = start_hour * 3600
        self.end_sec = (end_hour + 1) * 3600 - 1      # inclusive of :59:59
        self.bin_sec = bin_minutes * 60
        self.drop_dates = set(drop_dates or ())
        self.n_bins = (self.end_sec + 1 - self.start_sec) // self.bin_sec

    def bin_of(self, date, time_str) -> int | None:
        """Bin index for a row, or None if the row falls outside the band."""
        if not isinstance(date, str) or date != self.date or date in self.drop_dates:
            return None
        sec = time_to_seconds(time_str)
        if sec is None or sec < self.start_sec or sec > self.end_sec:
            return None
        return (sec - self.start_sec) // self.bin_sec

    def bin_to_clock(self, b: int) -> str:
        sec = self.start_sec + b * self.bin_sec
        return f"{sec // 3600:02d}:{(sec % 3600) // 60:02d}"

    def minutes_to_bins(self, minutes: int) -> int:
        return minutes * 60 // self.bin_sec


def band_from_config(cfg: dict, *, hours: tuple[int, int] | None = None) -> Band:
    """Build the modelling Band, or an alternative hour range on the same grid."""
    b = cfg["band"]
    start, end = hours if hours else (b["start_hour"], b["end_hour"])
    return Band(date=b["date"], start_hour=start, end_hour=end,
                bin_minutes=cfg["units"]["bin_minutes"],
                drop_dates=b.get("drop_dates", ()))


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------
def stream(path: str | Path, usecols: list[str], cfg: dict) -> Iterator[pd.DataFrame]:
    """Chunked reader. dtype=str throughout — the corpus has mixed junk in
    numeric-looking columns and we parse explicitly."""
    yield from pd.read_csv(path, usecols=usecols, chunksize=cfg["io"]["chunksize"],
                           dtype=str, on_bad_lines=cfg["io"]["on_bad_lines"],
                           engine="c")
