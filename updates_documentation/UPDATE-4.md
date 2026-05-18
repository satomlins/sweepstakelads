# UPDATE-4: Owner-filter sort + mobile layout polish

A small tranche of UI polish, batched from `TODO.md`. Three independent changes that all touch layout/CSS, none of which affect business logic or tests.

1. **Owner filter dropdown** on `/fixtures` — sort the 12 names alphabetically (currently insertion order from `COLOURS`).
2. **Header wordmark** — on mobile, stack `SWEEPSTAKELADS` and `2026 WORLD CUP` vertically and drop the `·` separator.
3. **Footer copyright** — same treatment: on mobile, stack `© <year> Sweepstakelads` and `website by Scott Tomlins` vertically and drop the `·` separator.
4. **Show GS/GA toggle** — on mobile, centre it horizontally (currently it sits inline next to the copyright on a left-aligned flex row, which crowds on a narrow viewport).

## Branch

`feat/mobile-polish` off `main`. Single PR.

After implementation, **do not merge**. Run `uv run python app.py` locally, share the dev URL with the user, and wait for confirmation that the look and feel are right on both desktop and mobile (use DevTools 375px / 414px / 768px) before opening the PR for merge.

---

## Scope

**In:**

- One-line sort change to the owner-filter `options` list in `app.py`.
- Restructuring two existing strings (wordmark, footer copyright) so the dot separator lives in its own targetable span.
- A short `@media (max-width: 480px)` block (plus one rule at 768px) in `assets/s1.css`.
- Footer layout rework on mobile so the GS/GA toggle sits on its own centred row.

**Out:**

- Any change to desktop layout for the wordmark, footer, or toggle. Desktop must look pixel-identical before and after this PR. The only behaviour change visible at ≥481px is the dropdown reorder, which is the same regardless of viewport.
- Changing `COLOURS` insertion order itself. `COLOURS` is the single source of truth for owner→colour mapping in many other places (group `Who` columns, fixture owner columns, leaderboard stripes). Re-sorting it would have far-reaching visual effects. Sort happens at the consumption site for the dropdown only.
- Sort order in any *other* surface that derives from `COLOURS.keys()` (e.g. the leaderboard row order is driven by points, not insertion order — already alphabetic-irrelevant). No other UI surface uses `COLOURS.keys()` as a display sequence.
- Adding any new mobile breakpoint. Reuse the existing `768px` and `480px` cut-offs already in `assets/s1.css`.
- Touching the social-icon row in the footer. It already sits as its own flex child of `.site-footer` and behaves fine on mobile.

---

## Behaviour

### 1. Owner filter sort

- Open the dropdown on `/fixtures`. Names appear A→Z: `Adrian, Alex, Brendan, Ella, Hugo, Isaac, Jacob, Keshy, Mary, Sam, Scott, Seth`.
- Selection / filter predicate / chip rendering / dark theme — all unchanged. Only the *order in the open menu* and *order chips appear when multi-selected* changes.
- (Implementation note: UPDATE-2 deliberately used `COLOURS` insertion order as "the canonical ordering used throughout the app". That decision is being reversed for this one surface only. The reasoning at the time was about keeping a single source of truth — that reasoning still holds for *colours*, but for *find-an-owner-quickly* alphabetical wins. Other surfaces are unaffected.)

### 2. Wordmark — mobile stacking

- **Desktop (≥481px):** unchanged. Single inline line: `SWEEPSTAKELADS · 2026 WORLD CUP`. The 22px bold mark, an 8px margin, a faint uppercase `·`, the 12px tagline.
- **Mobile (≤480px):** two centred lines, no separator:
  ```
  SWEEPSTAKELADS
   2026 WORLD CUP
  ```
  Both spans remain at their existing font sizes and colours — only the layout container changes. The `· ` separator span is hidden via `display: none`.

### 3. Footer copyright — mobile stacking

- **Desktop:** unchanged single line — `© 2026 Sweepstakelads · website by Scott Tomlins`.
- **Mobile (≤480px):** two centred lines, no separator:
  ```
  © 2026 Sweepstakelads
  website by Scott Tomlins
  ```
  Font size, colour, and dynamic year all preserved.

### 4. GS/GA toggle — mobile centring

- **Desktop:** unchanged. Toggle sits inline next to the copyright with a 16px gap (`flex; alignItems: center; gap: 16px`). Footer is a `space-between` row: `[copyright | toggle] … [social icons]`.
- **Mobile (≤480px):** footer becomes a centred vertical stack:
  ```
   (centred) © 2026 Sweepstakelads
             website by Scott Tomlins
   (centred) [ Show GS/GA ]
   (centred) ✉  in  ⌥
  ```
  The toggle therefore appears horizontally centred on the page on its own row, between the copyright block above and the social icons below.

---

## Files to change

### 1. `app.py` — owner filter options

At `app.py:617-622` (inside the `dcc.Dropdown` constructor for the owner filter on the fixtures page):

```python
options=[{"label": name, "value": name} for name in sorted(COLOURS.keys())],
```

Single-character change in effect (`COLOURS.keys()` → `sorted(COLOURS.keys())`). Nothing else in that block moves.

### 2. `app.py` — split the wordmark into three spans

The current wordmark is two spans (`app.py:314-333`):

```python
html.Span("SWEEPSTAKELADS", style={...22px...}),
html.Span(" · 2026 WORLD CUP", style={...12px, marginLeft: 8px...}),
```

Replace with three spans so the separator is targetable and removable:

```python
html.Span(
    "SWEEPSTAKELADS",
    style={
        "fontSize": "22px",
        "fontWeight": "600",
        "letterSpacing": "-0.01em",
        "color": "var(--text)",
    },
),
html.Span(
    " · ",
    className="wordmark-sep",
    style={
        "fontSize": "12px",
        "fontWeight": "600",
        "color": "var(--text-faint)",
        "marginLeft": "8px",
    },
),
html.Span(
    "2026 WORLD CUP",
    className="wordmark-tagline",
    style={
        "fontSize": "12px",
        "fontWeight": "600",
        "letterSpacing": "0.08em",
        "textTransform": "uppercase",
        "color": "var(--text-faint)",
    },
),
```

Notes:
- The tagline span loses its `marginLeft: 8px` — the gap is provided by the separator span's `marginLeft: 8px` and the natural width of `" · "`. On desktop the rendered horizontal spacing must look identical to today. **Test this carefully**; if there's a 1–2px drift the user will not care, but anything more than that warrants restoring a small explicit margin.
- The `className`s give CSS a hook to retarget on mobile without an inline `style` fight.
- Leave `html.Div(..., className="header-wordmark")` exactly as today — no class rename.

### 3. `app.py` — split the footer copyright

The current copyright is one span with an f-string (`app.py:513-516`):

```python
html.Span(
    f"© {pd.Timestamp.now().year} Sweepstakelads · website by Scott Tomlins",
    style={"color": "var(--text-faint)", "fontSize": "11px"},
),
```

Replace with a container `html.Span` carrying a class, three child spans, and the same outer style:

```python
html.Span(
    [
        html.Span(
            f"© {pd.Timestamp.now().year} Sweepstakelads",
            className="footer-copy-main",
        ),
        html.Span(" · ", className="footer-copy-sep"),
        html.Span(
            "website by Scott Tomlins",
            className="footer-copy-byline",
        ),
    ],
    className="footer-copyright",
    style={"color": "var(--text-faint)", "fontSize": "11px"},
),
```

`html.Span` is a valid container for child spans (the rendered DOM is `<span>...<span>...</span></span>` — perfectly valid HTML, all inline). If Sonnet prefers an `html.Div` outer container that's also fine, but then `display: inline-block` may need adding to keep the visual identical on desktop. Default to `html.Span` to minimise the chance of any desktop drift.

The dynamic year is preserved.

### 4. `app.py` — footer outer structure stays put

**Do not** restructure the outer `html.Footer` children. Both today and after this change, the footer holds two top-level `html.Div`s:

- Left Div: `[copyright, goals-toggle]`, `flex; alignItems: center; gap: 16px`.
- Right Div: the three social-icon `dcc.Link`s.

All mobile behaviour for centring + stacking is handled in CSS via `.site-footer` overrides. Keeping the markup identical on desktop means no risk of a regression at >=481px.

### 5. `assets/s1.css` — three new responsive rules

Add (or extend) the existing `@media (max-width: 480px)` block at `s1.css:396-420`. Place the new rules at the end of that block, before the closing `}` at line 420.

```css
/* Wordmark — stack the SWEEPSTAKELADS line and the 2026 WORLD CUP tagline
   into two centred rows on phones; hide the inline · separator. */
.header-wordmark {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
}

.wordmark-sep {
  display: none;
}

/* The tagline span lost its marginLeft when we hid the separator, so neutralise
   any browser-default whitespace between the now-stacked lines. */
.wordmark-tagline {
  margin-left: 0;
}

/* Footer — stack into a centred column on phones. The GS/GA toggle therefore
   sits on its own row, horizontally centred, between the copyright block and
   the social-icon row. */
.site-footer {
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

/* Copyright — stack the "© Sweepstakelads" line and the "website by..." byline
   vertically, drop the inline separator. */
.footer-copyright {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  text-align: center;
}

.footer-copy-sep {
  display: none;
}

/* The left footer Div (copyright + toggle) also needs to stack so the toggle
   centres beneath the copyright instead of sitting to its right. */
.site-footer > div:first-child {
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
```

There is **no** rule to add at 768px — the wordmark already has `text-align: center` in the existing 768px block (`s1.css:364-366`); the existing rule keeps working when the inner flex container is single-line at that breakpoint.

(If, on review, the user wants the stacking to kick in at 768px rather than 480px, the entire block can move into the 768 query. That's a one-line move and should not be done speculatively — wait for explicit feedback.)

---

## Tests

No new test required. All four changes are layout / sort-order tweaks with no logic surface area. Existing `uv run pytest -q` must stay green; that's the only bar.

---

## CLAUDE.md updates (mandatory)

Sonnet must update CLAUDE.md in the same commit.

1. Under **Architecture → `app.py`**, in the **Results & Fixtures** bullet, change the description of the `owner-filter` so it mentions alphabetical sort. Today the line ends `"…selecting one or more owners restricts both the Results and Fixtures tables to matches where the home or away team belongs to a selected owner (default empty = no filter)."` — append: `"Dropdown options are listed alphabetically by name."`

2. Under **Architecture → `app.py`**, in the **Header strip** bullet (which currently reads `"Header strip: wordmark left, timezone label + \"Last updated\" stacked right; footer: copyright left, social icons right"`), append: `"On mobile (≤480px) the wordmark stacks into two centred lines (no `·` separator), and the footer stacks into a centred column so the GS/GA toggle and the copyright lines all centre horizontally."`

3. Under **Architecture → `assets/s1.css`**, in the existing bullet listing the responsive rules at 768/480px, add: `"Mobile (≤480px) additionally stacks the header wordmark and footer copyright into centred two-line blocks (hiding their `·` separators) and reflows the footer to a centred column."`

No change needed to participant/colour/draw sections, deployment notes, or test docs.

---

## Verification before opening the PR

1. `uv run pytest -q` — green.
2. `uv run python app.py`, then in a browser at desktop width (≥1280px):
   - **`/fixtures`** — open the owner-filter dropdown. The 12 names are in alphabetical order: `Adrian, Alex, Brendan, Ella, Hugo, Isaac, Jacob, Keshy, Mary, Sam, Scott, Seth`. Pick two non-adjacent names (e.g. `Adrian` and `Seth`) — chips appear in selection order; filter still works correctly across both tables.
   - **Header (every tab)** — wordmark reads `SWEEPSTAKELADS · 2026 WORLD CUP` on a single line, identical to before. The `·` is faint, the tagline is uppercase, the spacing looks the same.
   - **Footer (every tab)** — copyright reads `© 2026 Sweepstakelads · website by Scott Tomlins` on a single line, identical to before. The GS/GA toggle sits to its right with 16px gap. Social icons are on the right.
   - **Toggle still works** — click `Show GS/GA`; team table grows two columns; click `Hide GS/GA`; team table contracts. Unchanged behaviour.
3. DevTools responsive mode at **480px** width (iPhone SE-ish), every tab:
   - **Wordmark** stacks into two centred lines, no `·` between them. Font sizes and colours unchanged.
   - **Footer** is a centred column. Copyright sits at the top as two centred lines (`© 2026 Sweepstakelads` / `website by Scott Tomlins`), no `·` between them. Below it, the `Show GS/GA` button is centred horizontally. Below the button, the three social icons are centred horizontally. No element is clipped or pushed off-screen.
   - **Owner-filter** on `/fixtures` (mobile) — dropdown still alphabetical, chips still wrap, the existing `@media (max-width: 480px) .owner-filter-wrap { max-width: 100% !important; }` rule still stretches it to full width.
4. DevTools at **768px** width (tablet), every tab:
   - **Wordmark** is still a single line `SWEEPSTAKELADS · 2026 WORLD CUP`, centred horizontally (per the existing 768px rule). The `·` is visible. (The 480px rule has not kicked in yet.)
   - **Footer** is unchanged from desktop — single row with `space-between`. (The 480px column rule has not kicked in yet.)
5. DevTools at **375px** width (smaller iPhone), every tab:
   - Same as the 480px test. Nothing horizontally overflows. The four tab links in the nav still scroll horizontally as today (unchanged).
6. **No keyboard / focus regressions.** Tab through the owner filter and the footer toggle button on both desktop and mobile. Focus rings appear on the same elements as before.
7. **Visual regression sweep.** With the dev server running, screenshot each tab at 1280px and at 375px before and after the change (or compare to a freshly-pulled `main` in a second tab). The four explicit changes above are the *only* visual diffs you should see. Anything else is a regression.

If everything looks right, share the dev URL with the user. Do **not** open the PR until the user has eyeballed it on a real phone (or DevTools responsive mode) and given the OK.

---

## Ship

1. User confirms it looks right → open the PR.
2. Wait for CI.
3. Ask before merging (deploy is user-visible).

---

## Things to flag while implementing

- **Wordmark spacing drift.** Splitting one span into three is the highest-risk change in this PR for an unintended desktop pixel-shift. The current rendered line is `SWEEPSTAKELADS<span 8px margin>· 2026 WORLD CUP`. The new structure renders `SWEEPSTAKELADS<span 8px margin>· <0px margin>2026 WORLD CUP`. The intervening space inside `" · "` is what provides the spacing on the right side of the dot. If it looks visibly tighter than today, add a `marginRight: 4px` to the separator span — but only if visibly different. Don't add margins prophylactically.
- **`html.Span` inside `html.Span`.** Valid HTML, works in Dash. If a future React/Dash upgrade complains, the fall-back is to switch the outer wrapper to `html.Div` with an explicit `display: "inline-block"` on desktop. Don't do this preemptively.
- **`COLOURS` is still the source of truth for colours.** The sort change is *only* at the dropdown option-construction site. Do not introduce a new sorted dict anywhere. Do not re-export a sorted view from `app.py`.
- **`sorted()` is case-sensitive Python-default — all participant names start with an uppercase letter, so this is moot today.** If a future participant name is added in lowercase, `sorted()` will place it after capitalised names. If that ever matters, switch to `sorted(COLOURS.keys(), key=str.casefold)` — but not in this PR.
- **Mobile breakpoint reuse.** Use the existing `@media (max-width: 480px)` block — do not add a new one. The PR diff in `s1.css` should be a *within-block* addition, not a new block.
- **Don't centre the social icons on desktop.** The mobile centring is achieved by `.site-footer { flex-direction: column; align-items: center }` — that rule must live inside the 480px media query only. If it accidentally leaks to desktop, the footer collapses entirely. Easy to spot in verification step 2.

---

## Out of scope (do not expand the PR)

- Reordering `COLOURS` itself. The dict's insertion order is referenced implicitly by other surfaces and tests; touch it and surprises follow.
- Adding a search box to the owner-filter (react-select / Dash's dropdown already supports type-to-filter inside the open menu).
- Sticky-footer behaviour or any change to vertical page rhythm.
- Restyling the wordmark / footer fonts, weights, or colours. Layout-only.
- Adding a hamburger menu for the four-tab nav at narrow widths (existing `overflow-x: auto` horizontal-scroll behaviour is already in place at 480px and the user has not flagged it).
- Animating the wordmark stack or the footer column transition. No transitions added.
- Adding a separate breakpoint for tablets. Reuse 480/768 as today.
