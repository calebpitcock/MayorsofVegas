"""Paired A/B of two code trees on the same games, after bt_all/runonly + cmp_td: anytime TD vs DraftKings (each tree's
own calibration and DK blend, fit on one season and tested on the other, as cmp_td.py) and DraftKings props at the
page's 80/20 blend. Differences are tree B minus tree A on identical rows, with 95% bootstrap intervals over games.
Usage: cmp_trees.py <tree A endzone-sim> <tree B endzone-sim> [label]"""
import sys, json, re, glob, numpy as np, pandas as pd, importlib.util
A, B = sys.argv[1], sys.argv[2]; LAB = sys.argv[3] if len(sys.argv) > 3 else 'B vs A'
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))); sig = lambda z: 1 / (1 + np.exp(-z))
ll = lambda p, y: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (np.maximum(o, 1) + 100.0)); dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
def cmpmod(T):
    spec = importlib.util.spec_from_file_location('c', f'{T}/audit/cmp_td.py'); return spec
def tdrows(T):
    """held-out DK+model chance per matched row for tree T (replicates cmp_td.py)"""
    src = open(f'{T}/audit/cmp_td.py').read().split('# 2026 weeks 1-2')[0]
    src = src.replace('T = sys.argv[1]', f'T = {T!r}').replace('print(', 'pass; (lambda *a, **k: None)(')
    g = {}; exec(compile(src, 'cmp_td', 'exec'), g)
    M = g['M']; out = []
    for a, b in ((2023, 2024), (2024, 2023)):
        tr, te = M[M.season == a], M[M.season == b]
        w1 = g['fitlr'](tr[['lk', 'lm']].values, tr.td.values)
        out.append(te.assign(p=g['sig'](w1[0] + w1[1] * te.lk + w1[2] * te.lm)))
    return pd.concat(out)[['id', 'key', 'season', 'td', 'p', 'price']]
def boot(d, col, by, n=2000):
    gsum = d.groupby(by)[col].agg(['sum', 'size']); rng = np.random.default_rng(1); r = []
    for _ in range(n):
        s = rng.integers(0, len(gsum), len(gsum)); r.append(gsum['sum'].values[s].sum() / gsum['size'].values[s].sum())
    return np.mean(d[col]), np.percentile(r, 2.5), np.percentile(r, 97.5)
print(f'== {LAB}   (A={A}\n   B={B})')
ta, tb = tdrows(A), tdrows(B); M = ta.merge(tb, on=['id', 'key', 'season', 'td', 'price'], suffixes=('a', 'b'))
M['d'] = ll(M.pb, M.td) - ll(M.pa, M.td)
for s in (2024, 2023, None):
    d = M if s is None else M[M.season == s]; m, lo, hi = boot(d, 'd', 'id')
    print(f'TD vs DK, held-out DK+model log loss, {s or "both"}: n={len(d)}  A {ll(d.pa, d.td).mean():.5f}  B {ll(d.pb, d.td).mean():.5f}  B-A {m:+.5f} (95% {lo:+.5f} to {hi:+.5f})')
for t, c in (('A', 'pa'), ('B', 'pb')):
    ev = M[c] * dec(M.price.values) - 1; m = ev > 0; pl = np.where(M.td[m] == 1, dec(M.price[m].values) - 1, -1.0)
    print(f'   EV>0 TD bets {t}: {m.sum()} bets, ROI {pl.mean():+.3f}')
def props(T):
    rows = []
    for f in ('bt_2024_1_18_pre_draftkings_rex2024', 'bt_2025_1_18_pre_draftkings_rex2025', 'bt_2026_1_2_pre_draftkings_rall'):
        rows += json.load(open(f'{T}/{f}_dk_rows.json'))['props']
    P = pd.DataFrame(rows); P = P[P.played & (P.actual != P.line)].copy(); P['y'] = (P.actual > P.line).astype(float)
    P['pm'] = (P.pOver / (1 - P.pPush)).clip(.01, .99); P['pb'] = .8 * P.fair + .2 * P.pm; return P
pa, pb = props(A), props(B); k = ['id', 'n', 'mk', 'line']
P = pa.merge(pb[k + ['pm', 'pb']], on=k, suffixes=('a', 'b')); P['d'] = ll(P.pbb, P.y) - ll(P.pba, P.y)
P['season'] = P.id.str[:4]
for s in ('2024', '2025', '2026', None):
    d = P if s is None else P[P.season == s]; m, lo, hi = boot(d, 'd', 'id')
    print(f'Props 80/20 log loss {s or "all"}: n={len(d)}  A {ll(d.pba, d.y).mean():.5f}  B {ll(d.pbb, d.y).mean():.5f}  B-A {m:+.5f} (95% {lo:+.5f} to {hi:+.5f})')
for t, c in (('A', 'pba'), ('B', 'pbb')):
    pr = np.where(P[c] >= .5, P.bestO, P.bestU); side = P[c] >= .5; pwin = np.where(side, P[c], 1 - P[c]); ev = pwin * dec(pr) - 1; m = ev > 0
    won = np.where(side, P.y == 1, P.y == 0)[m]; pl = np.where(won, dec(pr[m]) - 1, -1.0)
    print(f'   80/20 EV>0 prop bets {t}: {m.sum()} bets, ROI {pl.mean():+.3f} +/- {1.96*pl.std()/np.sqrt(max(1,m.sum())):.3f}')
