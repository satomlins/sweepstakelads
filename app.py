# Import required libraries
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from dash_iconify import DashIconify
import plotly.express as px
from Update_Scores import Tournament

# print(pd.to_datetime('today'))
EC2024 = Tournament('EC')

icon_size = 20
icon_style = {'margin': '0.1rem 0.4rem 0'}

header_style = {
    'backgroundColor': 'rgb(30, 30, 30)',
    'color': 'white',
    'fontWeight': 'bold',
    'textAlign': 'center',
}

data_style = {
    'backgroundColor': 'rgb(50, 50, 50)',
    'color': 'white',
    'textAlign': 'center',
    'minWidth': '2em'
}

people_colour_formats = [{
    'if': {
        'filter_query': "{In} = 'Out'",  # matching rows of a hidden column with the id, `id`
        'column_id': 'Team'
    },
    'backgroundColor': '#960000'
}]

colours = {'Scott': '#ffadad',
           'Hugo': '#ffd6a5',
           'Sam': '#fdffb6',
           'Brendan': '#caffbf',
           'Isaac': '#9bf6ff',
           'Adrian': '#a0c4ff',
           'Alex': '#bdb2ff',
           'Mary': '#ffc6ff',
           }

for key in colours:
    for col in ['Who', 'Home person', 'Away person']:
        people_colour_formats.append({
            'if': {
                'filter_query': '{{{}}} = {}'.format(col, key),
                'column_id': '{}'.format(col)
            },
            'backgroundColor': colours[key],
            'color': 'black'
        })

prevClickData = None

app = dash.Dash(__name__, meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}], )

app.title = 'SWEEPSTAKELADS 2024'
server = app.server

app.layout = html.Div([
    html.Div(
        [
            html.Div(
                [
                    html.Div(
                        [
                            html.H1(
                                children='SWEEPSTAKELADS EUROS 2024',
                                id='title',
                                style={
                                    "textAlign": "center",
                                    'margin': '0 0 0 0',
                                    'color': '#00FFFF',
                                },
                                className='container'
                            )
                        ],
                        style={'margin': '1em 0 0'},
                        className='twelve columns'
                    )
                ],
                id="header",
                className='row'),
            html.Div([
                dcc.Interval(id='interval', interval=60 * 1000 * 5),
                html.Div([
                    html.Div([
                        dash_table.DataTable(
                            id='team_table',  # Added an ID for the DataTable
                            # data=team_table.to_dict('records'),
                            columns=[{'name': col, 'id': col} for col in ['Team','PL','W','D','L','GD','GS','PNT','Who']],
                            style_header=header_style,
                            style_data=data_style,
                            style_data_conditional=people_colour_formats,
                        )
                    ],
                        style={'margin': '2em 0 0'},
                        className='five columns'),
                    html.Div([
                        dash_table.DataTable(
                            id='person_table',  # Added an ID for the second DataTable
                            # data=person_table.to_dict('records'),
                            columns=[{'name': col, 'id': col} for col in ['Who','PL','W','D','L','GD','GS','PNT']],
                            style_header=header_style,
                            style_data=data_style,
                            style_data_conditional=people_colour_formats

                        )
                    ],
                        style={'margin': '2em 0 0'},
                        className='five columns body'
                    )
                ],
                    id="top_two_tables",
                    className="row",
                    style={'margin': '2em 0 0'},
                ),
                html.Div([
                    html.Div([
                        dash_table.DataTable(
                            id='fixtures_table',  # Added an ID for the second DataTable
                            # data=EC2024.fixtures.drop(columns=['Special']).to_dict('records'),
                            columns=[{'name': col, 'id': col} for col in
                                     EC2024.fixtures.drop(columns=['Special']).columns],
                            style_header=header_style,
                            style_data=data_style,
                            style_data_conditional=people_colour_formats
                        )
                    ],
                        style={'margin': '2em 0 0'},
                        className='twelve columns body'
                    )
                ],
                    id="bottom_tables",
                    className="row",
                    style={'margin': '2em 0 0'},
                ),
            ])
        ],
        id="mainContainer",
        className='main_container'
    ),
    html.Div([
        html.Div([
            dcc.Link(
                DashIconify(
                    icon="bi:envelope",
                    width=icon_size,
                    height=icon_size,
                    style=icon_style
                ),
                target='_blank',
                href='mailto:scott@stomlins.com',
            ),
            dcc.Link(
                DashIconify(
                    icon="bi:linkedin",
                    width=icon_size,
                    height=icon_size,
                    style=icon_style
                ),
                target='_blank',
                href='https://www.linkedin.com/in/scotttomlins/',
            ),
            dcc.Link(
                DashIconify(
                    icon="bi:github",
                    width=icon_size,
                    height=icon_size,
                    style=icon_style
                ),
                target='_blank',
                href='https://github.com/satomlins/',
            ),
            dcc.Link(
                DashIconify(
                    icon="bi:medium",
                    width=icon_size,
                    height=icon_size,
                    style=icon_style
                ),
                target='_blank',
                href='https://stomlins.medium.com/',
            ),
        ]),
        html.P('© {} SWEEPSTAKELADS   |   website by Scott Tomlins'.format(pd.Timestamp.now().year)),
        html.P(id='last_updated'),
    ],
        className='footer')
])


@app.callback(
    Output("team_table", "data"),
    Output("person_table", "data"),
    Output("fixtures_table", "data"),
    Output('last_updated', 'children'),
    Input("interval", "n_intervals"),
)
def update_output(n):
    with open("assets/last_updated.txt") as last_updated_file:
        last_updated = pd.to_datetime(last_updated_file.read())

    if last_updated < pd.to_datetime('today') - pd.Timedelta(minutes=1):

        print("RUNNING NOW {}".format(pd.to_datetime('today').floor('s')))
        ec2024 = Tournament('EC')
        teamtable = ec2024.team_table.sort_values(['PNT', 'GD', 'GS'], ascending=False)

        persontable = ec2024.team_table[['Who','PL','W','D','L','GD','GS','PNT']].groupby('Who').sum().reset_index()
        persontable = persontable.sort_values(['PNT', 'GD', 'GS'], ascending=False)

        fixtures = ec2024.fixtures.drop(columns=['Special'])

        with open("assets/last_updated.txt", 'w') as the_file:
            last_updated = str(pd.to_datetime('today').floor('s'))
            the_file.write(last_updated)

        teamtable.to_csv('assets/teamtable.csv', index=False)
        persontable.to_csv('assets/persontable.csv', index=False)
        fixtures.to_csv('assets/fixtures.csv', index=False)

    else:
        teamtable = pd.read_csv('assets/teamtable.csv')
        persontable = pd.read_csv('assets/persontable.csv')
        fixtures = pd.read_csv('assets/fixtures.csv')

    return teamtable.to_dict('records'), persontable.to_dict('records'), fixtures.to_dict(
        'records'), "Last updated: {}".format(last_updated)


# Main
if __name__ == '__main__':
    app.run_server()  # , port=8069)
