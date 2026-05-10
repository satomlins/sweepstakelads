import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from dash_iconify import DashIconify

from tournament import get_data, load_draw

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

NUMERIC_COLS = ["PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]

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
    """Left-border stripe on owner rows (Who column)."""
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
    """Inset left-border stripe on team rows, coloured by owner."""
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
    """Stripe the Who column in team table by owner colour."""
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


def _make_table(
    table_id: str,
    columns: list[str],
    hidden: list[str] | None = None,
    sort: bool = False,
    compact: bool = False,
) -> dash_table.DataTable:
    hidden = hidden or []
    cell = {**CELL}
    if compact:
        cell = {**cell, "padding": "7px 10px"}
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": c, "id": c, "hideable": False} for c in columns],
        hidden_columns=hidden,
        style_header=HEADER,
        style_data=cell,
        style_cell_conditional=_numeric_align(NUMERIC_COLS),
        sort_action="native" if sort else "none",
        style_table={"overflowX": "auto"},
    )


# ---------------------------------------------------------------------------
# App layout
# ---------------------------------------------------------------------------

app = dash.Dash(
    __name__,
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
)
app.title = "SWEEPSTAKELADS 2026"
server = app.server

app.layout = html.Div(
    [
        dcc.Interval(id="interval", interval=5 * 60 * 1000),

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
                                    " · 2026 FIFA WORLD CUP",
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
                            id="last-updated",
                            style={
                                "fontSize": "11px",
                                "color": "var(--text-faint)",
                                "fontFamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
                            },
                        ),
                    ],
                    className="site-header",
                ),

                # Row 1 — Leaderboard + Teams
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3("Leaderboard", style=SECTION_LABEL),
                                _make_table(
                                    "person-table",
                                    ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"],
                                ),
                            ],
                            className="five columns",
                        ),
                        html.Div(
                            [
                                html.H3("Teams", style=SECTION_LABEL),
                                _make_table(
                                    "team-table",
                                    ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"],
                                    sort=True,
                                ),
                            ],
                            className="seven columns",
                        ),
                    ],
                    className="row section-gap",
                ),

                # Row 2 — Groups
                html.Div(
                    [
                        html.H3("Groups", style=SECTION_LABEL),
                        html.Div(id="group-tables", className="groups-grid"),
                    ],
                    className="section-gap",
                ),

                # Row 3 — Recent + Upcoming
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3("Recent results", style=SECTION_LABEL),
                                _make_table(
                                    "recent-table",
                                    ["Date", "Time", "Home", "Score", "Away", "Stage"],
                                ),
                            ],
                            className="six columns",
                        ),
                        html.Div(
                            [
                                html.H3("Upcoming fixtures", style=SECTION_LABEL),
                                _make_table(
                                    "upcoming-table",
                                    ["Date", "Time", "Home", "Away", "Stage"],
                                ),
                            ],
                            className="six columns",
                        ),
                    ],
                    className="row section-gap",
                ),

                # Row 4 — Knockout
                html.Div(
                    [
                        html.H3("Knockout stage", style=SECTION_LABEL),
                        _make_table(
                            "knockout-table",
                            ["Stage", "Home", "Score", "Away"],
                        ),
                    ],
                    id="knockout-section",
                    className="section-gap",
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
# Callback
# ---------------------------------------------------------------------------

@app.callback(
    Output("person-table", "data"),
    Output("person-table", "style_data_conditional"),
    Output("team-table", "data"),
    Output("team-table", "style_data_conditional"),
    Output("group-tables", "children"),
    Output("recent-table", "data"),
    Output("recent-table", "style_data_conditional"),
    Output("upcoming-table", "data"),
    Output("upcoming-table", "style_data_conditional"),
    Output("knockout-table", "data"),
    Output("knockout-table", "style_data_conditional"),
    Output("last-updated", "children"),
    Input("interval", "n_intervals"),
)
def update_all(n):
    data = get_data()
    draw = load_draw()

    timestamp = data["timestamp"]
    team_table = data["team_table"]
    person_table = data["person_table"]
    group_standings = data["group_standings"]
    fixtures = data["fixtures"]

    # Person table: stripe Who column by owner colour
    person_fmt = (
        _numeric_align(NUMERIC_COLS)
        + _person_stripe_rules("Who")
    )

    # Team table: eliminated rule, team stripe, Who stripe
    team_fmt = (
        _numeric_align(NUMERIC_COLS)
        + [_eliminated_rule()]
        + _team_stripe_rules(draw, "Team")
        + _who_stripe_rules(draw, "Who")
    )

    # Group tables
    group_cols = ["Team", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
    group_children = []
    for g in sorted(group_standings.keys()):
        gdf = group_standings[g]
        gfmt = (
            _numeric_align(NUMERIC_COLS)
            + _team_stripe_rules(draw, "Team")
        )
        cell = {**CELL, "padding": "7px 10px"}
        group_children.append(
            html.Div(
                [
                    html.P(f"Group {g}", style=GROUP_LABEL),
                    dash_table.DataTable(
                        data=gdf[group_cols].to_dict("records") if not gdf.empty else [],
                        columns=[{"name": c, "id": c} for c in group_cols],
                        style_header=HEADER,
                        style_data=cell,
                        style_cell_conditional=_numeric_align(NUMERIC_COLS),
                        style_data_conditional=gfmt,
                        style_table={"overflowX": "auto"},
                    ),
                ],
                className="group-cell",
            )
        )

    # Recent results
    finished = fixtures[fixtures["Status"] == "Finished"].tail(10).iloc[::-1]
    recent_fmt = (
        _team_stripe_rules(draw, "Home")
        + _team_stripe_rules(draw, "Away")
    )

    # Upcoming fixtures
    upcoming = fixtures[fixtures["Status"] == "Upcoming"].head(10)
    upcoming_fmt = (
        _team_stripe_rules(draw, "Home")
        + _team_stripe_rules(draw, "Away")
    )

    # Knockout stage
    ko = fixtures[~fixtures["Stage"].str.startswith("Group", na=False)].copy()
    ko_fmt = (
        _team_stripe_rules(draw, "Home")
        + _team_stripe_rules(draw, "Away")
    )

    return (
        person_table.to_dict("records"),
        person_fmt,
        team_table.to_dict("records"),
        team_fmt,
        group_children,
        finished[["Date", "Time", "Home", "Score", "Away", "Stage"]].to_dict("records"),
        recent_fmt,
        upcoming[["Date", "Time", "Home", "Away", "Stage"]].to_dict("records"),
        upcoming_fmt,
        ko[["Stage", "Home", "Score", "Away"]].to_dict("records") if not ko.empty else [],
        ko_fmt,
        f"Last updated: {timestamp} UTC",
    )


if __name__ == "__main__":
    app.run(debug=True)
