"""Game model v3 (team values the user asked for): separate, opponent-adjusted offense and defense (EPA/play and
success rate, from ratings2), special teams (st_games.py), each team's own home-field edge, the books' strength
rating (market.py) and the quarterback terms. Every feature is home minus away, so each team has its own value."""
import numpy as np, pandas as pd, market, model3, ratings2 as rt
ST = dict(HL=16.0, M0=8.0, CARRY=0.5)          # special teams: half-life in games, shrink (games of average), season carry
HF = dict(K=40.0, SEASONS=6)   # team home field: NOT used. Season-to-season r = -0.04 vs the line (2002-25), fitted weight -0.3; kept for tests
F4 = ['off_epa', 'off_sr', 'def_epa', 'def_sr', 'st', 'mkt', 'qb', 'qbd', 'qb2', 'rest', 'div', 'neutral']
def st_ratings():
    S = pd.read_parquet('st_games.parquet').merge(rt.ORDER, on='game_id').sort_values(['gameday', 'game_id'])
    st, pre = {}, {}; d = 0.5 ** (1 / ST['HL'])
    for (gd, gid), grp in S.groupby(['gameday', 'game_id'], sort=False):
        for r in grp.itertuples():
            s = st.setdefault(r.team, dict(season=r.season, w=0.0, x=0.0))
            if s['season'] != r.season: s['w'] *= ST['CARRY']; s['x'] *= ST['CARRY']; s['season'] = r.season
            pre[(gid, r.team)] = s['x'] / (s['w'] + ST['M0'])
        for r in grp.itertuples():
            s = st[r.team]; s['x'] = s['x'] * d + r.st; s['w'] = s['w'] * d + 1
    return pre, st
def home_edges(G):
    """Each team's extra home-field edge in points, from earlier seasons: (home margin - road margin)/2 relative to the
    league, shrunk toward 0. Returns {(season, team): edge} using only seasons before `season`."""
    h = G.assign(team=G.home_team, m=G.result, home=1); a = G.assign(team=G.away_team, m=-G.result, home=0)
    T = pd.concat([h, a])[['season', 'team', 'm', 'home']]; T = T[(G.location.reindex(T.index) != 'Neutral') if False else slice(None)]
    by = T.groupby(['team', 'season', 'home']).m.agg(['sum', 'count']).unstack('home').fillna(0)
    out = {}
    for s in sorted(G.season.unique()):
        past = by[(by.index.get_level_values('season') < s) & (by.index.get_level_values('season') >= s - HF['SEASONS'])]
        if not len(past): continue
        agg = past.groupby('team').sum()
        hm = agg[('sum', 1)] / agg[('count', 1)].clip(lower=1); rm = agg[('sum', 0)] / agg[('count', 0)].clip(lower=1)
        raw = (hm - rm) / 2; lg = raw.mean(); n = (agg[('count', 1)] + agg[('count', 0)]) / 2
        for t in agg.index: out[(s, t)] = float((raw[t] - lg) * n[t] / (n[t] + HF['K']))
    return out
def add(D):
    D = model3.add(D, model3.MP)
    pre, _ = rt.team_ratings(HG=14.0, CARRY=0.85, M0=3.0); spre, _ = st_ratings()
    G = market.load_games(); G = G[G.result.notna()]; he = home_edges(G)
    get = lambda g, t: pre.get((g, t))
    rows = []
    for g, h, a, s, neu in zip(D.game_id, D.home_team, D.away_team, D.season, D.neutral):
        H, A = get(g, h), get(g, a)
        rows.append(dict(off_epa=H[0][0] - A[0][0], off_sr=H[0][3] - A[0][3], def_epa=A[1][0] - H[1][0], def_sr=A[1][3] - H[1][3],
                         st=spre.get((g, h), 0.0) - spre.get((g, a), 0.0), thfa=0.0 if neu else he.get((s, h), 0.0)))
    return pd.concat([D.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
