"""This season's man-coverage and single-high rates, estimated. Real coverage charting (nflverse participation) for the
current season is only published after it ends, and the sites that chart it weekly are blocked from this environment,
so each defense's 2026 rates are estimated from what IS published weekly:
  Next Gen Stats receiving (cushion at the snap and separation at the catch, of the receivers it faced),
  FTN charting (blitz rate, pass rushers, box count, contested-ball rate) and play-by-play (deep-throw rate, aDOT faced),
plus the defense's rate last season. Man coverage shows up as tighter cushion, less separation and more contested balls;
single-high as more deep shots and a heavier box.
Test (the exact situation of a Week 4 build): from weeks 1-3 plus last season, predict the defense's rate over the rest of
that season; fitted on some seasons, scored on another. Usage: python3 coverage_2026.py [WEEK]  -> coverage_2026.json"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(HERE, '..', '..', 'data')
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
FEATS = ['cushion', 'sep', 'contested', 'blitz', 'rushers', 'box', 'deep', 'adot']

def games():
    g = pd.read_csv(f'{D}/games.csv'); g = g[g.game_type == 'REG']
    for c in ('home_team', 'away_team'): g[c] = g[c].replace(REP)
    return g

def defense_games(season, G):
    """per (defense, week): the weekly features."""
    s = G[G.season == season]
    opp = pd.concat([s[['week', 'home_team', 'away_team']].set_axis(['week', 'off', 'def'], axis=1),
                     s[['week', 'away_team', 'home_team']].set_axis(['week', 'off', 'def'], axis=1)])
    n = pd.read_parquet(f'{D}/ngs_receiving.parquet'); n = n[(n.season == season) & (n.season_type == 'REG') & (n.week > 0)]
    n = n.assign(off=n.team_abbr.replace(REP)).merge(opp, on=['week', 'off'])
    w = n.targets.clip(lower=1)
    ng = n.assign(wc=w * n.avg_cushion, ws=w * n.avg_separation, w=w).groupby(['def', 'week'])[['wc', 'ws', 'w']].sum()
    ng = pd.DataFrame({'cushion': ng.wc / ng.w, 'sep': ng.ws / ng.w})
    p = pd.read_csv(f'{D}/play_by_play_{season}.csv.gz', usecols=['game_id', 'play_id', 'season_type', 'week', 'defteam', 'posteam', 'pass_attempt', 'sack', 'air_yards', 'qb_dropback'], low_memory=False)
    p = p[(p.season_type == 'REG') & (p.qb_dropback == 1)].assign(defteam=lambda x: x.defteam.replace(REP))
    att = p[(p.pass_attempt == 1) & p.air_yards.notna()]
    pg = att.groupby(['defteam', 'week']).agg(deep=('air_yards', lambda a: (a >= 20).mean()), adot=('air_yards', 'mean'))
    pg.index.names = ['def', 'week']
    f = pd.read_parquet(f'{D}/ftn_charting_{season}.parquet').rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})
    f = f.merge(p[['game_id', 'play_id', 'defteam', 'pass_attempt']], on=['game_id', 'play_id'])
    fg = f.groupby(['defteam', 'week']).agg(blitz=('n_blitzers', lambda b: (b > 0).mean()), rushers=('n_pass_rushers', 'mean'), box=('n_defense_box', 'mean'),
                                           contested=('is_contested_ball', lambda c: c.astype(float).mean()))
    fg.index.names = ['def', 'week']
    return ng.join(pg, how='outer').join(fg, how='outer')

def truth(season):
    f = f'{D}/pbp_participation_{season}.parquet'
    if not os.path.exists(f): return None
    x = pd.read_parquet(f, columns=['nflverse_game_id', 'possession_team', 'defense_man_zone_type', 'defense_coverage_type'])
    g = games(); g = g[g.season == season][['game_id', 'week', 'home_team', 'away_team']]
    x = x.merge(g, left_on='nflverse_game_id', right_on='game_id')
    x['possession_team'] = x.possession_team.replace(REP)
    x['def'] = np.where(x.possession_team == x.home_team, x.away_team, x.home_team)
    mz = x[x.defense_man_zone_type.isin(['MAN_COVERAGE', 'ZONE_COVERAGE'])]
    man = mz.assign(m=(mz.defense_man_zone_type == 'MAN_COVERAGE').astype(float)).groupby(['def', 'week']).m.agg(['sum', 'count'])
    cv = x[x.defense_coverage_type.notna()]
    hi = cv.assign(h=cv.defense_coverage_type.isin(['COVER_0', 'COVER_1', 'COVER_3']).astype(float)).groupby(['def', 'week']).h.agg(['sum', 'count'])
    return man, hi

def rate(t, weeks):
    x = t[t.index.get_level_values('week').isin(weeks)].groupby(level='def').sum(); return x['sum'] / x['count']

def dataset(G, seasons, early=3):
    rows = []
    for s in seasons:
        F = defense_games(s, G); T = truth(s); P = truth(s - 1)
        if T is None or P is None: continue
        e = F[F.index.get_level_values('week') <= early].groupby(level='def').mean()
        e = (e - e.mean()) / e.std()          # each feature relative to that season's league (removes league-wide drift)
        for k, (t, pt) in {'man': (T[0], P[0]), 'hi': (T[1], P[1])}.items():
            y = rate(t, range(early + 1, 30)); prior = rate(pt, range(1, 30))
            df = e.assign(y=y - y.mean(), prior=prior - prior.mean(), season=s, kind=k).dropna(); rows.append(df)
    return pd.concat(rows)

def fit(X, y, lam=10.0):
    mu, sd = X.mean(), X.std().replace(0, 1); Z = (X - mu) / sd
    A = np.column_stack([np.ones(len(Z)), Z.values]); R = np.eye(A.shape[1]) * lam; R[0, 0] = 0
    return np.linalg.solve(A.T @ A + R, A.T @ y.values), mu, sd

def pred(b, mu, sd, X): return np.column_stack([np.ones(len(X)), ((X - mu) / sd).values]) @ b

def main(week=4):
    G = games(); data = dataset(G, [2023, 2024, 2025])
    out = {'season': 2026, 'week': week, 'test': {}, 'teams': {}}
    cols = FEATS + ['prior']
    for k in ('man', 'hi'):
        d = data[data.kind == k]
        errs = {}
        for hold in (2023, 2024, 2025):
            tr, te = d[d.season != hold], d[d.season == hold]
            b, mu, sd = fit(tr[cols], tr.y)
            errs[hold] = (float(np.sqrt(np.mean((pred(b, mu, sd, te[cols]) - te.y) ** 2))), float(np.sqrt(np.mean((te.prior - te.y) ** 2))),
                          float(np.corrcoef(pred(b, mu, sd, te[cols]), te.y)[0, 1]), float(np.corrcoef(te.prior, te.y)[0, 1]))
        out['test'][k] = {str(h): dict(rmse_model=round(a, 4), rmse_last_season=round(b_, 4), r_model=round(c, 3), r_last_season=round(e, 3)) for h, (a, b_, c, e) in errs.items()}
        b, mu, sd = fit(d[cols], d.y)
        F = defense_games(2026, G); e = F[F.index.get_level_values('week') < week].groupby(level='def').mean(); e = (e - e.mean()) / e.std()
        prior = rate(truth(2025)[0 if k == 'man' else 1], range(1, 30))
        e = e.assign(prior=prior - prior.mean()).dropna()
        p = np.clip(prior.mean() + pred(b, mu, sd, e[cols]), .03, .85)   # league level carried from 2025
        for t, v in zip(e.index, p): out['teams'].setdefault(t, {})[k] = round(float(v), 3); out['teams'][t][k + '2025'] = round(float(prior[t]), 3)
        print(k, json.dumps(out['test'][k]))
    json.dump(out, open(os.path.join(HERE, 'coverage_2026.json'), 'w'), indent=1)
    print('teams', len(out['teams']))

if __name__ == '__main__': main(int(sys.argv[1]) if len(sys.argv) > 1 else 4)
