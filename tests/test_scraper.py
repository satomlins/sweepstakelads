"""Scraper regression tests against pinned wikitext snapshots.

Run: uv run pytest tests/test_scraper.py -v
Refresh snapshots: uv run python scripts/refresh_fixtures.py
"""

from datetime import timezone
from pathlib import Path

import pytest

from scraper import parse_matches, _parse_datetime_utc, _extract_code, _code_to_name

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Group A snapshot
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def group_a_matches():
    wikitext = (FIXTURES / "group_a_2026-05-11.wikitext").read_text()
    return parse_matches(wikitext, stage_override="Group A")


def test_group_a_match_count(group_a_matches):
    assert len(group_a_matches) == 6


def test_group_a_first_match_teams(group_a_matches):
    m = group_a_matches[0]
    assert m["home_team"] == "Mexico"
    assert m["away_team"] == "South Africa"


def test_group_a_first_match_datetime(group_a_matches):
    m = group_a_matches[0]
    assert m["datetime_utc"] is not None
    assert m["datetime_utc"].tzinfo == timezone.utc
    assert m["datetime_utc"].isoformat() == "2026-06-11T19:00:00+00:00"


def test_group_a_all_stages(group_a_matches):
    for m in group_a_matches:
        assert m["stage"] == "Group A"


def test_group_a_all_upcoming(group_a_matches):
    # Tournament hasn't started in this snapshot
    for m in group_a_matches:
        assert m["status"] == "upcoming"
        assert m["home_score"] is None
        assert m["away_score"] is None


def test_group_a_all_have_datetimes(group_a_matches):
    for m in group_a_matches:
        assert m["datetime_utc"] is not None, f"Missing datetime for {m['home_team']} vs {m['away_team']}"


def test_group_a_last_matchday_simultaneous(group_a_matches):
    # MD3 matches kick off simultaneously (same UTC time) — anti-corruption requirement
    md3 = group_a_matches[4:]
    assert len(md3) == 2
    assert md3[0]["datetime_utc"] == md3[1]["datetime_utc"]


# ---------------------------------------------------------------------------
# Knockout snapshot
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def knockout_matches():
    wikitext = (FIXTURES / "knockout_2026-05-11.wikitext").read_text()
    return parse_matches(wikitext)


def test_knockout_match_count(knockout_matches):
    # R32 (16) + R16 (8) + QF (4) + SF (2) + 3rd place (1) = 31
    assert len(knockout_matches) == 31


def test_knockout_r32_count(knockout_matches):
    r32 = [m for m in knockout_matches if m["stage"] == "Round of 32"]
    assert len(r32) == 16


def test_knockout_r16_count(knockout_matches):
    r16 = [m for m in knockout_matches if m["stage"] == "Round of 16"]
    assert len(r16) == 8


def test_knockout_qf_count(knockout_matches):
    qf = [m for m in knockout_matches if m["stage"] == "Quarterfinals"]
    assert len(qf) == 4


def test_knockout_sf_count(knockout_matches):
    sf = [m for m in knockout_matches if m["stage"] == "Semifinals"]
    assert len(sf) == 2


def test_knockout_third_place(knockout_matches):
    tp = [m for m in knockout_matches if m["stage"] == "Match for third place"]
    assert len(tp) == 1


def test_knockout_all_upcoming(knockout_matches):
    for m in knockout_matches:
        assert m["status"] == "upcoming"


def test_knockout_placeholder_passthrough(knockout_matches):
    # Future rounds have placeholder names — scraper must pass them through
    r16 = [m for m in knockout_matches if m["stage"] == "Round of 16"]
    assert all("Winner" in m["home_team"] or "Winner" in m["away_team"] for m in r16)


# ---------------------------------------------------------------------------
# Unit tests for parsing helpers
# ---------------------------------------------------------------------------

def test_extract_code_standard():
    assert _extract_code("{{#invoke:flag|fb|MEX}}") == "MEX"


def test_extract_code_no_match():
    assert _extract_code("plain text") == ""


def test_code_to_name_known():
    assert _code_to_name("MEX") == "Mexico"
    assert _code_to_name("ENG") == "England"
    assert _code_to_name("CUW") == "Curaçao"


def test_code_to_name_unknown():
    # Unknown codes fall back to the code itself
    assert _code_to_name("XYZ") == "XYZ"


def test_parse_datetime_utc_basic():
    from datetime import date
    dt = _parse_datetime_utc(date(2026, 6, 11), "1:00 p.m. UTC−6")
    assert dt is not None
    assert dt.isoformat() == "2026-06-11T19:00:00+00:00"


def test_parse_datetime_utc_midnight():
    from datetime import date
    dt = _parse_datetime_utc(date(2026, 6, 12), "12:00 a.m. UTC+0")
    assert dt is not None
    assert dt.isoformat() == "2026-06-12T00:00:00+00:00"


def test_parse_datetime_utc_missing_date():
    assert _parse_datetime_utc(None, "1:00 p.m. UTC−6") is None


def test_parse_datetime_utc_garbage():
    from datetime import date
    assert _parse_datetime_utc(date(2026, 6, 11), "TBD") is None


# ---------------------------------------------------------------------------
# AET / penalty-shootout parsing
# ---------------------------------------------------------------------------

_AET_PENS_WIKITEXT = """
==Round of 16==
{{#invoke:football box|main
|date={{Start date|2026|7|4}}
|team1={{#invoke:flag|fb|ENG}}
|team2={{#invoke:flag|fb|GER}}
|score=1–1
|aet=yes
|penaltyscore=4–3
}}
""".strip()


_AET_NO_PENS_WIKITEXT = """
==Round of 16==
{{#invoke:football box|main
|date={{Start date|2026|7|4}}
|team1={{#invoke:flag|fb|ENG}}
|team2={{#invoke:flag|fb|GER}}
|score=2–1
|aet=yes
}}
""".strip()


def test_parse_aet_with_pens():
    matches = parse_matches(_AET_PENS_WIKITEXT)
    assert len(matches) == 1
    m = matches[0]
    assert m["home_team"] == "England"
    assert m["away_team"] == "Germany"
    assert m["home_score"] == 1
    assert m["away_score"] == 1
    assert m["aet"] is True
    assert m["pen_home"] == 4
    assert m["pen_away"] == 3
    assert m["status"] == "finished"


def test_parse_aet_without_pens():
    matches = parse_matches(_AET_NO_PENS_WIKITEXT)
    assert len(matches) == 1
    m = matches[0]
    assert m["home_score"] == 2
    assert m["away_score"] == 1
    assert m["aet"] is True
    assert m["pen_home"] is None
    assert m["pen_away"] is None
