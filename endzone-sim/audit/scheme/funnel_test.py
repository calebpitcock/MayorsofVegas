"""Run/pass funnel: does the opponent defense's pass-vs-run weakness (opponent-adjusted EPA allowed, pre-game ratings)
predict (a) the offense's neutral pass rate, (b) the share of its touchdowns scored rushing, (c) its red-zone pass
rate, beyond the offense's own prior tendencies? 2014-25, held out by season."""
import sys; sys.path.insert(0, '/home/user/MayorsofVegas/endzone-sim/gm')
import os; os.chdir('/home/user/MayorsofVegas/endzone-sim/gm')
import pandas as pd, numpy as np, ratings2 as rt
pre, _ = rt.team_ratings(HG=14.0, CARRY=0.85, M0=3.0)
D = '/home/user/MayorsofVegas/data'; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}; rows = []
for s in range(2013, 2026):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'down', 'wp', 'half_seconds_remaining', 'qb_dropback', 'yardline_100', 'rush_touchdown', 'pass_touchdown', 'two_point_attempt'], low_memory=False)
    p = p[(p.season_type == 'REG') & p.play_type.isin(['pass', 'run']) & (p.two_point_attempt.fillna(0) == 0)]
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
    n = p[p.down.isin([1, 2]) & p.wp.between(.2, .8) & (p.half_seconds_remaining > 120)]
    a = n.groupby(['game_id', 'season', 'week', 'posteam', 'defteam']).agg(np_=('qb_dropback', 'sum'), nn=('qb_dropback', 'size'))
    rz = p[p.yardline_100 <= 10].groupby(['game_id', 'posteam']).agg(rzp=('qb_dropback', 'sum'), rzn=('qb_dropback', 'size'))
    td = p.groupby(['game_id', 'posteam']).agg(rtd=('rush_touchdown', 'sum'), ptd=('pass_touchdown', 'sum'))
    rows.append(a.reset_index().join(rz, on=['game_id', 'posteam']).join(td, on=['game_id', 'posteam']))
X = pd.concat(rows).fillna({'rzp': 0, 'rzn': 0, 'rtd': 0, 'ptd': 0}).sort_values(['season', 'week'])
X['pr'] = X.np_ / X.nn; X['rzpr'] = X.rzp / X.rzn.clip(lower=1); X['rshare'] = X.rtd / (X.rtd + X.ptd).replace(0, np.nan)
g = X.groupby('posteam')
for c, n_ in (('pr', 'nn'), ('rzpr', 'rzn'), ('rshare', None)):      # offense's own prior tendency: last 16 games, weighted by sample
    num = (X[c].fillna(0) * (X[n_] if n_ else (X.rtd + X.ptd))); den = (X[n_] if n_ else (X.rtd + X.ptd))
    X[c + '_own'] = (num.groupby(X.posteam).transform(lambda v: v.shift(1).rolling(16, min_periods=4).sum()) /
                     den.groupby(X.posteam).transform(lambda v: v.shift(1).rolling(16, min_periods=4).sum()))
def dr(gm, t):
    r = pre.get((gm, t)); return (np.nan, np.nan) if r is None else (r[1][1], r[1][2])     # defense pass / rush EPA allowed
X['d_pass'], X['d_rush'] = zip(*[dr(gm, t) for gm, t in zip(X.game_id, X.defteam)])
X['funnel'] = X.d_pass - X.d_rush                               # + = the defense is worse against the pass than the run
X = X[X.season >= 2014].dropna(subset=['pr_own', 'funnel'])
for y, own, wt in (('pr', 'pr_own', 'nn'), ('rzpr', 'rzpr_own', 'rzn'), ('rshare', 'rshare_own', None)):
    Z = X.dropna(subset=[y, own]); wv = Z[wt].values if wt else (Z.rtd + Z.ptd).values
    out = []
    for S in range(2016, 2026):
        tr, te = Z[Z.season != S], Z[Z.season == S]; wtr = wv[(Z.season != S).values]; wte = wv[(Z.season == S).values]
        for cols in ([own], [own, 'funnel']):
            A = np.c_[np.ones(len(tr)), tr[cols].values]; W = wtr[:, None]
            b = np.linalg.solve((A * W).T @ A, (A * W).T @ tr[y].values)
            e = te[y].values - np.c_[np.ones(len(te)), te[cols].values] @ b; out.append((S, len(cols), float(np.sum(wte * e * e) / wte.sum()), b[-1]))
    O = pd.DataFrame(out, columns=['S', 'k', 'mse', 'coef']); piv = O.pivot(index='S', columns='k', values='mse')
    ch = 100 * (piv[2] - piv[1]) / piv[1]
    print(f"{y:7s}: funnel coef {O[O.k==2].coef.mean():+.3f} | held-out error change by season: " + ' '.join(f'{s % 100}:{v:+.1f}%' for s, v in ch.items()) + f" | seasons better {int((ch<0).sum())}/10")
