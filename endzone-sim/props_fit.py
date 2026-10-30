import json, sys, numpy as np, pandas as pd
rows = []
for f in sys.argv[1:]: rows += json.load(open(f))['props']
P = pd.DataFrame(rows); P = P[P.played]; P = P[P.actual != P.line]
P['y'] = (P.actual > P.line).astype(float); P['pm'] = (P.pOver / (1 - P.pPush)).clip(.02, .98); P['season'] = P.id.str[:4].astype(int)
dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
lg = lambda p: np.log(p / (1 - p)); sig = lambda z: 1 / (1 + np.exp(-z))
MK = ['player_reception_yds', 'player_receptions', 'player_rush_yds']
def X(d, model):
    cols = [(d.mk == m).astype(float).values for m in MK] + [lg(d.fair.clip(.02, .98)).values]
    if model: cols.append(lg(d.pm).values)
    return np.column_stack(cols)
def fit(A, y, l2=.5):
    w = np.zeros(A.shape[1])
    for _ in range(50):
        p = sig(A @ w); w -= np.linalg.solve((A * (p * (1 - p))[:, None]).T @ A + l2 * np.eye(len(w)), A.T @ (p - y) + l2 * w)
    return w
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def bet(d, p, thr=.03):
    eo = p * d.bestO.map(dec) - 1; eu = (1 - p) * d.bestU.map(dec) - 1; ev = np.maximum(eo, eu); side = np.where(eo >= eu, 'O', 'U'); m = (ev > thr).values
    won = np.where(side == 'O', d.y == 1, d.y == 0); pay = np.where(side == 'O', d.bestO.map(dec), d.bestU.map(dec)); pl = np.where(won, pay - 1, -1)[m]
    return f"{m.sum()} bets ({np.mean(side[m]=='U') if m.sum() else 0:.0%} unders) ROI {pl.mean() if m.sum() else 0:+.3f} ± {pl.std()/np.sqrt(max(1,m.sum())):.3f}"
for tr_s, te_s in (((2024, 2025), (2026,)), ((2025, 2026), (2024,)), ((2024, 2026), (2025,))):
    tr, te = P[P.season.isin(tr_s)], P[P.season.isin(te_s)]
    w0 = fit(X(tr, 0), tr.y.values); w1 = fit(X(tr, 1), tr.y.values)
    p0 = sig(X(te, 0) @ w0); p1 = sig(X(te, 1) @ w1)
    print(f"train {tr_s} test {te_s} n={len(te)}: LL DK {ll(te.fair,te.y):.4f} | DK+market bias {ll(p0,te.y):.4f} | +model {ll(p1,te.y):.4f}  model coef {w1[-1]:.3f}")
    print(f"     bets: bias-only {bet(te,p0)} | bias+model {bet(te,p1)}")
w0 = fit(X(P, 0), P.y.values); w1 = fit(X(P, 1), P.y.values)
print('pooled bias-only', dict(zip(MK + ['dk'], w0.round(3)))); print('pooled +model', dict(zip(MK + ['dk', 'model'], w1.round(3))))
json.dump(dict(mk=dict(zip(MK, map(float, w1[:3]))), dk=float(w1[3]), model=float(w1[4]), n=len(P),
               bias_only=dict(mk=dict(zip(MK, map(float, w0[:3]))), dk=float(w0[3]))), open('prop_dk_fit.json', 'w'))
