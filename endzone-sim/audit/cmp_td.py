"""Anytime TD vs DraftKings for one code tree. TD recalibration refit on that tree's own 2025 pregame rows (weeks
4-18, as td_cal.py), then the DK blend is fit on 2023 and tested on 2024 and vice versa (~5-min-before-kickoff DK
prices), plus 2026 Weeks 1-2 with the pooled 2023-24 fit. Usage: cmp_td.py <tree dir> [write]"""
import json, re, sys, glob, numpy as np, pandas as pd
T = sys.argv[1]; sys.path.insert(0, T)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))); sig = lambda z: 1 / (1 + np.exp(-z))
ll = lambda p, y: float(-np.mean(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1))))
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0)); dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
rows = lambda f: pd.DataFrame(json.load(open(f'{T}/{f}'))['rows'])
POS = ['QB', 'RB', 'WR', 'TE']
def cal_fit(R, l2=2.0):
    X = np.column_stack([lg(R.pTD)] + [(R.pos == p).astype(float) for p in POS]); y = R.td.values.astype(float); w = np.r_[1., 0, 0, 0, 0]
    for _ in range(60):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(5), X.T @ (p - y) + l2 * (w - np.r_[1, 0, 0, 0, 0]))
    return w
cal_apply = lambda R, w: sig(np.column_stack([lg(R.pTD)] + [(R.pos == p).astype(float) for p in POS]) @ w)
def fitlr(X, y, l2=1e-3):
    X = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X.shape[1])
    for _ in range(50):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w)), X.T @ (p - y) + l2 * w)
    return w
R25 = rows('bt_2025_1_18_pre_draftkings_rex2025_dk_rows.json'); R25 = R25[R25.week >= 4]
wc = cal_fit(R25)
Q = pd.read_csv('/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/phase7/stage_a/all_quotes.csv')
Q = Q[Q.sportsbook == 'draftkings'].copy(); Q['key'] = Q.player.map(norm); Q = Q.drop_duplicates(['game', 'key'])
R = pd.concat([rows('bt_2023_3_18_rex2023_dk_rows.json'), rows('bt_2024_3_18_rex2024_dk_rows.json')]); R['season'] = R.id.str[:4].astype(int)
R['key'] = R.n.map(norm); R['pc'] = cal_apply(R, wc)
M = R.merge(Q[['game', 'key', 'price']], left_on=['id', 'key'], right_on=['game', 'key']); M['lk'] = lg(imp(M.price.values)); M['lm'] = lg(M.pc.values)
out = {'cal': dict(slope=round(float(wc[0]), 4), **{p: round(float(v), 4) for p, v in zip(POS, wc[1:])})}
print(f"[{T}] TD calibration from own 2025 rows: {out['cal']} | Brier 2025 raw {np.mean((R25.pTD-R25.td)**2):.5f} cal {np.mean((cal_apply(R25,wc)-R25.td)**2):.5f}")
print(f"  matched DK prices 2023-24: {len(M)}")
gains = []
for a, b in ((2023, 2024), (2024, 2023)):
    tr, te = M[M.season == a], M[M.season == b]
    w0 = fitlr(tr[['lk']].values, tr.td.values); w1 = fitlr(tr[['lk', 'lm']].values, tr.td.values)
    p0 = sig(w0[0] + w0[1] * te.lk); p1 = sig(w1[0] + w1[1] * te.lk + w1[2] * te.lm)
    rng = np.random.default_rng(1); idx = np.arange(len(te)); d = []
    for _ in range(1000):
        s = rng.choice(idx, len(idx)); d.append(ll(p0.values[s], te.td.values[s]) - ll(p1.values[s], te.td.values[s]))
    ev = p1 * dec(te.price.values) - 1; m = (ev > 0).values; pl = np.where(te.td.values[m] == 1, dec(te.price.values[m]) - 1, -1.0)
    print(f"  fit {a} test {b}: LL DK {ll(p0, te.td):.5f} DK+model {ll(p1, te.td):.5f} gain {np.mean(d):.5f} (95% {np.percentile(d,2.5):.5f} to {np.percentile(d,97.5):.5f}) model w {w1[2]:.3f} | EV>0 bets {m.sum()} ROI {pl.mean():+.3f}")
w = fitlr(M[['lk', 'lm']].values, M.td.values); w0 = fitlr(M[['lk']].values, M.td.values)
out['fit'] = dict(a=float(w[0]), bk=float(w[1]), bm=float(w[2]), dva=float(w0[0]), dvb=float(w0[1]), n=int(len(M)), seasons='2023-2024', src='DraftKings anytime TD ~5 min before kickoff')
print('  pooled fit', {k: round(v, 4) for k, v in out['fit'].items() if isinstance(v, float)})
# 2026 weeks 1-2 (pregame), DK quotes from mogden16 2026 files
import importlib; ph = importlib.import_module('props_hist')
ev_ = pd.concat([pd.read_csv(f, usecols=['Event ID', 'Home', 'Away', 'Week']) for f in glob.glob('/home/user/MayorsofVegas/data/snap26/*.csv')]).drop_duplicates('Event ID')
E = dict(zip(ev_['Event ID'], [f"2026_{int(r.Week):02d}_{ph.ABBR[r.Away]}_{ph.ABBR[r.Home]}" for r in ev_.itertuples()]))
base = '/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/'
q26 = pd.concat([pd.read_csv(base + 'phase45_stage_a_all_quotes.csv').rename(columns={'american_odds': 'price'})[['event_id', 'player', 'sportsbook', 'price']],
                 pd.read_csv(base + 'atd_price_quotes_2026-09-17.csv')[['event_id', 'player', 'sportsbook', 'price']]])
q26 = q26[q26.sportsbook == 'draftkings'].drop_duplicates(['event_id', 'player']); q26['gid'] = q26.event_id.map(E); q26['key'] = q26.player.map(norm)
R26 = rows('bt_2026_1_2_pre_draftkings_rall_dk_rows.json'); R26['key'] = R26.n.map(norm); R26['pc'] = cal_apply(R26, wc)
N = R26.merge(q26, left_on=['id', 'key'], right_on=['gid', 'key']); lk = lg(imp(N.price.values))
p0 = sig(w0[0] + w0[1] * lk); p1 = sig(w[0] + w[1] * lk + w[2] * lg(N.pc.values))
print(f"  2026 wk1-2: n={len(N)} LL DK {ll(p0, N.td):.5f} DK+model {ll(p1, N.td):.5f}")
if len(sys.argv) > 2:
    json.dump(out['cal'], open(f'{T}/td_cal_nfl.json', 'w')); json.dump(out['fit'], open(f'{T}/td_dk_fit.json', 'w')); print('  wrote td_cal_nfl.json, td_dk_fit.json')
