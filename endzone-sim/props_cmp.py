import json, numpy as np, pandas as pd
def load(fs):
    rows = []; [rows.extend(json.load(open(f))['props']) for f in fs]
    P = pd.DataFrame(rows); P = P[P.played & (P.actual != P.line)].copy(); P['y'] = (P.actual > P.line).astype(int); P['s'] = P.id.str[:4]
    P['pm'] = (P.pOver / (1 - P.pPush)).clip(.01, .99); return P
B = load("bt_2024_1_1_pre_draftkings_dk_rows.json bt_2024_2_18_pre_draftkings_dk_rows.json bt_2025_1_1_pre_draftkings_dk_rows.json bt_2025_2_18_pre_draftkings_dk_rows.json bt_2026_1_2_pre_draftkings_dk_rows.json".split())
R = load("bt_2024_1_1_pre_draftkings_rex2024_dk_rows.json bt_2024_2_18_pre_draftkings_rex2024_dk_rows.json bt_2025_1_1_pre_draftkings_rex2025_dk_rows.json bt_2025_2_18_pre_draftkings_rex2025_dk_rows.json bt_2026_1_2_pre_draftkings_rall_dk_rows.json".split())
K = B.merge(R[['id', 'n', 'mk', 'line', 'pm']], on=['id', 'n', 'mk', 'line'], suffixes=('_b', '_r'))
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
print('matched props', len(K))
for s, g in list(K.groupby('s')) + [('all', K)]:
    out = f"{s}: n={len(g)} DK {ll(g.fair, g.y):.4f}"
    for t in ('b', 'r'):
        pb = .8 * g.fair + .2 * g['pm_' + t]
        eo = pb * g.bestO.map(dec) - 1; eu = (1 - pb) * g.bestU.map(dec) - 1; side = np.where(eo >= eu, 'O', 'U'); m = (np.maximum(eo, eu) > 0).values
        won = np.where(side == 'O', g.y == 1, g.y == 0); pay = np.where(side == 'O', g.bestO.map(dec), g.bestU.map(dec)); pl = np.where(won, pay - 1, -1)[m]
        out += f" | {'old' if t=='b' else 'role'}: sim {ll(g['pm_'+t], g.y):.4f} 80/20 {ll(pb, g.y):.4f} bets {m.sum()} ROI {pl.mean():+.3f}±{pl.std()/np.sqrt(max(1,m.sum())):.3f}"
    print(out)
for mk, g in K.groupby('mk'):
    print(f"  {mk}: n={len(g)} DK {ll(g.fair,g.y):.4f} old 80/20 {ll(.8*g.fair+.2*g.pm_b,g.y):.4f} role 80/20 {ll(.8*g.fair+.2*g.pm_r,g.y):.4f}")
W = np.arange(0, 1.01, .1)
for s in ('2024', '2025', '2026'):
    tr, te = K[K.s != s], K[K.s == s]
    w = W[np.argmin([ll(x * tr.fair + (1 - x) * tr.pm_r, tr.y) for x in W])]
    print(f"  role: train-best DK weight {w:.1f} -> held-out {s} LL {ll(w*te.fair+(1-w)*te.pm_r, te.y):.4f} vs DK {ll(te.fair, te.y):.4f}")
