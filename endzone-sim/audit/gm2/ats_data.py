"""One row per game (home perspective): everything knowable before kickoff that might predict covering the CLOSING
spread. Target: home covers (pushes dropped)."""
import pandas as pd, numpy as np
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
TZ = dict(ARI=-3, LA=-3, LAC=-3, LV=-3, SF=-3, SEA=-3, DEN=-2, CHI=-1, DAL=-1, GB=-1, HOU=-1, KC=-1, MIN=-1, NO=-1, TEN=-1)
G = pd.read_csv('/home/user/MayorsofVegas/data/games.csv'); G = G[(G.game_type == 'REG') & (G.season >= 2006) & G.spread_line.notna()].copy()
for c in ('home_team', 'away_team'): G[c] = G[c].replace(REP)
G = G.sort_values(['gameday', 'gametime', 'game_id']).reset_index(drop=True)
G['ats'] = G.result - G.spread_line
# per-team running form (only games before this one)
long = pd.concat([G[['game_id', 'gameday', 'season', 'home_team', 'ats', 'home_qb_id', 'result']].set_axis(['game_id', 'gameday', 'season', 'team', 'ats', 'qb', 'mg'], axis=1),
                  G[['game_id', 'gameday', 'season', 'away_team', 'ats', 'away_qb_id', 'result']].assign(ats=lambda d: -d.ats, result=lambda d: -d.result).set_axis(['game_id', 'gameday', 'season', 'team', 'ats', 'qb', 'mg'], axis=1)]).sort_values(['gameday', 'game_id'])
g = long.groupby('team')
long['ats3'] = g.ats.transform(lambda x: x.shift(1).rolling(3, min_periods=1).mean())
long['mg1'] = g.mg.shift(1)                        # last game's margin (blowout win / loss)
long['prev_qb'] = g.qb.shift(1); long['qbchg'] = ((long.qb != long.prev_qb) & long.prev_qb.notna()).astype(float)
long['sameseason'] = (g.season.shift(1) == long.season)
for c in ('ats3', 'mg1'): long.loc[~long.sameseason, c] = 0.0
long.loc[~long.sameseason, 'qbchg'] = 0.0
f = long.set_index(['game_id', 'team'])
for side in ('home', 'away'):
    k = list(zip(G.game_id, G[f'{side}_team']))
    for c in ('ats3', 'mg1', 'qbchg'): G[f'{side[0]}_{c}'] = f.loc[k, c].values
X = pd.DataFrame(dict(game_id=G.game_id, season=G.season, week=G.week, spread=G.spread_line, y=(G.ats > 0).astype(float), push=(G.ats == 0),
    ats=G.ats, result=G.result, hodds=G.home_spread_odds, aodds=G.away_spread_odds, hml=G.home_moneyline, aml=G.away_moneyline,
    homedog=(G.spread_line < 0).astype(float), bigfav=(G.spread_line.abs() >= 7).astype(float) * np.sign(G.spread_line),
    rest=np.clip(G.home_rest - G.away_rest, -7, 7), hshort=(G.home_rest <= 5).astype(float), ashort=(G.away_rest <= 5).astype(float),
    hbye=(G.home_rest >= 13).astype(float), abye=(G.away_rest >= 13).astype(float), div=G.div_game, neutral=(G.location == 'Neutral').astype(float),
    tz=[TZ.get(h, 0) - TZ.get(a, 0) for h, a in zip(G.home_team, G.away_team)],
    westearly=[float(TZ.get(a, 0) <= -2 and TZ.get(h, 0) == 0 and str(t) < '14') for h, a, t in zip(G.home_team, G.away_team, G.gametime)],
    prime=(G.gametime.astype(str) >= '19').astype(float), late=(G.week >= 15).astype(float),
    wind=G.wind.fillna(0).clip(0, 30) * (G.roof.isin(['outdoors', 'open'])), 
    ats3=G.h_ats3 - G.a_ats3, mg1=G.h_mg1 - G.a_mg1, qbchg=G.h_qbchg - G.a_qbchg))
W = pd.read_parquet('wf3.parquet'); X = X.merge(W, on='game_id', how='left'); X['dis'] = X.m - X.spread
T = pd.read_parquet('/home/user/MayorsofVegas/endzone-sim/gm/tue_dk.parquet')
Gk = G[['game_id', 'season', 'home_team', 'away_team']].merge(T, left_on=['season', 'home_team', 'away_team'], right_on=['season', 'home', 'away'], how='left')
X['move'] = X.spread.values - (-Gk.sp_h.values)          # close minus DK Tuesday (home points); NaN before 2021
X.to_parquet('ats.parquet'); print(X.shape, X.season.min(), X.dis.notna().sum(), X.move.notna().sum(), X.hodds.notna().mean().round(2))
