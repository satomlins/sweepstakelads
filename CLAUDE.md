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

# Seed fake data for UI development (writes cache files + sets timestamp 24h ahead so
# the app won't auto-refresh from Wikipedia during the session)
uv run python dev_seed.py
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
- Six tables: person leaderboard, team table, 12 group mini-tables, knockout stage, recent results, upcoming fixtures
- Page order: leaderboard + teams (equal width) → groups → knockout → recent results + upcoming fixtures
- Fixtures column order: `[Date, Time, HomeOwner, Home, Score, Away, AwayOwner, Stage]` — owner name flanks each team
- Group mini-tables: compact (12px font, 5px padding, fixed narrow numeric columns) — no horizontal scroll
- Single callback `update_all` fires every 5 minutes via `dcc.Interval`
- Owner identity: left-border stripe on name cell + full row text colour (leaderboard/teams); injected owner column coloured by owner (groups/fixtures)
- Eliminated teams: `color: var(--eliminated)` + `text-decoration: line-through` (no red)
- Header strip: wordmark left, "Last updated" right; footer: copyright left, social icons right
- Times are scraped as-is from Wikipedia — not localised to viewer's timezone

**`assets/s1.css`** — full design system (dark-only, greyscale palette):
- CSS custom properties in `:root` for all colours, surfaces, borders, text
- System font stack (no Google Fonts); `ui-monospace` for numeric columns
- Page fade-in animation, row hover, responsive breakpoints at 768px / 480px

## Participants and colours

10 confirmed: Scott, Hugo, Sam, Brendan, Isaac, Adrian, Alex, Mary, Keshy, Jacob. 2 TBC.

Owner colours appear in three ways:
- **Leaderboard / team table**: entire row text in owner colour; left-border accent stripe on the name cell
- **Groups**: `Who` column injected next to `Team`, both cells coloured by owner; left-border stripe on Team cell
- **Fixtures / knockout**: `HomeOwner` and `AwayOwner` columns injected (blank header) next to each team name, coloured by owner; left-border stripe on team name cell
- Never full cell backgrounds; colours are pastels for contrast on dark bg

Owner colour map (pastels):

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

- Host: Oracle Cloud always-free tier, URL: `sweepstakelads.stomlins.com`
- TLS + DNS via Cloudflare — tunnel UUID `dcd0bf6e-e2f4-4e36-9c2a-3f7d1b2566d7`, config at `/etc/cloudflared/config.yml`
- App directory: `/home/opc/sweepstakelads` (tracking `wc2026` branch of `github.com/satomlins/sweepstakelads`)
- Systemd unit: `sweepstakelads.service` — `ExecStart=/usr/local/bin/uv run gunicorn app:server --bind 127.0.0.1:8050 --workers 1`
- Env file: `/etc/sysconfig/sweepstakelads` (currently empty; kept for future secrets)

### Steady-state update workflow

```bash
# Local
git commit && git push origin wc2026

# Oracle
ssh stomlins-oracle
cd /home/opc/sweepstakelads
git pull
sudo systemctl restart sweepstakelads
# If pyproject.toml changed: uv sync  (before the restart)
```

### Hard constraints (Oracle)

- Billing must stay $0 — always-free tier only
- No `setenforce 0` — work with SELinux, not around it
- Bind to `127.0.0.1` only — cloudflared handles public exposure
- `ExecStart` must not point into `/home/opc/.venv/` — use `/usr/local/bin/uv run ...`
- `EnvironmentFile` must live outside `/home/opc/` — use `/etc/sysconfig/<app>`

## Design spec

Full UI design spec is in `DESIGN.md`. Implementation plan is in `PLAN_2026.md`.
