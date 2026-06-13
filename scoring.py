"""
Pure scoring functions — no I/O, no scraping.

Scoring rules:
  Regular time:      winner 3 pts, loser 0 pts; GD counted
  After extra time:  winner 3 pts, loser 1 pt;  GD counted
  Penalty shootout:  winner 2 pts, loser 1 pt;  GD NOT counted
  Draw (group only): both teams 1 pt; GD counted
  Third-place match: winner 1 pt, loser 0 pts;  GD counted (by any means of victory)

GS = goals scored (full-time incl. AET, excl. penalties)
GA = goals against (full-time incl. AET, excl. penalties)
GD = GS − GA (derived)
"""

import pandas as pd


def _is_third_place(stage: str) -> bool:
    return "third" in stage.lower()


def _apply_match(stats: dict[str, dict], match: dict) -> None:
    home = match["home_team"]
    away = match["away_team"]
    hs = match["home_score"]
    aws = match["away_score"]
    aet = match["aet"]
    pen_home = match["pen_home"]
    pen_away = match["pen_away"]
    third_place = _is_third_place(match.get("stage", ""))

    for team in (home, away):
        if team not in stats:
            stats[team] = {"W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "PTS": 0}

    # Goals always from the full-time (incl. AET) score
    stats[home]["GS"] += hs
    stats[home]["GA"] += aws
    stats[away]["GS"] += aws
    stats[away]["GA"] += hs

    penalties = pen_home is not None and pen_away is not None

    if penalties:
        # Penalty shootout: winner by pen score; match score was level at 120 mins.
        # GS/GA from the full-time score are already accumulated above — correct.
        # GD is naturally 0 (scores equal) so "GD not counted" needs no special handling.
        winner, loser = (home, away) if pen_home > pen_away else (away, home)
        stats[winner]["W"] += 1
        stats[loser]["L"] += 1
        if third_place:
            stats[winner]["PTS"] += 1
        else:
            stats[winner]["PTS"] += 2
            stats[loser]["PTS"] += 1

    elif hs != aws:
        winner, loser = (home, away) if hs > aws else (away, home)
        stats[winner]["W"] += 1
        stats[loser]["L"] += 1
        if third_place:
            stats[winner]["PTS"] += 1
        else:
            stats[winner]["PTS"] += 3
            stats[loser]["PTS"] += (1 if aet else 0)

    else:
        # Draw — only valid in group stage
        stats[home]["D"] += 1
        stats[away]["D"] += 1
        stats[home]["PTS"] += 1
        stats[away]["PTS"] += 1


def compute_team_table(draw: pd.DataFrame, matches: list[dict]) -> pd.DataFrame:
    """
    Build the sweepstake team table from the draw and all match results.

    draw: DataFrame with columns [Who, Team]. May be empty (pre-draw state).
    matches: list of match dicts from scraper.

    Returns DataFrame: Team, Who, PL, W, D, L, GS, GA, GD, PTS, In
    """
    stats: dict[str, dict] = {}

    # Seed from draw so all drawn teams appear even before matches start
    if not draw.empty:
        for team in draw["Team"]:
            stats[team] = {"W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "PTS": 0}

    # Apply finished matches
    for m in matches:
        if m["status"] != "finished" or m["home_score"] is None:
            continue
        _apply_match(stats, m)

    # Seed from group-stage matches — every real team appears there and placeholders don't
    for m in matches:
        if not m.get("stage", "").startswith("Group "):
            continue
        for team in (m["home_team"], m["away_team"]):
            if team not in stats:
                stats[team] = {"W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "PTS": 0}

    rows = []
    for team, s in stats.items():
        rows.append(
            {
                "Team": team,
                "PL": s["W"] + s["D"] + s["L"],
                "W": s["W"],
                "D": s["D"],
                "L": s["L"],
                "GS": s["GS"],
                "GA": s["GA"],
                "GD": s["GS"] - s["GA"],
                "PTS": s["PTS"],
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        df = pd.DataFrame(
            columns=["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS", "In"]
        )
        return df

    # Merge draw ownership
    if not draw.empty:
        df = df.merge(draw[["Team", "Who"]], on="Team", how="left")
        df["Who"] = df["Who"].fillna("")
    else:
        df["Who"] = ""

    # In/Out: "In" if the team has any non-finished match remaining
    in_teams: set[str] = set()
    for m in matches:
        if m["status"] != "finished":
            in_teams.add(m["home_team"])
            in_teams.add(m["away_team"])
    df["In"] = df["Team"].apply(lambda t: "In" if t in in_teams else "Out")

    return df


def compute_group_standings(matches: list[dict]) -> dict[str, pd.DataFrame]:
    """
    Compute group-stage-only standings per group (for the 12 group mini-tables).

    Returns dict: group_letter → DataFrame [Team, PL, W, D, L, GS, GA, GD, PTS],
    sorted PTS→GD→GS desc.
    """
    group_stats: dict[str, dict[str, dict]] = {}

    for m in matches:
        stage = m.get("stage", "")
        if not stage.startswith("Group "):
            continue
        group = stage.split("Group ")[-1].strip()
        if group not in group_stats:
            group_stats[group] = {}

        # Register both teams even for unplayed matches
        for team in (m["home_team"], m["away_team"]):
            if team not in group_stats[group]:
                group_stats[group][team] = {
                    "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "PTS": 0
                }

        if m["status"] != "finished" or m["home_score"] is None:
            continue

        _apply_match(group_stats[group], m)

    result: dict[str, pd.DataFrame] = {}
    for group, teams in sorted(group_stats.items()):
        rows = []
        for team, s in teams.items():
            rows.append(
                {
                    "Team": team,
                    "PL": s["W"] + s["D"] + s["L"],
                    "W": s["W"],
                    "D": s["D"],
                    "L": s["L"],
                    "GS": s["GS"],
                    "GA": s["GA"],
                    "GD": s["GS"] - s["GA"],
                    "PTS": s["PTS"],
                }
            )
        df = (
            pd.DataFrame(rows)
            .sort_values(["PTS", "GD", "GS"], ascending=False)
            .reset_index(drop=True)
        )
        result[group] = df

    return result


def compute_third_place_table(group_standings: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Collect 3rd-placed teams from all groups, sorted PTS→GD→GS desc.
    Top 8 of the 12 third-place teams advance to the knockout stage.
    """
    rows = []
    for g, df in sorted(group_standings.items()):
        if len(df) >= 3:
            row = df.iloc[2].to_dict()
            row["Group"] = g
            rows.append(row)
    if not rows:
        return pd.DataFrame(
            columns=["Group", "Team", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
        )
    result = (
        pd.DataFrame(rows)
        .sort_values(["PTS", "GD", "GS"], ascending=False)
        .reset_index(drop=True)
    )
    return result[["Group", "Team", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]]


def compute_person_table(team_table: pd.DataFrame) -> pd.DataFrame:
    """
    Aggregate team_table by owner to produce the person leaderboard.

    Returns DataFrame: Who, PL, W, D, L, GS, GA, GD, PTS, sorted PTS→GD→GS desc.
    """
    if team_table.empty or "Who" not in team_table.columns:
        return pd.DataFrame(
            columns=["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
        )

    sum_cols = ["PL", "W", "D", "L", "GS", "GA", "PTS"]
    agg = (
        team_table[["Who"] + sum_cols]
        .groupby("Who")
        .sum()
        .reset_index()
    )
    agg = agg[agg["Who"] != ""]
    agg["GD"] = agg["GS"] - agg["GA"]
    agg = (
        agg[["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]]
        .sort_values(["PTS", "GD", "GS"], ascending=False)
        .reset_index(drop=True)
    )
    return agg
