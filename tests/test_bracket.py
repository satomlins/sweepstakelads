"""Tests for bracket.resolve_placeholders and its helpers."""

import pandas as pd
import pytest

from bracket import (
    parse_bracket_section,
    _derive_feeder_match_numbers,
    resolve_placeholders,
)


def _group_df(teams_in_order):
    """Build a finished-group DataFrame (all PL=3) with teams in the given order."""
    rows = [
        {"Team": t, "PL": 3, "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "GD": 0, "PTS": 0}
        for t in teams_in_order
    ]
    return pd.DataFrame(rows)


def _knockout_wikitext(r32_lines, r16_lines, qf_lines="", sf_lines="", final_line="", third_line=""):
    """Assemble a minimal Bracket section containing the supplied per-round lines."""
    return (
        '<section begin="Bracket" />{{#invoke:RoundN|N32\n'
        "<!--Round of 32-->\n"
        + r32_lines
        + "\n<!--Round of 16-->\n"
        + r16_lines
        + "\n<!--Quarterfinals-->\n"
        + qf_lines
        + "\n<!--Semifinals-->\n"
        + sf_lines
        + "\n<!--Final-->\n"
        + final_line
        + "\n<!--Match for third place-->\n"
        + third_line
        + "\n}}<section end=\"Bracket\" />"
    )


def test_parse_bracket_section_decodes_codes_and_scores():
    wt = _knockout_wikitext(
        r32_lines=(
            "|June 28 – Inglewood|{{#invoke:flag|fb|RSA}}|0|{{#invoke:flag|fb|CAN}}|1\n"
            "|June 29 – Foxborough|{{#invoke:flag|fb|GER}}||{{#invoke:flag|fb|PAR}}|"
        ),
        r16_lines="",
    )
    entries = parse_bracket_section(wt)
    r32 = [e for e in entries if e["round"] == "Round of 32"]
    assert len(r32) == 2
    assert r32[0]["team1"] == "South Africa"
    assert r32[0]["team2"] == "Canada"
    assert r32[0]["score1"] == 0 and r32[0]["score2"] == 1
    assert r32[1]["team1"] == "Germany"
    assert r32[1]["score1"] is None  # unplayed


def test_derive_feeder_match_numbers_from_references():
    wt = _knockout_wikitext(
        r32_lines=(
            "|d|{{#invoke:flag|fb|GER}}||{{#invoke:flag|fb|PAR}}|\n"  # pos 1
            "|d|{{#invoke:flag|fb|FRA}}||{{#invoke:flag|fb|SWE}}|"     # pos 2
        ),
        r16_lines=(
            "|d|Winner Match 74||Winner Match 77|"  # pos 1 → feeds R32 pos 1 & 2
        ),
    )
    entries = parse_bracket_section(wt)
    nums = _derive_feeder_match_numbers(entries)
    assert nums[("Round of 32", 1)] == 74
    assert nums[("Round of 32", 2)] == 77


def test_resolve_group_placeholders_only_when_group_finished():
    matches = [
        {"home_team": "Winner Group A", "away_team": "Runner-up Group B", "stage": "Round of 32",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
    ]
    gs_partial = {"A": _group_df(["Argentina", "Brazil"])}
    gs_partial["A"].loc[0, "PL"] = 2  # not finished
    # Group B missing entirely
    resolved = resolve_placeholders(matches, gs_partial, "")
    # Nothing substituted (Group A unfinished, Group B missing)
    assert resolved[0]["home_team"] == "Winner Group A"
    assert resolved[0]["away_team"] == "Runner-up Group B"

    gs_full = {
        "A": _group_df(["Argentina", "Brazil", "Chile", "Denmark"]),
        "B": _group_df(["England", "France", "Germany", "Hungary"]),
    }
    resolved = resolve_placeholders(matches, gs_full, "")
    assert resolved[0]["home_team"] == "Argentina"
    assert resolved[0]["away_team"] == "France"


def test_resolve_cascades_winners_through_bracket():
    # Two R32 results known; R16 references them; chain to QF.
    wt = _knockout_wikitext(
        r32_lines=(
            # pos 1 = GER 2-1 PAR (Match 74, derived from R16 ref)
            "|d|{{#invoke:flag|fb|GER}}|2|{{#invoke:flag|fb|PAR}}|1\n"
            # pos 2 = FRA 0-1 SWE (Match 77)
            "|d|{{#invoke:flag|fb|FRA}}|0|{{#invoke:flag|fb|SWE}}|1"
        ),
        r16_lines=(
            "|d|Winner Match 74||Winner Match 77|"  # pos 1: GER (winner) vs SWE (winner)
        ),
        qf_lines=(
            "|d|Winner Match 89||Winner Match 90|"  # pos 1: refers to R16 pos 1 & 2 → Match 89/90
        ),
    )
    matches = [
        {"home_team": "Winner Match 74", "away_team": "Winner Match 77", "stage": "Round of 16",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
        {"home_team": "Winner Match 89", "away_team": "Winner Match 90", "stage": "Quarterfinals",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
    ]
    resolved = resolve_placeholders(matches, {}, wt)
    # R16 should be Germany vs Sweden
    assert resolved[0]["home_team"] == "Germany"
    assert resolved[0]["away_team"] == "Sweden"
    # QF still references Match 89/90 because no R16 result is filled in bracket
    assert "Winner Match" in resolved[1]["home_team"]


def test_resolve_loser_match_for_third_place():
    # Both SFs finished; Match for third place pairs the losers.
    wt = _knockout_wikitext(
        r32_lines="",
        r16_lines="",
        qf_lines="",
        sf_lines=(
            "|d|{{#invoke:flag|fb|ARG}}|3|{{#invoke:flag|fb|BRA}}|1\n"   # SF pos 1
            "|d|{{#invoke:flag|fb|FRA}}|0|{{#invoke:flag|fb|GER}}|2"     # SF pos 2
        ),
        final_line="|d|Winner Match 101||Winner Match 102|",
        third_line="|d|Loser Match 101||Loser Match 102|",
    )
    matches = [
        {"home_team": "Loser Match 101", "away_team": "Loser Match 102",
         "stage": "Match for third place",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
        {"home_team": "Winner Match 101", "away_team": "Winner Match 102", "stage": "Final",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
    ]
    resolved = resolve_placeholders(matches, {}, wt)
    assert {resolved[0]["home_team"], resolved[0]["away_team"]} == {"Brazil", "France"}
    assert {resolved[1]["home_team"], resolved[1]["away_team"]} == {"Argentina", "Germany"}


def test_resolve_leaves_third_placer_slots_alone():
    matches = [
        {"home_team": "Winner Group E", "away_team": "3rd Group A/B/C/D/F",
         "stage": "Round of 32",
         "home_score": None, "away_score": None, "date": None, "datetime_utc": None,
         "status": "upcoming", "aet": False, "pen_home": None, "pen_away": None, "time": ""},
    ]
    gs = {"E": _group_df(["Spain", "Portugal", "Italy", "Greece"])}
    resolved = resolve_placeholders(matches, gs, "")
    assert resolved[0]["home_team"] == "Spain"
    # Third-placer slot left untouched on purpose
    assert resolved[0]["away_team"] == "3rd Group A/B/C/D/F"
