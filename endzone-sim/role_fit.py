"""Fit the role correction (actual share - model share) on snap trend, practice report and availability signals.
Writes role_coef_all.json (for the live slate) and role_coef_ex{S}.json (fit without season S, for honest backtests)."""
import json, numpy as np, pandas as pd
R = pd.concat([pd.read_csv(f'role_{s}.csv') for s in (2023, 2024, 2025)])
FEATS = ['trend', 'gap', 'q', 'lim', 'dnp', 'back', 'trend_x', 'q_x', 'lim_x', 'back_x', 'new_x']
def fe(D, pred):
    trend = (D.s_last - D.s_prev).fillna(0); gap = D.s_last - D.s_all
    q = (D.status == 'Questionable').astype(float); lim = D.practice.str.contains('Limited', na=False).astype(float)
    dnp = D.practice.str.contains('Did Not', na=False).astype(float); back = (1 - D.played_last).astype(float); new = (D.g <= 1).astype(float)
    return np.column_stack([np.ones(len(D)), trend, gap, q, lim, dnp, back, trend * D[pred], q * D[pred], lim * D[pred], back * D[pred], new * D[pred]])
def fit(D, pred, act, l2=1.0):
    A = fe(D, pred); y = (D[act] - D[pred]).values
    return np.linalg.solve(A.T @ A + l2 * np.eye(A.shape[1]) * np.r_[0, np.ones(A.shape[1] - 1)], A.T @ y).tolist()
def fitall(D):
    return dict(rush_RB=fit(D[D.pos == 'RB'], 'rush', 'ar'), **{f'rec_{p}': fit(D[D.pos == p], 'rec', 'at') for p in ('WR', 'TE', 'RB')}, feats=['c'] + FEATS)
json.dump(fitall(R), open('role_coef_all.json', 'w'))
for s in (2023, 2024, 2025): json.dump(fitall(R[R.season != s]), open(f'role_coef_ex{s}.json', 'w'))
print(json.load(open('role_coef_all.json'))['rush_RB'])
