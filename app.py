import logging
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State
from dash_iconify import DashIconify
from datetime import datetime as _dt, timezone as _tz, timedelta

from tournament import get_data, load_draw
from scoring import compute_third_place_table

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COLOURS = {
    "Scott":   "#ffadad",
    "Hugo":    "#ffd6a5",
    "Sam":     "#fdffb6",
    "Brendan": "#caffbf",
    "Isaac":   "#9bf6ff",
    "Adrian":  "#a0c4ff",
    "Alex":    "#bdb2ff",
    "Mary":    "#ffc6ff",
    "Keshy":   "#c7ceea",
    "Jacob":   "#ffdac1",
    "Seth":    "#b5ead7",
    "Ella":    "#f8c8d4",
}

# Country name -> flag emoji. Keys must match the output of
# scraper._code_to_name exactly. Unmapped names fall through to the
# original string at substitution time (see _apply_flags).
FLAGS = {
    # CONCACAF
    "United States":  "🇺🇸",
    "Mexico":         "🇲🇽",
    "Canada":         "🇨🇦",
    "Costa Rica":     "🇨🇷",
    "Panama":         "🇵🇦",
    "Jamaica":        "🇯🇲",
    "Honduras":       "🇭🇳",
    "Trinidad & Tobago": "🇹🇹",
    "Haiti":          "🇭🇹",
    "Cuba":           "🇨🇺",
    "El Salvador":    "🇸🇻",
    "Nicaragua":      "🇳🇮",
    "Guatemala":      "🇬🇹",
    # UEFA
    "Germany":        "🇩🇪",
    "France":         "🇫🇷",
    "Spain":          "🇪🇸",
    "Portugal":       "🇵🇹",
    "England":        "🏴\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F",
    "Netherlands":    "🇳🇱",
    "Belgium":        "🇧🇪",
    "Italy":          "🇮🇹",
    "Switzerland":    "🇨🇭",
    "Croatia":        "🇭🇷",
    "Austria":        "🇦🇹",
    "Turkey":         "🇹🇷",
    "Denmark":        "🇩🇰",
    "Serbia":         "🇷🇸",
    "Scotland":       "🏴\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F",
    "Ukraine":        "🇺🇦",
    "Slovakia":       "🇸🇰",
    "Slovenia":       "🇸🇮",
    "Czech Republic": "🇨🇿",
    "Hungary":        "🇭🇺",
    "Georgia":        "🇬🇪",
    "Albania":        "🇦🇱",
    "Romania":        "🇷🇴",
    "Poland":         "🇵🇱",
    "Wales":          "🏴\U000E0067\U000E0062\U000E0077\U000E006C\U000E0073\U000E007F",
    "Norway":         "🇳🇴",
    "Sweden":         "🇸🇪",
    "Greece":         "🇬🇷",
    "Finland":        "🇫🇮",
    "Iceland":        "🇮🇸",
    "Northern Ireland": "🇬🇧",
    "Republic of Ireland": "🇮🇪",
    "Luxembourg":     "🇱🇺",
    "North Macedonia": "🇲🇰",
    "Bosnia and Herzegovina": "🇧🇦",
    "Montenegro":     "🇲🇪",
    # CONMEBOL
    "Brazil":         "🇧🇷",
    "Argentina":      "🇦🇷",
    "Uruguay":        "🇺🇾",
    "Colombia":       "🇨🇴",
    "Chile":          "🇨🇱",
    "Ecuador":        "🇪🇨",
    "Paraguay":       "🇵🇾",
    "Bolivia":        "🇧🇴",
    "Peru":           "🇵🇪",
    "Venezuela":      "🇻🇪",
    # AFC
    "Japan":          "🇯🇵",
    "South Korea":    "🇰🇷",
    "Australia":      "🇦🇺",
    "Iran":           "🇮🇷",
    "Saudi Arabia":   "🇸🇦",
    "Qatar":          "🇶🇦",
    "Iraq":           "🇮🇶",
    "Jordan":         "🇯🇴",
    "China":          "🇨🇳",
    "Uzbekistan":     "🇺🇿",
    "Bahrain":        "🇧🇭",
    "Oman":           "🇴🇲",
    "Kuwait":         "🇰🇼",
    "United Arab Emirates": "🇦🇪",
    "Syria":          "🇸🇾",
    "Kyrgyzstan":     "🇰🇬",
    "Tajikistan":     "🇹🇯",
    "Indonesia":      "🇮🇩",
    "Thailand":       "🇹🇭",
    "Vietnam":        "🇻🇳",
    "Palestine":      "🇵🇸",
    # CAF
    "Morocco":        "🇲🇦",
    "Egypt":          "🇪🇬",
    "Senegal":        "🇸🇳",
    "Nigeria":        "🇳🇬",
    "Cameroon":       "🇨🇲",
    "Ivory Coast":    "🇨🇮",
    "Ghana":          "🇬🇭",
    "Algeria":        "🇩🇿",
    "Tunisia":        "🇹🇳",
    "South Africa":   "🇿🇦",
    "Mali":           "🇲🇱",
    "DR Congo":       "🇨🇩",
    "Tanzania":       "🇹🇿",
    "Zambia":         "🇿🇲",
    "Mozambique":     "🇲🇿",
    "Comoros":        "🇰🇲",
    "Cape Verde":     "🇨🇻",
    "Benin":          "🇧🇯",
    "Ethiopia":       "🇪🇹",
    "Gabon":          "🇬🇦",
    "Zimbabwe":       "🇿🇼",
    "Gambia":         "🇬🇲",
    "Burkina Faso":   "🇧🇫",
    "Uganda":         "🇺🇬",
    "Kenya":          "🇰🇪",
    "Sudan":          "🇸🇩",
    # OFC
    "New Zealand":    "🇳🇿",
    "Curaçao":        "🇨🇼",
}

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

NUMERIC_COLS = ["PL", "W", "D", "L", "GS", "GA", "GD", "PTS", "Match"]

SECTION_LABEL = {
    "fontSize": "12px",
    "fontWeight": "600",
    "letterSpacing": "0.08em",
    "textTransform": "uppercase",
    "color": "var(--text-faint)",
    "textAlign": "left",
    "margin": "0 0 12px",
}

GROUP_LABEL = {
    "fontSize": "11px",
    "fontWeight": "600",
    "letterSpacing": "0.08em",
    "textTransform": "uppercase",
    "color": "var(--text-faint)",
    "margin": "0 0 8px",
}

_PERSON_COLS  = ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
_TEAM_COLS    = ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
_RESULT_COLS        = ["Date", "Time", "HomeOwner", "Home", "Score", "Away", "AwayOwner", "Stage"]
_FIXTURE_COLS       = ["Match", "Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"]
_HOME_UPCOMING_COLS = ["Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"]
_OWNER_LABELS       = {"HomeOwner": "", "AwayOwner": ""}
_THIRD_COLS   = ["Group", "Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]


# ---------------------------------------------------------------------------
# Style helpers
# ---------------------------------------------------------------------------

def _numeric_align(cols: list[str]) -> list[dict]:
    return [
        {
            "if": {"column_id": c},
            "textAlign": "right",
            "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
            "fontVariantNumeric": "tabular-nums",
        }
        for c in cols
    ]


def _person_stripe_rules(col: str) -> list[dict]:
    return [
        {
            "if": {
                "filter_query": f'{{{col}}} = "{name}"',
                "column_id": col,
            },
            "boxShadow": f"inset 8px 0 0 0 {colour}",
            "paddingLeft": "20px",
        }
        for name, colour in COLOURS.items()
    ]


def _team_stripe_rules(draw: pd.DataFrame, col: str = "Team") -> list[dict]:
    if draw.empty:
        return []
    rules = []
    for _, row in draw.iterrows():
        owner = row["Who"]
        team = row["Team"]
        colour = COLOURS.get(owner)
        if not colour:
            continue
        rules.append(
            {
                "if": {
                    "filter_query": f'{{{col}}} = "{team}"',
                    "column_id": col,
                },
                "boxShadow": f"inset 3px 0 0 0 {colour}",
            }
        )
    return rules


def _who_stripe_rules(draw: pd.DataFrame, col: str = "Who") -> list[dict]:
    return _person_stripe_rules(col)


def _eliminated_rule() -> dict:
    return {
        "if": {
            "filter_query": "{In} = 'Out'",
            "column_id": "Team",
        },
        "color": "var(--eliminated)",
        "textDecoration": "line-through",
    }


def _person_row_colour_rules() -> list[dict]:
    return [
        {"if": {"filter_query": f'{{Who}} = "{name}"'}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _team_row_colour_rules() -> list[dict]:
    return [
        {"if": {"filter_query": f'{{Who}} = "{name}"'}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _fixture_colour_rules(draw: pd.DataFrame) -> list[dict]:
    if draw.empty:
        return []
    rules = []
    for _, row in draw.iterrows():
        colour = COLOURS.get(row["Who"])
        if not colour:
            continue
        for col in ("Home", "Away"):
            rules.append({
                "if": {"filter_query": f'{{{col}}} = "{row["Team"]}"', "column_id": col},
                "color": colour,
            })
    return rules


def _group_colour_rules(draw: pd.DataFrame) -> list[dict]:
    if draw.empty:
        return []
    rules = []
    for _, row in draw.iterrows():
        colour = COLOURS.get(row["Who"])
        if colour:
            rules.append({
                "if": {"filter_query": f'{{Team}} = "{row["Team"]}"', "column_id": "Team"},
                "color": colour,
            })
    return rules


def _owner_col_colour_rules(col: str) -> list[dict]:
    return [
        {"if": {"filter_query": f'{{{col}}} = "{name}"', "column_id": col}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _fmt_local(dt_utc_str: str, tz_minutes: int) -> tuple[str, str]:
    """Convert an ISO UTC datetime string to (date_label, time_label) in the user's local timezone."""
    if not dt_utc_str:
        return "", ""
    try:
        dt = _dt.fromisoformat(dt_utc_str).replace(tzinfo=_tz.utc)
        local = dt + timedelta(minutes=tz_minutes)
        return local.strftime("%-d %b"), local.strftime("%H:%M")
    except (ValueError, TypeError):
        return "", ""
    except Exception:
        logger.exception("Unexpected error formatting datetime %r", dt_utc_str)
        return "", ""


def _tz_label(tz_minutes: int) -> str:
    h, m = divmod(abs(tz_minutes), 60)
    sign = "+" if tz_minutes >= 0 else "-"
    if h == 0 and m == 0:
        return "All times UTC"
    return f"All times UTC{sign}{h}" if m == 0 else f"All times UTC{sign}{h}:{m:02d}"


def _apply_flags(df: pd.DataFrame, cols: list[str], show: bool) -> pd.DataFrame:
    if not show or df.empty:
        return df.copy()
    out = df.copy()
    for col in cols:
        if col in out.columns:
            out[col] = out[col].map(lambda v: FLAGS.get(v, v))
    return out


def _owner_span(name: str) -> html.Span:
    if name:
        return html.Span(name, style={"color": COLOURS.get(name, "var(--text-faint)")})
    return html.Span("—", style={"color": "var(--text-faint)"})


def _fixture_cards(df: pd.DataFrame, is_result: bool = True) -> html.Div:
    """Build mobile card layout from a fixture/result DataFrame."""
    if df.empty:
        return html.Div(className="mobile-cards")
    cards = []
    current_date = None
    for _, row in df.iterrows():
        date = row.get("Date", "")
        if date != current_date:
            current_date = date
            cards.append(html.H4(date, className="card-date-header"))
        meta_div = html.Div(
            f"{row.get('Stage', '')} · {row.get('Time', '')}",
            className="card-meta",
        )
        home = row.get("Home", "")
        away = row.get("Away", "")
        home_owner = row.get("HomeOwner", "")
        away_owner = row.get("AwayOwner", "")
        home_colour = COLOURS.get(home_owner, "var(--text)") if home_owner else "var(--text)"
        away_colour = COLOURS.get(away_owner, "var(--text)") if away_owner else "var(--text)"
        if is_result:
            score = row.get("Score", "").replace("–", " – ", 1)
            winner = row.get("Winner", "")
            home_el = html.Span(home, className="winner", style={"color": home_colour}) if winner == "HOME" else html.Span(home, style={"color": home_colour})
            away_el = html.Span(away, className="winner", style={"color": away_colour}) if winner == "AWAY" else html.Span(away, style={"color": away_colour})
            matchup_div = html.Div(
                [
                    html.Div(home_el, className="card-matchup-home"),
                    html.Div(score, className="card-matchup-score"),
                    html.Div(away_el, className="card-matchup-away"),
                ],
                className="card-matchup",
            )
        else:
            matchup_div = html.Div(
                [
                    html.Div(html.Span(home, style={"color": home_colour}), className="card-matchup-home"),
                    html.Div("v", className="card-matchup-score"),
                    html.Div(html.Span(away, style={"color": away_colour}), className="card-matchup-away"),
                ],
                className="card-matchup",
            )
        owner_div = html.Div(
            [
                html.Div(_owner_span(home_owner), className="card-owner-home"),
                html.Div("·", className="card-owner-sep"),
                html.Div(_owner_span(away_owner), className="card-owner-away"),
            ],
            className="card-owners",
        )
        cards.append(html.Div([meta_div, matchup_div, owner_div], className="match-card"))
    return html.Div(cards, className="mobile-cards")


def _localize_fixtures(df: pd.DataFrame, tz_minutes: int) -> pd.DataFrame:
    """Replace Date/Time columns with timezone-correct values derived from DatetimeUTC.

    Always returns a frame with Date and Time columns, even when the input is empty or
    DatetimeUTC is absent — downstream projections require Time to exist.
    """
    out = df.copy()
    if out.empty or "DatetimeUTC" not in out.columns:
        if "Date" not in out.columns:
            out["Date"] = pd.Series(dtype=str)
        out["Time"] = pd.Series(dtype=str)
        return out
    pairs = [_fmt_local(r, tz_minutes) for r in df["DatetimeUTC"]]
    local_dates = [p[0] for p in pairs]
    local_times = [p[1] for p in pairs]
    out["Date"] = [ld if ld else od for ld, od in zip(local_dates, out["Date"])]
    out["Time"] = local_times
    return out


def _make_table(
    table_id: str,
    columns: list[str],
    sort: bool = False,
    compact: bool = False,
    col_labels: dict | None = None,
) -> dash_table.DataTable:
    col_labels = col_labels or {}
    cell = {**CELL}
    if compact:
        cell = {**cell, "padding": "7px 10px"}
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": col_labels.get(c, c), "id": c, "hideable": False} for c in columns],
        style_header=HEADER,
        style_data=cell,
        style_cell_conditional=_NUMERIC_ALIGN,
        sort_action="native" if sort else "none",
        style_table={"overflowX": "auto"},
        cell_selectable=False,
    )


# ---------------------------------------------------------------------------
# Pre-computed style constants (deterministic — no per-request inputs)
# ---------------------------------------------------------------------------

_NUMERIC_ALIGN   = _numeric_align(NUMERIC_COLS)
_PERSON_FMT      = _NUMERIC_ALIGN + _person_stripe_rules("Who") + _person_row_colour_rules()
_TEAM_ROW_COLOUR = _team_row_colour_rules()
_WHO_COL_COLOUR  = _owner_col_colour_rules("Who")
_TP_DIM_RULES = [
    {"if": {"row_index": i}, "color": "var(--text-faint)", "opacity": "0.6"}
    for i in range(8, 12)
]


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "SWEEPSTAKELADS 2026"
server = app.server

app.layout = html.Div(
    [
        dcc.Location(id="url", refresh=False),
        dcc.Interval(id="interval", interval=5 * 60 * 1000),
        dcc.Store(id="tz-offset", data=None),
        dcc.Store(id="show-goals", data=False),
        dcc.Store(id="show-flags", data=False),

        html.Main(
            [
                # Header strip
                html.Header(
                    [
                        html.Div(
                            [
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
                            ],
                            className="header-wordmark",
                        ),
                        html.Div(
                            [
                                html.Span(
                                    id="tz-label",
                                    style={
                                        "fontSize": "11px",
                                        "color": "var(--text-faint)",
                                        "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                                    },
                                ),
                                html.Div(
                                    id="last-updated",
                                    style={
                                        "fontSize": "11px",
                                        "color": "var(--text-faint)",
                                        "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                                    },
                                ),
                            ],
                            className="header-meta",
                            style={"display": "flex", "flexDirection": "column", "alignItems": "flex-end", "gap": "2px"},
                        ),
                    ],
                    className="site-header",
                ),

                # Tab navigation
                html.Nav(
                    [
                        dcc.Link("Home",                href="/",            id="tab-home",       className="tab-link"),
                        dcc.Link("Leaderboard",         href="/leaderboard", id="tab-leaderboard", className="tab-link"),
                        dcc.Link("Results & Fixtures",  href="/fixtures",    id="tab-fixtures",    className="tab-link"),
                        dcc.Link("Group Stages",        href="/groups",      id="tab-groups",      className="tab-link"),
                    ],
                    className="tab-nav",
                ),

                # ── Page: Home ────────────────────────────────────────────
                html.Div(
                    [
                        # Person leaderboard — full width
                        html.Div(
                            [
                                html.H3("Leaderboard", style=SECTION_LABEL),
                                _make_table("person-table", _PERSON_COLS),
                            ],
                        ),
                        # Recent results + Upcoming fixtures — side by side
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H3("Recent results", style=SECTION_LABEL),
                                        html.Div(id="recent-cards"),
                                    ],
                                    className="six columns",
                                ),
                                html.Div(
                                    [
                                        html.H3("Upcoming fixtures", style=SECTION_LABEL),
                                        html.Div(id="upcoming-cards"),
                                    ],
                                    className="six columns",
                                ),
                            ],
                            className="row section-gap",
                        ),
                    ],
                    id="page-home",
                ),

                # ── Page: Leaderboard ─────────────────────────────────────
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3("Leaderboard", style=SECTION_LABEL),
                                _make_table("person-table-lb", _PERSON_COLS),
                            ],
                        ),
                        html.Div(
                            [
                                html.H3("Teams", style=SECTION_LABEL),
                                _make_table("team-table", _TEAM_COLS, sort=True),
                            ],
                            className="section-gap",
                        ),
                    ],
                    id="page-leaderboard",
                    style={"display": "none"},
                ),

                # ── Page: Group Stage ─────────────────────────────────────
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3("Groups", style=SECTION_LABEL),
                                html.Div(id="group-tables", className="groups-grid"),
                            ],
                        ),
                        html.Div(
                            [
                                html.H3("Third-place standings", style=SECTION_LABEL),
                                html.P(
                                    "Top 8 of 12 qualify for the round of 32",
                                    style={
                                        "fontSize": "11px",
                                        "color": "var(--text-faint)",
                                        "margin": "0 0 10px",
                                        "fontFamily": "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                                    },
                                ),
                                _make_table("third-place-table", _THIRD_COLS),
                            ],
                            className="section-gap",
                        ),
                    ],
                    id="page-groups",
                    style={"display": "none"},
                ),

                # ── Page: Fixtures & Results ──────────────────────────────
                html.Div(
                    [
                        html.Div(
                            [
                                html.Label(
                                    "FILTER",
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
                                    options=[{"label": name, "value": name} for name in sorted(COLOURS.keys())],
                                    value=[],
                                    multi=True,
                                    placeholder="All",
                                    clearable=True,
                                    className="owner-filter",
                                ),
                            ],
                            className="owner-filter-wrap",
                            style={"marginBottom": "20px", "maxWidth": "240px"},
                        ),
                        html.Div(
                            [
                                html.H3("Results", style=SECTION_LABEL),
                                html.Div(id="all-results-cards"),
                            ],
                        ),
                        html.Div(
                            [
                                html.H3("Fixtures", style=SECTION_LABEL),
                                html.Div(id="all-upcoming-cards"),
                            ],
                            className="section-gap",
                        ),
                    ],
                    id="page-fixtures",
                    style={"display": "none"},
                ),

                # Footer
                html.Footer(
                    [
                        html.Div(
                            [
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
                            ],
                            style={"display": "flex", "alignItems": "center", "gap": "16px"},
                        ),
                        html.Div(
                            [
                                dcc.Link(
                                    DashIconify(icon="bi:envelope", width=14),
                                    href="mailto:scott@stomlins.com",
                                    target="_blank",
                                    className="footer-icon",
                                ),
                                dcc.Link(
                                    DashIconify(icon="bi:linkedin", width=14),
                                    href="https://www.linkedin.com/in/scotttomlins/",
                                    target="_blank",
                                    className="footer-icon",
                                ),
                                dcc.Link(
                                    DashIconify(icon="bi:github", width=14),
                                    href="https://github.com/satomlins/",
                                    target="_blank",
                                    className="footer-icon",
                                ),
                            ],
                            style={"display": "flex", "gap": "12px", "alignItems": "center"},
                        ),
                    ],
                    className="site-footer",
                ),
            ],
        ),
    ],
    id="mainContainer",
)


# ---------------------------------------------------------------------------
# Callbacks
# ---------------------------------------------------------------------------

app.clientside_callback(
    """
    function(pathname) {
        return -new Date().getTimezoneOffset();
    }
    """,
    Output("tz-offset", "data"),
    Input("url", "pathname"),
)


@app.callback(
    Output("tab-home",        "className"),
    Output("tab-leaderboard", "className"),
    Output("tab-groups",      "className"),
    Output("tab-fixtures",    "className"),
    Output("page-home",        "style"),
    Output("page-leaderboard", "style"),
    Output("page-groups",      "style"),
    Output("page-fixtures",    "style"),
    Input("url", "pathname"),
)
def switch_page(pathname):
    show = {}
    hide = {"display": "none"}
    active   = "tab-link active"
    inactive = "tab-link"
    if pathname == "/leaderboard":
        return inactive, active, inactive, inactive, hide, show, hide, hide
    if pathname == "/groups":
        return inactive, inactive, active, inactive, hide, hide, show, hide
    if pathname == "/fixtures":
        return inactive, inactive, inactive, active, hide, hide, hide, show
    return active, inactive, inactive, inactive, show, hide, hide, hide


@app.callback(
    Output("show-goals",      "data"),
    Output("goals-toggle",    "children"),
    Input("goals-toggle",     "n_clicks"),
    State("show-goals",       "data"),
    prevent_initial_call=True,
)
def toggle_goals(_n, current):
    show = not current
    return show, "Hide GS/GA" if show else "Show GS/GA"


@app.callback(
    Output("show-flags",   "data"),
    Output("flags-toggle", "children"),
    Input("flags-toggle",  "n_clicks"),
    State("show-flags",    "data"),
    prevent_initial_call=True,
)
def toggle_flags(_n, current):
    show = not current
    return show, "Show names" if show else "Show flags"


@app.callback(
    Output("person-table",       "data"),
    Output("person-table",       "style_data_conditional"),
    Output("person-table",       "columns"),
    Output("person-table-lb",    "data"),
    Output("person-table-lb",    "style_data_conditional"),
    Output("person-table-lb",    "columns"),
    Output("team-table",         "data"),
    Output("team-table",         "style_data_conditional"),
    Output("team-table",         "columns"),
    Output("group-tables",       "children"),
    Output("third-place-table",  "data"),
    Output("third-place-table",  "style_data_conditional"),
    Output("third-place-table",  "columns"),
    Output("recent-cards",       "children"),
    Output("upcoming-cards",     "children"),
    Output("all-results-cards",  "children"),
    Output("all-upcoming-cards", "children"),
    Output("tz-label",           "children"),
    Output("last-updated",       "children"),
    Input("interval",      "n_intervals"),
    Input("tz-offset",     "data"),
    Input("show-goals",    "data"),
    Input("show-flags",    "data"),
    Input("owner-filter",  "value"),
)
def update_all(n, tz_offset_minutes, show_goals_data, show_flags_data, selected_owners):
    tz_minutes = tz_offset_minutes if tz_offset_minutes is not None else 0
    show_goals = bool(show_goals_data)
    show_flags = bool(show_flags_data)
    selected_owners = selected_owners or []
    _skip = set() if show_goals else {"GS", "GA"}

    def _cols(names):
        return [{"name": c, "id": c, "hideable": False} for c in names]

    person_cols  = [c for c in _PERSON_COLS  if c not in _skip]
    team_cols    = [c for c in _TEAM_COLS    if c not in _skip]
    third_cols   = [c for c in _THIRD_COLS   if c not in _skip]

    data = get_data()
    draw = load_draw()

    timestamp    = data["timestamp"]
    team_table   = _apply_flags(data["team_table"],   ["Team"], show_flags)
    person_table = data["person_table"]
    group_standings = data["group_standings"]
    fixtures     = data["fixtures"].copy()
    fixtures["Match"] = range(1, len(fixtures) + 1)

    # Team table: row colour + stripes + eliminated (draw-dependent parts stay in callback)
    team_fmt = (
        _NUMERIC_ALIGN
        + _team_stripe_rules(draw, "Team")
        + _who_stripe_rules(draw, "Who")
        + _TEAM_ROW_COLOUR
        + [_eliminated_rule()]
    )

    team_to_owner = {} if draw.empty else dict(zip(draw["Team"], draw["Who"]))

    def _add_owner_cols(df: pd.DataFrame) -> pd.DataFrame:
        out = df.copy()
        if "Home" in out.columns:
            out["HomeOwner"] = out["Home"].map(lambda t: team_to_owner.get(t, ""))
        if "Away" in out.columns:
            out["AwayOwner"] = out["Away"].map(lambda t: team_to_owner.get(t, ""))
        return out

    # Group tables
    group_cols = ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]
    g_cols = [c for c in group_cols if c not in _skip]
    group_children = []
    for g in sorted(group_standings.keys()):
        gdf = group_standings[g]
        if not gdf.empty and not draw.empty:
            gdf = gdf.merge(draw[["Team", "Who"]], on="Team", how="left")
            gdf["Who"] = gdf["Who"].fillna("")
        else:
            gdf = gdf.copy()
            gdf["Who"] = ""
        gdf = _apply_flags(gdf, ["Team"], show_flags)
        gfmt = (
            _NUMERIC_ALIGN
            + _team_stripe_rules(draw, "Team")
            + _group_colour_rules(draw)
            + _WHO_COL_COLOUR
        )
        cell = {**CELL, "padding": "5px 6px", "fontSize": "12px"}
        hdr  = {**HEADER, "padding": "8px 6px"}
        group_col_widths = (
            [{"if": {"column_id": "Team"}, "minWidth": "80px", "width": "80px", "maxWidth": "80px",
              "overflow": "hidden", "textOverflow": "ellipsis"}]
            + [{"if": {"column_id": "Who"}, "minWidth": "52px", "width": "52px", "maxWidth": "52px",
               "overflow": "hidden", "textOverflow": "ellipsis"}]
            + [{"if": {"column_id": c}, "minWidth": "26px", "width": "26px", "maxWidth": "26px"}
               for c in ["PL", "W", "D", "L", "GS", "GA", "GD", "PTS"]]
        )
        group_children.append(
            html.Div(
                [
                    html.P(f"Group {g}", style=GROUP_LABEL),
                    dash_table.DataTable(
                        data=gdf[g_cols].to_dict("records") if not gdf.empty else [],
                        columns=[{"name": c, "id": c} for c in g_cols],
                        style_header=hdr,
                        style_data=cell,
                        style_cell_conditional=_NUMERIC_ALIGN + group_col_widths,
                        style_data_conditional=gfmt,
                        style_table={"overflowX": "hidden"},
                        cell_selectable=False,
                    ),
                ],
                className="group-cell",
            )
        )

    # Third-place standings table
    tp_df = compute_third_place_table(group_standings)
    if not tp_df.empty and not draw.empty:
        tp_df = tp_df.merge(draw[["Team", "Who"]], on="Team", how="left")
        tp_df["Who"] = tp_df["Who"].fillna("")
    else:
        tp_df = tp_df.copy()
        tp_df["Who"] = ""
    tp_df = _apply_flags(tp_df, ["Team"], show_flags)
    tp_fmt = (
        _NUMERIC_ALIGN
        + _team_stripe_rules(draw, "Team")
        + _group_colour_rules(draw)
        + _WHO_COL_COLOUR
        + _TP_DIM_RULES
    )
    tp_data = tp_df[third_cols].to_dict("records") if not tp_df.empty else []

    # Recent results (home page — last 10, newest first)
    finished = fixtures[fixtures["Status"] == "Finished"].tail(10).iloc[::-1]
    finished_loc = _localize_fixtures(finished, tz_minutes)
    recent_out = _add_owner_cols(finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage", "Winner"]])
    recent_out = _apply_flags(recent_out, ["Home", "Away"], show_flags)

    # Upcoming fixtures (home page — next 10, ascending datetime order)
    upcoming = fixtures[fixtures["Status"] == "Upcoming"].head(10)
    upcoming_loc = _localize_fixtures(upcoming, tz_minutes)
    upcoming_out = _add_owner_cols(upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])
    upcoming_out = _apply_flags(upcoming_out, ["Home", "Away"], show_flags)

    # All results (fixtures page — newest first)
    all_finished = fixtures[fixtures["Status"] == "Finished"].iloc[::-1]
    all_finished_loc = _localize_fixtures(all_finished, tz_minutes)
    all_results_out = _add_owner_cols(all_finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage", "Winner"]])
    if selected_owners:
        all_results_out = all_results_out[
            all_results_out["HomeOwner"].isin(selected_owners)
            | all_results_out["AwayOwner"].isin(selected_owners)
        ]
    all_results_out = _apply_flags(all_results_out, ["Home", "Away"], show_flags)

    # All upcoming (fixtures page — ascending datetime order)
    all_upcoming = fixtures[fixtures["Status"] == "Upcoming"]
    all_upcoming_loc = _localize_fixtures(all_upcoming, tz_minutes)
    all_upcoming_out = _add_owner_cols(all_upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])
    if selected_owners:
        all_upcoming_out = all_upcoming_out[
            all_upcoming_out["HomeOwner"].isin(selected_owners)
            | all_upcoming_out["AwayOwner"].isin(selected_owners)
        ]
    all_upcoming_out = _apply_flags(all_upcoming_out, ["Home", "Away"], show_flags)

    return (
        person_table.to_dict("records"),
        _PERSON_FMT,
        _cols(person_cols),
        person_table.to_dict("records"),
        _PERSON_FMT,
        _cols(person_cols),
        team_table.to_dict("records"),
        team_fmt,
        _cols(team_cols),
        group_children,
        tp_data,
        tp_fmt,
        _cols(third_cols),
        _fixture_cards(recent_out, is_result=True),
        _fixture_cards(upcoming_out, is_result=False),
        _fixture_cards(all_results_out, is_result=True),
        _fixture_cards(all_upcoming_out, is_result=False),
        _tz_label(tz_minutes),
        "Last updated: {} {}".format(*_fmt_local(timestamp, tz_minutes)),
    )


if __name__ == "__main__":
    app.run(debug=True)
