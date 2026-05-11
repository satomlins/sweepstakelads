"""Scoring regression tests — deterministic match dicts and expected outputs.

Covers: regular win, AET win, penalty shootout, group draw, third-place match,
compute_team_table (with draw), compute_person_table, compute_group_standings,
compute_third_place_table.
"""

import pandas as pd
import pytest

from scoring import (
    _apply_match,
    compute_group_standings,
    compute_person_table,
    compute_team_table,
    compute_third_place_table,
)


def _match(home, away, hs, aws, *, aet=False, pen_home=None, pen_away=None, stage="Group A"):
    return {
        "home_team": home,
        "away_team": away,
        "home_score": hs,
        "away_score": aws,
        "aet": aet,
        "pen_home": pen_home,
        "pen_away": pen_away,
        "stage": stage,
        "status": "finished" if hs is not None else "upcoming",
    }


# ---------------------------------------------------------------------------
# _apply_match unit tests
# ---------------------------------------------------------------------------

def test_regular_win():
    stats = {}
    _apply_match(stats, _match("A", "B", 2, 0))
    assert stats["A"] == {"W": 1, "D": 0, "L": 0, "GS": 2, "GA": 0, "PNT": 3}
    assert stats["B"] == {"W": 0, "D": 0, "L": 1, "GS": 0, "GA": 2, "PNT": 0}


def test_regular_win_away():
    stats = {}
    _apply_match(stats, _match("A", "B", 0, 1))
    assert stats["B"]["W"] == 1
    assert stats["B"]["PNT"] == 3
    assert stats["A"]["L"] == 1
    assert stats["A"]["PNT"] == 0


def test_aet_win():
    stats = {}
    _apply_match(stats, _match("A", "B", 2, 1, aet=True))
    assert stats["A"]["PNT"] == 3
    assert stats["B"]["PNT"] == 1  # consolation point for AET loss
    assert stats["A"]["GS"] == 2
    assert stats["B"]["GS"] == 1


def test_penalty_shootout():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1, aet=True, pen_home=4, pen_away=3))
    assert stats["A"]["W"] == 1
    assert stats["A"]["PNT"] == 2  # penalty winner gets 2
    assert stats["B"]["PNT"] == 1  # penalty loser gets 1
    # GD should be zero (scores were level)
    assert stats["A"]["GS"] == 1
    assert stats["A"]["GA"] == 1


def test_group_draw():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1))
    assert stats["A"]["D"] == 1
    assert stats["B"]["D"] == 1
    assert stats["A"]["PNT"] == 1
    assert stats["B"]["PNT"] == 1


def test_third_place_win_regular():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 0, stage="Match for third place"))
    assert stats["A"]["PNT"] == 1
    assert stats["B"]["PNT"] == 0


def test_third_place_win_aet():
    stats = {}
    _apply_match(stats, _match("A", "B", 2, 1, aet=True, stage="Match for third place"))
    assert stats["A"]["PNT"] == 1
    assert stats["B"]["PNT"] == 0  # no consolation point in 3rd-place match


def test_third_place_win_pens():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1, aet=True, pen_home=5, pen_away=4, stage="Match for third place"))
    assert stats["A"]["PNT"] == 1
    assert stats["B"]["PNT"] == 0


# ---------------------------------------------------------------------------
# compute_team_table
# ---------------------------------------------------------------------------

def test_team_table_no_matches():
    draw = pd.DataFrame({"Who": ["Alice", "Bob"], "Team": ["Mexico", "France"]})
    matches = [_match("Mexico", "France", None, None)]  # upcoming
    df = compute_team_table(draw, matches)
    assert set(df["Team"]) == {"Mexico", "France"}
    assert all(df["PNT"] == 0)
    assert all(df["Who"].isin(["Alice", "Bob"]))


def test_team_table_with_result():
    draw = pd.DataFrame({"Who": ["Alice", "Bob"], "Team": ["Mexico", "France"]})
    matches = [_match("Mexico", "France", 2, 1)]
    df = compute_team_table(draw, matches)
    mexico = df[df["Team"] == "Mexico"].iloc[0]
    france = df[df["Team"] == "France"].iloc[0]
    assert mexico["PNT"] == 3
    assert mexico["GS"] == 2
    assert france["PNT"] == 0
    assert france["L"] == 1


def test_team_table_empty_draw():
    draw = pd.DataFrame(columns=["Who", "Team"])
    matches = [_match("Mexico", "France", 1, 0)]
    df = compute_team_table(draw, matches)
    assert len(df) == 2
    assert all(df["Who"] == "TBC")


def test_team_table_in_out_flag():
    draw = pd.DataFrame({"Who": ["Alice", "Bob", "Carol"], "Team": ["Mexico", "France", "Brazil"]})
    matches = [
        _match("Mexico", "France", 2, 0),     # France eliminated (hypothetically)
        _match("Brazil", "Mexico", None, None),  # upcoming — both still "In"
    ]
    df = compute_team_table(draw, matches)
    mexico = df[df["Team"] == "Mexico"].iloc[0]
    brazil = df[df["Team"] == "Brazil"].iloc[0]
    assert mexico["In"] == "In"
    assert brazil["In"] == "In"


def test_team_table_excludes_placeholders():
    draw = pd.DataFrame({"Who": ["Alice"], "Team": ["Mexico"]})
    matches = [
        _match("Mexico", "France", 2, 0, stage="Group A"),
        _match("Winner of Match 1", "France", None, None, stage="Round of 16"),
    ]
    df = compute_team_table(draw, matches)
    # "Winner of Match 1" must not appear as a row — it's a placeholder
    assert "Winner of Match 1" not in df["Team"].values


# ---------------------------------------------------------------------------
# compute_person_table
# ---------------------------------------------------------------------------

def test_person_table_sums_by_owner():
    draw = pd.DataFrame({"Who": ["Alice", "Alice", "Bob"], "Team": ["Mexico", "France", "Brazil"]})
    matches = [
        _match("Mexico", "Brazil", 2, 1),
        _match("France", "Brazil", 1, 0),
    ]
    team_df = compute_team_table(draw, matches)
    person_df = compute_person_table(team_df)
    alice = person_df[person_df["Who"] == "Alice"].iloc[0]
    bob = person_df[person_df["Who"] == "Bob"].iloc[0]
    assert alice["PNT"] == 6  # Mexico 3 + France 3
    assert bob["PNT"] == 0


def test_person_table_empty():
    df = compute_person_table(pd.DataFrame())
    assert list(df.columns) == ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
    assert len(df) == 0


# ---------------------------------------------------------------------------
# compute_group_standings
# ---------------------------------------------------------------------------

def test_group_standings_keys():
    matches = [
        _match("Mexico", "France", 1, 0, stage="Group A"),
        _match("Brazil", "Germany", 2, 2, stage="Group B"),
    ]
    gs = compute_group_standings(matches)
    assert set(gs.keys()) == {"A", "B"}


def test_group_standings_all_teams_appear():
    matches = [
        _match("Mexico", "France", None, None, stage="Group A"),  # upcoming
        _match("Brazil", "Mexico", None, None, stage="Group A"),
    ]
    gs = compute_group_standings(matches)
    teams = set(gs["A"]["Team"].tolist())
    assert "Mexico" in teams
    assert "France" in teams
    assert "Brazil" in teams


def test_group_standings_sorted():
    matches = [
        _match("Mexico", "France", 2, 0, stage="Group A"),
        _match("Brazil", "Germany", 1, 1, stage="Group A"),
        _match("Mexico", "Brazil", 1, 0, stage="Group A"),
        _match("France", "Germany", 2, 1, stage="Group A"),
    ]
    gs = compute_group_standings(matches)
    df = gs["A"]
    # Points should be descending
    assert list(df["PNT"]) == sorted(df["PNT"].tolist(), reverse=True)


# ---------------------------------------------------------------------------
# compute_third_place_table
# ---------------------------------------------------------------------------

def test_third_place_table_collects_third_teams():
    # 3 groups each with 4 teams, one set of results to produce distinct standings
    gs = {
        "A": pd.DataFrame([
            {"Team": "Mexico", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 6, "GA": 0, "GD": 6, "PNT": 9},
            {"Team": "France", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 4, "GA": 2, "GD": 2, "PNT": 6},
            {"Team": "Brazil", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PNT": 3},
            {"Team": "Germany", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 6, "GD": -6, "PNT": 0},
        ]),
        "B": pd.DataFrame([
            {"Team": "Spain", "PL": 3, "W": 2, "D": 1, "L": 0, "GS": 5, "GA": 1, "GD": 4, "PNT": 7},
            {"Team": "Italy", "PL": 3, "W": 1, "D": 1, "L": 1, "GS": 3, "GA": 3, "GD": 0, "PNT": 4},
            {"Team": "Japan", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PNT": 3},
            {"Team": "Korea", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 2, "GD": -2, "PNT": 0},
        ]),
    }
    result = compute_third_place_table(gs)
    # Two groups → two third-place teams
    assert len(result) == 2
    assert set(result["Team"].tolist()) == {"Brazil", "Japan"}
    # Brazil (3 pts, GD -2) and Japan (3 pts, GD -2) — same stats so arbitrary order is fine


def test_third_place_table_sorted_by_points():
    gs = {
        "A": pd.DataFrame([
            {"Team": "A1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 6, "GA": 0, "GD": 6, "PNT": 9},
            {"Team": "A2", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PNT": 3},
            {"Team": "A3", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 1, "GA": 3, "GD": -2, "PNT": 3},
            {"Team": "A4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 6, "GD": -6, "PNT": 0},
        ]),
        "B": pd.DataFrame([
            {"Team": "B1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PNT": 9},
            {"Team": "B2", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 4, "GA": 2, "GD": 2, "PNT": 6},
            {"Team": "B3", "PL": 3, "W": 0, "D": 1, "L": 2, "GS": 1, "GA": 4, "GD": -3, "PNT": 1},
            {"Team": "B4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 8, "GD": -8, "PNT": 0},
        ]),
    }
    result = compute_third_place_table(gs)
    # A3 (3 pts) should rank above B3 (1 pt)
    assert result.iloc[0]["Team"] == "A3"
    assert result.iloc[1]["Team"] == "B3"


def test_third_place_table_empty_groups():
    result = compute_third_place_table({})
    assert len(result) == 0
