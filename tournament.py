"""
Tournament orchestration — wires scraper + scoring + caching.

CLI usage:
    python -m tournament        # re-fetches and prints current standings
    python -m tournament --cache  # reads from CSV cache if fresh
"""

import argparse
import json
import logging
import os
import threading
import pandas as pd
from datetime import datetime, timezone

from scraper import fetch_all_matches
from scoring import compute_team_table, compute_group_standings, compute_person_table

logger = logging.getLogger(__name__)

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


def _atomic_write_csv(df: pd.DataFrame, path: str) -> None:
    tmp = path + ".tmp"
    df.to_csv(tmp, index=False)
    os.replace(tmp, path)


def _atomic_write_json(data: object, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _atomic_write_text(text: str, path: str) -> None:
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


def _write_timestamp() -> str:
    ts = str(_now().replace(microsecond=0))
    _atomic_write_text(ts, LAST_UPDATED_PATH)
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


def _winner_label(m: dict) -> str:
    hs = m["home_score"]
    aws = m["away_score"]
    if hs is None or aws is None:
        return ""
    if m["aet"] and m["pen_home"] is not None and m["pen_away"] is not None:
        if m["pen_home"] > m["pen_away"]:
            return "HOME"
        if m["pen_away"] > m["pen_home"]:
            return "AWAY"
        return ""
    if hs > aws:
        return "HOME"
    if aws > hs:
        return "AWAY"
    return "DRAW"


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

        dt_utc = m.get("datetime_utc")
        rows.append(
            {
                "DatetimeUTC": dt_utc.strftime("%Y-%m-%dT%H:%M:%S") if dt_utc else "",
                "Date": str(m["date"]) if m["date"] else "",
                "Home": m["home_team"],
                "Score": score + annotation,
                "Away": m["away_team"],
                "Stage": m["stage"],
                "Status": m["status"].capitalize(),
                "Winner": _winner_label(m),
            }
        )
    return pd.DataFrame(rows)


def refresh() -> dict:
    """Fetch fresh data, compute all tables, write cache. Returns data dict."""
    logger.info("Fetching match data from Wikipedia...")
    draw = load_draw()
    matches = fetch_all_matches()

    team_table = compute_team_table(draw, matches)
    person_table = compute_person_table(team_table)
    group_standings = compute_group_standings(matches)
    fixtures_df = _matches_to_fixtures_df(matches)

    team_table.sort_values(["PNT", "GD", "GS"], ascending=False, inplace=True)
    team_table.reset_index(drop=True, inplace=True)

    fixtures_df["_sort"] = pd.to_datetime(fixtures_df["DatetimeUTC"], errors="coerce")
    fixtures_df.sort_values("_sort", inplace=True, na_position="last")
    fixtures_df.drop(columns=["_sort"], inplace=True)
    fixtures_df.reset_index(drop=True, inplace=True)

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

    _atomic_write_csv(team_table, CACHE_TEAM)
    _atomic_write_csv(person_table, CACHE_PERSON)
    _atomic_write_csv(fixtures_df, CACHE_FIXTURES)

    gs_serialisable = {
        g: df.to_dict(orient="records") for g, df in group_standings.items()
    }
    _atomic_write_json(gs_serialisable, CACHE_GROUPS)

    # Write timestamp last — a missing/stale timestamp means cache is incomplete
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


_refresh_lock = threading.Lock()
_refresh_in_flight = False


def _maybe_refresh_async() -> None:
    global _refresh_in_flight
    with _refresh_lock:
        if _refresh_in_flight:
            return
        _refresh_in_flight = True

    def _run() -> None:
        global _refresh_in_flight
        try:
            refresh()
        except Exception:
            logger.exception("Background refresh failed")
        finally:
            with _refresh_lock:
                _refresh_in_flight = False

    threading.Thread(target=_run, daemon=True).start()


def get_data(force_refresh: bool = False) -> dict:
    """Return current data. Triggers a background refresh if cache is stale."""
    cache_exists = all(
        os.path.exists(p)
        for p in [CACHE_TEAM, CACHE_PERSON, CACHE_FIXTURES, CACHE_GROUPS]
    )
    if not cache_exists:
        return refresh()
    if force_refresh or _cache_age_minutes() >= CACHE_TTL_MINUTES:
        _maybe_refresh_async()
    return read_cache()


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
