"""Train the game model directly on the closing-line residual (result - close) instead of on the result."""
import sys; sys.path.insert(0, '/home/user/MayorsofVegas/endzone-sim/gm')
import numpy as np, pandas as pd, model2, model3
D = model3.add(pd.read_parquet('D.parquet'), model3.MP); D['ats'] = D.result - D.spread_line
X = pd.read_parquet('/home/user/work/gm2/ats.parquet')[['game_id', 'hodds', 'aodds']]
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
def walkres(cols, S0=2016, S1=2025, l2=1.0, RHL=8.0):
    out = []
    for S in range(S0, S1 + 1):
        tr = D[(D.season < S) & (D.week >= 3)].dropna(subset=['spread_line']); te = D[D.season == S].copy()
        sw = 0.5 ** ((S - 1 - tr.season) / RHL); A = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols]); W = sw.values[:, None]
        w = np.linalg.solve((A * W).T @ A + l2 * np.diag([0] + [1] * len(cols)), (A * W).T @ tr.ats.values)
        te['pred'] = np.column_stack([np.ones(len(te))] + [te[c] for c in cols]) @ w; out.append(te)
    return pd.concat(out)
def rep(E, lab):
    E = E.merge(X, on='game_id').dropna(subset=['hodds']); E = E[E.ats != 0]
    side = E.pred > 0; won = np.where(side, E.ats > 0, E.ats < 0); pay = np.where(side, dec(E.hodds.values), dec(E.aodds.values)); pl = np.where(won, pay - 1, -1)
    a = E.pred.abs(); s = f"{lab:40s} n={len(E)}"
    for q in (.5, .8, .9):
        m = (a >= a.quantile(q)).values; by = pd.Series(pl[m]).groupby(E.season.values[m]).mean()
        s += f" | top {int(round(100*(1-q)))}%: {won[m].mean():.3f} ROI {pl[m].mean():+.3f}±{pl[m].std()/np.sqrt(m.sum()):.3f} ({int((by>0).sum())}/{len(by)} seasons up)"
    print(s)
# baseline: current model's disagreement (fit to result)
O = model2.walk(D, 2016, 2025, RHL=8.0, cols=model3.F3); O['pred'] = O.m - O.spread_line; O['ats'] = O.result - O.spread_line
rep(O, 'current (fit to result), disagreement')
D['mk_line'] = D.mkt + 0 - D.spread_line   # market rating margin vs this line (hfa absorbed by intercept)
rep(walkres(model3.F3 + ['spread_line']), 'fit to closing residual, all features')
rep(walkres(['epa', 'pepa', 'repa', 'sr', 'qb', 'qbd', 'qb2', 'spread_line']), 'residual: efficiency+QB only')
rep(walkres(['qb', 'qbd', 'qb2', 'mkt', 'spread_line']), 'residual: QB + market strength')
