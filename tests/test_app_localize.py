"""Regression tests for _localize_fixtures.

Verifies that the function always returns a frame with a Time (and Date) column,
even when the input slice is empty — the downstream projection to ["Date", "Time", ...]
was crashing when Status == "Finished" yielded zero rows before the tournament began.
"""

import pandas as pd

from app import _localize_fixtures


def _fixture_row(status="Upcoming"):
    return {
        "DatetimeUTC": "2026-06-11T19:00:00",
        "Date": "2026-06-11",
        "Home": "Mexico",
        "Score": "vs",
        "Away": "South Africa",
        "Stage": "Group A",
        "Status": status,
    }


def test_empty_df_has_time_column():
    df = pd.DataFrame(columns=["DatetimeUTC", "Date", "Home", "Score", "Away", "Stage", "Status"])
    result = _localize_fixtures(df, tz_minutes=0)
    assert "Time" in result.columns
    assert "Date" in result.columns
    assert len(result) == 0


def test_empty_filtered_slice_has_time_column():
    """Exact regression: filter to Status==Finished on pre-tournament data → empty → must still have Time."""
    df = pd.DataFrame([_fixture_row("Upcoming"), _fixture_row("Upcoming")])
    finished = df[df["Status"] == "Finished"]
    result = _localize_fixtures(finished, tz_minutes=0)
    assert "Time" in result.columns
    # Must be projectable without KeyError
    projected = result[["Date", "Time", "Home", "Score", "Away", "Stage"]]
    assert len(projected) == 0


def test_empty_filtered_slice_projectable_with_no_tz():
    """Same case with tz_minutes=None default fallback (0)."""
    df = pd.DataFrame([_fixture_row("Upcoming")])
    finished = df[df["Status"] == "Finished"]
    result = _localize_fixtures(finished, tz_minutes=0)
    _ = result[["Date", "Time", "Home", "Score", "Away", "Stage"]]  # must not raise


def test_non_empty_slice_synthesises_time():
    df = pd.DataFrame([_fixture_row("Finished")])
    result = _localize_fixtures(df, tz_minutes=0)
    assert "Time" in result.columns
    assert result["Time"].iloc[0] == "19:00"
    assert result["Date"].iloc[0] == "11 Jun"


def test_non_empty_slice_with_positive_offset():
    df = pd.DataFrame([_fixture_row("Upcoming")])
    result = _localize_fixtures(df, tz_minutes=60)
    assert result["Time"].iloc[0] == "20:00"
