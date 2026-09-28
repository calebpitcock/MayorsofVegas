import json, re, numpy as np, pandas as pd
Q = pd.read_csv('/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/phase7/stage_a/all_quotes.csv')
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
Q = Q[Q.sportsbook == 'draftkings']; Q['key'] = Q.player.map(norm); Q = Q.drop_duplicates(['game', 'key'])
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0))
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))); sig = lambda z: 1 / (1 + np.exp(-z))
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def fitlr(X, y, l2=1e-3):
    X = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X.shape[1])
    for _ in range(50):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w)), X.T @ (p - y) + l2 * w)
    return w
def cal_fit(R):     # slope + position offsets, as td_cal.py
    P = ['QB', 'RB', 'WR', 'TE']; X = np.column_stack([lg(R.pTD)] + [(R.pos == p).astype(float) for p in P]); y = R.td.values; w = np.r_[1, 0, 0, 0, 0.]
    for _ in range(60):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + 2 * np.eye(5), X.T @ (p - y) + 2 * (w - np.r_[1, 0, 0, 0, 0]))
    return lambda D: sig(np.column_stack([lg(D.pTD)] + [(D.pos == p).astype(float) for p in P]) @ w)
def load(f):
    R = pd.DataFrame(json.load(open(f))['rows']); R['key'] = R.n.map(norm); return R
base25, role25 = load('bt_2025_4_18_B4_rows.json'), load('bt_2025_4_18_rex2025_B4_rows.json')
br = lambda p, y: float(np.mean((p - y) ** 2))
for lab, R in (('baseline', base25), ('role', role25)):
    c = cal_fit(R); print(f'2025 {lab}: n={len(R)} Brier raw {br(R.pTD, R.td):.5f} calibrated(in-sample) {br(c(R), R.td):.5f}')
cb, cr = cal_fit(base25), cal_fit(role25)        # calibrations fit on 2025, applied to 2023-24
M = {}
for lab, files, cal in (('baseline', ('bt_2023_3_18_td_rows.json', 'bt_2024_3_18_td_rows.json'), cb), ('role', ('bt_2023_3_18_rex2023_td_rows.json', 'bt_2024_3_18_rex2024_td_rows.json'), cr)):
    R = pd.concat([load(f) for f in files]); R['pc'] = cal(R); R['season'] = R.id.str[:4].astype(int)
    M[lab] = R.merge(Q[['game', 'key', 'price']], left_on=['id', 'key'], right_on=['game', 'key'])
k = M['baseline'].merge(M['role'][['id', 'key', 'pc']], on=['id', 'key'], suffixes=('_b', '_r'))
k['lk'] = lg(imp(k.price.values))
print('matched on both', len(k))
for tr_s, te_s in ((2023, 2024), (2024, 2023)):
    tr, te = k[k.season == tr_s], k[k.season == te_s]
    w0 = fitlr(tr[['lk']].values, tr.td.values); p0 = sig(w0[0] + w0[1] * te.lk)
    out = f'fit {tr_s} test {te_s}: DK {ll(p0, te.td):.5f}'
    for s in ('b', 'r'):
        w = fitlr(np.column_stack([tr.lk, lg(tr['pc_' + s])]), tr.td.values); p = sig(w[0] + w[1] * te.lk + w[2] * lg(te['pc_' + s]))
        out += f" | +{'baseline' if s=='b' else 'role'} model {ll(p, te.td):.5f} (w {w[2]:.3f}, model alone {ll(te['pc_'+s], te.td):.5f})"
    print(out)
