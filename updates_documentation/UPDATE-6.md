# UPDATE-6: Footer toggle to swap country names for flag emojis

A second toggle button in the footer, sitting alongside the existing "Show GS/GA"
button. When pressed, every country name in every table (Team Table, Group
Standings mini-tables, Third-Place table, Fixtures, Results) is replaced with
the country's flag emoji. Press again to swap back.

The toggle is a **swap**, not an addition: a cell shows the name *or* the flag,
never both. The button label flips between `Show flags` and `Show names` to
reflect what pressing it will do.

The motivation is screen real-estate on phones — full country names eat a lot
of horizontal space in the fixtures table, especially with `Bosnia and
Herzegovina` and `United Arab Emirates`. Flags collapse to one or two glyphs.

---

## Branch

`feat/flag-toggle` off `main`. Single PR. Merge after CI is green and after
clicking the toggle on every page once locally to verify cells swap.

---

## Scope

**In:**

- A `FLAGS` dict at module scope in `app.py`, mapping the *output* country
  names produced by `scraper._code_to_name` to flag-emoji strings.
- A `dcc.Store(id="show-flags", data=False)` mirroring `show-goals`.
- A new `html.Button("Show flags", id="flags-toggle", className="goals-toggle-btn", n_clicks=0)`
  in the footer, immediately to the right of the existing `goals-toggle`
  button. **Same CSS class** as `goals-toggle-btn` — the existing styling fits
  this exactly.
- A `toggle_flags` callback mirroring `toggle_goals` — flips the store, flips
  the button label between `Show flags` ↔ `Show names`.
- A new `Input("show-flags", "data")` on the existing `update_all` callback.
- A helper `_apply_flags(df, cols, show)` that, when `show` is true, replaces
  each value in the listed columns with `FLAGS.get(value, value)`. Falls back
  to the original string when a team isn't in `FLAGS`.
- Wire `_apply_flags` into `update_all`:
  - Team Table: substitute `Team` column.
  - Group mini-tables: substitute `Team` column in each per-group DataFrame.
  - Third-Place table: substitute `Team` column.
  - Fixtures DataFrame (the shared `fixtures_loc` used to derive all four
    results/upcoming projections): substitute `Home` and `Away` columns
    **after** the owner-filter step and **before** the four output projections
    are built.
- Short additions to `CLAUDE.md` documenting the toggle and the `FLAGS` map.
- One new test file `tests/test_flags.py` covering the helper.

**Out:**

- Owner names (`Who`, `HomeOwner`, `AwayOwner` columns). Owners are people,
  not countries — never substituted.
- The `Stage` column (`Group A`, `Round of 16`, etc.). Stage is not a country.
- Knockout placeholder names like `Winner of Match 57` — fall through to the
  original string via `FLAGS.get(name, name)`. No special-case needed.
- A flags-only column or a "flag + name" side-by-side layout. The toggle is a
  pure swap.
- Per-table override toggles. One global toggle, applied everywhere.
- Persisting the toggle state across browser sessions. The store resets to
  `False` on reload, same as `show-goals`.
- Any change to `scraper.py`, `scoring.py`, `tournament.py`, or `assets/*.csv`.
- Touching the owner-colour stripe, the eliminated-team styling, or the
  winning-team bolding. All four interact with the team-name cell but each is
  keyed on different attributes (`column_id` / row-data filters) — the cell's
  text content changes, but the styling rules don't reference the text.

---

## Files to change

### 1. `app.py` — `FLAGS` dict at module scope

Place directly under the existing `COLOURS` dict (find the comment block for
participants/colours and put `FLAGS` right after it). Starter content:

```python
# Country name -> flag emoji. Keys must match the output of
# scraper._code_to_name exactly. Unmapped names fall through to the
# original string at substitution time (see _apply_flags).
FLAGS = {
    # Hosts (auto-qualified)
    "United States": "🇺🇸",
    "Mexico":        "🇲🇽",
    "Canada":        "🇨🇦",
    # Currently owned (assets/draw_2026.csv as of 2026-05-21)
    "Qatar":                   "🇶🇦",
    "New Zealand":             "🇳🇿",
    "Bosnia and Herzegovina":  "🇧🇦",
    "Iraq":                    "🇮🇶",
    "South Africa":            "🇿🇦",
    "Saudi Arabia":            "🇸🇦",
    "Haiti":                   "🇭🇹",
    "Jordan":                  "🇯🇴",
    "Ghana":                   "🇬🇭",
    "Uzbekistan":              "🇺🇿",
    "Cape Verde":              "🇨🇻",
    "Curaçao":                 "🇨🇼",
}
```

The implementer can (and should) extend this dict to cover the remaining
finalists as they appear in `draw_2026.csv` or in live scraper output. **Every
value in `scraper.FIFA_TEAM_NAMES` is a legitimate key candidate** — running a
quick `set(FIFA_TEAM_NAMES.values())` and filling in flags for each is a
worthwhile one-off pass. But the minimum to ship is the 15 entries above;
unmapped names render as text and the toggle is still useful for the teams
that are mapped.

Special cases for the implementer to handle when extending:

- **UK home nations** (`England`, `Scotland`, `Wales`, `Northern Ireland`)
  have subdivision flag emojis using black-flag + VS-16 + tag sequences. They
  render correctly on macOS/iOS but **not on Windows < 11 or older Android**.
  Include them; accept the platform gap. Sample sequences:
  - England: `"🏴\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F"`
  - Scotland: `"🏴\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F"`
  - Wales: `"🏴\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F"`
- **Northern Ireland** has no standard flag emoji. Use `"🇬🇧"` (UK flag) or
  leave it out so it falls through to text. Implementer's call.
- **Republic of Ireland** maps to `"🇮🇪"`.
- **Diacritics** in keys must match `_code_to_name` output exactly. `Curaçao`
  has a cedilla; `São Tomé` (if it ever appears) has a tilde. Copy/paste from
  `scraper.py` — don't retype.

Do **not** auto-derive flag emojis from ISO codes at runtime. Hardcoded dict
keeps the source of truth in one place that's grep-able and reviewable.

### 2. `app.py` — `dcc.Store` for the toggle state

In the layout block where the other stores are declared (around line 311),
add one line:

```python
dcc.Store(id="show-flags", data=False),
```

Place it immediately after the existing `dcc.Store(id="show-goals", data=False)`.

### 3. `app.py` — footer button

In the footer section (around lines 544–549), duplicate the goals-toggle
button block for flags. The result should be two adjacent buttons inside the
same `flex` container (gap `16px`, already set on line 551):

```python
html.Button(
    "Show GS/GA",
    id="goals-toggle",
    n_clicks=0,
    className="goals-toggle-btn",
),
html.Button(
    "Show flags",
    id="flags-toggle",
    n_clicks=0,
    className="goals-toggle-btn",
),
```

Same class — the existing `.goals-toggle-btn` CSS rules (border, padding,
hover) apply to both. No new CSS needed.

### 4. `app.py` — toggle callback

Immediately under the existing `toggle_goals` callback (around line 633), add
its twin:

```python
@app.callback(
    Output("show-flags",   "data"),
    Output("flags-toggle", "children"),
    Input("flags-toggle",  "n_clicks"),
    State("show-flags",    "data"),
    prevent_initial_call=True,
)
def toggle_flags(_n, current):
    show = not current
    return show, "Show names" if not current else "Show flags"
```

Note the label flip: pressing while in "names mode" sets `show=True` and shows
the label `Show names` (because the *next* press will swap back). Pressing
while in "flags mode" sets `show=False` and shows `Show flags`. This mirrors
`toggle_goals` semantics where the label always describes what pressing will
do next.

### 5. `app.py` — `_apply_flags` helper

Place at module scope, near `_localize_fixtures` or `_add_owner_cols`. Pure
function, no side effects:

```python
def _apply_flags(df: pd.DataFrame, cols: list[str], show: bool) -> pd.DataFrame:
    """Return a new DataFrame with the listed columns replaced by flag emojis.

    When show is False, returns a shallow copy unchanged. When True, each cell
    in the listed columns is mapped through FLAGS; values not in FLAGS pass
    through as-is so knockout placeholders (e.g. 'Winner of Match 57') and
    unmapped finalists remain readable.
    """
    if not show or df.empty:
        return df.copy()
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = out[col].map(lambda v: FLAGS.get(v, v))
    return out
```

Why a copy: `update_all` derives multiple projections from the same source
DataFrames; mutating in place would leak flag substitution into projections
that should still show the original name (none today, but the copy keeps the
function honest).

Why `if col in out.columns`: defensive — the same helper is called against
multiple DataFrames with different schemas. Missing columns are a no-op rather
than a `KeyError`.

### 6. `app.py` — wire `_apply_flags` into `update_all`

Three integration points, all inside the existing `update_all` callback:

**6a. Pick up the new input.** Add to the callback's `Input` list (after
`Input("show-goals", "data")` around line 664):

```python
Input("show-flags",   "data"),
```

…and to the signature:

```python
def update_all(n, tz_offset_minutes, show_goals_data, show_flags_data, selected_owners):
    ...
    show_flags = bool(show_flags_data)
```

**Argument order must match input order.** Verify against the existing
`Input(...)` declarations before saving.

**6b. Apply to the standings tables.** After `team_df` and `groups` and
`third_df` are built (search for `compute_team_table`, `compute_group_standings`,
`compute_third_place_table` in `update_all`), wrap each in `_apply_flags` before
they feed into the `data=` and `style_data_conditional` outputs:

```python
team_df    = _apply_flags(team_df,    ["Team"], show_flags)
third_df   = _apply_flags(third_df,   ["Team"], show_flags)
groups     = {g: _apply_flags(df, ["Team"], show_flags) for g, df in groups.items()}
```

**Order matters**: do this *after* any logic that filters or styles rows by
team name (currently nothing — team-name-based filtering doesn't exist), but
*before* the records are projected into `data=` for the output tables.

**6c. Apply to the fixtures DataFrame.** In `update_all`, after the owner
filter is applied to produce `finished_loc` / `all_finished_loc` /
`upcoming_loc` / `all_upcoming_loc` (the filtered, localised projections),
substitute `Home` and `Away` on each:

```python
finished_loc      = _apply_flags(finished_loc,      ["Home", "Away"], show_flags)
all_finished_loc  = _apply_flags(all_finished_loc,  ["Home", "Away"], show_flags)
upcoming_loc      = _apply_flags(upcoming_loc,      ["Home", "Away"], show_flags)
all_upcoming_loc  = _apply_flags(all_upcoming_loc,  ["Home", "Away"], show_flags)
```

**Critical ordering**: the owner filter matches against original team names
(it joins on the draw — `draw.set_index("Team")["Who"]`). If you substitute
flags first, the owner filter will fail to match because `🇧🇦` is not in the
draw. **Filter first, then substitute.** Triple-check this in the diff.

The owner-column derivation (`_add_owner_cols`) also keys on team names — it
must run *before* substitution, for the same reason. Same applies to the
`_RESULT_COLS` projection (which selects columns after substitution; column
values change but column ids do not).

### 7. `CLAUDE.md` — three small additions

Under **Architecture → `app.py`**, in the bullet block that describes column
sets / styling, add one new bullet (place it after the winning-team-bolding
bullet from UPDATE-5):

> - **Flag-emoji toggle**: footer button (`flags-toggle`) flips a
>   `dcc.Store(id="show-flags")` between `False` (names) and `True` (flags).
>   `update_all` reads the store and calls `_apply_flags(df, cols, show)` on
>   the Team Table, each Group Stages mini-table, the Third-Place table, and
>   the four fixture projections (`finished_loc`, `all_finished_loc`,
>   `upcoming_loc`, `all_upcoming_loc`) for the `Home` and `Away` columns. The
>   substitution falls back to the original name when a team is not in the
>   `FLAGS` dict, so knockout placeholders like `Winner of Match 57` and
>   unmapped finalists render as text. Substitution runs **after** the owner
>   filter and **after** `_add_owner_cols`, because both key on the original
>   team names. The toggle is a pure swap — cells show the name *or* the
>   flag, never both. State does not persist across reloads.

Under **Participants and colours**, add one new bullet at the bottom:

> - The `FLAGS` dict in `app.py` maps team names to flag emojis for the
>   footer toggle. Keys are the values emitted by `scraper._code_to_name`
>   (e.g. `"Bosnia and Herzegovina"`, `"Curaçao"`). Missing entries fall
>   through to the original name. UK home nations use subdivision flag
>   sequences (`🏴…`) that render on macOS/iOS only.

No other CLAUDE.md edits required.

### 8. `tests/test_flags.py` — new file

```python
"""Unit tests for app._apply_flags."""

import pandas as pd

from app import FLAGS, _apply_flags


def test_show_false_returns_unchanged_copy():
    df = pd.DataFrame({"Team": ["Brazil", "Qatar"], "Stage": ["Group A", "Group B"]})
    out = _apply_flags(df, ["Team"], show=False)
    assert list(out["Team"]) == ["Brazil", "Qatar"]
    assert out is not df  # copy, not the same object


def test_show_true_substitutes_mapped_names():
    df = pd.DataFrame({"Team": ["Qatar", "Ghana"]})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]
    assert out.loc[1, "Team"] == FLAGS["Ghana"]


def test_unmapped_falls_through_to_original():
    df = pd.DataFrame({"Team": ["Qatar", "Winner of Match 57"]})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]
    assert out.loc[1, "Team"] == "Winner of Match 57"  # unchanged


def test_multiple_columns_substituted_independently():
    df = pd.DataFrame({"Home": ["Qatar"], "Away": ["Ghana"], "Stage": ["Group A"]})
    out = _apply_flags(df, ["Home", "Away"], show=True)
    assert out.loc[0, "Home"] == FLAGS["Qatar"]
    assert out.loc[0, "Away"] == FLAGS["Ghana"]
    assert out.loc[0, "Stage"] == "Group A"  # untouched


def test_missing_column_is_noop():
    df = pd.DataFrame({"Team": ["Qatar"]})
    # 'Home' is not a column; should not raise.
    out = _apply_flags(df, ["Home", "Team"], show=True)
    assert out.loc[0, "Team"] == FLAGS["Qatar"]


def test_empty_dataframe_returns_empty_copy():
    df = pd.DataFrame({"Team": []})
    out = _apply_flags(df, ["Team"], show=True)
    assert out.empty
```

Notes for the implementer:

- These are pure-helper tests. No Dash app needed; importing `app` for the
  `FLAGS` constant is fine but slow — if app import side-effects bother the
  test runner (network call on first scrape, etc.), copy the relevant FLAGS
  entries into the test file as a small local dict. Default to importing
  unless that fails.
- Don't test the callbacks. `toggle_flags` is a one-liner and the integration
  is best verified manually (see below).

---

## Tests

`uv run pytest -q` must stay green. Six new tests should pass.

```bash
uv run pytest tests/test_flags.py -v
```

No existing tests should change outcome — `scraper.py`, `scoring.py`,
`tournament.py` are all untouched.

---

## Visual verification (do this before opening the PR)

`uv run python app.py` and click through every page with the toggle in both
states:

1. **Home page** — toggle the button. Person leaderboard is unaffected (no
   country column). Recent Results and Upcoming Fixtures cards: `Home` and
   `Away` cells should flip between names and flags. Owner columns
   (`HomeOwner` / `AwayOwner`) stay as people names.
2. **Leaderboard page** — Person Leaderboard unaffected. Team Table: the
   `Team` column flips. Owner colours (left-border stripe + row text colour)
   should still apply correctly — the stripe is on the cell, the text
   substitution doesn't touch styling.
3. **Group Stages page** — every group mini-table's `Team` column flips. The
   `Who` column (owner) stays unchanged. Third-place table: `Team` column
   flips, `Who` column stays. Dimmed bottom-4 styling (`opacity: 0.6`)
   should still apply because it's row-position-keyed, not text-keyed.
4. **Results & Fixtures page** — same as Home but the full list. Apply an
   owner filter, then toggle flags. **Critical**: with an owner filter on
   "Sam" (owning Bosnia and Herzegovina), the table should still show only
   Bosnia's matches when in flags mode — proving the filter ran on the
   original name before substitution. If the table goes empty when flags are
   on, the substitution order is wrong (step 6c).

Then click the toggle a few times rapidly. Should be jitter-free; the
substitution is cheap (small dataframes, dict lookups).

On a phone-width browser (Cmd-Opt-M in DevTools, 375px), confirm the second
button doesn't break the footer layout. The CSS at ≤480px stacks the footer
into a centred column — the two buttons sit side by side on the same line in
that column, fed by the existing `gap: 16px`.

---

## CLAUDE.md updates (mandatory)

Already itemised as file #7. Two additions: one bullet under `app.py`
describing the toggle + helper; one bullet under "Participants and colours"
describing the `FLAGS` dict.

---

## Verification before opening the PR

1. `uv run pytest -q` — green, with 6 more tests passing than before.
2. `grep -n "FLAGS\|show-flags\|flags-toggle\|_apply_flags" app.py` — every
   reference is intentional; no stray edits.
3. PR diff is exactly: `app.py` (+ FLAGS dict, store, button, callback,
   helper, projection edits), `CLAUDE.md` (2 bullet edits),
   `tests/test_flags.py` (new file), `updates_documentation/UPDATE-6.md`
   (this file). No other files touched.
4. No diff in `scraper.py`, `scoring.py`, `tournament.py`, `assets/s1.css`,
   `assets/*.csv`.

---

## Ship

1. Open the PR after CI is green and the manual click-through has been done.
2. Auto-deploy runs on merge per `deploy.yml`.
3. No cache invalidation needed — `FLAGS` is in-process state, not on disk.

---

## Things to flag while implementing

- **Filter-then-substitute order.** This is the only non-obvious part. The
  owner filter and the owner-column injection both key on original team
  names. Substituting flags first will silently empty the filtered table.
  Verify by toggling flags on with the owner filter set — if rows disappear,
  the order is wrong.
- **Subdivision flag rendering.** UK home nations' flags (`England`,
  `Scotland`, `Wales`) use long tag sequences. On macOS/iOS Safari/Chrome
  they render as proper flags. On Windows pre-11 they render as a black-flag
  glyph + visible tag letters. The user's primary device is macOS, so this
  is acceptable, but the implementer should not be alarmed by the Windows
  rendering during cross-browser checks. Document the limitation in
  `CLAUDE.md` as noted above.
- **Don't auto-derive flags from ISO codes.** Tempting to compute
  `chr(0x1F1E6 + ord(c) - ord("A")) for c in "BR"` to get `🇧🇷`. Don't.
  The scraper uses FIFA 3-letter codes, not ISO-2; the dict is the single
  reviewable source of truth; subdivision flags break the formula anyway.
- **No new column.** Flags replace names in the *same* column. Don't add a
  `Flag` or `FlagOrName` column. The DataTable's column id stays as `Team`
  / `Home` / `Away`; only the cell content changes.
- **`Who` columns are never substituted.** People are not countries. The
  `_apply_flags` calls list only `Team`, `Home`, `Away` — verify in the
  diff that no `Who`, `HomeOwner`, or `AwayOwner` slipped in.
- **Toggle state does not persist.** A page reload resets to names mode.
  This matches `show-goals` behaviour. If the user later asks for
  persistence, that's a future PR — for now, parity with GS/GA is correct.
- **Owner-colour stripe survives substitution.** The stripe is a CSS
  border-left on the team-name cell, keyed on `column_id`. The cell's text
  content changes (`Brazil` → `🇧🇷`) but the styling rule still applies.
  Verify visually on the Leaderboard page in flag mode — the stripe should
  still be there next to the flag.
- **Eliminated + flag stacking.** An eliminated team shows
  `color: var(--eliminated)` + `text-decoration: line-through`. In flag
  mode, the flag emoji will be dimmed and struck through. Emoji presentation
  varies — on macOS the strike-through draws through the emoji. Accept that.
- **Winning-team bolding survives substitution.** Bolding is keyed on the
  hidden `Winner` column in row data. The visible cell text changes, but
  `fontWeight: 700` still applies. Verify with a hand-edited fixture row
  (same trick as UPDATE-5's manual probe) in flag mode.

---

## Out of scope (do not expand the PR)

- A flag column **alongside** the name column. The toggle is a swap.
- Per-page or per-table toggles. One global toggle.
- Persisting the toggle to localStorage / a query param. State resets on
  reload.
- An icon-only button or a switch widget. Plain text button matches the
  existing GS/GA toggle.
- Touching the owner-colour mechanics, eliminated-team styling, or the
  winning-team bolding from UPDATE-5.
- Refactoring `_localize_fixtures` or `_add_owner_cols` to take a
  `show_flags` parameter. Keep the substitution in its own helper, called
  separately.
- Adding flag-related entries to `scraper.py` or any scraping logic. Flags
  are a presentation concern, not a data concern.
- Expanding `FLAGS` to every nation on earth speculatively. Stick to teams
  that have appeared in `draw_2026.csv` or in live scraper output. Easy to
  extend later.
