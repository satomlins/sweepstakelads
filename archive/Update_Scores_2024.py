import pandas as pd
import requests

pd.set_option('future.no_silent_downcasting', True)


class Tournament:
    def __init__(self, tournament):

        self.draw, self.team_table, self.week_pnt, self.week_gd = self.setup_tables()

        self.fixtures = self.setup_tournament(tournament)

        self.fixtures.apply(self.fill_table, axis=1)

        self.team_table['PL'] = self.team_table[['W', 'D', 'L']].sum(axis=1)

    def setup_tournament(self, tournament):
        uri = 'https://api.football-data.org/v4/competitions/{}/matches'.format(tournament)
        headers = {'X-Auth-Token': 'e3758bc638da4294b7a7335738be867a'}

        response = requests.get(uri, headers=headers)
        d = response.json()

        temp_d = {}

        for n, match in enumerate(d['matches']):
            temp_d[n] = {'Home team': match['homeTeam']['name'],
                         'Away team': match['awayTeam']['name'],
                         'Home score': match['score']['fullTime']['home'],
                         'Away score': match['score']['fullTime']['away'],
                         'Round': match['stage'],
                         'Duration': match['score']['duration'],
                         'Status': d['matches'][n]['status'],
                         'Date': pd.to_datetime(match['utcDate']).date(),
                         'KO': pd.to_datetime(match['utcDate']).strftime('%H:%M')}

        df = pd.DataFrame(temp_d).transpose()

        df = df.dropna(how='all', subset=['Home team', 'Away team'])

        df = pd.merge(df, self.draw, how='left', left_on='Home team', right_on='Team').drop(columns='Team').rename(
            columns={'Who': 'Home person'})

        df = pd.merge(df, self.draw, how='left', left_on='Away team', right_on='Team').drop(columns='Team').rename(
            columns={'Who': 'Away person'})

        df['Status'] = df['Status'].map({'FINISHED': 'Finished', 'TIMED': 'Future', 'IN_PLAY': 'Live'})

        # df['NEW Status'] = df['Duration'].map({"EXTRA_TIME": ' - AET', "PENALTIES": ' - pens', 'REGULAR': ''})
        #
        # df['Status'] = ['{}{}'.format(x, y) for x, y in zip(df['Status'].values, df['NEW Status'].values)]
        #
        # df.drop(columns='NEW Status', inplace=True)

        df['Round'] = df['Round'].apply(lambda x: x.replace('_', ' ').capitalize())

        df = df[['Date', 'KO', 'Home person', 'Home team', 'Home score', 'Away score', 'Away team', 'Away person',
                 'Round', 'Duration', 'Status']]

        in_df = pd.concat([df[['Home team', 'Status']].rename(columns={'Home team': 'Team'}),
                         df[['Away team', 'Status']].rename(columns={'Away team': 'Team'})])

        in_df = in_df[in_df['Status'] != 'Finished'].dropna(how='any', subset='Team').drop(columns='Status')

        in_df['In'] = 'In'

        self.team_table = self.team_table.merge(in_df, how='left').fillna('Out')

        return df

    def setup_tables(self):
        # draw = pd.read_excel('assets/Euro_2024.xlsx', sheet_name='draw', engine='openpyxl')[['Who', 'Team']]
        draw = pd.read_csv('assets/Euro_2024.csv')
        team_table = pd.DataFrame(columns=['Team', 'PL', 'W', 'D', 'L', 'GD', 'GS', 'PNT', 'Who'])
        team_table[['Team', 'Who']] = draw[['Team', 'Who']]
        team_table.fillna(0, inplace=True)

        week_pnt = pd.DataFrame([[0, 0, 0, 0, 0, 0, 0, 0]], columns=team_table['Who'].unique()).T
        week_gd = week_pnt.copy()

        return draw, team_table, week_pnt, week_gd

    def fill_table(self, row):
        if row['Status'] != 'Finished':
            return

        if row['Duration'] == 'EXTRA_TIME':
            win_score = 3
            lose_score = 1
        elif row['Duration'] == 'PENALTY_SHOOTOUT':
            win_score = 2
            lose_score = 1
        else:
            win_score = 3
            lose_score = 0

        winner = ''
        loser = ''

        if row['Home score'] > row['Away score']:
            winner = row['Home team']
            loser = row['Away team']
        elif row['Home score'] < row['Away score']:
            winner = row['Away team']
            loser = row['Home team']

        else:
            self.team_table.loc[self.team_table['Team'] == row['Home team'], 'D'] += 1
            self.team_table.loc[self.team_table['Team'] == row['Away team'], 'D'] += 1

            self.team_table.loc[self.team_table['Team'] == row['Home team'], 'PNT'] += 1
            self.team_table.loc[self.team_table['Team'] == row['Away team'], 'PNT'] += 1

        if winner != '':
            self.team_table.loc[self.team_table['Team'] == winner, 'W'] += 1
            self.team_table.loc[self.team_table['Team'] == winner, 'PNT'] += win_score

            self.team_table.loc[self.team_table['Team'] == loser, 'L'] += 1
            self.team_table.loc[self.team_table['Team'] == loser, 'PNT'] += lose_score

            if row['Duration'] != 'PENALTY_SHOOTOUT':
                GD = abs(row['Home score'] - row['Away score'])
                self.team_table.loc[self.team_table['Team'] == winner, 'GD'] += GD
                self.team_table.loc[self.team_table['Team'] == loser, 'GD'] -= GD

        self.team_table.loc[self.team_table['Team'] == row['Home team'], 'GS'] += row['Home score']
        self.team_table.loc[self.team_table['Team'] == row['Away team'], 'GS'] += row['Away score']

        self.week_pnt[row.name + 1] = self.team_table[['Who', 'PNT']].groupby('Who').sum().sort_values(['Who'],
                                                                                                       ascending=False)
        self.week_gd[row.name + 1] = self.team_table[['Who', 'GD']].groupby('Who').sum().sort_values(['Who'],
                                                                                                     ascending=False)


if __name__ == '__main__':
    EC2024 = Tournament('EC')
