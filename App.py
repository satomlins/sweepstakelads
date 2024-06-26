# Import required libraries
import pandas as pd
import dash
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output
from dash_iconify import DashIconify
import plotly.express as px
from Update_Scores import Tournament

print(pd.to_datetime('today'))
EC2024 = Tournament('EC')
team_table = EC2024.team_table.sort_values(['PNT', 'GD'], ascending=False)
person_table = EC2024.team_table.drop(columns='Team').groupby('Who').sum().reset_index().sort_values(['PNT', 'GD'],
                                                                                                     ascending=False)
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

people_colour_formats = []

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
                                'SWEEPSTAKELADS EUROS 2024',
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
                html.Div([
                    dash_table.DataTable(
                        id='team_table',  # Added an ID for the DataTable
                        data=team_table.to_dict(
                            'records'),
                        columns=[{'name': col, 'id': col} for col in team_table.columns],
                        style_header=header_style,
                        style_data=data_style,
                        style_data_conditional=people_colour_formats
                    )
                ],
                    style={'margin': '2em 0 0'},
                    className='five columns'),
                html.Div([
                    dash_table.DataTable(
                        id='person_table',  # Added an ID for the second DataTable
                        data=person_table.to_dict(
                            'records'),
                        columns=[{'name': col, 'id': col} for col in person_table.columns],
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
                        data=EC2024.fixtures.drop(columns=['Special']).to_dict('records'),
                        columns=[{'name': col, 'id': col} for col in EC2024.fixtures.drop(columns=['Special']).columns],
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
    ],
        className='footer')
])

# # def prettify_row(row):
# #     return 0
#
# # @ app.callback(Output('title', 'children'),
# #                Output('info', 'children'),
# #                Output('bullets', 'children'),
# #                [Input('main_graph', 'hoverData'),
# #
# #                 Input('main_graph', 'clickData')])
#
#
# # def update_info(hoverData, clickData):
# #     global df
# #     global prevClickData
# #     global newData
# #
# #     if clickData == prevClickData:
# #         newData = hoverData
# #     else:
# #         newData = clickData
# #
# #     x = newData['points'][0]['x']
# #     x2 = newData['points'][0]['base']
# #     y = newData['points'][0]['y']
# #
# #     row = df[(df['start'] <= x)
# #              & (df['end'] >= x)
# #              & (df['start'] <= x2)
# #              & (df['end'] >= x2)
# #              & (df['type'] == y)]
# #
# #     prevClickData = clickData
# #
# #     linkInfo = row['info'].values[0].split('|')
# #
# #     if len(linkInfo) == 1:
# #         info = html.H6(
# #             row['info'],
# #             className="info_text"
# #         )
# #     else:
# #         info = dcc.Link(
# #             html.H6(
# #                 linkInfo[0],
# #                 className="info_text"
# #             ),
# #             target='_blank',
# #             href=linkInfo[1],
# #         ),
# #
# #     print(info)
# #
# #     return row['title'], \
# #            info, \
# #            [html.Li(i) for i in (row['bullet_1'],
# #                                  row['bullet_2'],
# #                                  row['bullet_3'],
# #                                  row['bullet_4'],
# #                                  row['bullet_5']) if i.any()]


# Main
if __name__ == '__main__':
    app.run_server(debug=True)  # , port=8069)
