"""Scoring regression tests — deterministic match dicts and expected outputs.

Covers: regular win, AET win, penalty shootout, group draw, third-place match,
compute_team_table (with draw), compute_person_table, compute_group_standings,
compute_third_place_table.
"""

import pandas as pd
import pytest

from scoring import (
    _apply_match,
    _team_out_status,
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
    assert stats["A"] == {"W": 1, "D": 0, "L": 0, "GS": 2, "GA": 0, "PTS": 3}
    assert stats["B"] == {"W": 0, "D": 0, "L": 1, "GS": 0, "GA": 2, "PTS": 0}


def test_regular_win_away():
    stats = {}
    _apply_match(stats, _match("A", "B", 0, 1))
    assert stats["B"]["W"] == 1
    assert stats["B"]["PTS"] == 3
    assert stats["A"]["L"] == 1
    assert stats["A"]["PTS"] == 0


def test_aet_win():
    stats = {}
    _apply_match(stats, _match("A", "B", 2, 1, aet=True))
    assert stats["A"]["PTS"] == 3
    assert stats["B"]["PTS"] == 1  # consolation point for AET loss
    assert stats["A"]["GS"] == 2
    assert stats["B"]["GS"] == 1


def test_penalty_shootout():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1, aet=True, pen_home=4, pen_away=3))
    assert stats["A"]["W"] == 1
    assert stats["A"]["PTS"] == 2  # penalty winner gets 2
    assert stats["B"]["PTS"] == 1  # penalty loser gets 1
    # GD should be zero (scores were level)
    assert stats["A"]["GS"] == 1
    assert stats["A"]["GA"] == 1


def test_group_draw():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1))
    assert stats["A"]["D"] == 1
    assert stats["B"]["D"] == 1
    assert stats["A"]["PTS"] == 1
    assert stats["B"]["PTS"] == 1


def test_third_place_win_regular():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 0, stage="Match for third place"))
    assert stats["A"]["PTS"] == 1
    assert stats["B"]["PTS"] == 0


def test_third_place_win_aet():
    stats = {}
    _apply_match(stats, _match("A", "B", 2, 1, aet=True, stage="Match for third place"))
    assert stats["A"]["PTS"] == 1
    assert stats["B"]["PTS"] == 0  # no consolation point in 3rd-place match


def test_third_place_win_pens():
    stats = {}
    _apply_match(stats, _match("A", "B", 1, 1, aet=True, pen_home=5, pen_away=4, stage="Match for third place"))
    assert stats["A"]["PTS"] == 1
    assert stats["B"]["PTS"] == 0


# ---------------------------------------------------------------------------
# compute_team_table
# ---------------------------------------------------------------------------

def test_team_table_no_matches():
    draw = pd.DataFrame({"Who": ["Alice", "Bob"], "Team": ["Mexico", "France"]})
    matches = [_match("Mexico", "France", None, None)]  # upcoming
    df = compute_team_table(draw, matches)
    assert set(df["Team"]) == {"Mexico", "France"}
    assert all(df["PTS"] == 0)
    assert all(df["Who"].isin(["Alice", "Bob"]))


def test_team_table_with_result():
    draw = pd.DataFrame({"Who": ["Alice", "Bob"], "Team": ["Mexico", "France"]})
    matches = [_match("Mexico", "France", 2, 1)]
    df = compute_team_table(draw, matches)
    mexico = df[df["Team"] == "Mexico"].iloc[0]
    france = df[df["Team"] == "France"].iloc[0]
    assert mexico["PTS"] == 3
    assert mexico["GS"] == 2
    assert france["PTS"] == 0
    assert france["L"] == 1


def test_team_table_empty_draw():
    draw = pd.DataFrame(columns=["Who", "Team"])
    matches = [_match("Mexico", "France", 1, 0)]
    df = compute_team_table(draw, matches)
    assert len(df) == 2
    assert all(df["Who"] == "")


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
    assert "" not in person_df["Who"].values
    alice = person_df[person_df["Who"] == "Alice"].iloc[0]
    bob = person_df[person_df["Who"] == "Bob"].iloc[0]
    assert alice["PTS"] == 6  # Mexico 3 + France 3
    assert bob["PTS"] == 0


def test_person_table_empty():
    df = compute_person_table(pd.DataFrame())
    assert list(df.columns) == ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
    assert len(df) == 0


def test_person_table_excludes_unowned():
    draw = pd.DataFrame({"Who": ["Alice", "Bob"], "Team": ["Mexico", "France"]})
    matches = [
        _match("Mexico", "France", 2, 1),
        _match("Brazil", "Germany", 1, 0),  # unowned teams
    ]
    team_df = compute_team_table(draw, matches)
    person_df = compute_person_table(team_df)
    assert len(person_df) == 2
    assert set(person_df["Who"]) == {"Alice", "Bob"}


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
    assert list(df["PTS"]) == sorted(df["PTS"].tolist(), reverse=True)


# ---------------------------------------------------------------------------
# compute_third_place_table
# ---------------------------------------------------------------------------

def test_third_place_table_collects_third_teams():
    # 3 groups each with 4 teams, one set of results to produce distinct standings
    gs = {
        "A": pd.DataFrame([
            {"Team": "Mexico", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 6, "GA": 0, "GD": 6, "PTS": 9},
            {"Team": "France", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 4, "GA": 2, "GD": 2, "PTS": 6},
            {"Team": "Brazil", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PTS": 3},
            {"Team": "Germany", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 6, "GD": -6, "PTS": 0},
        ]),
        "B": pd.DataFrame([
            {"Team": "Spain", "PL": 3, "W": 2, "D": 1, "L": 0, "GS": 5, "GA": 1, "GD": 4, "PTS": 7},
            {"Team": "Italy", "PL": 3, "W": 1, "D": 1, "L": 1, "GS": 3, "GA": 3, "GD": 0, "PTS": 4},
            {"Team": "Japan", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PTS": 3},
            {"Team": "Korea", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 2, "GD": -2, "PTS": 0},
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
            {"Team": "A1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 6, "GA": 0, "GD": 6, "PTS": 9},
            {"Team": "A2", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 4, "GD": -2, "PTS": 3},
            {"Team": "A3", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 1, "GA": 3, "GD": -2, "PTS": 3},
            {"Team": "A4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 6, "GD": -6, "PTS": 0},
        ]),
        "B": pd.DataFrame([
            {"Team": "B1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PTS": 9},
            {"Team": "B2", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 4, "GA": 2, "GD": 2, "PTS": 6},
            {"Team": "B3", "PL": 3, "W": 0, "D": 1, "L": 2, "GS": 1, "GA": 4, "GD": -3, "PTS": 1},
            {"Team": "B4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 8, "GD": -8, "PTS": 0},
        ]),
    }
    result = compute_third_place_table(gs)
    # A3 (3 pts) should rank above B3 (1 pt)
    assert result.iloc[0]["Team"] == "A3"
    assert result.iloc[1]["Team"] == "B3"


def test_third_place_table_empty_groups():
    result = compute_third_place_table({})
    assert len(result) == 0


# ---------------------------------------------------------------------------
# _team_out_status — mathematical elimination
# ---------------------------------------------------------------------------

def _complete_group(t1_pts=9, t2_pts=6, t3=("T3", 3, 1, 2, 1), t4_pts=0,
                   t1="T1", t2="T2", t4="T4"):
    """Helper: a 4-team completed group. t3 is (name, PTS, GD, GS, W)."""
    t3_name, t3_p, t3_gd, t3_gs, t3_w = t3
    return pd.DataFrame([
        {"Team": t1, "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PTS": t1_pts},
        {"Team": t2, "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 6, "GA": 2, "GD": 4, "PTS": t2_pts},
        {"Team": t3_name, "PL": 3, "W": t3_w, "D": 0, "L": 3 - t3_w,
         "GS": t3_gs, "GA": t3_gs - t3_gd, "GD": t3_gd, "PTS": t3_p},
        {"Team": t4, "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 9, "GD": -9, "PTS": t4_pts},
    ])


def test_team_out_topped_completed_group_is_in():
    gs = {"A": _complete_group()}
    assert _team_out_status("T1", gs, []) == "In"


def test_team_out_fourth_in_completed_group_is_out():
    gs = {"A": _complete_group()}
    assert _team_out_status("T4", gs, []) == "Out"


def test_team_out_third_completed_group_but_other_groups_pending_is_in():
    # A is complete; B has only 1 played match so its 3rd-placer is undetermined.
    # Even one free variable plus 0 above_or_tied → worst-case rank well below 9.
    gs = {
        "A": _complete_group(),
        "B": pd.DataFrame([
            {"Team": "U1", "PL": 1, "W": 1, "D": 0, "L": 0, "GS": 1, "GA": 0, "GD": 1, "PTS": 3},
            {"Team": "U2", "PL": 1, "W": 0, "D": 0, "L": 1, "GS": 0, "GA": 1, "GD": -1, "PTS": 0},
            {"Team": "U3", "PL": 0, "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "GD": 0, "PTS": 0},
            {"Team": "U4", "PL": 0, "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "GD": 0, "PTS": 0},
        ]),
    }
    assert _team_out_status("T3", gs, []) == "In"


def test_team_out_third_in_completed_group_cannot_qualify_is_out():
    # T3 is 3rd in Group A with 0 pts. All 11 other groups are complete with
    # 3rd-placers that beat T3 on (PTS, GD, GS). worst_case_rank = 12 → Out.
    a_third = ("T3", 0, -3, 0, 0)  # 0 PTS, -3 GD, 0 GS
    groups = {"A": _complete_group(t3=a_third)}
    for letter in "BCDEFGHIJKL":
        # Each group's 3rd-placer at 3 PTS, GD 0, GS 2 — strictly above T3.
        groups[letter] = pd.DataFrame([
            {"Team": f"{letter}1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PTS": 9},
            {"Team": f"{letter}2", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 6, "GA": 2, "GD": 4, "PTS": 6},
            {"Team": f"{letter}3", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 2, "GD": 0, "PTS": 3},
            {"Team": f"{letter}4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 9, "GD": -9, "PTS": 0},
        ])
    assert _team_out_status("T3", groups, []) == "Out"


def test_team_out_third_just_misses_top_eight_when_all_complete_is_out():
    # T3 has 1 PTS; 8 other 3rd-placers strictly above (3 PTS), 3 below (0 PTS).
    # All groups complete → no free variables. above_or_tied = 8 → rank = 9 → Out.
    groups = {"A": _complete_group(t3=("T3", 1, -2, 0, 0))}
    for letter in "BCDEFGHI":  # 8 groups with stronger 3rd-placers
        groups[letter] = pd.DataFrame([
            {"Team": f"{letter}1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PTS": 9},
            {"Team": f"{letter}2", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 6, "GA": 2, "GD": 4, "PTS": 6},
            {"Team": f"{letter}3", "PL": 3, "W": 1, "D": 0, "L": 2, "GS": 2, "GA": 2, "GD": 0, "PTS": 3},
            {"Team": f"{letter}4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 9, "GD": -9, "PTS": 0},
        ])
    for letter in "JKL":  # 3 groups with weaker 3rd-placers
        groups[letter] = pd.DataFrame([
            {"Team": f"{letter}1", "PL": 3, "W": 3, "D": 0, "L": 0, "GS": 9, "GA": 0, "GD": 9, "PTS": 9},
            {"Team": f"{letter}2", "PL": 3, "W": 2, "D": 0, "L": 1, "GS": 6, "GA": 2, "GD": 4, "PTS": 6},
            {"Team": f"{letter}3", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 4, "GD": -4, "PTS": 0},
            {"Team": f"{letter}4", "PL": 3, "W": 0, "D": 0, "L": 3, "GS": 0, "GA": 9, "GD": -9, "PTS": 0},
        ])
    assert _team_out_status("T3", groups, []) == "Out"


def test_team_out_knockout_loser_is_out():
    gs = {"A": _complete_group()}
    matches = [
        _match("T1", "X", 0, 1, stage="Round of 32"),  # T1 lost R32
    ]
    assert _team_out_status("T1", gs, matches) == "Out"


def test_team_out_knockout_winner_stays_in():
    gs = {"A": _complete_group()}
    matches = [
        _match("T1", "X", 2, 0, stage="Round of 32"),  # T1 won R32
    ]
    assert _team_out_status("T1", gs, matches) == "In"


def test_team_out_penalty_shootout_loser_is_out():
    gs = {"A": _complete_group()}
    matches = [
        _match("T1", "X", 1, 1, aet=True, pen_home=3, pen_away=4, stage="Round of 16"),
    ]
    assert _team_out_status("T1", gs, matches) == "Out"


def test_compute_team_table_in_uses_elimination():
    """End-to-end: 4th in completed group → Out; 1st → In (no remaining real-name fixtures)."""
    draw = pd.DataFrame({"Who": ["A", "B", "C", "D"], "Team": ["T1", "T2", "T3", "T4"]})
    matches = [
        _match("T1", "T2", 1, 0, stage="Group A"),
        _match("T1", "T3", 1, 0, stage="Group A"),
        _match("T1", "T4", 1, 0, stage="Group A"),
        _match("T2", "T3", 1, 0, stage="Group A"),
        _match("T2", "T4", 1, 0, stage="Group A"),
        _match("T3", "T4", 1, 0, stage="Group A"),
        # No upcoming real-name fixture; next round uses placeholders.
        _match("Winner of Match 1", "X", None, None, stage="Round of 32"),
    ]
    df = compute_team_table(draw, matches)
    t1 = df[df["Team"] == "T1"].iloc[0]
    t4 = df[df["Team"] == "T4"].iloc[0]
    # T1 topped a completed group — should stay In despite no real-name fixture.
    assert t1["In"] == "In"
    # T4 finished bottom of completed group → Out.
    assert t4["In"] == "Out"


# ---------------------------------------------------------------------------
# compute_group_standings — FIFA head-to-head tiebreakers
# ---------------------------------------------------------------------------

def test_group_h2h_two_way_tie_broken_by_h2h():
    # A and B both 4 pts overall (1W 1D 1L). A beat B head-to-head → A first.
    matches = [
        _match("A", "B", 1, 0, stage="Group A"),  # A wins H2H
        _match("A", "C", 1, 1, stage="Group A"),  # A draws C
        _match("B", "C", 3, 0, stage="Group A"),  # B beats C
        # All three played 2; add 3rd matches so PTS counts make A=B=4
        # Currently: A=4 (W+D), B=3 (W+L), C=1 (D+L). Need to equalise.
        # Add vs D so each plays 3.
        _match("A", "D", 0, 0, stage="Group A"),  # A +1 → 5
        _match("B", "D", 1, 0, stage="Group A"),  # B +3 → 6 — too many
    ]
    # Re-design simply: just 2 teams in subset tied, ignore equality and assert H2H wins.
    matches = [
        _match("A", "B", 2, 1, stage="Group A"),  # A beats B
        _match("A", "C", 0, 1, stage="Group A"),  # A loses to C
        _match("B", "C", 3, 0, stage="Group A"),  # B beats C
        # A: 1W 1L = 3pts, GD = 2-2 = 0, GS = 2
        # B: 1W 1L = 3pts, GD = 4-2 = 2, GS = 4
        # C: 1W 1L = 3pts, GD = 1-3 = -2, GS = 1
        # All tied at 3 pts. H2H mini = overall (cyclic). H2H GD: B=2, A=0, C=-2.
    ]
    gs = compute_group_standings(matches)
    order = gs["A"]["Team"].tolist()
    assert order == ["B", "A", "C"]


def test_group_h2h_three_way_tie_broken_by_h2h_mini_table():
    # Cyclic 3-way tie; asymmetric scores → H2H GD separates all three.
    matches = [
        _match("A", "B", 2, 0, stage="Group B"),  # A beats B
        _match("B", "C", 1, 0, stage="Group B"),  # B beats C
        _match("C", "A", 1, 0, stage="Group B"),  # C beats A
        # Each: 1W 1L = 3 pts. H2H GD: A=1, B=-1, C=0.
    ]
    gs = compute_group_standings(matches)
    order = gs["B"]["Team"].tolist()
    assert order == ["A", "C", "B"]


def test_group_h2h_separates_one_then_others_need_overall_gd():
    # 3-way overall tie at 4 pts each. Within the tied set, A beat B (1-0)
    # and B drew C (1-1); A vs C unplayed. H2H separates A. Re-applying Step 1
    # on {B, C} (their only match was the draw) leaves them tied → fall to
    # overall GD. C's overall GD beats B's.
    matches = [
        _match("A", "B", 1, 0, stage="Group C"),  # A wins H2H over B
        _match("B", "C", 1, 1, stage="Group C"),  # B and C draw H2H
        # A vs C upcoming (None, None)
        _match("A", "C", None, None, stage="Group C"),
        _match("A", "D", 0, 0, stage="Group C"),  # A +1
        _match("B", "D", 1, 0, stage="Group C"),  # B +3
        _match("C", "D", 2, 0, stage="Group C"),  # C +3
    ]
    # Final overall:
    # A: W vs B, draw vs D, vs C upcoming → 3+1 = 4 pts. GS=2 (1+0+1+0), GA=1 (0+0+1+0); actually:
    #   A-B 1-0 → A GS+=1 GA+=0; A-D 0-0 → GS+=0 GA+=0. Total A: GS=1, GA=0, GD=+1.
    # B: lost vs A (0-1), drew vs C (1-1), beat D (1-0) → 0+1+3=4 pts. GS=0+1+1=2, GA=1+1+0=2, GD=0.
    # C: drew vs B (1-1), beat D (2-0) → 1+3=4 pts. GS=1+2=3, GA=1+0=1, GD=+2.
    # All three at 4 pts. H2H: A=3 (1W), B=1 (1L 1D), C=1 (1D).
    # A separates; {B,C} re-applied: their only match is draw → still tied; overall GD: C>B.
    gs = compute_group_standings(matches)
    order = gs["C"]["Team"].tolist()
    # A first, then C (overall GD 2 > B's 0), then B, then D (1 pt).
    assert order[:3] == ["A", "C", "B"]
    assert order[3] == "D"


def test_group_h2h_unresolved_falls_to_overall_gd():
    # A and B tied at 4 pts; H2H drew. Overall GD differentiates.
    matches = [
        _match("A", "B", 1, 1, stage="Group D"),  # H2H draw
        _match("A", "C", 5, 0, stage="Group D"),  # A overall GD large
        _match("B", "C", 2, 0, stage="Group D"),  # B overall GD smaller
        # A: 4 pts, GS=6, GA=1, GD=+5
        # B: 4 pts, GS=3, GA=1, GD=+2
        # C: 0 pts
    ]
    gs = compute_group_standings(matches)
    order = gs["D"]["Team"].tolist()
    assert order == ["A", "B", "C"]


def test_group_h2h_unresolved_falls_to_overall_gs():
    # A and B tied at 4 pts; H2H draw; overall GD also tied; overall GS differs.
    matches = [
        _match("A", "B", 2, 2, stage="Group E"),  # H2H draw, both contribute equally
        _match("A", "C", 1, 0, stage="Group E"),  # A overall: GS=3, GA=2, GD=+1
        _match("B", "C", 2, 1, stage="Group E"),  # B overall: GS=4, GA=3, GD=+1
        # A and B both 4 pts, GD +1, but B has GS=4 > A's GS=3.
    ]
    gs = compute_group_standings(matches)
    order = gs["E"]["Team"].tolist()
    assert order[:2] == ["B", "A"]
