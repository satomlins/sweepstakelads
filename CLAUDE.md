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

Dependencies are managed with `uv` (pyproject.toml + uv.lock). Install with `uv sync`.

## Tests

```bash
uv run pytest -q          # run all tests
uv run pytest -v          # verbose output
```

- **`tests/test_scraper.py`** — scraper regression tests against pinned wikitext snapshots in `tests/fixtures/`. Catches silent zero-match failures if Wikipedia changes the football-box template format.
- **`tests/test_scoring.py`** — pure scoring function tests: regular win, AET, penalties, draw, third-place match, team/person table, group standings, third-place table.
- **`tests/fixtures/`** — pinned wikitext snapshots (`group_a_2026-05-11.wikitext`, `knockout_2026-05-11.wikitext`). Run `uv run python scripts/refresh_fixtures.py` to regenerate when upstream pages legitimately change.
- **`.github/workflows/test.yml`** — runs `uv sync --frozen && uv run pytest -q` on every push and PR.

## Architecture

Strict separation of concerns — each module has one job:

**`scraper.py`** — Wikipedia-only, no scoring logic:
- Fetches all 13 pages in a **single batched HTTP request** via `action=query&prop=revisions&rvprop=content&titles=<pipe-joined titles>` (one ~215 KB call vs 13 sequential calls)
- `fetch_all_wikitext()` returns `{page_title: wikitext}` dict; `fetch_all_matches()` parses all pages and returns the flat match list
- Parses `{{footballbox}}` / `{{footballbox collapsible}}` templates
- Returns a flat list of match dicts with keys: `date`, `time`, `datetime_utc`, `home_team`, `away_team`, `home_score`, `away_score`, `pen_home`, `pen_away`, `aet`, `stage`, `status`
- `datetime_utc` is a `datetime` object in UTC parsed from Wikipedia's "H:MM a.m./p.m. UTC±N" format (handles Unicode minus U+2212 and `<includeonly>` HTML tags); `None` if unparseable
- Pages scraped: 12 individual group pages (`2026 FIFA World Cup Group A` … `Group L`) + `2026 FIFA World Cup knockout stage` + `2026 FIFA World Cup final` (separate Wikipedia page; uses `stage_override="Final"` since the page's own heading is `==Match==`)
- Future knockout rounds appear with placeholder team names (e.g. "Winner of Match 57") — the scraper passes these through as-is after stripping wikitext markup
- Uses `logging` (module-level `logger`); partial failures logged as `logger.warning`

**`scoring.py`** — pure functions, no I/O:
- `compute_team_table(draw, matches)` → DataFrame with columns `[Team, Who, PL, W, D, L, GS, GA, GD, PNT, In]`
- `compute_person_table(team_table)` → DataFrame summing team stats per owner
- `compute_group_standings(matches)` → dict of `{group_letter: DataFrame}`
- `compute_third_place_table(group_standings)` → DataFrame of all 12 third-place teams sorted PNT→GD→GS; top 8 advance to the knockout stage
- Scoring rules: regular win 3/0, AET win 3/1 (GD counts), pens 2/1 (GD not counted), group draw 1/1, third-place match 1/0
- `_apply_match` handles: penalty shootout; regular/AET win (single branch — winner determined by `hs > aws`); draw
- `compute_team_table` seeds team rows from group-stage matches only — knockout placeholder names like "Winner of Match X" are intentionally excluded; unowned teams get `Who = ""` (not `"TBC"`)
- `compute_person_table` filters out any row where `Who == ""` — unowned teams are excluded from the person leaderboard entirely

**`tournament.py`** — orchestration + caching:
- `get_data(force_refresh=False)` — main entry point for `app.py`; on first start (no cache) blocks on `refresh()`; otherwise returns cached data immediately and fires a **background refresh** via `threading.Thread(daemon=True)` if cache is stale — UI render is always ~5 ms
- `_maybe_refresh_async()` — guards against concurrent background refreshes with a `threading.Lock`
- `load_draw()` — reads `assets/draw_2026.csv` (Who, Team); returns empty DataFrame if not yet populated
- Cache TTL: 5 minutes. Cache files: `assets/teamtable.csv`, `assets/persontable.csv`, `assets/fixtures.csv`, `assets/group_standings.json`, `assets/last_updated.txt`
- `refresh()` calls scraper → scoring → writes cache using **atomic temp-file writes** (`_atomic_write_csv`, `_atomic_write_json`, `_atomic_write_text`); `last_updated.txt` written last so a partial write shows as stale rather than corrupt; fixtures sorted ascending by `DatetimeUTC` before caching
- `fixtures.csv` columns: `DatetimeUTC` (ISO 8601 UTC string), `Date`, `Home`, `Score`, `Away`, `Stage`, `Status`, `Winner` — note: no `Time` column; `Time` is synthesised by `_localize_fixtures` in `app.py` at render time from `DatetimeUTC`. `Winner` is `"HOME"` / `"AWAY"` / `"DRAW"` / `""` (empty for unplayed); for matches decided on penalties, `Winner` is set from the shootout result, not the 90+ET draw.
- **`Score` column format** in `fixtures.csv`: regulation result → `"2–1"`; extra-time decisive → `"2–1 (aet)"`; draw after AET decided by penalties → `"1–1 (pens 4–3)"`. The annotation is baked in at `_matches_to_fixtures_df`; the `Score` column is a single string with no nested styling. `aet=True` with `pen_home=None` renders the `(aet)` suffix; `aet=True` with `pen_home` set renders `(pens X–Y)` (the score itself is still the AET total since Wikipedia's `score` field reports full-time-plus-ET).
- CLI entrypoint: `python -m tournament [--cache]`

**`app.py`** — Dash layout + callbacks only, no business logic:
- Four-tab navigation (Home / Leaderboard / Results & Fixtures / Group Stages) using `dcc.Location` URL routing; active tab highlighted by CSS class
- **Page: Home** — person leaderboard (full width) + recent results / upcoming fixtures side-by-side (upcoming shows no Match column)
- **Page: Leaderboard** — person leaderboard + team table (sortable)
- **Page: Results & Fixtures** — all results + all upcoming fixtures (section heading "Fixtures", not "Upcoming Fixtures"; no knockout section — redundant with full fixture list); page has an `owner-filter` multi-select dropdown above the Results section; selecting one or more owners restricts both the Results and Fixtures tables to matches where the home or away team belongs to a selected owner (default empty = no filter). Dropdown options are listed alphabetically by name.
- **Page: Group Stages** — 12 group mini-tables + third-place standings table
- Single callback `update_all` fires on `dcc.Interval` (5 min), on `tz-offset` store change, on `show-goals` store change, and on `Input("owner-filter", "value")` change
- **Timezone handling**: browser offset detected via clientside callback (`-new Date().getTimezoneOffset()` → `dcc.Store(id="tz-offset")`); `_localize_fixtures(df, tz_minutes)` synthesises `Date` and `Time` columns from `DatetimeUTC` — `Time` is not stored in the CSV; `DatetimeUTC` is the single source of truth — dates shift correctly across timezones (e.g. a late-night UTC-7 match shows as next-day for UK users); header shows "All times UTC+X" label
- **Match numbers**: `fixtures["Match"] = range(1, len(fixtures) + 1)` applied globally in `update_all` after loading (sequential by chronological sort order, 1-indexed)
- **Pre-computed style constants** at module scope: `_NUMERIC_ALIGN`, `_PERSON_FMT`, `_TEAM_ROW_COLOUR`, `_WHO_COL_COLOUR`, `_FIXTURE_OWNER_FMT`, `_TP_DIM_RULES`, `_WINNER_BOLD_RULES` — deterministic rules built once; draw-dependent rules (`_team_stripe_rules`, `_fixture_colour_rules`, `_group_colour_rules`) are still built inside the callback
- **Winning team bolding**: results tables (Home Recent Results + Results & Fixtures All Results) bold the winner's country name and owner name via four `style_data_conditional` rules keyed on a hidden `Winner` column in the row data (`"HOME"` / `"AWAY"` / `"DRAW"` / `""`). `Winner` is included in the projection but **not** in `_RESULT_COLS`, so it never renders as a visible column. Draws (group stage) leave both sides unbolded. Upcoming fixtures get no bolding. `results_fmt = fixture_fmt + _WINNER_BOLD_RULES` is used for the two results tables; upcoming tables use `fixture_fmt`.
- All `dash_table.DataTable` instances (both the `_make_table` helper and the inline group mini-tables) set `cell_selectable=False` so clicking a cell does not trigger Dash's default light-background active-cell styling, which would be unreadable against the dark theme
- Column sets (constants at top of file):
  - `_RESULT_COLS` = `[Date, Time, HomeOwner, Home, Score, Away, AwayOwner, Stage]`
  - `_FIXTURE_COLS` = `[Match, Date, Time, HomeOwner, Home, Away, AwayOwner, Stage]`
  - `_HOME_UPCOMING_COLS` = `[Date, Time, HomeOwner, Home, Away, AwayOwner, Stage]` (no Match — home page only)
  - `_THIRD_COLS` = `[Group, Team, Who, PL, W, D, L, GS, GA, GD, PNT]`
- **Third-place standings**: computed from `compute_third_place_table(group_standings)` in callback; top 8 rows are normal weight, bottom 4 rows dimmed (opacity 0.6, `var(--text-faint)`) to indicate non-qualifiers
- Owner identity: left-border stripe on name cell + full row text colour (leaderboard/teams); injected owner column coloured by owner (groups/fixtures); unknown teams (e.g. "Winner of Match X") show blank owner column
- Eliminated teams: `color: var(--eliminated)` + `text-decoration: line-through` (no red)
- Header strip: wordmark left, timezone label + "Last updated" stacked right; footer: copyright left, social icons right. On mobile (≤480px) the wordmark stacks into two centred lines (no `·` separator), and the footer stacks into a centred column so the GS/GA toggle and the copyright lines all centre horizontally.
- Group mini-tables: compact (12px font, 5px padding, fixed narrow numeric columns) — no horizontal scroll

**`assets/s1.css`** — full design system (dark-only, greyscale palette):
- CSS custom properties in `:root` for all colours, surfaces, borders, text
- System font stack (no Google Fonts); `ui-monospace` for numeric columns
- Tab navigation styles: `.tab-nav`, `.tab-link`, `.tab-link.active`
- Page fade-in animation, responsive breakpoints at 768px / 480px. Mobile (≤480px) additionally stacks the header wordmark and footer copyright into centred two-line blocks (hiding their `·` separators) and reflows the footer to a centred column.
- DataTable rows and cells have no hover styling — Dash's bundled light-mode hover is neutralised in CSS, and our former dark-grey `--hover` rule has been removed. Hover affordances remain on tab nav, footer icons, GS/GA toggle button, and links — i.e. everything that is not a table
- Mobile breakpoints also tighten `.tab-link` (font/padding) and add `overflow-x: auto` + scrollbar suppression on `.tab-nav` so the four-tab nav fits on phones
- Dark-theme overrides for `dcc.Dropdown` (`.owner-filter` class) so the owner filter on the Results & Fixtures page matches the surrounding UI

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

`assets/draw_2026.csv` holds the live Who → Team mapping from the real draw. Round 1 (12 teams) is populated; further rounds will be appended as the draw progresses. Edit this file by hand only — there is no fake-draw generator (intentionally removed so the real draw cannot be overwritten). `assets/participants.csv` has the 12 confirmed names so the person leaderboard exists pre-draw.

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

## Deployment

- Host: Oracle Cloud always-free tier, URL: `sweepstakelads.stomlins.com`
- TLS + DNS via Cloudflare — tunnel UUID `dcd0bf6e-e2f4-4e36-9c2a-3f7d1b2566d7`, config at `/etc/cloudflared/config.yml`
- App directory: `/home/opc/sweepstakelads` (tracking `main` branch of `github.com/satomlins/sweepstakelads`)
- Systemd unit: `sweepstakelads.service` — `ExecStart=/usr/local/bin/uv run gunicorn app:server --bind 127.0.0.1:8050 --workers 1`
- Env file: `/etc/sysconfig/sweepstakelads` (currently empty; kept for future secrets)

### Steady-state update workflow

Push to `main` triggers auto-deploy via GitHub Actions (`.github/workflows/deploy.yml`):
1. Tests run (`uv run pytest -q`)
2. On success, SSH into Oracle via deploy key and run `scripts/deploy.sh`
3. `deploy.sh` pulls `main`, runs `uv sync --frozen`, restarts the service, and smoke-tests it

Manual deploy (fallback):

```bash
ssh stomlins-oracle
cd /home/opc/sweepstakelads
git pull
sudo systemctl restart sweepstakelads
# If pyproject.toml changed: uv sync  (before the restart)
```

Rollback: `git reset --hard <previous-sha>` on Oracle + `sudo systemctl restart sweepstakelads`. See `docs/DEPLOY_PLAN.md` for full instructions.

### Hard constraints (Oracle)

- Billing must stay $0 — always-free tier only
- No `setenforce 0` — work with SELinux, not around it
- Bind to `127.0.0.1` only — cloudflared handles public exposure
- `ExecStart` must not point into `/home/opc/.venv/` — use `/usr/local/bin/uv run ...`
- `EnvironmentFile` must live outside `/home/opc/` — use `/etc/sysconfig/<app>`

## Working practices

Before every commit, update CLAUDE.md to reflect any architectural, behavioural, or participant changes made in that session. The goal is that CLAUDE.md always gives an accurate picture of the current codebase to a future Claude session with no prior context.

`TODO.md` (repo root) is a holding area for small ideas the user has flagged but not yet specced. Items there are *unscheduled*: when the user is writing the spec for the next update (`updates_documentation/UPDATE-N.md`), ask whether any TODO items should be bundled into that update; on a yes, fold them in and clear them from `TODO.md` as part of the spec.

## Design spec

Full UI design spec is in `docs/DESIGN.md`. Implementation plan is in `docs/PLAN_2026.md`. Deployment notes are in `docs/DEPLOY_PLAN.md`. Per-update specs (one per shipped change tranche) live in `updates_documentation/UPDATE-N.md`.
