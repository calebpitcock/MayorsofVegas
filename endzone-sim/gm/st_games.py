"""Special teams per team-game from nflverse play-by-play 2012-2026: net expected points on kickoffs, punts, field
goals and extra points (a team's EPA on plays where it has the ball, minus its opponents' EPA on the rest).
EPA is already in points, so this is 'points special teams added'."""
import pandas as pd, numpy as np
D = '../../data'; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
out = []
for s in range(2012, 2027):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'epa'], low_memory=False)
    p = p[(p.season_type == 'REG') & p.play_type.isin(['kickoff', 'punt', 'field_goal', 'extra_point']) & p.epa.notna() & p.posteam.notna()]
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
    a = p.groupby(['game_id', 'season', 'week', 'posteam']).epa.sum().rename('for_').reset_index().rename(columns={'posteam': 'team'})
    b = p.groupby(['game_id', 'season', 'week', 'defteam']).epa.sum().rename('against').reset_index().rename(columns={'defteam': 'team'})
    m = a.merge(b, on=['game_id', 'season', 'week', 'team'], how='outer').fillna(0); m['st'] = m.for_ - m.against; out.append(m)
S = pd.concat(out); S.to_parquet('st_games.parquet'); print(len(S), S.st.std().round(2))
# reliability: does a team's first-half ST predict its second half?
h = S.assign(half=np.where(S.week % 2 == 1, 'o', 'e')).groupby(['team', 'season', 'half']).st.mean().unstack()
print('split-half r', round(float(np.corrcoef(h.o, h.e)[0, 1]), 3))
