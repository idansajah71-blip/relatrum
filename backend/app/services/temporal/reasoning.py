"""Temporal reasoning: interval overlap, applicability, supersession.

Semantics:
  * Timestamps are opaque strings until they parse (ISO-8601 accepted).
  * Unknown bounds are treated as UNKNOWN, never as an implicit infinity or an
    implicit exact date; comparisons involving unknown return None (unknown).
  * 'within-N-days' style durations apply relative to submission, not as exact
    dates; they are converted only for numeric comparison.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta

_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "ten": 10, "fourteen": 14,
    "satu": 1, "dua": 2, "tiga": 3, "empat": 4, "lima": 5,
}

_DURATION_RE = re.compile(r"within\s+(?:(\d+)|(\w+))\s+(working\s+)?days?", re.IGNORECASE)
_ELAPSED_RE = re.compile(r"\b(?:took|after|completed in)\s+(?:(\d+)|(\w+))\s+(working\s+)?days?", re.IGNORECASE)


@dataclass(frozen=True)
class Interval:
    start: date | None
    end: date | None

    @classmethod
    def parse(cls, text: str | None) -> "Interval | None":
        if not text:
            return None
        cleaned = str(text).strip()
        bounds = _parse_iso(cleaned)
        if bounds is None:
            return None
        start, end, raw_text = bounds
        return Interval(start=start, end=end)

    def overlaps(self, other: "Interval") -> bool | None:
        if other is None or (self.start is None and self.end is None) or (other.start is None and other.end is None):
            return None
        a_start = self.start if self.start is not None else date.min
        a_end = self.end if self.end is not None else date.max
        b_start = other.start if other.start is not None else date.min
        b_end = other.end if other.end is not None else date.max
        return a_start <= b_end and b_start <= a_end

    def contains(self, point: date) -> bool | None:
        if point is None:
            return None
        start = self.start if self.start is not None else date.min
        end = self.end if self.end is not None else date.max
        return start <= point <= end


@dataclass(frozen=True)
class TemporalJudgement:
    compatibility: str  # 'compatible' | 'incompatible' | 'unknown'
    detail: str


def _parse_iso(text: str) -> tuple[date | None, date | None, str] | None:
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        day = parsed.date() if hasattr(parsed, "date") else parsed
        return day, day, text
    except (ValueError, AttributeError):
        pass
    year_only = re.fullmatch(r"(20\d{2})", text)
    if year_only:
        return date(int(year_only.group(1)), 1, 1), None, text
    month_year = re.fullmatch(r"(20\d{2})[-/](\d{1,2})", text)
    if month_year:
        y, m = int(month_year.group(1)), int(month_year.group(2))
        return date(y, m, 1), None, text
    return None


def statement_interval(statement) -> Interval | None:
    """Interval from explicit statement temporal columns (valid_from/until).

    A from-date opens an interval (open-ended) unless an until-date closes it;
    either column alone also yields a usable, one-sided interval.
    """
    start_iv = Interval.parse(statement.temporal_valid_from) if statement.temporal_valid_from else None
    end_iv = Interval.parse(statement.temporal_valid_until) if statement.temporal_valid_until else None
    if start_iv is None and end_iv is None:
        return None
    return Interval(
        start=start_iv.start if start_iv else None,
        end=end_iv.end if end_iv else None,
    )


def observed_date(statement) -> date | None:
    for field in (statement.observed_at, statement.reported_at):
        if field:
            interval = Interval.parse(field)
            if interval is not None:
                return interval.start
    return None


def extract_duration_days(text: str | None) -> float | None:
    """Parse 'within two working days' style durations into a day count.

    Working days are treated as calendrical days for comparison (approximation
    documented in methodology; holiday counting is out of scope for the engine).
    """
    if not text:
        return None
    match = _DURATION_RE.search(text)
    if not match:
        return None
    number = match.group(1)
    if number:
        return float(number)
    word = match.group(2) or ""
    return _WORD_NUMBERS.get(word.lower(), None)


def extract_elapsed_days(text: str | None) -> float | None:
    """Parse 'took twenty days' / 'after four days' style elapsed durations.

    Same approximation as extract_duration_days: working days count as
    calendar days. Returns None when the text states no elapsed duration.
    """
    if not text:
        return None
    match = _ELAPSED_RE.search(text)
    if not match:
        return None
    number = match.group(1)
    if number:
        return float(number)
    word = match.group(2) or ""
    return _WORD_NUMBERS.get(word.lower(), None)


def classify_temporal_pair(requirement, observation) -> TemporalJudgement:
    """Version-aware applicability check for a (requirement, observation) pair."""
    req_interval = statement_interval(requirement)
    obs_point = observed_date(observation)
    req_duration = extract_duration_days(requirement.original_text or "")
    obs_duration = extract_duration_days(observation.original_text or "")

    if req_interval is not None and obs_point is not None:
        applicable = req_interval.contains(obs_point)
        if applicable is False:
            return TemporalJudgement(
                compatibility="incompatible",
                detail=(
                    f"Observed date {obs_point.isoformat()} falls outside the "
                    f"requirement's validity window "
                    f"{req_interval.start or '?'}..{req_interval.end or '?'}."
                ),
            )
        if applicable is True:
            return _duration_judgement(req_duration, obs_duration)

    if req_interval is None and obs_point is None:
        return TemporalJudgement(
            compatibility="unknown",
            detail="Neither the requirement nor the observation carries usable dates.",
        )
    return TemporalJudgement(
        compatibility="unknown",
        detail=(
            "One side lacks temporal information; applicability could not be "
            "checked without inventing dates."
        ),
    )


def _duration_judgement(req_duration: float | None, obs_duration: float | None) -> TemporalJudgement:
    if obs_duration is None:
        return TemporalJudgement(
            compatibility="unknown",
            detail="Observation does not state a processing duration to compare.",
        )
    if req_duration is None:
        return TemporalJudgement(
            compatibility="unknown",
            detail="Requirement does not state a measurable processing duration.",
        )
    if obs_duration <= req_duration:
        return TemporalJudgement(
            compatibility="compatible",
            detail=(
                f"Observed duration ({obs_duration:g}d) is within the specified "
                f"maximum ({req_duration:g}d)."
            ),
        )
    return TemporalJudgement(
        compatibility="incompatible",
        detail=(
            f"Observed duration ({obs_duration:g}d) exceeds the specified "
            f"maximum ({req_duration:g}d)."
        ),
    )


def supersession_pairs(requirements: list) -> list[tuple[int, int, str]]:
    """Detect candidate supersession between requirement statements.

    Two requirements with the same subject (normalized) and a differing,
    tappable validity window pattern supersede one another when their windows
    do not overlap and one is strictly later. Returns (older_index, newer_index,
    explanation).
    """
    out: list[tuple[int, int, str]] = []
    for i, older in enumerate(requirements):
        for j, newer in enumerate(requirements):
            if i == j:
                continue
            same_subject = (older.subject or "").lower() == (newer.subject or "").lower()
            if not same_subject and older.subject and newer.subject:
                continue
            old_iv, new_iv = statement_interval(older), statement_interval(newer)
            if old_iv is None or new_iv is None:
                continue
            if old_iv.end is None or new_iv.start is None:
                continue
            if new_iv.start > old_iv.end:
                out.append(
                    (
                        i,
                        j,
                        (
                            f"Requirement {older.id or older.original_text[:40]} validity ends "
                            f"{old_iv.end.isoformat()}; requirement {j} starts "
                            f"{new_iv.start.isoformat()}, implying later revision."
                        ),
                    )
                )
    return out
