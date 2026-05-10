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


def _person_row_colour_rules() -> list[dict]:
    """Colour entire row text by owner (no column_id = applies to all cells)."""
    return [
        {"if": {"filter_query": f'{{Who}} = "{name}"'}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _team_row_colour_rules() -> list[dict]:
    """Colour entire row text by Who column."""
    return [
        {"if": {"filter_query": f'{{Who}} = "{name}"'}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _fixture_colour_rules(draw: pd.DataFrame) -> list[dict]:
    """Colour Home and Away cells by team ownership."""
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
    """Colour Team cell text in group mini-tables by owner."""
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
    """Colour an owner-name column by the owner's colour."""
    return [
        {"if": {"filter_query": f'{{{col}}} = "{name}"', "column_id": col}, "color": colour}
        for name, colour in COLOURS.items()
    ]


def _make_table(
    table_id: str,
    columns: list[str],
    hidden: list[str] | None = None,
    sort: bool = False,
    compact: bool = False,
    col_labels: dict | None = None,
) -> dash_table.DataTable:
    hidden = hidden or []
    col_labels = col_labels or {}
    cell = {**CELL}
    if compact:
        cell = {**cell, "padding": "7px 10px"}
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": col_labels.get(c, c), "id": c, "hideable": False} for c in columns],
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
                            className="six columns",
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
                            className="six columns",
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

                # Row 3 — Knockout
                html.Div(
                    [
                        html.H3("Knockout stage", style=SECTION_LABEL),
                        _make_table(
                            "knockout-table",
                            ["Stage", "HomeOwner", "Home", "Score", "Away", "AwayOwner"],
                            col_labels={"HomeOwner": "", "AwayOwner": ""},
                        ),
                    ],
                    id="knockout-section",
                    className="section-gap",
                ),

                # Row 4 — Recent + Upcoming
                html.Div(
                    [
                        html.Div(
                            [
                                html.H3("Recent results", style=SECTION_LABEL),
                                _make_table(
                                    "recent-table",
                                    ["Date", "Time", "HomeOwner", "Home", "Score", "Away", "AwayOwner", "Stage"],
                                    col_labels={"HomeOwner": "", "AwayOwner": ""},
                                ),
                            ],
                            className="six columns",
                        ),
                        html.Div(
                            [
                                html.H3("Upcoming fixtures", style=SECTION_LABEL),
                                _make_table(
                                    "upcoming-table",
                                    ["Date", "Time", "HomeOwner", "Home", "Away", "AwayOwner", "Stage"],
                                    col_labels={"HomeOwner": "", "AwayOwner": ""},
                                ),
                            ],
                            className="six columns",
                        ),
                    ],
                    className="row section-gap",
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

    # Person table: stripe + full row text colour by owner
    person_fmt = (
        _numeric_align(NUMERIC_COLS)
        + _person_stripe_rules("Who")
        + _person_row_colour_rules()
    )

    # Team table: row colour first, eliminated overrides Team cell last
    team_fmt = (
        _numeric_align(NUMERIC_COLS)
        + _team_stripe_rules(draw, "Team")
        + _who_stripe_rules(draw, "Who")
        + _team_row_colour_rules()
        + [_eliminated_rule()]
    )

    # Lookup: team name → owner name (for injecting owner columns)
    team_to_owner = {} if draw.empty else dict(zip(draw["Team"], draw["Who"]))

    def _add_owner_cols(df: pd.DataFrame, home_col: str = "Home", away_col: str = "Away") -> pd.DataFrame:
        out = df.copy()
        if home_col in out.columns:
            out["HomeOwner"] = out[home_col].map(lambda t: team_to_owner.get(t, ""))
        if away_col in out.columns:
            out["AwayOwner"] = out[away_col].map(lambda t: team_to_owner.get(t, ""))
        return out

    # Group tables
    group_cols = ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
    group_children = []
    for g in sorted(group_standings.keys()):
        gdf = group_standings[g]
        # Attach owner column
        if not gdf.empty and not draw.empty:
            gdf = gdf.merge(draw[["Team", "Who"]], on="Team", how="left")
            gdf["Who"] = gdf["Who"].fillna("")
        else:
            gdf = gdf.copy()
            gdf["Who"] = ""
        gfmt = (
            _numeric_align(NUMERIC_COLS)
            + _team_stripe_rules(draw, "Team")
            + _group_colour_rules(draw)
            + _owner_col_colour_rules("Who")
        )
        cell = {**CELL, "padding": "5px 6px", "fontSize": "12px"}
        hdr = {**HEADER, "padding": "8px 6px"}
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
                        style_cell_conditional=_numeric_align(NUMERIC_COLS) + group_col_widths,
                        style_data_conditional=gfmt,
                        style_table={"overflowX": "hidden"},
                    ),
                ],
                className="group-cell",
            )
        )

    owner_colour_rules = (
        _owner_col_colour_rules("HomeOwner")
        + _owner_col_colour_rules("AwayOwner")
    )
    fixture_colours = _fixture_colour_rules(draw)
    fixture_stripes = _team_stripe_rules(draw, "Home") + _team_stripe_rules(draw, "Away")
    fixture_fmt = fixture_stripes + fixture_colours + owner_colour_rules

    # Recent results
    finished = fixtures[fixtures["Status"] == "Finished"].tail(10).iloc[::-1]
    finished_out = _add_owner_cols(finished[["Date", "Time", "Home", "Score", "Away", "Stage"]])

    # Upcoming fixtures
    upcoming = fixtures[fixtures["Status"] == "Upcoming"].head(10)
    upcoming_out = _add_owner_cols(upcoming[["Date", "Time", "Home", "Away", "Stage"]])

    # Knockout stage
    ko = fixtures[~fixtures["Stage"].str.startswith("Group", na=False)].copy()
    ko_out = _add_owner_cols(ko[["Stage", "Home", "Score", "Away"]]) if not ko.empty else pd.DataFrame()

    return (
        person_table.to_dict("records"),
        person_fmt,
        team_table.to_dict("records"),
        team_fmt,
        group_children,
        finished_out.to_dict("records"),
        fixture_fmt,
        upcoming_out.to_dict("records"),
        fixture_fmt,
        ko_out[["Stage", "Home", "HomeOwner", "Score", "Away", "AwayOwner"]].to_dict("records") if not ko_out.empty else [],
        fixture_fmt,
        f"Last updated: {timestamp} UTC",
    )


if __name__ == "__main__":
    app.run(debug=True)
