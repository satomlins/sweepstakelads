import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from dash_iconify import DashIconify

from tournament import get_data, load_draw

# ---------------------------------------------------------------------------
# Colours — one per participant
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

# ---------------------------------------------------------------------------
# Table style helpers
# ---------------------------------------------------------------------------

HEADER = {
    "backgroundColor": "rgb(30, 30, 30)",
    "color": "white",
    "fontWeight": "bold",
    "textAlign": "center",
}

CELL = {
    "backgroundColor": "rgb(50, 50, 50)",
    "color": "white",
    "textAlign": "center",
    "minWidth": "2em",
}

ICON_SIZE = 20
ICON_STYLE = {"margin": "0.1rem 0.4rem 0"}


def _person_colour_rules(col: str) -> list[dict]:
    """Conditional formatting rules that colour a column by participant name."""
    return [
        {
            "if": {
                "filter_query": f'{{{col}}} = "{name}"',
                "column_id": col,
            },
            "backgroundColor": colour,
            "color": "black",
        }
        for name, colour in COLOURS.items()
    ]


def _team_colour_rules(draw: pd.DataFrame, col: str) -> list[dict]:
    """
    Conditional formatting rules that colour a team-name column by owner colour.
    draw: DataFrame with columns [Who, Team].
    col: the column id to colour.
    """
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
                "backgroundColor": colour,
                "color": "black",
            }
        )
    return rules


def _eliminated_rule(col: str = "Team") -> dict:
    return {
        "if": {
            "filter_query": "{In} = 'Out'",
            "column_id": col,
        },
        "backgroundColor": "#960000",
        "color": "white",
    }


def _make_table(table_id: str, columns: list[str], hidden: list[str] | None = None,
                sort: bool = False) -> dash_table.DataTable:
    hidden = hidden or []
    return dash_table.DataTable(
        id=table_id,
        columns=[{"name": c, "id": c, "hideable": False} for c in columns],
        hidden_columns=hidden,
        style_header=HEADER,
        style_data=CELL,
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
        # Header
        html.Div(
            html.H1(
                "SWEEPSTAKELADS 2026",
                style={"textAlign": "center", "color": "#00FFFF", "margin": "0"},
            ),
            style={"margin": "1em 0 0"},
            className="twelve columns",
        ),

        dcc.Interval(id="interval", interval=5 * 60 * 1000),

        # Row 1 — Person leaderboard + Team table
        html.Div(
            [
                html.Div(
                    [
                        html.H3("Leaderboard", style={"color": "white", "textAlign": "center"}),
                        _make_table(
                            "person-table",
                            ["Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"],
                        ),
                    ],
                    className="five columns",
                    style={"marginTop": "2em"},
                ),
                html.Div(
                    [
                        html.H3("Teams", style={"color": "white", "textAlign": "center"}),
                        _make_table(
                            "team-table",
                            ["Team", "Who", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT", "In"],
                            hidden=["In"],
                            sort=True,
                        ),
                    ],
                    className="seven columns",
                    style={"marginTop": "2em"},
                ),
            ],
            className="row",
        ),

        # Row 2 — Group tables
        html.Div(
            [
                html.H3("Groups", style={"color": "white", "textAlign": "center"}),
                html.Div(id="group-tables"),
            ],
            className="row",
            style={"marginTop": "2em"},
        ),

        # Row 3 — Recent results + Upcoming fixtures
        html.Div(
            [
                html.Div(
                    [
                        html.H3("Recent results", style={"color": "white", "textAlign": "center"}),
                        _make_table(
                            "recent-table",
                            ["Date", "Time", "Home", "Score", "Away", "Stage"],
                        ),
                    ],
                    className="six columns",
                    style={"marginTop": "2em"},
                ),
                html.Div(
                    [
                        html.H3("Upcoming fixtures", style={"color": "white", "textAlign": "center"}),
                        _make_table(
                            "upcoming-table",
                            ["Date", "Time", "Home", "Away", "Stage"],
                        ),
                    ],
                    className="six columns",
                    style={"marginTop": "2em"},
                ),
            ],
            className="row",
        ),

        # Row 4 — Knockout stage
        html.Div(
            [
                html.H3("Knockout stage", style={"color": "white", "textAlign": "center"}),
                _make_table(
                    "knockout-table",
                    ["Stage", "Home", "Score", "Away"],
                ),
            ],
            id="knockout-section",
            className="row",
            style={"marginTop": "2em"},
        ),

        # Footer
        html.Div(
            [
                html.Div(
                    [
                        dcc.Link(DashIconify(icon="bi:envelope", width=ICON_SIZE, style=ICON_STYLE),
                                 href="mailto:scott@stomlins.com", target="_blank"),
                        dcc.Link(DashIconify(icon="bi:linkedin", width=ICON_SIZE, style=ICON_STYLE),
                                 href="https://www.linkedin.com/in/scotttomlins/", target="_blank"),
                        dcc.Link(DashIconify(icon="bi:github", width=ICON_SIZE, style=ICON_STYLE),
                                 href="https://github.com/satomlins/", target="_blank"),
                    ]
                ),
                html.P(f"© {pd.Timestamp.now().year} SWEEPSTAKELADS   |   website by Scott Tomlins"),
                html.P(id="last-updated"),
            ],
            className="footer",
        ),
    ],
    id="mainContainer",
    className="main_container",
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

    # -- Person table formatting
    person_fmt = _person_colour_rules("Who")

    # -- Team table formatting
    # Eliminated teams: red background on Team cell (checked first so owner colour wins for "In")
    team_fmt = (
        [_eliminated_rule("Team")]
        + _team_colour_rules(draw, "Team")
        + _person_colour_rules("Who")
    )

    # -- Group tables (12 mini-tables, 4 per row)
    group_cols = ["Team", "PL", "W", "D", "L", "GS", "GA", "GD", "PNT"]
    group_children = []
    groups_sorted = sorted(group_standings.keys())
    rows_of_groups = [groups_sorted[i:i+3] for i in range(0, len(groups_sorted), 3)]

    for row_groups in rows_of_groups:
        row_divs = []
        for g in row_groups:
            gdf = group_standings[g]
            gfmt = _team_colour_rules(draw, "Team")
            row_divs.append(
                html.Div(
                    [
                        html.H5(
                            f"Group {g}",
                            style={"color": "white", "textAlign": "center", "margin": "0.5em 0 0.2em"},
                        ),
                        dash_table.DataTable(
                            data=gdf[group_cols].to_dict("records") if not gdf.empty else [],
                            columns=[{"name": c, "id": c} for c in group_cols],
                            style_header=HEADER,
                            style_data=CELL,
                            style_data_conditional=gfmt,
                            style_table={"overflowX": "auto"},
                        ),
                    ],
                    className="four columns",
                )
            )
        group_children.append(
            html.Div(row_divs, className="row", style={"marginBottom": "1em"})
        )

    # -- Recent results (last 10 finished, newest first)
    finished = fixtures[fixtures["Status"] == "Finished"].tail(10).iloc[::-1]
    recent_fmt = (
        _team_colour_rules(draw, "Home")
        + _team_colour_rules(draw, "Away")
    )

    # -- Upcoming fixtures (next 10)
    upcoming = fixtures[fixtures["Status"] == "Upcoming"].head(10)
    upcoming_fmt = (
        _team_colour_rules(draw, "Home")
        + _team_colour_rules(draw, "Away")
    )

    # -- Knockout stage (all knockout matches)
    ko = fixtures[~fixtures["Stage"].str.startswith("Group", na=False)].copy()
    ko_fmt = (
        _team_colour_rules(draw, "Home")
        + _team_colour_rules(draw, "Away")
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
