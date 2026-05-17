# UPDATE-2: Owner filter on the Results & Fixtures page

A single, self-contained feature: a multi-select dropdown at the top of the **Results & Fixtures** page that filters both the Results table and the Fixtures table to matches involving the selected owners' teams. Selecting "Scott" shows every fixture where Scott owns either the home or away team — nothing else. Selecting multiple names ORs them together. Selecting nothing shows everything (current behaviour).

## Branch

`feat/owner-filter` off `main`. Single PR.

After implementation, **do not merge**. Run `uv run python app.py` locally, share the dev URL with the user, and wait for confirmation that the look and feel are right before opening the PR for merge.

---

## Scope

**In:** A new dropdown on **Results & Fixtures only**. Filters `all-results-table` and `all-upcoming-table`.

**Out:**
- The Home page's `recent-table` and `upcoming-table` — those are deliberately tight summaries, no filter.
- The Leaderboard and Group Stages pages — filter is fixtures-specific.
- Saving filter state across page navigations or refreshes — not requested; component state inside `dcc.Dropdown` is enough.
- A "select all" shortcut — emptying the box is already the equivalent.

---

## Behaviour

1. **Options.** Exactly the 12 confirmed participants, in the order they appear in `COLOURS` (the canonical ordering already used throughout the app):
   `Scott, Hugo, Sam, Brendan, Isaac, Adrian, Alex, Mary, Keshy, Jacob, Seth, Ella`.
   Hard-code by iterating `COLOURS.keys()` — do **not** derive from the live draw, because that would mean an empty dropdown pre-draw and would re-introduce blank/TBC entries the user explicitly does not want.
2. **Default.** No names selected → both tables show all fixtures (identical to current behaviour). Placeholder text: `"All owners"`.
3. **Multi-select.** `multi=True`. Each selected name appears as a removable chip inside the control.
4. **Filter predicate.** A row passes if `HomeOwner ∈ selected ∨ AwayOwner ∈ selected`. Unowned teams (placeholder names like "Winner of Match 57", or teams not yet drawn) have `HomeOwner == ""` / `AwayOwner == ""` and therefore never pass when any filter is active — exactly what the user wants.
5. **Sort order is preserved.** Filtering is applied **after** `_localize_fixtures` and `_add_owner_cols`, so the existing chronological sort (descending for results, ascending for fixtures) is unaffected.
6. **Empty state.** If the filter eliminates every row, the DataTable renders an empty body — no special "no matches" message. The dropdown chips make it obvious what was selected; that's enough.

---

## Files to change

### 1. `app.py` — layout

Add the dropdown as the **first child** inside `page-fixtures` (currently `app.py:459-477`), before the Results section:

```python
html.Div(
    [
        html.Label(
            "Filter by owner",
            htmlFor="owner-filter",
            style={
                "fontSize": "11px",
                "fontWeight": "600",
                "letterSpacing": "0.08em",
                "textTransform": "uppercase",
                "color": "var(--text-faint)",
                "margin": "0 0 6px",
                "display": "block",
            },
        ),
        dcc.Dropdown(
            id="owner-filter",
            options=[{"label": name, "value": name} for name in COLOURS.keys()],
            value=[],
            multi=True,
            placeholder="All owners",
            clearable=True,
            className="owner-filter",
        ),
    ],
    className="owner-filter-wrap",
    style={"marginBottom": "20px", "maxWidth": "520px"},
),
```

Notes:
- `COLOURS` is already imported at module scope — reuse it; do not re-list the 12 names anywhere.
- `clearable=True` because the user wants it easy to wipe selections; the `×` icon next to the chips handles per-chip removal regardless.
- The wrapper `className="owner-filter-wrap"` exists only for the responsive width rule in CSS — see §3.

### 2. `app.py` — callback wiring

Add a new `Input` to `update_all` (`app.py:606-609`):

```python
Input("owner-filter", "value"),
```

Position: after `Input("show-goals", "data")`. Add a new parameter `selected_owners` to the function signature, in the same position:

```python
def update_all(n, tz_offset_minutes, show_goals_data, selected_owners):
```

`dcc.Dropdown` with `multi=True` and no `value` sends `None` on initial load; defend with `selected_owners = selected_owners or []` at the top of the function so the `[]` default works regardless of how Dash fires the first callback.

Apply the filter in two places — **after** `_add_owner_cols` has already produced the `HomeOwner` and `AwayOwner` columns (`app.py:732` and `app.py:737`):

```python
# All results (fixtures page — newest first)
all_finished = fixtures[fixtures["Status"] == "Finished"].iloc[::-1]
all_finished_loc = _localize_fixtures(all_finished, tz_minutes)
all_results_out = _add_owner_cols(all_finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage"]])
if selected_owners:
    all_results_out = all_results_out[
        all_results_out["HomeOwner"].isin(selected_owners)
        | all_results_out["AwayOwner"].isin(selected_owners)
    ]

# All upcoming (fixtures page — ascending datetime order)
all_upcoming = fixtures[fixtures["Status"] == "Upcoming"]
all_upcoming_loc = _localize_fixtures(all_upcoming, tz_minutes)
all_upcoming_out = _add_owner_cols(all_upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])
if selected_owners:
    all_upcoming_out = all_upcoming_out[
        all_upcoming_out["HomeOwner"].isin(selected_owners)
        | all_upcoming_out["AwayOwner"].isin(selected_owners)
    ]
```

Leave `recent_out` and `upcoming_out` (home page) untouched.

The `switch_page` callback is **not** touched — it operates on tab class/page style outputs only.

### 3. `assets/s1.css` — dark theme for the dropdown

`dcc.Dropdown` is react-select v1 under the hood, which ships with a light, white-background look. Without CSS overrides it will look jarring on the dark page. Add rules (placement: near the bottom of `s1.css`, alongside other component overrides like `.goals-toggle-btn`):

```css
/* ── Owner filter (dcc.Dropdown, react-select v1) ───────────────────────── */
.owner-filter .Select-control,
.owner-filter.is-focused:not(.is-open) > .Select-control {
    background-color: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    box-shadow: none;
    border-radius: 4px;
    min-height: 36px;
}

.owner-filter .Select-control:hover {
    border-color: var(--text-faint);
}

.owner-filter .Select-placeholder,
.owner-filter .Select-input > input {
    color: var(--text-faint);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 13px;
}

.owner-filter .Select-input > input {
    color: var(--text);
}

.owner-filter .Select-arrow {
    border-color: var(--text-faint) transparent transparent;
}

.owner-filter.is-open .Select-arrow {
    border-color: transparent transparent var(--text-faint);
}

/* Selected chips (multi mode) */
.owner-filter .Select--multi .Select-value {
    background-color: var(--surface-2, #1f1f1f);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 3px;
    font-size: 12px;
    margin: 3px 4px 0 0;
}

.owner-filter .Select--multi .Select-value-label {
    color: var(--text);
    padding: 2px 6px;
}

.owner-filter .Select--multi .Select-value-icon {
    border-right: 1px solid var(--border);
    color: var(--text-faint);
    padding: 1px 6px;
}

.owner-filter .Select--multi .Select-value-icon:hover {
    background-color: transparent;
    color: var(--text);
}

/* Dropdown menu */
.owner-filter .Select-menu-outer {
    background-color: var(--surface);
    border: 1px solid var(--border);
    color: var(--text);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
}

.owner-filter .Select-option {
    background-color: transparent;
    color: var(--text);
    font-size: 13px;
    padding: 8px 12px;
}

.owner-filter .Select-option.is-focused {
    background-color: rgba(255, 255, 255, 0.05);
    color: var(--text);
}

.owner-filter .Select-option.is-selected {
    background-color: rgba(255, 255, 255, 0.08);
    color: var(--text);
}

/* Mobile: let the filter stretch a bit on phones */
@media screen and (max-width: 480px) {
    .owner-filter-wrap {
        max-width: 100% !important;
    }
}
```

If `--surface-2` doesn't exist in the `:root` block, fall back to a literal `#1f1f1f` (already in the rule). Sonnet, check `s1.css` first — if there's already a slightly-lighter surface variable, prefer that; otherwise leave the literal.

---

## Tests

No new test required. Filtering is two `df[df["col"].isin(...)]` lines — there's no pure-logic surface area to regress. Existing `pytest -q` must stay green; that's the only test bar.

(If Sonnet feels strongly about a smoke test for the filter predicate, a tiny `tests/test_owner_filter.py` covering "single owner picks home and away matches" + "multi-select unions" is fine but explicitly optional.)

---

## CLAUDE.md updates (mandatory)

Sonnet must update CLAUDE.md in the same commit:

1. Under the **Architecture → `app.py`** section, in the bullet describing the Results & Fixtures page, append: "Page has an `owner-filter` multi-select dropdown above the Results section; selecting one or more owners restricts both the Results and Fixtures tables to matches where the home or away team belongs to a selected owner (default empty = no filter)."
2. Under **Architecture → `app.py`** in the `update_all` description, add the new `Input("owner-filter", "value")` to the listed inputs.
3. Under **Architecture → `assets/s1.css`**, add a one-line bullet: "Dark-theme overrides for `dcc.Dropdown` (`.owner-filter` class) so the owner filter on the Results & Fixtures page matches the surrounding UI."

No change needed to participant/colour/draw sections.

---

## Verification before opening the PR

1. `uv run pytest -q` — green.
2. `uv run python app.py`, then in a browser:
   - **Navigate to `/fixtures`.** Dropdown is visible at the top of the page, labelled "Filter by owner", placeholder "All owners". The two tables below show every result and every fixture (same as before the change).
   - **Open the dropdown.** All 12 names appear in `COLOURS` order. No "TBC", no blank entry, no placeholder team names.
   - **Pick "Scott".** Both tables shrink to only rows where Scott owns the home or away team. (Pre-draw, this leaves the tables empty — that is correct and expected.)
   - **Add a second name.** Both tables expand to the union.
   - **Click the `×` on a chip.** That owner is removed; tables update.
   - **Clear all chips (click the global `×` or remove them one by one).** Tables return to "all rows".
   - **Sort order check.** Results table is still newest-first; fixtures table is still ascending datetime. Filtering does not reorder anything.
   - **Other tabs unchanged.** Navigate to `/`, `/leaderboard`, `/groups` and confirm none of them show the dropdown and the home page's "Recent results" / "Upcoming fixtures" are unaffected.
3. **Dark-theme styling.** Dropdown background, border, chip colour, menu background, hover state — none of them flash white. If anything looks light/unstyled, the CSS class on the `dcc.Dropdown` isn't matching; double-check the `className="owner-filter"` wiring.
4. **Mobile (DevTools at 480px).** Dropdown stretches to the content width via the `@media` rule; chips wrap onto multiple rows inside the control as more are selected. Nothing horizontally overflows.
5. **Show GS/GA toggle still works** on the Results & Fixtures page — it doesn't share columns with the fixture tables, so it shouldn't be affected, but worth a single sanity click.

If everything looks right, share the dev URL with the user. Do **not** open the PR until the user has eyeballed it and given the OK.

---

## Ship

1. User confirms it looks right → open the PR.
2. Wait for CI.
3. Ask before merging (deploy is user-visible).

---

## Things to flag while implementing

- **Initial-load `None` from the dropdown.** Confirm the `selected_owners = selected_owners or []` guard is in place. Without it, `selected_owners.isin(...)` would throw on first render.
- **react-select class names.** These are stable in the Dash version pinned by `uv.lock` (react-select v1.x). If Sonnet finds the CSS isn't taking effect, the most likely culprit is a Dash version bump that switched to react-select v2 (different class names — `.Select__control`, `.Select__option`, etc., with double underscores). If that happens: stop, flag to the user, do not chase it down inside this PR.
- **`COLOURS` is the single source of truth.** Don't re-derive the option list from `assets/participants.csv` — that file is informational only; `COLOURS` is what every other UI surface uses to colour rows.
- **The `Stage` filter is unchanged.** This PR is owner-only. If a future request asks to also filter by group/knockout, that is UPDATE-3.

---

## Out of scope (do not expand the PR)

- Persisting the filter across page reloads (query string, localStorage, etc.).
- A "Reset" button — the built-in `×` clear is enough.
- Showing the count of filtered matches anywhere — tables render their own row counts implicitly.
- Touching the Home page's recent/upcoming snippets.
- Replacing `dcc.Dropdown` with a custom component to avoid the react-select CSS overrides.
