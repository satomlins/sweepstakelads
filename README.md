# sweepstakelads

A sweepstake dashboard for the 2026 World Cup. Twelve players, four teams each,
one winner at the end of July. The app tracks live results, computes standings
per person, and shows group tables, fixtures, and the knockout bracket.

Live at **[sweepstakelads.stomlins.com](https://sweepstakelads.stomlins.com)**.

## What it does

- Pulls match data from Wikipedia (one batched HTTP request for all 13 pages)
- Computes a leaderboard by aggregating each person's four teams
- Shows group standings, the full fixture list with local times, and the
  knockout stage bracket
- Caches results for 5 minutes; background refresh so the UI never blocks
- Dark, greyscale design — each participant has a colour that follows their
  teams across every table

## Running locally

Dependencies are managed with [uv](https://github.com/astral-sh/uv).

```bash
uv sync
uv run python app.py        # starts dev server at http://localhost:8050
```

To work on the UI without hitting Wikipedia, seed fake data first:

```bash
uv run python dev_seed.py   # writes cache files + sets timestamp 24h ahead
uv run python app.py
```

## Tests

```bash
uv run pytest -q
```

Scraper tests run against pinned wikitext snapshots in `tests/fixtures/` —
they'll catch silent zero-match failures if Wikipedia changes its template
format. Scoring tests cover the full rules: regular wins, extra time, penalties,
group draws, and the third-place playoff.

To regenerate the wikitext snapshots from the live pages:

```bash
uv run python scripts/refresh_fixtures.py
```

## Deployment

Runs on Oracle Cloud (always-free tier) behind a Cloudflare tunnel. Pushes to
`main` trigger a GitHub Actions workflow that runs tests and, on success, SSHs
into the server and runs the deploy script.

See `docs/DEPLOY_PLAN.md` for the full setup.

## Codebase

| File | What it does |
|---|---|
| `app.py` | Dash layout and callbacks |
| `tournament.py` | Orchestration, caching, background refresh |
| `scoring.py` | Pure scoring functions — no I/O |
| `scraper.py` | Wikipedia fetch and parse |
| `dev_seed.py` | Fake data generator for UI development |
| `assets/s1.css` | Stylesheet |
