# FIX_WIDTH — Mobile Fixture/Result Layout

## Problem

On mobile (≤480px), the Results & Fixtures tables have 7–8 columns in a flat
`DataTable` row. They don't fit on a 375px screen without horizontal scrolling.

All information must be preserved — no columns dropped.

## Solution: Card Layout on Mobile

Replace the flat `DataTable` with a **card-based layout** on mobile. Desktop
keeps the existing table unchanged. The mobile view uses custom `html.Div`
components instead of `dash_table.DataTable`.

### Visual spec

```
13 Jun                          ← date header, groups matches by local date
─────────────────────────────
  Group B · 20:00               ← metadata: stage + time, small, dimmed
  Qatar 0 – 0 Switzerland      ← matchup: Home Score – Score Away, one line
  Scott · Ella                  ← owners: home owner · away owner, small, coloured
─────────────────────────────
  Group C · 23:00
  Brazil 2 – 1 Morocco
  Sam · Seth
─────────────────────────────

14 Jun
─────────────────────────────
  Group C · 02:00
  Haiti 0 – 0 Scotland
  Alex · Keshy
─────────────────────────────
```

### Layout rules

1. **Date header**: Matches are grouped by their local date (respecting the
   user's timezone offset, same as today). The date string (e.g. `13 Jun`)
   appears as a section header. No repeating date per row.

2. **Match card** — three lines stacked vertically within a bordered/separated
   block:

   - **Line 1 (metadata)**: `Stage · Time` — small font, dimmed colour
     (`var(--text-faint)` or similar). For fixtures with a Match number,
     render as `Group B · 20:00` (no match number on mobile). For the
     Results & Fixtures page's fixture section (which has Match numbers on
     desktop), still omit the match number on mobile.

   - **Line 2 (matchup)**: `Home Score – Score Away` for results;
     `Home v Away` for unplayed fixtures. Team names in default text colour.
     **Bold the winning team name** for results (same logic as the existing
     `Winner` column: `"HOME"` → bold left, `"AWAY"` → bold right, `"DRAW"`
     → neither bold). Score uses an en-dash `–` with spaces, matching the
     existing convention. AET/penalties annotations render inline:
     `Qatar 1 – 1 Switzerland (pens 4–3)`.

   - **Line 3 (owners)**: `HomeOwner · AwayOwner` — small font, each name
     in its owner colour (from `COLOURS` dict). If an owner is unknown/blank
     (knockout placeholders), that side is omitted or shows as `—`.

3. **Separators**: A subtle horizontal rule (`border-bottom: 1px solid
   var(--border)`) between cards within a date group. Slightly more space
   between date groups.

4. **No card background** — cards sit directly on the page background,
   separated by borders only. Consistent with the existing dark theme.

### Which tables get the card treatment

All four fixture/result outputs in `update_all`:

| Table ID | Page | Desktop | Mobile |
|---|---|---|---|
| `recent-table` | Home | DataTable (results) | Cards |
| `upcoming-table` | Home | DataTable (fixtures) | Cards |
| `all-results-table` | Results & Fixtures | DataTable (results) | Cards |
| `all-upcoming-table` | Results & Fixtures | DataTable (fixtures) | Cards |

Tables that do NOT change: person leaderboard, team table, group mini-tables,
third-place table. These already fit on mobile or are already compact.

### Breakpoint

- **≤480px**: card layout
- **>480px**: existing DataTable layout (no changes)

Detection: The callback already receives `tz-offset` from a clientside
callback. Add a second `dcc.Store(id="viewport-width")` populated by a
clientside callback (`window.innerWidth`), and use it in `update_all` to
decide which layout to render.

Alternatively, render **both** layouts and use CSS `display: none` /
`display: block` at the breakpoint to toggle. This avoids an extra callback
round-trip and means the server doesn't need to know the viewport width.
**This is the recommended approach** — it's simpler and avoids FOUC.

### Desktop: no changes

The existing `DataTable` layout, column sets, styling, sorting — all unchanged
on viewports >480px.

## Implementation detail

### Python (`app.py`)

Add a helper function that converts a fixture/result DataFrame into a list of
`html.Div` components in the card layout:

```python
def _fixture_cards(df, show_flags, is_result=True):
    """Build mobile card layout from fixture/result DataFrame."""
    cards = []
    current_date = None
    for _, row in df.iterrows():
        # Date group header
        if row["Date"] != current_date:
            current_date = row["Date"]
            cards.append(html.H4(current_date, className="card-date-header"))

        # Metadata line
        meta = f"{row['Stage']} · {row['Time']}"
        meta_div = html.Div(meta, className="card-meta")

        # Matchup line
        if is_result:
            home = row["Home"]
            away = row["Away"]
            score = row["Score"]
            matchup_text = f"{home} {score} {away}"
            # Bold winner via spans
            ...
        else:
            matchup_text = f"{home} v {away}"

        # Owner line
        ...

        cards.append(html.Div([meta_div, matchup_div, owner_div],
                              className="match-card"))
    return html.Div(cards, className="mobile-cards")
```

Each of the four table outputs becomes a wrapper `html.Div` containing both:
- The existing `DataTable` (class `desktop-only`)
- The card layout (class `mobile-only`)

### CSS (`assets/s1.css`)

```css
/* Toggle between table and cards at mobile breakpoint */
.mobile-only  { display: none; }
.desktop-only { display: block; }

@media screen and (max-width: 480px) {
  .mobile-only  { display: block; }
  .desktop-only { display: none; }
}

/* Card layout styles */
.card-date-header {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 24px 0 8px;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}

.card-date-header:first-child {
  margin-top: 0;
}

.match-card {
  padding: 10px 0;
  border-bottom: 1px solid var(--border);
}

.card-meta {
  font-size: 11px;
  color: var(--text-faint);
  margin-bottom: 4px;
}

.card-matchup {
  font-size: 14px;
  color: var(--text-primary);
  margin-bottom: 3px;
}

.card-matchup .winner {
  font-weight: 700;
}

.card-owners {
  font-size: 11px;
}

.card-owner {
  /* colour set inline from COLOURS dict */
}
```

## What does NOT change

- Desktop layout: identical to today
- Group mini-tables: already mobile-friendly
- Person / team leaderboard: no overflow issues
- Third-place table: same as group tables
- Flag toggle: still works — `_apply_flags` runs before card rendering
- Owner filter: still works — filtering happens before rendering
- Winner bolding: preserved via spans with `.winner` class

## Testing

1. `uv run python app.py` locally
2. Access via Tailscale from mobile device
3. Verify on:
   - iPhone SE (375px) — tightest common viewport
   - iPhone 14 (390px)
   - Desktop browser with DevTools responsive mode
4. Check all four tables: Home recent, Home upcoming, R&F results, R&F fixtures
5. Check flag toggle works in card view
6. Check owner filter works in card view
7. Check winner bolding appears for results in card view
