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


def _match_loser(match: dict) -> str | None:
    """Return the losing team for a finished decisive match, else None."""
    if match.get("status") != "finished" or match.get("home_score") is None:
        return None
    hs = match["home_score"]
    aws = match["away_score"]
    pen_home = match.get("pen_home")
    pen_away = match.get("pen_away")
    if pen_home is not None and pen_away is not None:
        return match["away_team"] if pen_home > pen_away else match["home_team"]
    if hs != aws:
        return match["away_team"] if hs > aws else match["home_team"]
    return None


def _rank_overall(teams: list[str], overall_stats: dict[str, dict]) -> list[str]:
    """FIFA Step 2: overall GD then overall GS (descending)."""
    def key(t):
        s = overall_stats[t]
        return (-(s["GS"] - s["GA"]), -s["GS"])
    return sorted(teams, key=key)


def _rank_h2h(
    tied_teams: list[str],
    all_matches: list[dict],
    overall_stats: dict[str, dict],
) -> list[str]:
    """FIFA Step 1 on a points-tied subset: H2H PTS → H2H GD → H2H GS.

    H2H stats are computed from finished matches where both teams are in the
    tied subset. If Step 1 separates some but not all, it is re-applied on the
    still-tied subset (with H2H stats recomputed on the smaller subset). If a
    sub-bucket cannot be separated, fall to Step 2 (overall GD, overall GS).
    """
    if len(tied_teams) <= 1:
        return list(tied_teams)

    tied_set = set(tied_teams)
    h2h_stats: dict[str, dict] = {
        t: {"W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "PTS": 0} for t in tied_teams
    }
    for m in all_matches:
        if m.get("status") != "finished" or m.get("home_score") is None:
            continue
        if m["home_team"] in tied_set and m["away_team"] in tied_set:
            _apply_match(h2h_stats, m)

    def h2h_key(t):
        s = h2h_stats[t]
        return (-s["PTS"], -(s["GS"] - s["GA"]), -s["GS"])

    sorted_teams = sorted(tied_teams, key=h2h_key)

    result: list[str] = []
    i = 0
    while i < len(sorted_teams):
        j = i
        while j < len(sorted_teams) and h2h_key(sorted_teams[j]) == h2h_key(sorted_teams[i]):
            j += 1
        subset = sorted_teams[i:j]
        if len(subset) == 1:
            result.extend(subset)
        elif len(subset) == len(tied_teams):
            # No separation at all → fall to Step 2
            result.extend(_rank_overall(subset, overall_stats))
        else:
            # Step 1 partially separated; re-apply on the still-tied subset
            result.extend(_rank_h2h(subset, all_matches, overall_stats))
        i = j
    return result


def _rank_group(
    team_stats: dict[str, dict], group_matches: list[dict]
) -> list[str]:
    """Rank a group's teams by FIFA criteria: overall PTS → H2H → overall GD/GS."""
    teams = list(team_stats.keys())
    by_pts = sorted(teams, key=lambda t: -team_stats[t]["PTS"])
    result: list[str] = []
    i = 0
    while i < len(by_pts):
        j = i
        while j < len(by_pts) and team_stats[by_pts[j]]["PTS"] == team_stats[by_pts[i]]["PTS"]:
            j += 1
        bucket = by_pts[i:j]
        if len(bucket) == 1:
            result.extend(bucket)
        else:
            result.extend(_rank_h2h(bucket, group_matches, team_stats))
        i = j
    return result


def _team_out_status(
    team: str,
    group_standings: dict[str, pd.DataFrame],
    matches: list[dict],
) -> str:
    """Mathematical elimination test. Returns 'Out' or 'In'.

    A team is Out only if:
      1. 4th in a fully-completed group (every team played 3); or
      2. 3rd in a fully-completed group AND mathematically cannot finish in
         the top 8 of all 12 third-placers (treating any not-yet-determined
         3rd-place slot as worst-case-for-this-team, i.e. above them); or
      3. Named loser of any finished knockout-stage match (R32 onwards,
         which here is any non-group stage).
    """
    team_group = None
    for g, gdf in group_standings.items():
        if team in gdf["Team"].values:
            team_group = g
            break
    if team_group is None:
        return "In"

    gdf = group_standings[team_group]
    group_complete = len(gdf) >= 4 and bool((gdf["PL"] == 3).all())

    pos_idx = gdf.index[gdf["Team"] == team].tolist()
    if not pos_idx:
        return "In"
    position = pos_idx[0] + 1  # 1-indexed

    # Rule 1: 4th in completed group
    if group_complete and position == 4:
        return "Out"

    # Rule 2: 3rd in completed group AND cannot reach top 8 of 3rd-placers
    if group_complete and position == 3:
        team_row = gdf.iloc[2]
        team_key = (int(team_row["PTS"]), int(team_row["GD"]), int(team_row["GS"]))

        above_or_tied = 0
        free_variables = 0
        for g, other_df in group_standings.items():
            if g == team_group:
                continue
            other_complete = len(other_df) >= 4 and bool((other_df["PL"] == 3).all())
            if not other_complete or len(other_df) < 3:
                free_variables += 1
                continue
            other_third = other_df.iloc[2]
            other_key = (
                int(other_third["PTS"]),
                int(other_third["GD"]),
                int(other_third["GS"]),
            )
            # `>=` treats a (PTS, GD, GS) tie as worst-case-above, because
            # further FIFA tiebreakers among 3rd-placers aren't computed here.
            if other_key >= team_key:
                above_or_tied += 1

        worst_case_rank = 1 + above_or_tied + free_variables
        if worst_case_rank >= 9:
            return "Out"

    # Rule 3: lost a knockout-stage match
    for m in matches:
        stage = m.get("stage", "")
        if stage.startswith("Group "):
            continue
        if m.get("status") != "finished" or m.get("home_score") is None:
            continue
        if m["home_team"] != team and m["away_team"] != team:
            continue
        if _match_loser(m) == team:
            return "Out"

    return "In"


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

    # In/Out: mathematical elimination — see _team_out_status
    group_standings = compute_group_standings(matches)
    df["In"] = df["Team"].apply(
        lambda t: _team_out_status(t, group_standings, matches)
    )

    return df


def compute_group_standings(matches: list[dict]) -> dict[str, pd.DataFrame]:
    """
    Compute group-stage-only standings per group (for the 12 group mini-tables).

    Sort order is FIFA: overall PTS, then for points-tied teams apply head-to-head
    (H2H PTS → H2H GD → H2H GS), falling back to overall GD → overall GS when
    head-to-head cannot separate them.
    """
    group_stats: dict[str, dict[str, dict]] = {}
    group_matches: dict[str, list[dict]] = {}

    for m in matches:
        stage = m.get("stage", "")
        if not stage.startswith("Group "):
            continue
        group = stage.split("Group ")[-1].strip()
        if group not in group_stats:
            group_stats[group] = {}
            group_matches[group] = []
        group_matches[group].append(m)

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
    for group in sorted(group_stats.keys()):
        teams = group_stats[group]
        ranked = _rank_group(teams, group_matches[group])
        rows = []
        for team in ranked:
            s = teams[team]
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
        result[group] = pd.DataFrame(rows).reset_index(drop=True)

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
