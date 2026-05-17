# UPDATE-1: UI tidy-up tranche

Four discrete UI changes, all in one PR off `main`.

## Branch

`ui-tidy-tranche-1` off `main`. Single PR; if any one piece gets gnarly Sonnet can split, but at first glance each change is small.

---

## Change 1: Remove "TBC" from leaderboards

**Source:** `scoring.py:132-134` puts the literal string `"TBC"` into the `Who` column for any team the draw hasn't claimed. This pollutes two places:

- **Person table** (Home + Leaderboard pages): a row labelled `TBC` aggregates all 36 unowned teams' stats. Cosmetic noise right now, semantic noise once games start.
- **Team table** (Leaderboard page): the `Who` column shows `TBC` for unowned rows.

Group standings and the third-place table already use `.fillna("")` inside `app.py` (lines 615, 657), so they're unaffected.

**Fix** (in `scoring.py`):

1. In `compute_team_table` (line 130-134), change both `.fillna("TBC")` and the `else` branch to use empty string `""`.
2. In `compute_person_table` (read the function — it groups by `Who`), after the groupby, filter out the row where `Who == ""`. Don't sum unowned teams into a phantom row.

**Tests** (`tests/test_scoring.py`):

- `test_team_table_no_matches`, `test_team_table_with_result`, `test_team_table_empty_draw`, `test_team_table_in_out_flag` — will currently assert `"TBC"`; update to assert `""`.
- `test_person_table_sums_by_owner` and `test_person_table_empty` — confirm/add that no `Who == ""` row appears in the result.
- Add one explicit test: `test_person_table_excludes_unowned` — given two owned teams and two unowned, the resulting frame has exactly two rows.

**Cache invalidation:** `assets/persontable.csv` and `assets/teamtable.csv` currently contain `TBC` values from the last refresh. The 5-minute background refresh on prod will rewrite them automatically once the new scoring code lands; no manual cache delete needed. If you want it instant, run `uv run python -c "from tournament import refresh; refresh()"` locally and commit the regenerated CSVs as part of the PR. Recommendation: commit them — saves a 5-minute window of stale TBC after deploy.

---

## Change 2: New "Group Stage" tab

**Currently** the Fixtures & Results tab (`app.py:424-474`) contains five sections: groups, third-place, knockout, results, upcoming. Move two of them out.

**Layout (`app.py`):**

1. Add a fourth `dcc.Link` to the nav (line 360-367): `dcc.Link("Group Stage", href="/groups", id="tab-groups", className="tab-link")`. Suggested order: Home / Leaderboard / Group Stage / Fixtures & Results.
2. Add a new page div `id="page-groups"` containing the existing Groups section + Third-place standings section (currently `app.py:427-448`). Cut them from `page-fixtures` and paste here. Default `style={"display": "none"}`.
3. After this and Change 3, `page-fixtures` should contain only the Results section and the Upcoming fixtures section (currently `app.py:457-470`).

**Callback (`switch_page`, line 531-549):**

1. Add `Output("tab-groups", "className")` and `Output("page-groups", "style")` to the output list — there are now four tab classNames and four page styles.
2. Add a branch `if pathname == "/groups": return inactive, inactive, active, inactive, hide, hide, show, hide` (order matches the output list — Sonnet, double-check the tuple by reading lines 531-549 carefully; this changes from a 6-tuple to an 8-tuple and the existing returns also need to grow by two slots each).

**Callback (`update_all`):** No structural change — `group-tables` and `third-place-table` IDs are unchanged, so the existing Output wiring (lines 559-561) still works.

---

## Change 3: Remove the knockout stage table from Fixtures & Results

The full fixture list already includes all knockout matches with their owners, so the dedicated knockout table is redundant.

**Layout:** Delete the entire `html.Div(... id="knockout-section" ...)` block (`app.py:449-456`).

**Callback wiring:**

1. In `update_all`'s `@app.callback` decorator, remove `Output("knockout-table", "data")` and `Output("knockout-table", "style_data_conditional")` (lines 566-567).
2. In the function body, delete the knockout computation block (`app.py:695-702`).
3. In the return tuple, drop `ko_data` and the corresponding `fixture_fmt` slot (`app.py:718-719`). Count the return tuple carefully — every removed `Output` must drop its return value at the matching position.

**Constants:** `_KO_COLS` (`app.py:83`) becomes unused. Delete it.

---

## Change 4: Remove the Match column from the home-tab upcoming fixtures

Match numbers belong on the full fixture list, not the snippet on the home page.

**Constants:** Add a new column list at module scope alongside `_FIXTURE_COLS`:

```python
_HOME_UPCOMING_COLS = ["Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"]
```

Leave `_FIXTURE_COLS` alone — the all-upcoming table on the Fixtures & Results page keeps Match.

**Layout:** In the home page (`app.py:392`), change `_make_table("upcoming-table", _FIXTURE_COLS, ...)` to use `_HOME_UPCOMING_COLS`.

**Callback:** No data-projection change needed. The current line `upcoming_out = _add_owner_cols(upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])` produces a dict that still contains `Match`; the DataTable just ignores any data column not declared in its `columns=` spec. Leave the projection alone to keep churn minimal.

(If Sonnet prefers symmetry, dropping `Match` from the projection too is fine — it's a one-word edit. Either is acceptable; the former is less churn.)

---

## CLAUDE.md updates (mandatory)

Sonnet must update CLAUDE.md in the same commit to reflect:

- Nav is now **four** tabs, not three.
- Page contents:
  - **Home** — person leaderboard + recent results + upcoming fixtures (no Match column)
  - **Leaderboard** — person leaderboard + team table
  - **Group Stage** (new) — 12 group mini-tables + third-place standings table
  - **Fixtures & Results** — all results + all upcoming fixtures (no knockout table; that's redundant with the full fixture list)
- Scoring note: `compute_team_table` no longer labels unowned teams `"TBC"` (empty string instead); `compute_person_table` excludes unowned-team rows.
- Column-set constants: add `_HOME_UPCOMING_COLS`, remove `_KO_COLS` from the listed set.

---

## Verification before commit

1. `uv run pytest -q` — green, with the new/updated scoring tests.
2. `uv run python app.py` locally:
   - Navigate to `/` — no Match column on the upcoming list; no TBC row on the leaderboard.
   - Navigate to `/leaderboard` — no TBC row, no TBC values in the `Who` column.
   - Navigate to `/groups` — 12 group tables + third-place table. Tab highlights correctly.
   - Navigate to `/fixtures` — only Results + Upcoming sections; no Groups, no third-place, no knockout.
   - All four tabs highlight correctly when clicked; mobile breakpoint at 480px doesn't blow up (four nav links instead of three — flag to user if it wraps badly, don't try to fix unless asked).
3. If the regenerated CSVs are committed, eyeball `assets/persontable.csv` — should have 12 rows (one per participant), no TBC.

## Ship

One commit (or up to four small ones — Sonnet's call) → PR → wait for CI → ask before merging (deploy is user-visible).

## Out of scope

- The `python -m tournament` async refresh CLI bug (still outstanding from earlier).
- Refactoring the four near-identical fixture-table projection blocks in `update_all`.
- Cleaning up unused `_KO_COLS` etc. beyond what these changes require.
- Bumping deprecated GitHub Actions Node 20 runners.

## Things to flag while implementing

- The `switch_page` callback tuple grows from 6 to 8 outputs — careful with positional ordering. Adding tests for `switch_page` would be useful but isn't strictly required by this plan.
- If Sonnet finds that `compute_person_table` already filters something, or has unexpected merging behaviour, stop and ask rather than guessing.
- Four nav tabs on mobile: handled by Change 5 below (folded into the same PR after first-pass implementation revealed the overflow is real, not theoretical).

---

## Change 5: Mobile nav fits four tabs (added after Changes 1–4 landed locally)

**Problem.** With three tabs the desktop padding (`12px 20px`) and font (`12px / 0.06em`) just-about fit at the 480px breakpoint. The fourth tab pushes total nav width to ~513px against a ~448px content area at 480px viewport (after the existing `padding: 24px 16px 64px` from the 768px breakpoint), and far worse on real phones (≤360px). With no `flex-wrap` and no `overflow-x` on `.tab-nav`, this currently overflows the body and triggers horizontal page scroll — exactly the regression UPDATE-1's original "out of scope" note was hedging against.

The visual underline trick (`.tab-link { margin-bottom: -1px; }` overlapping `.tab-nav { border-bottom: 1px }`) requires the tabs to stay on a single row, so wrapping is not an option. Two viable shapes: tighten the tabs, or scroll horizontally. Use both — tighten so common phone widths fit on one row without scrolling, and add `overflow-x: auto` as a safety net for the narrowest screens.

**Fix** (in `assets/s1.css` only — no Python changes, no layout changes, no label changes):

1. Inside the existing `@media screen and (max-width: 768px)` block, add a `.tab-link` rule that reduces padding, font, and letter-spacing, and prevents per-tab text wrap:

   ```css
   .tab-link {
     padding: 10px 12px;
     font-size: 11px;
     letter-spacing: 0.04em;
     white-space: nowrap;
   }
   ```

2. Inside the existing `@media screen and (max-width: 480px)` block, add a `.tab-nav` overflow-scroll safety net (with cross-browser scrollbar hiding) and a further tightening of `.tab-link`:

   ```css
   .tab-nav {
     overflow-x: auto;
     -webkit-overflow-scrolling: touch;
     scrollbar-width: none;
   }

   .tab-nav::-webkit-scrollbar {
     display: none;
   }

   .tab-link {
     padding: 10px 10px;
     font-size: 10px;
     letter-spacing: 0.03em;
   }
   ```

**Why these numbers.** With the ≤480px values, the four tabs measure roughly: HOME ~46px, LEADERBOARD ~91px, GROUP STAGE ~91px, FIXTURES & RESULTS ~137px → **~365px total**, comfortably inside a 448px content area. At iPhone-SE-class 360px viewports (≈328px content) the total slightly overflows; the `overflow-x: auto` lets it scroll cleanly with the scrollbar suppressed for visual consistency with the rest of the dark UI.

**What this does NOT touch.**
- Tab order, labels, or routes (`/`, `/leaderboard`, `/groups`, `/fixtures`).
- The underline-on-active mechanism — `margin-bottom: -1px` continues to work because it's independent of font size.
- The home-page side-by-side tables — they already stack at 768px via the existing `.row { flex-direction: column }` rule. Their per-table column overflow on phones is a pre-existing issue and remains out of scope.
- Tablet/desktop tab appearance — the base `.tab-link` rule (12px font, 12px 20px padding) is unchanged; only the two existing mobile breakpoints are extended.

**Verification.**

1. `uv run python app.py`, open in browser, and use DevTools device emulation to confirm at:
   - **≥769px** (desktop): tabs look identical to the pre-PR three-tab nav, just with one more entry.
   - **768px**: tabs tighten visibly but all four fit on one row without horizontal scroll.
   - **480px**: tabs tighten further; all four fit; no horizontal page scroll on the body.
   - **360px** (iPhone SE): tabs may not all fit, but `.tab-nav` scrolls horizontally without a visible scrollbar and the body itself does not scroll horizontally.
2. Active-tab underline aligns flush with the bottom border of `.tab-nav` at every breakpoint.
3. Tapping any tab still navigates correctly (no JS change, so this is just a regression check).

**CLAUDE.md update for Change 5.** Append one line to the `assets/s1.css` bullet list noting that the mobile breakpoints now also tighten `.tab-link` and add a horizontal-scroll safety net to `.tab-nav` so the four-tab nav fits on phones.

**Out of scope for Change 5 (do not expand the PR).**
- Redesigning the tab nav as a hamburger / dropdown on mobile — overkill for four tabs.
- Fixing per-table column overflow on phones — pre-existing, separate work.

---

## Change 6: Tab label / order polish (added post-implementation)

Three small label and ordering tweaks requested after seeing the four-tab nav running locally. Pure `app.py` label changes — no routing, no callback, no CSS changes.

1. **Rename tab**: `"Fixtures & Results"` → `"Results & Fixtures"` (`app.py` nav, `id="tab-fixtures"`).
2. **Reorder tabs**: move Group Stages to the end — new order is Home / Leaderboard / Results & Fixtures / Group Stages. The `switch_page` callback Outputs reference element IDs, not DOM positions, so the return tuples are unchanged.
3. **Rename tab**: `"Group Stage"` → `"Group Stages"` (`app.py` nav, `id="tab-groups"`).
4. **Rename section heading**: on the Results & Fixtures page (`page-fixtures`), `html.H3("Upcoming fixtures")` → `html.H3("Fixtures")`. The home-page heading (`"Upcoming fixtures"` inside `page-home`) is left unchanged.

**CLAUDE.md updates:** Tab order and page names updated to reflect the above.
