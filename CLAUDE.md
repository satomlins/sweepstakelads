# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Plotly Dash web app tracking a 2026 FIFA World Cup sweepstake. It scrapes live match data from Wikipedia, computes standings, and displays them in a dark, greyscale dashboard.

## Running the app

```bash
# Development
uv run python app.py

# Production (Oracle Cloud, behind cloudflared)
gunicorn app:server

# Print current standings from the command line
uv run python -m tournament          # re-fetch from Wikipedia
uv run python -m tournament --cache  # use CSV cache if fresh
```

Dependencies are managed with `uv` (pyproject.toml + uv.lock) for local dev, and `requirements.txt` for deployment. Install with `uv sync`.

## Architecture

Strict separation of concerns — each module has one job:

**`scraper.py`** — Wikipedia-only, no scoring logic:
- Fetches wikitext via `https://en.wikipedia.org/w/api.php?action=parse&prop=wikitext&page=<title>`
- Parses `{{footballbox}}` / `{{footballbox collapsible}}` templates
- Returns a flat list of match dicts with keys: `date`, `time`, `home_team`, `away_team`, `home_score`, `away_score`, `pen_home`, `pen_away`, `aet`, `stage`, `status`
- Pages scraped: `2026 FIFA World Cup group stage`, `2026 FIFA World Cup knockout stage`

**`scoring.py`** — pure functions, no I/O:
- `compute_team_table(draw, matches)` → DataFrame with columns `[Team, Who, PL, W, D, L, GS, GA, GD, PNT, In]`
- `compute_person_table(team_table)` → DataFrame summing team stats per owner
- `compute_group_standings(matches)` → dict of `{group_letter: DataFrame}`
- Scoring rules: regular win 3/0, AET win 3/1 (GD counts), pens 2/1 (GD not counted), group draw 1/1, third-place match 1/0

**`tournament.py`** — orchestration + caching:
- `get_data(force_refresh=False)` — main entry point for `app.py`; returns fresh data or reads CSV/JSON cache
- `load_draw()` — reads `assets/draw_2026.csv` (Who, Team); returns empty DataFrame if not yet populated
- Cache TTL: 5 minutes. Cache files: `assets/teamtable.csv`, `assets/persontable.csv`, `assets/fixtures.csv`, `assets/group_standings.json`, `assets/last_updated.txt`
- `refresh()` calls scraper → scoring → writes cache
- CLI entrypoint: `python -m tournament [--cache]`

**`app.py`** — Dash layout + callbacks only, no business logic:
- Six tables: person leaderboard, team table, 12 group mini-tables, recent results, upcoming fixtures, knockout stage
- Single callback `update_all` fires every 5 minutes via `dcc.Interval`
- Owner identity shown as inset left-border stripe (`boxShadow: inset N px 0 0 0 <colour>`) — no full-cell background tints
- Eliminated teams: `color: var(--eliminated)` + `text-decoration: line-through` (no red)
- Header strip: wordmark left, "Last updated" right; footer: copyright left, social icons right

**`assets/s1.css`** — full design system (dark-only, greyscale palette):
- CSS custom properties in `:root` for all colours, surfaces, borders, text
- System font stack (no Google Fonts); `ui-monospace` for numeric columns
- Page fade-in animation, row hover, responsive breakpoints at 768px / 480px

## Participants and colours

10 confirmed: Scott, Hugo, Sam, Brendan, Isaac, Adrian, Alex, Mary, Keshy, Jacob. 2 TBC.

Owner colours (pastels, used only as accent stripes — never full cell backgrounds):

```python
COLOURS = {
    "Scott":   "#ffadad",
    "Hugo":    "#ffd6a5",
    "Sam":     "#fdffb6",
    "Brendan": "#caffbf",
    "Isaac":   "#9bf6ff",
    "Adrian":  "#a0c4ff",
    "Alex":    "#bdb2ff",
    "Mary":    "#ffc6ff",
    "Keshy":   "#c7ceea",
    "Jacob":   "#ffdac1",
}
```

## Draw status

`assets/draw_2026.csv` ships with headers only until the draw is held. App renders with all-zero standings and "TBC" owners until populated. `assets/participants.csv` has the 10 confirmed names so the person leaderboard exists pre-draw.

## Key assets

| File | Purpose |
|---|---|
| `assets/draw_2026.csv` | Who → Team mapping (populated after draw) |
| `assets/participants.csv` | Confirmed participant names |
| `assets/teamtable.csv` | Cached team standings |
| `assets/persontable.csv` | Cached person standings |
| `assets/fixtures.csv` | Cached fixture list |
| `assets/group_standings.json` | Cached group standings (JSON) |
| `assets/last_updated.txt` | Cache timestamp (UTC) |
| `archive/` | 2024 Euro code (preserved for reference) |

## Deployment

- Host: Oracle Cloud, URL: `sweepstakelads.stomlins.com`
- TLS + DNS via Cloudflare (existing `cloudflared` tunnel — no certbot needed)
- Run: `gunicorn app:server` bound to localhost; cloudflared forwards to it
- Managed as a systemd unit

## Design spec

Full UI design spec is in `DESIGN.md`. Implementation plan is in `PLAN_2026.md`.
