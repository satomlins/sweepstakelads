import logging
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
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

NUMERIC_COLS = ["PL", "W", "D", "L", "GS", "GA", "GD", "PNT", "Match"]

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

_PERSON_COLS  = ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
_TEAM_COLS    = ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
_RESULT_COLS        = ["Date", "Time", "HomeOwner", "Home", "Score", "Away", "AwayOwner", "Stage"]
_FIXTURE_COLS       = ["Match", "Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"]
_HOME_UPCOMING_COLS = ["Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"]
_OWNER_LABELS       = {"HomeOwner": "", "AwayOwner": ""}
_THIRD_COLS   = ["Group", "Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]


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
    )


# ---------------------------------------------------------------------------
# Pre-computed style constants (deterministic — no per-request inputs)
# ---------------------------------------------------------------------------

_NUMERIC_ALIGN   = _numeric_align(NUMERIC_COLS)
_PERSON_FMT      = _NUMERIC_ALIGN + _person_stripe_rules("Who") + _person_row_colour_rules()
_TEAM_ROW_COLOUR = _team_row_colour_rules()
_WHO_COL_COLOUR  = _owner_col_colour_rules("Who")
_FIXTURE_OWNER_FMT = (
    _owner_col_colour_rules("HomeOwner") + _owner_col_colour_rules("AwayOwner")
)
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
                                    " · 2026 WORLD CUP",
                                    style={
                                        "fontSize": "12px",
                                        "fontWeight": "600",
                                        "letterSpacing": "0.08em",
                                        "textTransform": "uppercase",
                                        "color": "var(--text-faint)",
                                        "marginLeft": "8px",
                                    },
                                ),
                            ]
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
                                        _make_table("recent-table", _RESULT_COLS, col_labels=_OWNER_LABELS),
                                    ],
                                    className="six columns",
                                ),
                                html.Div(
                                    [
                                        html.H3("Upcoming fixtures", style=SECTION_LABEL),
                                        _make_table("upcoming-table", _HOME_UPCOMING_COLS, col_labels=_OWNER_LABELS),
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
                                html.H3("Results", style=SECTION_LABEL),
                                _make_table("all-results-table", _RESULT_COLS, col_labels=_OWNER_LABELS),
                            ],
                        ),
                        html.Div(
                            [
                                html.H3("Fixtures", style=SECTION_LABEL),
                                _make_table("all-upcoming-table", _FIXTURE_COLS, col_labels=_OWNER_LABELS),
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
                        html.Span(
                            f"© {pd.Timestamp.now().year} Sweepstakelads · website by Scott Tomlins",
                            style={"color": "var(--text-faint)", "fontSize": "11px"},
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
    Output("person-table",     "data"),
    Output("person-table",     "style_data_conditional"),
    Output("person-table-lb",  "data"),
    Output("person-table-lb",  "style_data_conditional"),
    Output("team-table",       "data"),
    Output("team-table",       "style_data_conditional"),
    Output("group-tables",       "children"),
    Output("third-place-table",  "data"),
    Output("third-place-table",  "style_data_conditional"),
    Output("recent-table",     "data"),
    Output("recent-table",     "style_data_conditional"),
    Output("upcoming-table",   "data"),
    Output("upcoming-table",   "style_data_conditional"),
    Output("all-results-table",  "data"),
    Output("all-results-table",  "style_data_conditional"),
    Output("all-upcoming-table", "data"),
    Output("all-upcoming-table", "style_data_conditional"),
    Output("tz-label",         "children"),
    Output("last-updated",     "children"),
    Input("interval", "n_intervals"),
    Input("tz-offset", "data"),
)
def update_all(n, tz_offset_minutes):
    tz_minutes = tz_offset_minutes if tz_offset_minutes is not None else 0
    data = get_data()
    draw = load_draw()

    timestamp    = data["timestamp"]
    team_table   = data["team_table"]
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
    group_cols = ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
    group_children = []
    for g in sorted(group_standings.keys()):
        gdf = group_standings[g]
        if not gdf.empty and not draw.empty:
            gdf = gdf.merge(draw[["Team", "Who"]], on="Team", how="left")
            gdf["Who"] = gdf["Who"].fillna("")
        else:
            gdf = gdf.copy()
            gdf["Who"] = ""
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
               for c in ["PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]]
        )
        group_children.append(
            html.Div(
                [
                    html.P(f"Group {g}", style=GROUP_LABEL),
                    dash_table.DataTable(
                        data=gdf[group_cols].to_dict("records") if not gdf.empty else [],
                        columns=[{"name": c, "id": c} for c in group_cols],
                        style_header=hdr,
                        style_data=cell,
                        style_cell_conditional=_NUMERIC_ALIGN + group_col_widths,
                        style_data_conditional=gfmt,
                        style_table={"overflowX": "hidden"},
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
    tp_fmt = (
        _NUMERIC_ALIGN
        + _team_stripe_rules(draw, "Team")
        + _group_colour_rules(draw)
        + _WHO_COL_COLOUR
        + _TP_DIM_RULES
    )
    tp_data = tp_df[_THIRD_COLS].to_dict("records") if not tp_df.empty else []

    # Fixture formatting shared across result/upcoming tables
    fixture_colours = _fixture_colour_rules(draw)
    fixture_stripes = _team_stripe_rules(draw, "Home") + _team_stripe_rules(draw, "Away")
    fixture_fmt = fixture_stripes + fixture_colours + _FIXTURE_OWNER_FMT

    # Recent results (home page — last 10, newest first)
    finished = fixtures[fixtures["Status"] == "Finished"].tail(10).iloc[::-1]
    finished_loc = _localize_fixtures(finished, tz_minutes)
    recent_out = _add_owner_cols(finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage"]])

    # Upcoming fixtures (home page — next 10, ascending datetime order)
    upcoming = fixtures[fixtures["Status"] == "Upcoming"].head(10)
    upcoming_loc = _localize_fixtures(upcoming, tz_minutes)
    upcoming_out = _add_owner_cols(upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])

    # All results (fixtures page — newest first)
    all_finished = fixtures[fixtures["Status"] == "Finished"].iloc[::-1]
    all_finished_loc = _localize_fixtures(all_finished, tz_minutes)
    all_results_out = _add_owner_cols(all_finished_loc[["Date", "Time", "Home", "Score", "Away", "Stage"]])

    # All upcoming (fixtures page — ascending datetime order)
    all_upcoming = fixtures[fixtures["Status"] == "Upcoming"]
    all_upcoming_loc = _localize_fixtures(all_upcoming, tz_minutes)
    all_upcoming_out = _add_owner_cols(all_upcoming_loc[["Match", "Date", "Time", "Home", "Away", "Stage"]])

    return (
        person_table.to_dict("records"),
        _PERSON_FMT,
        person_table.to_dict("records"),
        _PERSON_FMT,
        team_table.to_dict("records"),
        team_fmt,
        group_children,
        tp_data,
        tp_fmt,
        recent_out.to_dict("records"),
        fixture_fmt,
        upcoming_out.to_dict("records"),
        fixture_fmt,
        all_results_out.to_dict("records"),
        fixture_fmt,
        all_upcoming_out.to_dict("records"),
        fixture_fmt,
        _tz_label(tz_minutes),
        f"Last updated: {timestamp} UTC",
    )


if __name__ == "__main__":
    app.run(debug=True)
