# Elimination logic + Group-stage tiebreakers

Two correctness fixes to scoring. Both live in `scoring.py`; one downstream
display consequence in `app.py`.

---

## 1. Elimination (the strikethrough rule)

### Rule

A team is **Out** only when both of the following hold:

1. The team has played 3 group matches (`PL == 3` in `compute_group_standings`).
2. The team is either **bottom of its group** (last row of the
   H2H-ranked standings; group has 4 teams) **or** in the **bottom 4 of
   the third-place table**.

Anything else is **In**, including:

- A team mid-group-stage (PL &lt; 3) — even if currently last.
- A 3rd-placed team that has so far avoided the bottom 4 of the
  cross-group third-place ranking.
- A team that lost a knockout match. Knockout results deliberately do
  not change `In`/`Out`; the leaderboard only reflects group-stage
  position.

### Why this rule

The previous rule ("any non-finished match remaining") wrongly flagged
every team as Out the moment its group matches finished, because future
knockout fixtures use placeholder names like `"Winner of Match 73"`.
A purely mathematical version was tried (3rd-placer worst-case rank
across all 12 groups) but produced surprising edge cases and was harder
to reason about. The simple rule above matches how a viewer scanning the
group tables would decide who is out.

### Implementation

- `_team_out_status(team, group_standings, matches)` in `scoring.py` is
  the source of truth. The `matches` argument is accepted for signature
  compatibility but not used — only `group_standings` matters.
- `compute_team_table` calls `compute_group_standings` once and applies
  `_team_out_status` to every team to populate the `In` column.
- "Bottom of group" uses `gdf.iloc[-1]` of the FIFA-H2H-ranked group
  standings (so the H2H tiebreaker resolves the bottom slot too).
- "Bottom 4 of third-place table" uses
  `compute_third_place_table(group_standings).tail(4)` and skips if the
  table has fewer than 4 rows (early-tournament safety).

### Display

No CSS or layout change. `_eliminated_rule()` in `app.py` keys off
`{In} = 'Out'`; once `In` is correct, the strikethrough is correct.

---

## 2. Group-stage tiebreakers

### Symptom

Group mini-tables sort by `PTS → GD → GS` only. FIFA uses head-to-head
criteria before falling back to overall GD/GS, so the displayed order
can disagree with the actual qualification order.

### Correct rule (FIFA 2026, as supplied)

When two or more teams in the same group are level on points, apply in
order:

**Step 1 — among the tied teams only:**

1. Greatest points obtained in matches between the tied teams.
2. Superior goal difference in matches between the tied teams.
3. Greatest goals scored in matches between the tied teams.

If Step 1 separates *some* but not *all* of the tied teams, the criteria
in Step 1 are re-applied to the still-tied subset before moving to Step 2.

**Step 2 — overall, only if teams are still tied after Step 1:**

4. Superior goal difference across all group matches.
5. Greatest goals scored across all group matches.

(Further FIFA tiebreakers — fair-play points, drawing of lots — are out
of scope for this update.)

### Where it applies

- `scoring.py::compute_group_standings` — the 12 group mini-tables on the
  Group Stages page.

### Where it does **not** apply

- `scoring.py::compute_third_place_table` — these 12 teams are from
  different groups and have not played each other, so head-to-head is
  undefined. Continue sorting by overall `PTS → GD → GS`. (FIFA does
  define further criteria for this cross-group case; out of scope here.)
- `compute_team_table` and `compute_person_table` sort orders are
  display-level (sortable DataTable columns / a leaderboard); they are
  not group standings and don't change.

### Implementation notes

- Write `_rank_group(teams, matches)` in `scoring.py` that takes the
  group's team stats dict and the list of group matches between those
  teams, and returns teams in finishing order. Tested via
  `tests/test_scoring.py` with at least:
  - 2-way tie broken by head-to-head result
  - 3-way tie broken by head-to-head (mini-table among the three)
  - 3-way tie where head-to-head separates one team and the other two
    still need overall GD
  - Tie unresolved by head-to-head, broken by overall GD
  - Tie unresolved everywhere down to overall GS
- The "matches between the tied teams" subset is built from the existing
  match list — filter to matches where both `home_team` and `away_team`
  are in the tied set, and which have `status == "finished"`. If a
  head-to-head match is still unplayed, the head-to-head mini-table is
  computed on what's been played; an unplayable tiebreaker is fine,
  Step 2 will resolve it.
- Keep `_apply_match` as-is; the head-to-head computation reuses it by
  feeding it a filtered match list into a fresh stats dict.
- Return the same DataFrame columns as today — sort order is the only
  thing changing.

### Display

No layout or styling change. The mini-tables already render whatever
order they receive.

---

## Tests

Update `tests/test_scoring.py` with:

- `test_team_out_*` / `test_compute_team_table_in_uses_elimination` — at least:
  - Team that has played 3 group games and topped the group → `In`.
  - Team that has played 3 group games and is bottom of its group → `Out`.
  - Team that is 3rd in a group and in the bottom 4 of the third-place
    table (12 complete groups) → `Out`.
  - Team that is 3rd in a group but in the top 8 of the third-place
    table → `In`.
  - Team mid-group-stage (`PL < 3`), currently last → `In`.
  - Team that lost a knockout match but topped its group → `In`.

- `test_compute_group_standings_head_to_head_*` — at least the five
  tiebreaker scenarios listed above.

Existing `test_scoring.py` assertions for the simple `PTS → GD → GS`
groups should continue to pass (only the tiebreaker logic changes, not
the base ordering).

---

## Out of scope

- Person leaderboard sort order (unchanged: PTS → GD → GS).
- Third-place ranking tiebreakers beyond overall GD/GS.
- Any UI / CSS changes — both fixes are pure scoring.
- Caching format: `teamtable.csv` and `group_standings.json` columns are
  unchanged; only the `In` value and the row order change.
