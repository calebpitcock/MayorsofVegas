import json, sys, numpy as np, pandas as pd
rows = []
for f in sys.argv[1:]: rows += json.load(open(f))['props']
P = pd.DataFrame(rows); P = P[P.played]; P = P[P.actual != P.line]
P['y'] = (P.actual > P.line).astype(float); P['pm'] = (P.pOver / (1 - P.pPush)).clip(.01, .99); P['season'] = P.id.str[:4]
dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
P['pu'] = np.where(P.y == 0, P.bestU.map(dec) - 1, -1.0)
def rep(lab, m):
    g = P[m]; out = f"{lab:44s} n={len(g):4d} ROI {g.pu.mean():+.3f} ± {g.pu.std()/np.sqrt(max(len(g),1)):.3f} |"
    for s in ('2024', '2025', '2026'):
        h = g[g.season == s]; out += f" {s} {h.pu.mean():+.3f} ({len(h)})"
    print(out)
rep('every under', P.y == P.y)
rep('model agrees (model over < DK over)', P.pm < P.fair)
rep('model disagrees', P.pm >= P.fair)
rep('model over < DK over - 5 pts', P.pm < P.fair - .05)
rep('model over < DK over - 10 pts', P.pm < P.fair - .10)
for mk in P.mk.unique():
    rep(f'{mk}', P.mk == mk); rep(f'{mk} + model agrees', (P.mk == mk) & (P.pm < P.fair))
for pos in ('RB', 'WR', 'TE'):
    rep(f'{pos}', P.pos == pos)
P['uprice'] = P.bestU
rep('under priced -120 or longer', P.bestU <= -120); rep('under priced -119 to +100', P.bestU > -120)
q = P.line.rank(pct=True)
for mk in P.mk.unique():
    g = P.mk == mk; med = P[g].line.median(); rep(f'{mk} line above median {med}', g & (P.line > med)); rep(f'{mk} line at/below median', g & (P.line <= med))
for pos in ('QB','RB','WR'):
    rep(f'rush yds {pos}', (P.mk=='player_rush_yds')&(P.pos==pos))
