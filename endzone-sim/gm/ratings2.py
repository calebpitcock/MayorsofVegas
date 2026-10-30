"""Pre-game ratings (no market input), parameterised for tuning. See ratings.py for the idea; adds the quarterback the
team's recent numbers were produced with, so a starter change can be measured against it."""
import numpy as np, pandas as pd
T0 = pd.read_parquet('team_games.parquet'); Q0 = pd.read_parquet('qb_games.parquet')
G0 = pd.read_csv('../../data/games.csv'); G0 = G0[(G0.game_type == 'REG') & (G0.season >= 2012)]
ORDER = G0[['game_id', 'gameday']].drop_duplicates()
STATS = ['epa', 'pepa', 'repa', 'sr']
def team_ratings(HG=8.0, CARRY=0.45, M0=3.0):
    T = T0.merge(ORDER, on='game_id').sort_values(['gameday', 'game_id']); lg = T.groupby('season')[STATS].mean()
    def one(adj):
        st, pre = {}, {}; d = 0.5 ** (1 / HG)
        for (gd, gid), grp in T.groupby(['gameday', 'game_id'], sort=False):
            season = int(grp.season.iloc[0]); mu = lg.loc[season].values
            for r in grp.itertuples():
                for team in (r.posteam, r.defteam):
                    s = st.get(team)
                    if s is None: s = st[team] = dict(season=season, wo=0.0, so=np.zeros(4), wd=0.0, sd=np.zeros(4))
                    if s['season'] != season:
                        s['wo'] *= CARRY; s['wd'] *= CARRY; s['so'] *= CARRY; s['sd'] *= CARRY; s['season'] = season
                    pre[(gid, team)] = ((s['so'] + M0 * mu) / (s['wo'] + M0) - mu, (s['sd'] + M0 * mu) / (s['wd'] + M0) - mu)
            for r in grp.itertuples():
                x = np.array([getattr(r, c) if not pd.isna(getattr(r, c)) else lg.loc[season, c] for c in STATS])
                xo = x - adj[(gid, r.defteam)][1] if adj else x; xd = x - adj[(gid, r.posteam)][0] if adj else x
                so, sd = st[r.posteam], st[r.defteam]
                so['so'] = so['so'] * d + xo; so['wo'] = so['wo'] * d + 1; sd['sd'] = sd['sd'] * d + xd; sd['wd'] = sd['wd'] * d + 1
        return pre, st
    raw, _ = one(None); adj, state = one(raw)
    return adj, state
def qb_ratings(QHL=350.0, QCARRY=0.7, QM0=250.0, QPRIOR=-0.02, UHL=4.0):
    Q = Q0.merge(ORDER, on='game_id').sort_values(['gameday', 'game_id'])
    qs, qpre, used, upre = {}, {}, {}, {}
    ud = 0.5 ** (1 / UHL)
    for (gd, gid), grp in Q.groupby(['gameday', 'game_id'], sort=False):
        season = int(grp.season.iloc[0])
        for r in grp.itertuples():
            s = qs.get(r.qb)
            if s is None: s = qs[r.qb] = dict(season=season, w=0.0, x=0.0)
            if s['season'] != season: s['w'] *= QCARRY; s['x'] *= QCARRY; s['season'] = season
            qpre[(gid, r.qb)] = (s['x'] + QM0 * QPRIOR) / (s['w'] + QM0)
        for team in grp.posteam.unique():
            u = used.get(team); upre[(gid, team)] = (u['x'] / u['w']) if u and u['w'] > 0 else QPRIOR
        for team, tg in grp.groupby('posteam'):           # dropback-weighted rating of the QBs who played for the team
            u = used.setdefault(team, dict(w=0.0, x=0.0)); tot = tg.db.sum()
            val = sum(qpre[(gid, r.qb)] * r.db for r in tg.itertuples()) / max(1, tot)
            u['x'] = u['x'] * ud + val; u['w'] = u['w'] * ud + 1
        for r in grp.itertuples():
            s = qs[r.qb]; dd = 0.5 ** (r.db / QHL); s['x'] = s['x'] * dd + r.qepa; s['w'] = s['w'] * dd + r.db
    return qpre, upre, qs, used
