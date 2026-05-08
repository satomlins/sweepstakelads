# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Plotly Dash web app that tracks a Euro 2024 football sweepstake. It fetches live match data from the football-data.org API, computes standings, and displays them as tables in a dark-themed dashboard.

## Running the app

```bash
# Development
python app.py

# Production (what the hosting platform uses)
gunicorn app:server
```

Dependencies are managed with `uv` (pyproject.toml + uv.lock) for local dev, and `requirements.txt` for deployment. Install with `uv sync` or `pip install -r requirements.txt`.

## Architecture

**`Update_Scores.py`** — `Tournament` class is the data engine:
- Calls `https://api.football-data.org/v4/competitions/{tournament}/matches` (API key hardcoded)
- Reads `assets/Euro_2024.csv` (the sweepstake draw: who owns which teams)
- Computes W/D/L/GD/GS/PNT per team via `fill_table()`, called row-by-row on the fixtures DataFrame
- Marks teams still in the tournament as "In" / "Out" via a merge

**`app.py`** — Dash frontend:
- Three `DataTable` components: teams, persons (aggregated from teams), fixtures
- A `dcc.Interval` fires every 5 minutes, triggering the single callback `update_output`
- The callback checks `assets/last_updated.txt`; if data is >1 minute old, it re-instantiates `Tournament`, recomputes everything, and writes results to CSV cache files (`teamtable.csv`, `persontable.csv`, `fixtures.csv`)
- If data is fresh, it reads directly from the CSV cache

**Scoring rules** (in `fill_table`):
- Regular win: 3 pts winner, 0 loser
- AET win: 3 pts winner, 1 loser; GD counted
- Penalty shootout: 2 pts winner, 1 loser; GD **not** counted

**`assets/Euro_2024.csv`** — the draw (Who → Team mapping, 3 teams per person, 8 people)

## Participants and colours

Scott, Hugo, Sam, Brendan, Isaac, Adrian, Alex, Mary — each has a pastel colour defined in `app.py:colours`. Eliminated teams show red (`#960000`) in the team table.
