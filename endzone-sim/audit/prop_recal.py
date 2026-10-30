"""Per-market recalibration of the simulation's P(over) for DraftKings props, tested one season held out.
Usage: prop_recal.py <rows files...>"""
import json, sys, numpy as np, pandas as pd
F = sys.argv[1:]
P = pd.concat([pd.DataFrame(json.load(open(f))['props']).assign(season=f.split('/')[-1][3:7]) for f in F]); P = P[P.played & (P.actual != P.line)].copy()
P['y'] = (P.actual > P.line).astype(float); P['pm'] = (P.pOver / (1 - P.pPush)).clip(.02, .98)
lg = lambda p: np.log(p / (1 - p)); sig = lambda z: 1 / (1 + np.exp(-z)); dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def fit(d, l2=2.0):
    X = np.column_stack([np.ones(len(d)), lg(d.pm.values)]); y = d.y.values; w = np.array([0., 1.])
    for _ in range(40):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(2), X.T @ (p - y) + l2 * (w - [0, 1]))
    return w
def roi(d, p):
    eo = p * d.bestO.map(dec) - 1; eu = (1 - p) * d.bestU.map(dec) - 1; s = np.where(eo >= eu, 'O', 'U'); m = (np.maximum(eo, eu) > 0).values
    won = np.where(s == 'O', d.y == 1, d.y == 0); pay = np.where(s == 'O', d.bestO.map(dec), d.bestU.map(dec)); pl = np.where(won, pay - 1, -1)[m]
    return m.sum(), (pl.mean() if m.sum() else 0), (pl.std() / np.sqrt(max(1, m.sum())))
out = []
for s in sorted(P.season.unique()):
    tr, te = P[P.season != s], P[P.season == s].copy(); te['pr'] = te.pm
    for mk, g in tr.groupby('mk'):
        w = fit(g); i = te.mk == mk; te.loc[i, 'pr'] = sig(w[0] + w[1] * lg(te.loc[i, 'pm']))
    out.append(te)
E = pd.concat(out)
for lab, col in (('sim as is', 'pm'), ('recalibrated', 'pr')):
    b = .8 * E.fair + .2 * E[col]; n, r, se = roi(E, b)
    by = {s: round(roi(g, .8 * g.fair + .2 * g[col])[1], 3) for s, g in E.groupby('season')}
    print(f"{lab:13s}: sim LL {ll(E[col], E.y):.4f} | 80/20 LL {ll(b, E.y):.4f} (DK {ll(E.fair, E.y):.4f}) | bets {n} ROI {r:+.3f} ± {se:.3f} by season {by}")
