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
- Returns a flat list of match dicts with keys: `date`, `time`, `datetime_utc`, `home_team`, `away_team`, `home_score`, `away_score`, `pen_home`, `pen_away`, `aet`, `stage`, `status`
- `datetime_utc` is a `datetime` object in UTC parsed from Wikipedia's "H:MM a.m./p.m. UTC±N" format (handles Unicode minus U+2212 and `<includeonly>` HTML tags); `None` if unparseable
- Pages scraped: 12 individual group pages (`2026 FIFA World Cup Group A` … `Group L`) + `2026 FIFA World Cup knockout stage`
- Future knockout rounds appear with placeholder team names (e.g. "Winner of Match 57") — the scraper passes these through as-is after stripping wikitext markup

**`scoring.py`** — pure functions, no I/O:
- `compute_team_table(draw, matches)` → DataFrame with columns `[Team, Who, PL, W, D, L, GS, GA, GD, PNT, In]`
- `compute_person_table(team_table)` → DataFrame summing team stats per owner
- `compute_group_standings(matches)` → dict of `{group_letter: DataFrame}`
- Scoring rules: regular win 3/0, AET win 3/1 (GD counts), pens 2/1 (GD not counted), group draw 1/1, third-place match 1/0
- `compute_team_table` seeds team rows from group-stage matches only — knockout placeholder names like "Winner of Match X" are intentionally excluded

**`tournament.py`** — orchestration + caching:
- `get_data(force_refresh=False)` — main entry point for `app.py`; returns fresh data or reads CSV/JSON cache
- `load_draw()` — reads `assets/draw_2026.csv` (Who, Team); returns empty DataFrame if not yet populated
- Cache TTL: 5 minutes. Cache files: `assets/teamtable.csv`, `assets/persontable.csv`, `assets/fixtures.csv`, `assets/group_standings.json`, `assets/last_updated.txt`
- `refresh()` calls scraper → scoring → writes cache; fixtures are sorted ascending by `DatetimeUTC` before caching so `head(N)` / `tail(N)` slices in app.py are chronologically correct
- `fixtures.csv` columns: `DatetimeUTC` (ISO 8601 UTC string), `Date`, `Time`, `Home`, `Score`, `Away`, `Stage`, `Status`
- CLI entrypoint: `python -m tournament [--cache]`

**`app.py`** — Dash layout + callbacks only, no business logic:
- Three-tab navigation (Home / Leaderboard / Fixtures & Results) using `dcc.Location` URL routing; active tab highlighted by CSS class
- **Page: Home** — person leaderboard (full width) + recent results / upcoming fixtures side-by-side
- **Page: Leaderboard** — person leaderboard + team table (sortable)
- **Page: Fixtures & Results** — 12 group mini-tables + knockout stage + all results + all upcoming fixtures
- Single callback `update_all` fires on `dcc.Interval` (5 min) and on `tz-offset` store change
- **Timezone handling**: browser offset detected via clientside callback (`-new Date().getTimezoneOffset()` → `dcc.Store(id="tz-offset")`); `_localize_fixtures(df, tz_minutes)` converts `DatetimeUTC` → local date + time for display; `DatetimeUTC` is the single source of truth — dates shift correctly across timezones (e.g. a late-night UTC-7 match shows as next-day for UK users); header shows "All times UTC+X" label
- **Match numbers**: `fixtures["Match"] = range(1, len(fixtures) + 1)` applied globally in `update_all` after loading (sequential by chronological sort order, 1-indexed)
- Column sets (constants at top of file):
  - `_RESULT_COLS` = `[Date, Time, HomeOwner, Home, Score, Away, AwayOwner, Stage]`
  - `_FIXTURE_COLS` = `[Match, Date, Time, HomeOwner, Home, Away, AwayOwner, Stage]`
  - `_KO_COLS` = `[Match, Stage, HomeOwner, Home, Score, Away, AwayOwner]`
- Owner identity: left-border stripe on name cell + full row text colour (leaderboard/teams); injected owner column coloured by owner (groups/fixtures); unknown teams (e.g. "Winner of Match X") show blank owner column
- Eliminated teams: `color: var(--eliminated)` + `text-decoration: line-through` (no red)
- Header strip: wordmark left, timezone label + "Last updated" stacked right; footer: copyright left, social icons right
- Group mini-tables: compact (12px font, 5px padding, fixed narrow numeric columns) — no horizontal scroll

**`assets/s1.css`** — full design system (dark-only, greyscale palette):
- CSS custom properties in `:root` for all colours, surfaces, borders, text
- System font stack (no Google Fonts); `ui-monospace` for numeric columns
- Tab navigation styles: `.tab-nav`, `.tab-link`, `.tab-link.active`
- Page fade-in animation, row hover, responsive breakpoints at 768px / 480px

**`dev_seed.py`** — generates fake match data for UI development:
- Writes all cache files and sets `last_updated.txt` 24 hours ahead (prevents auto-refresh)
- `knockout_matches` generates: R32 all finished → R16 first 4 finished + last 4 upcoming → QF 4 upcoming with cross-bracket pairing (each QF has one known team + one "Winner of Match X" placeholder)
- `matches_to_fixtures` adds `DatetimeUTC` column and sorts ascending before writing CSV

## Participants and colours

12 confirmed: Scott, Hugo, Sam, Brendan, Isaac, Adrian, Alex, Mary, Keshy, Jacob, Seth, Ella. All 12 have colours in `COLOURS` dict in `app.py`.

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
    "Seth":    "#b5ead7",
    "Ella":    "#f8c8d4",
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
| `assets/fixtures.csv` | Cached fixture list (sorted ascending by DatetimeUTC) |
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

## Working practices

Before every commit, update CLAUDE.md to reflect any architectural, behavioural, or participant changes made in that session. The goal is that CLAUDE.md always gives an accurate picture of the current codebase to a future Claude session with no prior context.

## Design spec

Full UI design spec is in `docs/DESIGN.md`. Implementation plan is in `docs/PLAN_2026.md`. Deployment notes are in `docs/DEPLOY_PLAN.md`.
