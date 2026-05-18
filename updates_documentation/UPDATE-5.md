# UPDATE-5: Bold winning team in Results, plus AET / penalty-shootout lock-in

Two related changes shipped as one PR:

1. **Bold the winning team** in every Results table — country name and owner name both bold, for wins after regulation, after extra time, or on penalties. Group-stage draws stay unbolded on both sides. Upcoming fixtures get no bolding (no winner yet).
2. **Lock-in for the AET / penalty-shootout score display** already implemented in `tournament.py:_matches_to_fixtures_df`: add scraper tests + a CLAUDE.md note + clear the bullet from `TODO.md`. The AET/pens string format (`"2–1 (aet)"`, `"1–1 (pens 4–3)"`) stays exactly as it is — we are not restyling the Score cell.

The two ship together because they share the same touchpoints: knockout outcome semantics, the Score column, `_matches_to_fixtures_df`, and `CLAUDE.md` documentation around fixtures. Bundling them avoids a second pass over the same files a week later.

The Score column itself stays a plain string. The bold treatment is on the **team name** and **owner name** cells only — the Score cell never gets weight changes. (Reasons: keeping Score plain matches the lock-in section's intent; team-name bolding is where the eye lands on a Results table anyway; and the AET/pens parenthetical inside Score reads cleanly without competing weight.)

---

## Branch

`feat/bold-winners` off `main`. Single PR. Merge after CI is green and after eyeballing a Results table locally with at least one mocked finished match per outcome type (regulation, AET, pens, draw).

---

## Scope

**In:**

- Add a `Winner` column to the fixtures DataFrame produced by `_matches_to_fixtures_df` in `tournament.py`. Values: `"HOME"`, `"AWAY"`, `"DRAW"`, `""` (empty for unplayed).
- Persist `Winner` to `assets/fixtures.csv` (new eighth column).
- In `app.py`, include `Winner` in the projection for results tables (Home page Recent Results + Results & Fixtures page All Results) so it's available to `style_data_conditional` filter queries, but **do not** add it to the displayed `columns=` list — it must not render as a visible column.
- Add four `style_data_conditional` rules that set `fontWeight: 700` on the appropriate `Home` / `HomeOwner` or `Away` / `AwayOwner` cell based on `{Winner}`.
- One new scraper test (two functions) in `tests/test_scraper.py` proving `parse_matches` correctly extracts `aet=yes` and `penaltyscore=4–3` from a hand-crafted `{{footballbox}}` snippet.
- One new test file `tests/test_tournament.py` with a focused unit test on the Winner derivation in `_matches_to_fixtures_df` covering regulation home win, regulation away win, group draw, AET decisive (no pens), pens, and unplayed.
- Short additions to `CLAUDE.md` documenting (a) the `Winner` column + bold treatment, and (b) the Score-string format.
- Clear the AET/pens question bullet from `TODO.md`.

**Out:**

- Bolding inside the `Score` cell. Score stays plain string.
- Bolding in the Upcoming Fixtures table, Home page Upcoming card, or anywhere else — Results only.
- Any change to `scraper.py`, `scoring.py`, or `assets/s1.css`.
- A new visual treatment for AET/pens (dim parenthetical, italics, tooltip, separate column). Explicitly rejected.
- A real-world wikitext fixture from a past tournament. The hand-crafted snippet is simpler.
- Touching `tests/fixtures/*.wikitext` — the 2026 snapshots stay as they are.
- Any refactor of `_matches_to_fixtures_df` beyond appending the `Winner` derivation.

---

## Files to change

### 1. `tournament.py` — add `Winner` to `_matches_to_fixtures_df`

In `_matches_to_fixtures_df` (lines 92–118), add a `winner` computation before building the row dict and include it in the row:

```python
def _winner_label(m: dict) -> str:
    hs = m["home_score"]
    aws = m["away_score"]
    if hs is None or aws is None:
        return ""
    if m["aet"] and m["pen_home"] is not None and m["pen_away"] is not None:
        if m["pen_home"] > m["pen_away"]:
            return "HOME"
        if m["pen_away"] > m["pen_home"]:
            return "AWAY"
        return ""  # tied pens shouldn't happen; fall through to no winner
    if hs > aws:
        return "HOME"
    if aws > hs:
        return "AWAY"
    return "DRAW"
```

Place the helper at module scope directly above `_matches_to_fixtures_df`. Inside the existing loop, add `"Winner": _winner_label(m),` to the row dict (any position, but cleanest after `Status`).

Why a free helper rather than inlining: the logic is six branches and it's worth being able to unit-test directly without rebuilding the whole DataFrame.

### 2. `assets/fixtures.csv` schema

Adding a column means existing caches are stale. Two options:

- **Preferred**: let it regenerate naturally. The cache is rewritten on every `refresh()` (5-minute TTL), and `_atomic_write_csv` overwrites the whole file. No migration needed. The first prod render after deploy may read the old cache once (no `Winner` column → all rows untreated), then the background refresh produces a new file with `Winner` populated. Acceptable.
- If for some reason the implementer would rather not rely on that: delete `assets/fixtures.csv` from the repo as part of the PR. (It's already gitignored in spirit — it's regenerated state. Check: `git ls-files assets/fixtures.csv` — if it's tracked, decide whether to drop it from tracking too. Don't churn unrelated files.)

Either way, document the schema change in CLAUDE.md (see file #4 below).

### 3. `app.py` — wire `Winner` into the results tables and add the bold rules

Three sub-edits:

**3a. Pre-computed style constant** (place under the existing `_FIXTURE_OWNER_FMT` constant around line 280, in the "Pre-computed style constants" block):

```python
_WINNER_BOLD_RULES = [
    {"if": {"filter_query": '{Winner} = "HOME"', "column_id": "Home"},      "fontWeight": "700"},
    {"if": {"filter_query": '{Winner} = "HOME"', "column_id": "HomeOwner"}, "fontWeight": "700"},
    {"if": {"filter_query": '{Winner} = "AWAY"', "column_id": "Away"},      "fontWeight": "700"},
    {"if": {"filter_query": '{Winner} = "AWAY"', "column_id": "AwayOwner"}, "fontWeight": "700"},
]
```

These are deterministic and have no per-request inputs, so they belong in the constants block rather than being rebuilt inside the callback.

**3b. Projection updates** (inside `update_all`, the two results-table preparation blocks around lines 772–790).

For `recent_out` (Home page Recent Results, around line 775):

```python
recent_out = _add_owner_cols(
    finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage", "Winner"]]
)
```

For `all_results_out` (Results & Fixtures page, around line 785):

```python
all_results_out = _add_owner_cols(
    all_finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage", "Winner"]]
)
```

Do **not** add `Winner` to `upcoming_out` or `all_upcoming_out` — by definition there's no winner; an empty-string `Winner` would match nothing anyway, but skipping it keeps the projections honest.

**3c. Style rules** (inside `update_all`, the existing `fixture_fmt` construction around line 770):

Build a results-specific format on top of the shared one:

```python
fixture_fmt = fixture_stripes + fixture_colours + _FIXTURE_OWNER_FMT
results_fmt = fixture_fmt + _WINNER_BOLD_RULES
```

Then in the callback's return tuple, use `results_fmt` for the two Results table style outputs (`recent-table` and `all-results-table`) and leave `upcoming-table` and `all-upcoming-table` on `fixture_fmt`. Check the existing return tuple order against the `Output(...)` declarations around lines 647–653; the four ids map to four positional values — only the two results ones change.

Important: do **not** add `Winner` to `_RESULT_COLS`. That constant is the list of *displayed* columns; adding it would render a "Winner" column in the table. `Winner` belongs only in the row data so `filter_query` can match on it. Dash's filter_query works against the `data` records regardless of whether the column is listed in `columns=`.

This is also why we are **not** using `hidden_columns` — per existing project convention (see [`feedback_design.md`] in memory), `hidden_columns` triggers a jarring built-in column-toggle button in the table header.

### 4. `CLAUDE.md` — three small additions

Under **Architecture → `tournament.py`**:

- Append `Winner` to the `fixtures.csv columns` line. Updated bullet:
  > - `fixtures.csv` columns: `DatetimeUTC` (ISO 8601 UTC string), `Date`, `Home`, `Score`, `Away`, `Stage`, `Status`, `Winner` — note: no `Time` column; `Time` is synthesised by `_localize_fixtures` in `app.py` at render time from `DatetimeUTC`. `Winner` is `"HOME"` / `"AWAY"` / `"DRAW"` / `""` (empty for unplayed); for matches decided on penalties, `Winner` is set from the shootout result, not the 90+ET draw.
- Add a new bullet just under it:
  > - **`Score` column format** in `fixtures.csv`: regulation result → `"2–1"`; extra-time decisive → `"2–1 (aet)"`; draw after AET decided by penalties → `"1–1 (pens 4–3)"`. The annotation is baked in at `_matches_to_fixtures_df`; the `Score` column is a single string with no nested styling. `aet=True` with `pen_home=None` renders the `(aet)` suffix; `aet=True` with `pen_home` set renders `(pens X–Y)` (the score itself is still the AET total since Wikipedia's `score` field reports full-time-plus-ET).

Under **Architecture → `app.py`**, in the bullet block that describes column sets / styling, add one new bullet:

> - **Winning team bolding**: results tables (Home Recent Results + Results & Fixtures All Results) bold the winner's country name and owner name via four `style_data_conditional` rules keyed on a hidden `Winner` column in the row data (`"HOME"` / `"AWAY"` / `"DRAW"` / `""`). `Winner` is included in the projection but **not** in `_RESULT_COLS`, so it never renders as a visible column. Draws (group stage) leave both sides unbolded. Upcoming fixtures get no bolding.

No other CLAUDE.md edits required. The owner-colour bullets, eliminated-team bullet, etc. already reflect the surrounding behaviour.

### 5. `tests/test_scraper.py` — AET / pens lock-in (carried over from the original UPDATE-5)

Append to the bottom of the "Unit tests for parsing helpers" section (after the existing `_parse_datetime_utc` cluster, around line 163):

```python
# ---------------------------------------------------------------------------
# AET / penalty-shootout parsing (will only fire for real once the knockout
# round produces an extra-time match; this exists so the parser doesn't
# silently regress before then).
# ---------------------------------------------------------------------------

_AET_PENS_WIKITEXT = """
==Round of 16==
{{footballbox
|date=4 July 2026
|time=20:00 UTC
|team1={{#invoke:flag|fb|ENG}}
|team2={{#invoke:flag|fb|GER}}
|score=1–1
|aet=yes
|penaltyscore=4–3
}}
""".strip()


_AET_NO_PENS_WIKITEXT = """
==Round of 16==
{{footballbox
|date=4 July 2026
|time=20:00 UTC
|team1={{#invoke:flag|fb|ENG}}
|team2={{#invoke:flag|fb|GER}}
|score=2–1
|aet=yes
}}
""".strip()


def test_parse_aet_with_pens():
    matches = parse_matches(_AET_PENS_WIKITEXT)
    assert len(matches) == 1
    m = matches[0]
    assert m["home_team"] == "England"
    assert m["away_team"] == "Germany"
    assert m["home_score"] == 1
    assert m["away_score"] == 1
    assert m["aet"] is True
    assert m["pen_home"] == 4
    assert m["pen_away"] == 3
    assert m["status"] == "finished"


def test_parse_aet_without_pens():
    # AET that produced a goal — no penalty shootout.
    matches = parse_matches(_AET_NO_PENS_WIKITEXT)
    assert len(matches) == 1
    m = matches[0]
    assert m["home_score"] == 2
    assert m["away_score"] == 1
    assert m["aet"] is True
    assert m["pen_home"] is None
    assert m["pen_away"] is None
```

Notes:

- The wikitext uses an en-dash `–` in the score because that's what `_parse_score` already handles. If `_parse_score` rejects en-dashes (check the existing implementation), switch the test strings to ASCII `-`. Don't change the parser to chase the test.
- Country codes `ENG` and `GER` must resolve via `_code_to_name`. Verify with a quick grep that both are in the code-to-name map. If `GER` lives there as `DEU` or similar, swap accordingly. Don't expand the map for the test.
- These are unit-style tests calling `parse_matches` directly with an inline string — matches the style of `test_extract_code_standard` and friends, not the fixture-backed `group_a_matches` pattern.

### 6. `tests/test_tournament.py` — new file, Winner derivation tests

```python
"""Unit tests for tournament._matches_to_fixtures_df Winner column."""

from tournament import _matches_to_fixtures_df


def _match(
    home="A", away="B", hs=None, aws=None,
    aet=False, ph=None, pa=None, stage="Group A", status="finished",
):
    return {
        "date": "1 Jun 2026",
        "time": "20:00",
        "datetime_utc": None,
        "home_team": home, "away_team": away,
        "home_score": hs, "away_score": aws,
        "pen_home": ph, "pen_away": pa,
        "aet": aet,
        "stage": stage,
        "status": status,
    }


def test_winner_home_regulation():
    df = _matches_to_fixtures_df([_match(hs=2, aws=1)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_away_regulation():
    df = _matches_to_fixtures_df([_match(hs=0, aws=3)])
    assert df.iloc[0]["Winner"] == "AWAY"


def test_winner_group_draw():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1)])
    assert df.iloc[0]["Winner"] == "DRAW"


def test_winner_aet_decisive_no_pens():
    # Goal scored in extra time, no shootout.
    df = _matches_to_fixtures_df([_match(hs=2, aws=1, aet=True)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_pens_home():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1, aet=True, ph=4, pa=3)])
    assert df.iloc[0]["Winner"] == "HOME"


def test_winner_pens_away():
    df = _matches_to_fixtures_df([_match(hs=1, aws=1, aet=True, ph=3, pa=5)])
    assert df.iloc[0]["Winner"] == "AWAY"


def test_winner_unplayed():
    df = _matches_to_fixtures_df([_match(status="upcoming")])
    assert df.iloc[0]["Winner"] == ""
```

Notes for the implementer:

- The `_match` factory keeps each test to one assertion line. Don't over-elaborate it.
- If `_winner_label` was named differently or kept inline, adjust imports. The test contract is the **`Winner` column in the output DataFrame**, not the helper name.
- If `_matches_to_fixtures_df` requires fields the factory above is missing (check it before writing), add them with safe defaults. The factory above is built from the keys the existing `_matches_to_fixtures_df` reads (`home_score`, `away_score`, `pen_home`, `pen_away`, `aet`, `home_team`, `away_team`, `stage`, `status`, `date`, `datetime_utc`) — but verify against the current source before relying on it.

### 7. `TODO.md` — clear the AET/pens question

Delete the single bullet:

> - How are we going to display AET and penalty shootout results in the Results table? Is that already planned?

Leave the file's preamble paragraph intact so it remains a holding area for future items. Do not delete the file.

---

## Tests

`uv run pytest -q` must stay green. The two new scraper tests and seven new tournament tests should all pass. Quick targeted run first:

```bash
uv run pytest tests/test_scraper.py::test_parse_aet_with_pens tests/test_scraper.py::test_parse_aet_without_pens tests/test_tournament.py -v
```

No changes are expected to existing test outcomes. If anything else turns red, stop and investigate — `scoring.py` is untouched and `scraper.py` is untouched, so existing scraper/scoring tests should be unaffected.

---

## Visual verification (do this before opening the PR)

`uv run python app.py` and open the Results & Fixtures page. The cache will be empty initially; the first refresh populates `fixtures.csv` with the new `Winner` column. Once populated:

- Confirm zero results show bolding today (May 2026 — no matches have happened yet, all rows are `Upcoming`).
- To actually see the styling work, temporarily hand-edit one row of `assets/fixtures.csv` to `Status = Finished` with a score like `2–1` and `Winner = HOME` (back up the file first), refresh the page, and verify the Home column + HomeOwner column on that row are visibly bolder than the Away side. Restore the file when done.
- Also check the Home page Recent Results card with the same trick.
- Confirm the Upcoming Fixtures table on both pages shows no bolding even when the same row is in the data (because `Winner` isn't projected into the upcoming tables).
- Confirm no `Winner` column is visible in any table header.

This manual probe is the only way to eyeball the feature pre-tournament. Once the real World Cup starts producing finished matches, the test data lands naturally.

---

## CLAUDE.md updates (mandatory)

Already itemised as file #4. Three additions: `Winner` appended to the `fixtures.csv columns` bullet; a new `Score column format` bullet; a new bullet under `app.py` describing the winner-bolding mechanism.

---

## Verification before opening the PR

1. `uv run pytest -q` — green, with 9 more tests passing than before (2 scraper + 7 tournament).
2. `cat TODO.md` — the AET/pens bullet is gone; preamble paragraph remains.
3. `grep -n "Winner\|Score.*format" CLAUDE.md` — the new bullets are present.
4. PR diff is exactly: `tournament.py` (+ helper + Winner field), `app.py` (+ constant + 2 projection columns + results_fmt usage), `CLAUDE.md` (3 bullet edits), `tests/test_scraper.py` (added tests), `tests/test_tournament.py` (new file), `TODO.md` (1 bullet removed), `updates_documentation/UPDATE-5.md` (this file). Plus possibly `assets/fixtures.csv` if the implementer chose to delete it; otherwise it'll regenerate at deploy time.
5. No diff in `scraper.py`, `scoring.py`, or `assets/s1.css`.

---

## Ship

1. Open the PR after CI is green and the manual eyeball check has been done.
2. Auto-deploy runs on merge per `deploy.yml`.
3. On the Oracle host, the first request after deploy may read the old (winner-less) `fixtures.csv`; the background refresh within 5 minutes will rewrite it with the `Winner` column. No manual cache invalidation needed.

---

## Things to flag while implementing

- **Country code drift.** If `GER` is not in the code-to-name map and the test asserts `away_team == "Germany"`, the test will fail. Either pick a pair of countries that *are* in the map (e.g. `ENG` vs `BRA`) or assert on the raw code. The test's purpose is `aet`/`penaltyscore`, not country resolution.
- **Score separator.** If `_parse_score` rejects en-dashes, swap to ASCII `-` in the test wikitext.
- **No new fixture file.** Resist saving the snippet to `tests/fixtures/aet_sample.wikitext`. Inline strings are clearer for parsing unit tests.
- **`Winner` column must not display.** Triple-check that `Winner` is in `data=` but not in `columns=` for any DataTable. The four DataTable instances that touch results/upcoming data are `recent-table`, `upcoming-table`, `all-results-table`, `all-upcoming-table` — none of them should have `Winner` in their displayed columns. The displayed-column lists are `_RESULT_COLS`, `_FIXTURE_COLS`, `_HOME_UPCOMING_COLS` at the top of `app.py`; leave all three unchanged.
- **Don't combine `Winner` filter_query with column-id rules accidentally.** `filter_query` matches the row; `column_id` scopes which cell gets styled. The four bold rules above each pair one query with one column id. Don't try to clever-collapse them with a single `column_id: ["Home", "HomeOwner"]` array — Dash doesn't support that syntax in `column_id`.
- **`fontWeight: "700"`**, not `"bold"`. Strings work, but the numeric form is unambiguous and matches the rest of the codebase if anything else sets weights (grep first to check). If nothing else sets weights, `"bold"` is also fine — pick one and stay consistent.
- **Eliminated + winner stacking.** A team that wins a knockout match but is later eliminated by losing the next round will, in their winning row, show as bold + struck-through + dimmed colour. That's accurate (they did win that match, they are now out) — don't add special-case logic to suppress bolding for eliminated teams.
- **Group draws stay unbolded.** `Winner = "DRAW"` matches none of the four bold rules — that's deliberate. Don't add a "bold both sides on draw" rule.

---

## Out of scope (do not expand the PR)

- Bolding inside the `Score` cell or any treatment of `(aet)` / `(pens X–Y)` annotations.
- Bolding in the Upcoming Fixtures tables.
- Bolding the winning team's name in the Group Stages mini-tables or the Team Table on the Leaderboard. (Those are standings tables, not match outcomes — wrong place.)
- A "Result" column abbreviated to W/L/D — Winner is intentionally hidden, used only for styling.
- Restyling AET/pens cells (italics, dim parenthetical, tooltip, separate column).
- A pinned past-tournament wikitext fixture.
- Refactoring `_matches_to_fixtures_df` further than appending the `Winner` derivation.
- Updating `scoring.py` or its tests.
