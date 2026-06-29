"""Scraper regression tests against pinned wikitext snapshots.

Run: uv run pytest tests/test_scraper.py -v
Refresh snapshots: uv run python scripts/refresh_fixtures.py
"""

from datetime import timezone
from pathlib import Path

import pytest

from unittest.mock import MagicMock, patch

from scraper import (
    parse_matches,
    _parse_datetime_utc,
    _extract_code,
    _code_to_name,
    _extract_labeled_section,
    _resolve_transclusions,
)

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


# ---------------------------------------------------------------------------
# Transclusion resolution tests
# ---------------------------------------------------------------------------

def test_extract_labeled_section():
    wikitext = (
        "preamble\n"
        "<section begin=F4/>{{#invoke:football box|main\n"
        "|date={{Start date|2026|6|21}}\n"
        "|team1={{#invoke:flag|fb-rt|TUN}}\n"
        "|score=0–0\n"
        "|team2={{#invoke:flag|fb|JPN}}\n"
        "}}<section end=F4/>\n"
        "postamble"
    )
    result = _extract_labeled_section(wikitext, "F4")
    assert "football box" in result
    assert "TUN" in result
    assert "JPN" in result
    assert "preamble" not in result
    assert "postamble" not in result


def test_extract_labeled_section_missing():
    assert _extract_labeled_section("no sections here", "F4") == ""


def test_extract_labeled_section_quoted_name():
    wikitext = (
        'pre\n<section begin="R32-1" />{{#invoke:football box|main\n'
        "|team1={{#invoke:flag|fb-rt|RSA}}\n"
        "|team2={{#invoke:flag|fb|CAN}}\n"
        '}}<section end="R32-1" />\npost'
    )
    result = _extract_labeled_section(wikitext, "R32-1")
    assert "RSA" in result and "CAN" in result
    assert "pre" not in result and "post" not in result


@patch("scraper.requests.get")
def test_resolve_transclusions_restores_match(mock_get):
    target_wikitext = (
        "<section begin=F4/>{{#invoke:football box|main\n"
        "|date={{Start date|2026|6|21}}\n"
        "|time=11:00 p.m. UTC-5\n"
        "|team1={{#invoke:flag|fb-rt|TUN}}\n"
        "|score=0–0\n"
        "|team2={{#invoke:flag|fb|JPN}}\n"
        "}}<section end=F4/>"
    )
    mock_resp = MagicMock()
    mock_resp.json.return_value = {
        "query": {
            "pages": [
                {
                    "title": "Tunisia v Japan (2026 FIFA World Cup)",
                    "revisions": [{"content": target_wikitext}],
                }
            ]
        }
    }
    mock_resp.raise_for_status = MagicMock()
    mock_get.return_value = mock_resp

    pages = {
        "2026 FIFA World Cup Group F": (
            "==Matchday 2==\n"
            "{{#lst:Tunisia v Japan (2026 FIFA World Cup)|F4}}\n"
        )
    }
    resolved = _resolve_transclusions(pages)
    assert "football box" in resolved["2026 FIFA World Cup Group F"]

    matches = parse_matches(
        resolved["2026 FIFA World Cup Group F"],
        stage_override="Group F",
    )
    teams = [(m["home_team"], m["away_team"]) for m in matches]
    assert ("Tunisia", "Japan") in teams


def test_resolve_transclusions_no_ops_without_lst():
    pages = {"Some Page": "{{#invoke:football box|main|...}}"}
    assert _resolve_transclusions(pages) is pages


@patch("scraper.requests.get", side_effect=Exception("network error"))
def test_resolve_transclusions_graceful_on_fetch_failure(mock_get):
    pages = {
        "Group F": "before\n{{#lst:Missing Page|F4}}\nafter"
    }
    result = _resolve_transclusions(pages)
    assert "{{#lst:Missing Page|F4}}" in result["Group F"]
