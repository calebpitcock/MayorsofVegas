"""Fit a touchdown recalibration: logit(p') = a + b*logit(p) + c_pos, on backtest rows.
Reports out-of-sample Brier (fit weeks 4-11, test 12-18) before choosing to use it."""
import json, sys, numpy as np, pandas as pd
d = json.load(open(sys.argv[1] if len(sys.argv) > 1 else 'bt_2025_4_18_rows.json'))
R = pd.DataFrame(d['rows'])
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
POS = ['QB', 'RB', 'WR', 'TE']
def X(df): return np.c_[np.ones(len(df)), lg(df.pTD.values)] if False else np.c_[lg(df.pTD.values)]
def design(df):
    cols = [lg(df.pTD.values)] + [(df.pos == p).astype(float).values for p in POS]
    return np.column_stack(cols)
def fit(df, l2=2.0, iters=60):
    Xm = design(df); y = df.td.values.astype(float); w = np.zeros(Xm.shape[1]); w[0] = 1.0
    for _ in range(iters):  # Newton on penalised log-likelihood; slope penalised toward 1, offsets toward 0
        z = Xm @ w; p = 1 / (1 + np.exp(-z))
        g = Xm.T @ (p - y) + l2 * (w - np.r_[1, np.zeros(len(POS))])
        H = (Xm * (p * (1 - p))[:, None]).T @ Xm + l2 * np.eye(len(w))
        w -= np.linalg.solve(H, g)
    return w
def apply(df, w): z = design(df) @ w; return 1 / (1 + np.exp(-z))
brier = lambda p, y: float(np.mean((p - y) ** 2))
tr, te = R[R.week <= 11], R[R.week >= 12]
w = fit(tr)
print('fit on weeks 4-11:', dict(zip(['slope'] + POS, np.round(w, 3))))
print(f'test weeks 12-18  n={len(te)}: raw Brier {brier(te.pTD, te.td):.4f}  recalibrated {brier(apply(te, w), te.td):.4f}  constant {brier(np.full(len(te), te.td.mean()), te.td):.4f}')
wa = fit(R)
print('fit on all weeks:', dict(zip(['slope'] + POS, np.round(wa, 3))))
R['pc'] = apply(R, wa)
R['bin'] = pd.cut(R.pc, [0, .05, .1, .15, .2, .3, .4, .5, .6, 1])
print(R.groupby('bin', observed=True).agg(n=('td', 'size'), model=('pc', 'mean'), actual=('td', 'mean')).round(3).to_string())
json.dump(dict(slope=round(float(wa[0]), 4), **{p: round(float(v), 4) for p, v in zip(POS, wa[1:])}), open('td_cal.json', 'w'))
