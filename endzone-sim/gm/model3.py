"""Game model v2: model2's play-by-play and quarterback features plus market team strength (market.py) and a
second-year quarterback term. Walk-forward exactly like model2."""
import numpy as np, pandas as pd, model2, market
MP = dict(HLW=4.0, CARRY=0.5, LAM=1.0)   # tuned on 2016-20 only (tune3.py)
F3 = model2.F + ['mkt', 'qb2']
_Q = pd.read_parquet('qb_games.parquet'); FIRST = _Q.groupby('qb').season.min()
def career_year(qb, season):
    f = FIRST.get(qb)
    return None if f is None or f <= 2012 else season - f          # careers that start inside the data only
def add(D, mp=MP):
    G = market.load_games(); pre, _ = market.ratings(G, **mp)
    D = D.copy()
    D['mkt'] = [pre.get((g, h), 0.0) - pre.get((g, a), 0.0) for g, h, a in zip(D.game_id, D.home_team, D.away_team)]
    q = G.set_index('game_id')[['home_qb_id', 'away_qb_id']]
    y2 = lambda qb, s: 1.0 if career_year(qb, s) == 1 else 0.0
    D['qb2'] = [y2(q.home_qb_id.get(g), s) - y2(q.away_qb_id.get(g), s) for g, s in zip(D.game_id, D.season)]
    return D
