#!/usr/bin/env python
"""Generate fake match data for UI development. Writes directly to cache files."""
import json
import random
import pandas as pd
from datetime import date, timedelta, datetime, timezone
from scoring import compute_team_table, compute_group_standings, compute_person_table

random.seed(42)

DRAW_ROWS = [
    ("Scott",   "USA"),            ("Scott",   "Argentina"),    ("Scott",   "Japan"),              ("Scott",   "Italy"),
    ("Hugo",    "Brazil"),         ("Hugo",    "Germany"),      ("Hugo",    "France"),              ("Hugo",    "Morocco"),
    ("Sam",     "England"),        ("Sam",     "Spain"),        ("Sam",     "Netherlands"),         ("Sam",     "Nigeria"),
    ("Brendan", "Mexico"),         ("Brendan", "Canada"),       ("Brendan", "Portugal"),            ("Brendan", "Senegal"),
    ("Isaac",   "Colombia"),       ("Isaac",   "Saudi Arabia"), ("Isaac",   "Croatia"),             ("Isaac",   "Australia"),
    ("Adrian",  "Belgium"),        ("Adrian",  "Iran"),         ("Adrian",  "Serbia"),              ("Adrian",  "Egypt"),
    ("Alex",    "South Korea"),    ("Alex",    "Turkey"),       ("Alex",    "Ivory Coast"),         ("Alex",    "Chile"),
    ("Mary",    "Switzerland"),    ("Mary",    "Uruguay"),      ("Mary",    "Cameroon"),            ("Mary",    "Indonesia"),
    ("Keshy",   "Ecuador"),        ("Keshy",   "Peru"),         ("Keshy",   "Scotland"),            ("Keshy",   "Guinea"),
    ("Jacob",   "Panama"),         ("Jacob",   "Bolivia"),      ("Jacob",   "Denmark"),             ("Jacob",   "Jamaica"),
    ("TBC",     "Venezuela"),      ("TBC",     "Curacao"),      ("TBC",     "Honduras"),            ("TBC",     "Albania"),
    ("TBC",     "Qatar"),          ("TBC",     "Uzbekistan"),   ("TBC",     "Trinidad & Tobago"),   ("TBC",     "New Zealand"),
]

GROUPS = {
    "A": ["USA", "Panama", "Albania", "Morocco"],
    "B": ["Canada", "Honduras", "Belgium", "Trinidad & Tobago"],
    "C": ["Mexico", "Jamaica", "France", "Curacao"],
    "D": ["Argentina", "Chile", "Germany", "Peru"],
    "E": ["Brazil", "Bolivia", "England", "Venezuela"],
    "F": ["Colombia", "Ecuador", "Spain", "Uruguay"],
    "G": ["Nigeria", "Cameroon", "Italy", "Senegal"],
    "H": ["Egypt", "Ivory Coast", "Netherlands", "Guinea"],
    "I": ["Japan", "South Korea", "Portugal", "Indonesia"],
    "J": ["Saudi Arabia", "Iran", "Switzerland", "Qatar"],
    "K": ["Australia", "New Zealand", "Croatia", "Uzbekistan"],
    "L": ["Serbia", "Turkey", "Denmark", "Scotland"],
}

STRENGTHS = {
    "France": 9, "Brazil": 9, "Argentina": 9, "England": 8, "Spain": 8, "Germany": 8,
    "Portugal": 8, "Netherlands": 8, "Colombia": 7, "Uruguay": 7, "Morocco": 7,
    "Belgium": 7, "Mexico": 7, "USA": 7, "Japan": 7, "South Korea": 7, "Croatia": 7,
    "Switzerland": 7, "Senegal": 7, "Nigeria": 7, "Denmark": 7, "Serbia": 7,
    "Australia": 6, "Italy": 6, "Chile": 6, "Ecuador": 6, "Turkey": 6, "Egypt": 6,
    "Ivory Coast": 6, "Saudi Arabia": 6, "Iran": 6, "Canada": 6, "Peru": 5,
    "Albania": 5, "Bolivia": 5, "Venezuela": 5, "Cameroon": 5, "Scotland": 5,
    "Panama": 5, "Jamaica": 5, "Guinea": 5, "Honduras": 4, "Curacao": 4,
    "Indonesia": 4, "Qatar": 4, "Uzbekistan": 4, "New Zealand": 4,
    "Trinidad & Tobago": 4,
}

TIMES = ["14:00", "16:00", "17:00", "18:00", "19:00", "20:00", "21:00"]


def gen_score(home: str, away: str) -> tuple[int, int]:
    h, a = STRENGTHS.get(home, 5), STRENGTHS.get(away, 5)
    hg = max(0, round(random.gauss((h + (h - a) * 0.25) / 4.5, 0.8)))
    ag = max(0, round(random.gauss((a + (a - h) * 0.25) / 4.5, 0.8)))
    return hg, ag


def group_matches() -> list[dict]:
    matches = []
    base = date(2026, 6, 11)
    round_pairs = [[(0, 1), (2, 3)], [(0, 2), (1, 3)], [(0, 3), (1, 2)]]

    for r_idx, pairs in enumerate(round_pairs):
        for g_idx, group in enumerate(GROUPS.keys()):
            teams = GROUPS[group]
            for p_idx, (i, j) in enumerate(pairs):
                home, away = teams[i], teams[j]
                hs, aws = gen_score(home, away)
                match_date = base + timedelta(days=r_idx * 8 + g_idx // 4 + p_idx // 2)
                matches.append({
                    "date": str(match_date),
                    "time": TIMES[(g_idx + p_idx * 3) % len(TIMES)],
                    "home_team": home,
                    "away_team": away,
                    "home_score": hs,
                    "away_score": aws,
                    "pen_home": None,
                    "pen_away": None,
                    "aet": False,
                    "stage": f"Group {group}",
                    "status": "finished",
                })

    return matches


def knockout_matches(group_standings: dict) -> list[dict]:
    winners, runners, thirds = [], [], []
    for g, df in sorted(group_standings.items()):
        if len(df) >= 1:
            winners.append(df.iloc[0]["Team"])
        if len(df) >= 2:
            runners.append(df.iloc[1]["Team"])
        if len(df) >= 3:
            thirds.append((df.iloc[2]["PNT"], df.iloc[2]["GD"], df.iloc[2]["GS"], df.iloc[2]["Team"]))

    thirds.sort(reverse=True)
    best_thirds = [t[3] for t in thirds[:8]]

    # 16 R32 pairings: winners cross with runners-up + 4 third-place pairs
    r32_pairs = [(winners[i], runners[11 - i]) for i in range(12)]
    for i in range(4):
        r32_pairs.append((best_thirds[i], best_thirds[7 - i]))

    matches = []
    r16_teams = []
    base_r32 = date(2026, 7, 4)

    for i, (home, away) in enumerate(r32_pairs):
        hs, aws = gen_score(home, away)
        if hs == aws:
            hs += 1  # knockout: no draws (simplification — treat as AET winner)
        winner = home if hs > aws else away
        r16_teams.append(winner)
        matches.append({
            "date": str(base_r32 + timedelta(days=i // 4)),
            "time": TIMES[i % len(TIMES)],
            "home_team": home,
            "away_team": away,
            "home_score": hs,
            "away_score": aws,
            "pen_home": None,
            "pen_away": None,
            "aet": False,
            "stage": "Round of 32",
            "status": "finished",
        })

    # R16: first 4 finished, last 4 upcoming
    base_r16 = date(2026, 7, 14)
    r16_pairs = [(r16_teams[i], r16_teams[15 - i]) for i in range(8)]
    qf_teams = []

    for i, (home, away) in enumerate(r16_pairs):
        if i < 4:
            hs, aws = gen_score(home, away)
            if hs == aws:
                hs += 1
            winner = home if hs > aws else away
            qf_teams.append(winner)
            matches.append({
                "date": str(base_r16 + timedelta(days=i // 4)),
                "time": TIMES[i % len(TIMES)],
                "home_team": home,
                "away_team": away,
                "home_score": hs,
                "away_score": aws,
                "pen_home": None,
                "pen_away": None,
                "aet": False,
                "stage": "Round of 16",
                "status": "finished",
            })
        else:
            qf_teams.append(f"Winner of Match {89 + i}")
            matches.append({
                "date": str(base_r16 + timedelta(days=i // 4)),
                "time": TIMES[i % len(TIMES)],
                "home_team": home,
                "away_team": away,
                "home_score": None,
                "away_score": None,
                "pen_home": None,
                "pen_away": None,
                "aet": False,
                "stage": "Round of 16",
                "status": "upcoming",
            })

    # QF: 4 upcoming — cross-bracket so each match has one known team + one TBD
    base_qf = date(2026, 7, 18)
    qf_pairs = [(qf_teams[i], qf_teams[7 - i]) for i in range(4)]

    for i, (home, away) in enumerate(qf_pairs):
        matches.append({
            "date": str(base_qf + timedelta(days=i // 2)),
            "time": TIMES[i % len(TIMES)],
            "home_team": home,
            "away_team": away,
            "home_score": None,
            "away_score": None,
            "pen_home": None,
            "pen_away": None,
            "aet": False,
            "stage": "Quarter-final",
            "status": "upcoming",
        })

    return matches


def matches_to_fixtures(matches: list[dict]) -> pd.DataFrame:
    rows = []
    for m in matches:
        hs, aws = m["home_score"], m["away_score"]
        score = f"{hs}–{aws}" if hs is not None else "vs"
        # Treat dev times as UTC (24h strings like "14:00") — good enough for UI dev
        dt_utc = ""
        try:
            dt = datetime.strptime(f"{m['date']} {m['time']}", "%Y-%m-%d %H:%M")
            dt_utc = dt.replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        except Exception:
            pass
        rows.append({
            "DatetimeUTC": dt_utc,
            "Date": m["date"],
            "Time": m["time"],
            "Home": m["home_team"],
            "Score": score,
            "Away": m["away_team"],
            "Stage": m["stage"],
            "Status": m["status"].capitalize(),
        })
    df = pd.DataFrame(rows)
    df["_sort"] = pd.to_datetime(df["DatetimeUTC"], errors="coerce")
    df.sort_values("_sort", inplace=True, na_position="last")
    df.drop(columns=["_sort"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def main():
    draw_df = pd.DataFrame(DRAW_ROWS, columns=["Who", "Team"])
    draw_df.to_csv("assets/draw_2026.csv", index=False)
    print(f"Written draw: {len(draw_df)} teams")

    g_matches = group_matches()
    print(f"Generated {len(g_matches)} group stage matches")

    group_standings = compute_group_standings(g_matches)

    ko_matches = knockout_matches(group_standings)
    print(f"Generated {len(ko_matches)} knockout matches ({sum(1 for m in ko_matches if m['status'] == 'finished')} finished, {sum(1 for m in ko_matches if m['status'] == 'upcoming')} upcoming)")

    all_matches = g_matches + ko_matches

    draw = pd.DataFrame(DRAW_ROWS, columns=["Who", "Team"])
    team_table = compute_team_table(draw, all_matches)
    team_table.sort_values(["PNT", "GD", "GS"], ascending=False, inplace=True)
    team_table.reset_index(drop=True, inplace=True)

    person_table = compute_person_table(team_table)

    existing = set(person_table["Who"].tolist())
    all_owners = list({r[0] for r in DRAW_ROWS})
    missing = [n for n in all_owners if n not in existing]
    if missing:
        filler = pd.DataFrame([
            {"Who": n, "PL": 0, "W": 0, "D": 0, "L": 0, "GS": 0, "GA": 0, "GD": 0, "PNT": 0}
            for n in missing
        ])
        person_table = pd.concat([person_table, filler], ignore_index=True)
        person_table.sort_values(["PNT", "GD", "GS"], ascending=False, inplace=True)
        person_table.reset_index(drop=True, inplace=True)

    fixtures_df = matches_to_fixtures(all_matches)

    team_table.to_csv("assets/teamtable.csv", index=False)
    person_table.to_csv("assets/persontable.csv", index=False)
    fixtures_df.to_csv("assets/fixtures.csv", index=False)

    gs_full = compute_group_standings(all_matches)
    with open("assets/group_standings.json", "w") as f:
        json.dump({g: df.to_dict(orient="records") for g, df in gs_full.items()}, f)

    # Write a timestamp 24 hours in the future so the cache never appears stale during dev.
    future = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0) + timedelta(hours=24)
    with open("assets/last_updated.txt", "w") as f:
        f.write(str(future))

    print("\nPerson leaderboard:")
    print(person_table.to_string(index=False))
    print("\nDone. Cache files written.")


if __name__ == "__main__":
    main()
