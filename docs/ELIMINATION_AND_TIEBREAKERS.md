# Elimination logic + Group-stage tiebreakers

Two correctness fixes to scoring. Both live in `scoring.py`; one downstream
display consequence in `app.py`.

---

## 1. Elimination (the strikethrough bug)

### Symptom

On the country leaderboard, every team that has played 3 matches is shown
with a strikethrough — even teams that have just topped their group and
are clearly through.

### Root cause

`scoring.py::compute_team_table` sets `In = "Out"` for any team that
**does not appear in a not-yet-finished match**:

```python
in_teams: set[str] = set()
for m in matches:
    if m["status"] != "finished":
        in_teams.add(m["home_team"])
        in_teams.add(m["away_team"])
df["In"] = df["Team"].apply(lambda t: "In" if t in in_teams else "Out")
```

The bug: knockout fixtures use placeholder names like `"Winner of Match 73"`
until the bracket fills in. So once a real team has played its 3rd group
match, its real name no longer appears in any unfinished fixture — the
unfinished fixtures all reference placeholders. Result: every team gets
flagged `Out` the instant their group matches finish.

### Correct rule

A team is **Out** only when its tournament is mathematically over. There
are three ways that happens:

1. **Finished 4th in its group** — the group has played all 6 matches
   (so the 4th-placed team is locked in), and the team is in 4th.
2. **Finished 3rd in its group AND mathematically cannot reach the top 8
   of all 12 third-placed teams.** Both conditions matter:
   - The team's own group must have completed (their 3rd-place stats
     are locked in).
   - Across all 12 groups, considering every remaining 3rd-place
     possibility (groups whose 3rd-placer is not yet determined),
     there is no scenario in which 8 other teams could finish below
     this team on the 3rd-place ranking.
3. **Lost a knockout match** (R32 onwards). The team is the named loser
   of a finished knockout fixture.

Anything else is **In**, including:

- A team that has finished 3rd in its group but is still mathematically
  in contention for the top-8-of-3rds slot.
- A team that has finished 3rd and is currently outside the top 8 of
  3rd-placers, but where some 3rd-place slots in other groups are still
  to be determined and could plausibly come in below them.
- A team between knockout rounds that has not yet lost.

### Implementation notes

- The "mathematically cannot reach top 8 of 3rds" check needs to consider
  the worst-case-for-the-team finishing position of every still-undetermined
  3rd-placer. For any group whose 3 matches are not all complete, treat
  the eventual 3rd-placer as a free variable that could finish anywhere
  from "below this team" to "above this team" on the cross-group ordering.
  A team is only eliminated if even when **all** free variables resolve
  "above this team", it would still be 9th or lower among 3rd-placers.
- The simplest correct version: only mark a 3rd-placed team Out once
  enough groups have completed that the top 8 of 3rd-placers is fully
  determined and this team is not in it. (Cheaper to compute, slightly
  later marker; acceptable because the UI is read-only.)
- Recommend implementing both `_team_out_status(team, group_standings,
  matches)` as a pure helper and replacing the current `in_teams` block.
- The 4th-place check needs the group to be "complete" — `PL == 3` for
  every team in the group is the simplest test.
- Knockout losses already work implicitly today (any knockout-stage
  loser team doesn't have a future *real-name* fixture either, but they
  also shouldn't — they're genuinely Out). Make sure the new logic
  preserves that.

### Display

No CSS or layout change needed. `_eliminated_rule()` in `app.py` already
keys off `{In} = 'Out'`; once `In` is correct, the strikethrough is correct.

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

- `test_compute_team_table_in_out_*` — at least:
  - Team that has played 3 group games and topped the group → `In`.
  - Team that has played 3 group games and is 4th in a fully-completed
    group → `Out`.
  - Team that is 3rd in a fully-completed group, with enough other
    groups complete to confirm it as a non-qualifier → `Out`.
  - Team that is 3rd in a fully-completed group, with other groups
    still in progress such that it might still reach top 8 → `In`.
  - Team that lost an R32 knockout match → `Out`.

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
