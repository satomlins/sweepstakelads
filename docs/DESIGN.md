# SWEEPSTAKELADS 2026 — UI Design Spec

Visual overhaul of the dashboard. Implementer: Sonnet.

Aesthetic in three words: **greyscale, slick, modern.** Restrained, system-font typography; micro-caption section headings; generous whitespace; almost-invisible chrome. Full-width dashboard layout — no narrow reading column.

---

## 1. Design principles

1. **Chrome disappears, data is the foreground.** No neon, no borders for decoration, no heavy headers.
2. **Greyscale is the rule; owner colour is the only exception.** Every UI element except owner identification is some shade of grey. Owner colour is reduced to small accents, never full-cell pastel washes.
3. **Information density without noise.** Tight rows, thin dividers, monospaced numerics so columns align cleanly.
4. **Typography does the work.** Section labels are small uppercase captions in muted grey, so headings recede and tables are the focal point.
5. **No motion theatre.** A single page fade-in. Hover states are subtle. That's it.

---

## 2. Colour tokens

Define as CSS custom properties in `assets/s1.css`, replacing the existing palette. Do **not** introduce a colour-scheme media query — this is dark-only.

```css
:root {
  /* Surfaces */
  --bg:            #0e0e0e;   /* page background */
  --surface:       #161616;   /* table/section background */
  --surface-2:     #1c1c1c;   /* table header row, subtle elevation */
  --hover:         #202020;   /* row hover */

  /* Borders */
  --border:        #262626;   /* table dividers, subtle separators */
  --border-strong: #333333;   /* section edges if needed */

  /* Text */
  --text:          #e8e8e8;   /* primary */
  --text-muted:    #8a8a8a;   /* secondary / metadata */
  --text-faint:    #5a5a5a;   /* captions, headings */

  /* Status (greyscale, not red/green) */
  --eliminated:    #5a5a5a;   /* "Out" teams: muted + strikethrough, NOT red */
  --live:          #e8e8e8;   /* live match indicator dot */

  /* Focus / selection */
  --focus:         #6bc1d7;   /* one allowed accent, used only on focus rings */
  --selection-bg:  rgba(255,255,255,0.12);
}
```

**Owner colours.** Keep the current pastel hex values from `app.py:COLOURS`, but use them only as small accents (see §6.3). Do not use them as full cell backgrounds. The pastels stay because participants recognise their colour from prior years; we just reduce the surface area.

**Eliminated teams.** Replace the existing `#960000` red rule. Set `color: var(--eliminated)` and `text-decoration: line-through`, no background change. Cleaner, no shouting.

---

## 3. Typography

System font stack:

```css
font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Ubuntu, Cantarell,
  Roboto, Helvetica, Arial, "Noto Sans", sans-serif,
  "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol";
-webkit-font-smoothing: antialiased;
-moz-osx-font-smoothing: grayscale;
```

Numeric columns (PL / W / D / L / GS / GA / GD / PTS and scores) use a monospace stack so digits align:

```css
font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
font-variant-numeric: tabular-nums;
```

### Type scale

| Element            | Size  | Weight | Tracking | Case      | Colour            |
| ------------------ | ----- | ------ | -------- | --------- | ----------------- |
| Page wordmark (H1) | 22px  | 600    | -0.01em  | normal    | `--text`          |
| Section labels (H3 in current code) | **12px** | 600 | **0.08em** | **UPPERCASE** | `--text-faint`    |
| Group labels (H5)  | 11px  | 600    | 0.08em   | UPPERCASE | `--text-faint`    |
| Body / table cell  | 13px  | 400    | 0        | normal    | `--text`          |
| Table header       | 11px  | 600    | 0.06em   | UPPERCASE | `--text-muted`    |
| Footer / meta      | 11px  | 400    | 0        | normal    | `--text-faint`    |

The micro-caption H3 is the most important typographic move — it's what makes the page feel slick. The current centred white "Leaderboard" / "Teams" / "Groups" headings (24px+) become 12px uppercase tracked greys, **left-aligned**. Headings recede; tables advance.

---

## 4. Spacing & layout

- Base unit: 4px. Use multiples (4, 8, 12, 16, 24, 32, 48, 64).
- Page container: `max-width: 1400px`, centred, `padding: 48px 32px 96px`. No border, no rounded corner, no background — page bg is the same as container bg.
- Section gap (between Leaderboard, Groups, Fixtures, Knockout): `64px`.
- Within-section heading-to-table gap: `12px`.
- Row 1 (Leaderboard + Team table): two-column grid, **5/12 + 7/12** as today. Gap `32px`.
- Group tables: `grid-template-columns: repeat(3, 1fr)` with 24px gap. 12 groups → 4 rows. (Current code does 3-per-row already; verify.)
- Recent + Upcoming: 1/2 + 1/2, gap `32px`.
- Knockout: full-width table.

Replace the current `.main_container` (5% padding, dark grey border, rounded) with a flat `<main>` matching the body. The "card" look goes.

---

## 5. Page structure

```
┌───────────────────────────────────────────────────────────┐
│  SWEEPSTAKELADS                                  [last upd]│   ← header strip
├───────────────────────────────────────────────────────────┤
│                                                            │
│  LEADERBOARD                  TEAMS                        │   ← H3 captions
│  ┌─────────────┐              ┌─────────────────────────┐  │
│  │             │              │                         │  │
│  │             │              │                         │  │
│  └─────────────┘              └─────────────────────────┘  │
│                                                            │
│  GROUPS                                                    │
│  ┌────────┐  ┌────────┐  ┌────────┐                        │
│  │  A     │  │  B     │  │  C     │   ...                  │
│  └────────┘  └────────┘  └────────┘                        │
│                                                            │
│  RECENT RESULTS               UPCOMING                     │
│  ┌─────────────┐              ┌─────────────────────────┐  │
│  │             │              │                         │  │
│  └─────────────┘              └─────────────────────────┘  │
│                                                            │
│  KNOCKOUT                                                  │
│  ┌────────────────────────────────────────────────────┐    │
│  └────────────────────────────────────────────────────┘    │
│                                                            │
│  © 2026 Sweepstakelads · website by Scott Tomlins · ⓘ ⓛ ⓖ │
└───────────────────────────────────────────────────────────┘
```

### Header strip

Replace the current centred neon-cyan H1. New header:

- Left: wordmark `SWEEPSTAKELADS` in 22px/600, `--text`. Optionally followed by a `--text-faint` token like `· 2026 FIFA WORLD CUP` at 12px tracked uppercase.
- Right: "Last updated: …" in 11px `--text-faint`, monospaced. (Move it out of the footer to here — it's status, it belongs at the top.)
- Bottom border: `1px solid var(--border)`, padding `0 0 16px`.

### Footer

- 1px top border `var(--border)`, padding `24px 0`.
- Single line, `--text-faint`, 11px. Copyright on the left, social icons on the right (envelope / linkedin / github), `--text-muted` default, `--text` on hover. Use the existing `dash_iconify` icons but at 14px not 20px.

---

## 6. Components

### 6.1 Tables (the main event)

All `dash_table.DataTable` instances share one style. Replace `HEADER` and `CELL` dicts in `app.py` with these:

```python
HEADER = {
    "backgroundColor": "transparent",
    "color": "var(--text-muted)",
    "fontWeight": "600",
    "fontSize": "11px",
    "letterSpacing": "0.06em",
    "textTransform": "uppercase",
    "textAlign": "left",
    "border": "none",
    "borderBottom": "1px solid var(--border)",
    "padding": "10px 12px",
    "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
}

CELL = {
    "backgroundColor": "transparent",
    "color": "var(--text)",
    "textAlign": "left",
    "border": "none",
    "borderBottom": "1px solid var(--border)",
    "padding": "10px 12px",
    "fontSize": "13px",
    "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
}
```

CSS overrides (in `s1.css`) for things `dash_table` won't accept inline:

```css
/* Numeric columns — right-align and tabular figures.
   Apply via column-id targeting in style_cell_conditional, or by
   selecting the .dash-cell:nth-child correspondence. */
.dash-table-container .column-PL,
.dash-table-container .column-W,
.dash-table-container .column-D,
.dash-table-container .column-L,
.dash-table-container .column-GS,
.dash-table-container .column-GA,
.dash-table-container .column-GD,
.dash-table-container .column-PTS,
.dash-table-container .column-Score {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace !important;
  font-variant-numeric: tabular-nums;
  text-align: right !important;
}

/* Row hover */
.dash-table-container tr:hover td {
  background-color: var(--hover) !important;
}

/* Last row: no bottom border */
.dash-table-container tr:last-child td {
  border-bottom: none !important;
}
```

Use `style_cell_conditional` for column-specific alignment in Python where the CSS approach is fragile across `dash_table` versions.

**Sort indicators.** Default `dash_table` sort arrows are ugly. Hide them and rely on column-header click affordance, or restyle to a single chevron in `--text-faint`.

### 6.2 Group mini-tables

Same row styling as the main tables but more compact:

- 9px padding (vs 10px).
- Group label (`Group A`, `Group B`, …) is a small caption above each table — 11px uppercase tracked, `--text-faint`, left-aligned, 8px below it.
- Optional: top 2 group teams (qualified) get a tiny leading "▸" or just a `--text` colour vs `--text-muted` for 3rd/4th — implementer's call, but if shown, must be greyscale.

### 6.3 Owner identity (the key decision)

**Replace full-cell pastel backgrounds with two compact accents:**

1. **Owner chip** next to the owner name in the Person leaderboard's `Who` column and the Team table's `Who` column:

   ```
   ●  Scott
   ```

   A 6px circle, `background: <owner-colour>`, vertical-align middle, 8px right margin. Implement as a Dash `html.Span` with inline style — easier than CSS pseudo-elements through `dash_table`.

2. **Team-row owner stripe** in the Team table and group tables. Use `style_data_conditional` to apply a 3px-equivalent left border-shadow per row, e.g.:

   ```python
   {"if": {"filter_query": '{Team} = "England"'},
    "boxShadow": "inset 3px 0 0 0 #ffadad"}
   ```

   `dash_table` supports `boxShadow` in conditional styles. This gives a thin vertical bar of owner colour at the start of the row. No background tint.

3. **Recent / Upcoming / Knockout fixtures.** The `Home` and `Away` columns each get a leading 6px owner-colour dot before the team name (same pattern as §6.3.1). Don't tint the cell.

   If the user pushes back wanting the old pastel cells, the fallback is: tint the row with the owner colour at **8% alpha** as a background (`rgba(...)` with `0.08` alpha), keeping `--text` text colour. Still readable, no longer dominant. Don't do this by default.

**Eliminated teams** (`In = "Out"`):

```python
{"if": {"filter_query": '{In} = "Out"', "column_id": "Team"},
 "color": "var(--eliminated)",
 "textDecoration": "line-through"}
```

Drop the `#960000` red.

### 6.4 Live-match indicator (optional, stretch)

If a fixture is currently in play (status from the scraper), show a 6px pulsing white dot before the score. CSS keyframes:

```css
@keyframes live-pulse { 0%,100% { opacity:1 } 50% { opacity:0.3 } }
.live-dot { animation: live-pulse 1.4s ease-in-out infinite; }
```

Skip if it adds scope.

---

## 7. Interactions & motion

- **Page load:** single fade-in with 8px upward translate, 400ms ease-out.

  ```css
  @keyframes fadeIn { from { opacity: 0; transform: translateY(8px) } to { opacity: 1; transform: none } }
  main { animation: fadeIn 400ms ease-out both; }
  ```

- **Row hover:** background → `--hover`, 120ms ease.
- **Link hover:** `--text-muted` → `--text`, 120ms.
- **Focus ring:** 2px solid `--focus`, 2px offset, only on `:focus-visible`.
- **Selection:**
  ```css
  ::selection { background: var(--selection-bg); color: var(--text); }
  ```
- No other transitions. No card tilts, no shimmer, no skeleton loaders.

---

## 8. Responsive

Single breakpoint at `768px`.

Below 768px:

- Page padding shrinks to `24px 16px 64px`.
- Header strip wraps: wordmark on top, "Last updated" below at 11px.
- All two-column rows (Leaderboard/Teams, Recent/Upcoming) stack to single column.
- Groups: `grid-template-columns: repeat(2, 1fr)` (was 3).
- Tables: allow horizontal scroll inside the table container; do not shrink fonts.

Below 480px:

- Groups: `1fr` (single column).

The current `.row { flex-direction: column }` mobile rule survives — it's already correct.

---

## 9. Files to touch

1. **`assets/s1.css`** — full rewrite. Preserve only the column-width grid utilities (`.five.columns`, `.seven.columns`, etc.) since `app.py` references them; everything else goes. Strip the Roboto Mono / Montserrat `@import`s (use system fonts and `ui-monospace`).
2. **`app.py`** —
   - Replace `COLOURS`, `HEADER`, `CELL` constants with the values above.
   - Replace the H1 header `Div` with the new header strip (wordmark + last-updated on the right).
   - Convert all H3 / H5 section labels to lowercase styling: `style={"fontSize": "12px", "fontWeight": 600, "letterSpacing": "0.08em", "textTransform": "uppercase", "color": "var(--text-faint)", "textAlign": "left", "margin": "0 0 12px"}`. Or move all of this into CSS classes and just attach `className="section-label"`.
   - In the Person and Team table generators, prepend an `html.Span` colour-dot to the owner column. Since `dash_table` doesn't render HTML in cells, the dot has to be implemented via `style_data_conditional` `boxShadow` on `column_id="Who"` instead — same trick as the team row stripe (`"boxShadow": "inset 8px 0 0 0 <colour>"` then add 16px left padding to the cell).
   - Remove the `In/Out` red rule; replace with the muted strikethrough rule.
   - Move `"last-updated"` text from footer into the header strip.
   - Footer: keep social icons but at 14px, colour `--text-muted` → `--text` on hover.
3. **`assets/`** — verify `s1.css` is the file Dash auto-loads. (Dash loads anything in `assets/` alphabetically; `s1.css` already works. If you rename, update Dash's expectation.)

Do **not** create new files.

---

## 10. Open taste decisions for the user

The implementer should pause and ask if any of these feel wrong:

1. **Owner colour as chip + stripe instead of full cell tint.** This is the biggest visual change vs 2024. If the user wants the pastel cells back, fall back to 8% alpha row tint (§6.3 fallback) — don't go back to full opacity.
2. **Eliminated teams: muted + strikethrough, no red.** If the user wants red, keep red but desaturate to `#7a2a2a` so it doesn't fight the greyscale palette.
3. **Last updated in the header, not the footer.** It's status info; status lives at the top in slick dashboards.
4. **Section labels left-aligned, not centred.** This is the single most "modern" move in the redesign.

---

## 11. Out of scope

- No new charts, sparklines, or visualisations. Tables only.
- No theme toggle. Dark only.
- No login or personalisation.
- No bracket diagram (PLAN_2026.md lists this as v2 stretch).
- No animation beyond the page fade-in and row hover.
