# UPDATE-7: Round 2 of the 2026 draw

Round 2 of the real-world WC2026 draw has been held. Twelve new team→owner
mappings are appended to `assets/draw_2026.csv`. Each owner now owns two
teams. There are no code changes.

## Round 2 picks

| Owner   | Team           |
|---------|----------------|
| Keshy   | Scotland       |
| Mary    | Norway         |
| Brendan | Egypt          |
| Hugo    | Panama         |
| Adrian  | Tunisia        |
| Ella    | Czech Republic |
| Jacob   | Sweden         |
| Isaac   | Algeria        |
| Seth    | Canada         |
| Alex    | Paraguay       |
| Scott   | Ivory Coast    |
| Sam     | DR Congo       |

Team-name strings exactly match the values emitted by `scraper._code_to_name`
(notably `"Czech Republic"`, `"Ivory Coast"`, `"DR Congo"`). All twelve names
are already present as keys in the `FLAGS` dict in `app.py`, so the flag
toggle continues to work for every owned team.

## Branch

`feat/draw-round-2` off `main`. Single PR. Merge after CI is green;
auto-deploy runs on merge per `.github/workflows/deploy.yml`.

## Scope

**In:**

- `assets/draw_2026.csv` — append 12 rows for round 2.
- `CLAUDE.md` — update the one-line "Draw status" note to reflect rounds 1
  and 2 populated.
- `updates_documentation/UPDATE-7.md` — this file, for the documentation trace.

**Out:**

- Any change to `scraper.py`, `scoring.py`, `tournament.py`, `app.py`, CSS,
  tests, or any other code. The scoring, group-standings, and person-table
  logic already aggregate per-owner across multiple teams; the app reads
  `assets/draw_2026.csv` on each refresh.
- Any change to `FLAGS` — every round-2 team is already mapped.
- Cache invalidation. `tournament.refresh()` re-reads the draw via
  `load_draw()` on each cache refresh; the live deploy picks up the new
  ownership on the next 5-minute tick (or immediately on restart).

## Verification

1. `uv run pytest -q` — green (no code touched).
2. `uv run python app.py` locally:
   - Person leaderboard lists 12 owners; each has two teams' totals summed.
   - Team Table shows 24 owned rows.
   - Group Stages: groups containing newly-drawn teams show those teams
     coloured by their new owner; the `Who` column is populated.
   - Flag toggle: every owned team's flag renders.
3. After merge to `main`, watch the deploy workflow go green and confirm on
   `sweepstakelads.stomlins.com`.

## Ship

1. Commit on `feat/draw-round-2`.
2. Push, open PR, wait for CI, merge.
3. Auto-deploy runs on merge.
