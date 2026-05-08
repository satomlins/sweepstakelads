"""
Tournament orchestration — wires scraper + scoring + caching.

CLI usage:
    python -m tournament        # re-fetches and prints current standings
    python -m tournament --cache  # reads from CSV cache if fresh
"""

import argparse
import json
import os
import pandas as pd
from datetime import datetime, timezone

from scraper import fetch_all_matches
from scoring import compute_team_table, compute_group_standings, compute_person_table

DRAW_PATH = "assets/draw_2026.csv"
PARTICIPANTS_PATH = "assets/participants.csv"
LAST_UPDATED_PATH = "assets/last_updated.txt"

CACHE_TEAM = "assets/teamtable.csv"
CACHE_PERSON = "assets/persontable.csv"
CACHE_FIXTURES = "assets/fixtures.csv"
CACHE_GROUPS = "assets/group_standings.json"

# Minutes before the cache is considered stale
CACHE_TTL_MINUTES = 5


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cache_age_minutes() -> float:
    try:
        with open(LAST_UPDATED_PATH) as f:
            last = pd.to_datetime(f.read().strip())
        return (_now() - last).total_seconds() / 60
    except Exception:
        return float("inf")


def _write_timestamp() -> str:
    ts = str(_now().replace(microsecond=0))
    with open(LAST_UPDATED_PATH, "w") as f:
        f.write(ts)
    return ts


def load_draw() -> pd.DataFrame:
    try:
        df = pd.read_csv(DRAW_PATH)
        if df.empty or "Team" not in df.columns or "Who" not in df.columns:
            return pd.DataFrame(columns=["Who", "Team"])
        return df[["Who", "Team"]].dropna()
    except Exception:
        return pd.DataFrame(columns=["Who", "Team"])


def load_participants() -> list[str]:
    try:
        df = pd.read_csv(PARTICIPANTS_PATH)
        return df["Name"].dropna().tolist()
    except Exception:
        return []


def _matches_to_fixtures_df(matches: list[dict]) -> pd.DataFrame:
    """Convert match list to display DataFrame."""
    rows = []
    for m in matches:
        hs = m["home_score"]
        aws = m["away_score"]
        score = f"{hs}–{aws}" if hs is not None else "vs"

        annotation = ""
        if m["aet"] and m["pen_home"] is not None:
            annotation = f" (pens {m['pen_home']}–{m['pen_away']})"
        elif m["aet"]:
            annotation = " (aet)"

        rows.append(
            {
                "Date": str(m["date"]) if m["date"] else "",
                "Time": m["time"],
                "Home": m["home_team"],
                "Score": score + annotation,
                "Away": m["away_team"],
                "Stage": m["stage"],
                "Status": m["status"].capitalize(),
            }
        )
    return pd.DataFrame(rows)


def refresh() -> dict:
    """Fetch fresh data, compute all tables, write cache. Returns data dict."""
    print(f"Fetching match data from Wikipedia...")
    draw = load_draw()
    matches = fetch_all_matches()

    team_table = compute_team_table(draw, matches)
    person_table = compute_person_table(team_table)
    group_standings = compute_group_standings(matches)
    fixtures_df = _matches_to_fixtures_df(matches)

    team_table.sort_values(["PNT", "GD", "GS"], ascending=False, inplace=True)
    team_table.reset_index(drop=True, inplace=True)

    # Ensure participants without teams still appear in person table
    participants = load_participants()
    if participants:
        existing = set(person_table["Who"].tolist())
        missing = [p for p in participants if p not in existing]
        if missing:
            filler = pd.DataFrame(
                [{"Who": p, "PL": 0, "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "GD": 0, "PNT": 0}
                 for p in missing]
            )
            person_table = pd.concat([person_table, filler], ignore_index=True)
            person_table.sort_values(["PNT", "GD", "GS"], ascending=False, inplace=True)
            person_table.reset_index(drop=True, inplace=True)

    team_table.to_csv(CACHE_TEAM, index=False)
    person_table.to_csv(CACHE_PERSON, index=False)
    fixtures_df.to_csv(CACHE_FIXTURES, index=False)

    # Serialise group standings to JSON (list of {group, rows} dicts)
    gs_serialisable = {
        g: df.to_dict(orient="records") for g, df in group_standings.items()
    }
    with open(CACHE_GROUPS, "w") as f:
        json.dump(gs_serialisable, f)

    timestamp = _write_timestamp()

    return {
        "team_table": team_table,
        "person_table": person_table,
        "group_standings": group_standings,
        "fixtures": fixtures_df,
        "matches": matches,
        "timestamp": timestamp,
    }


def read_cache() -> dict:
    """Read all tables from CSV/JSON cache."""
    team_table = pd.read_csv(CACHE_TEAM)
    person_table = pd.read_csv(CACHE_PERSON)
    fixtures_df = pd.read_csv(CACHE_FIXTURES)

    with open(CACHE_GROUPS) as f:
        gs_raw = json.load(f)
    group_standings = {g: pd.DataFrame(rows) for g, rows in gs_raw.items()}

    with open(LAST_UPDATED_PATH) as f:
        timestamp = f.read().strip()

    return {
        "team_table": team_table,
        "person_table": person_table,
        "group_standings": group_standings,
        "fixtures": fixtures_df,
        "matches": [],
        "timestamp": timestamp,
    }


def get_data(force_refresh: bool = False) -> dict:
    """Return current data, refreshing from Wikipedia if cache is stale."""
    cache_exists = all(
        os.path.exists(p)
        for p in [CACHE_TEAM, CACHE_PERSON, CACHE_FIXTURES, CACHE_GROUPS]
    )
    if not force_refresh and cache_exists and _cache_age_minutes() < CACHE_TTL_MINUTES:
        return read_cache()
    return refresh()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sweepstakelads 2026 standings")
    parser.add_argument("--cache", action="store_true", help="Use cached data if fresh")
    args = parser.parse_args()

    data = get_data(force_refresh=not args.cache)

    print("\n=== PERSON LEADERBOARD ===")
    print(data["person_table"].to_string(index=False))

    print("\n=== TEAM TABLE ===")
    print(data["team_table"].to_string(index=False))

    print("\n=== GROUP STANDINGS ===")
    for group, df in data["group_standings"].items():
        print(f"\nGroup {group}")
        print(df.to_string(index=False))
