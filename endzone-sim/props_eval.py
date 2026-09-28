import json, sys, numpy as np, pandas as pd
rows = []
for f in sys.argv[1:]:
    rows += json.load(open(f))['props']
P = pd.DataFrame(rows)
P = P[P.played]
P = P[P.actual != P.line]                      # pushes
P['y'] = (P.actual > P.line).astype(float)
P['pm'] = (P.pOver / (1 - P.pPush)).clip(.01, .99)
dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
br = lambda p, y: float(np.mean((p - y) ** 2))
print(f"props graded: {len(P)}  (rec yds {sum(P.mk=='player_reception_yds')}, receptions {sum(P.mk=='player_receptions')}, rush yds {sum(P.mk=='player_rush_yds')})")
print(f"over hit rate {P.y.mean():.3f}   market says {P.fair.mean():.3f}   model says {P.pm.mean():.3f}")
print(f"log loss  market {ll(P.fair,P.y):.4f}   model {ll(P.pm,P.y):.4f}   coin {ll(np.full(len(P),.5),P.y):.4f}")
best = None
for w in np.arange(0, 1.01, .1):
    pb = w * P.fair + (1 - w) * P.pm
    l = ll(pb, P.y)
    print(f"  market weight {w:.1f}: log loss {l:.4f}  Brier {br(pb,P.y):.4f}")
    if best is None or l < best[1]: best = (w, l)
print('best market weight', round(best[0], 1))
rng = np.random.default_rng(1); d = []
idx = np.arange(len(P))
for _ in range(2000):
    s = rng.choice(idx, len(idx)); q = P.iloc[s]
    d.append(ll(q.fair, q.y) - ll(.5 * q.fair + .5 * q.pm, q.y))
d = np.array(d); print(f"50/50 blend beats market by {np.mean(d):.4f} log-loss (95% CI {np.percentile(d,2.5):.4f} to {np.percentile(d,97.5):.4f}); P(better) {np.mean(d>0):.2f}")
def sim(w, thr):
    pb = w * P.fair + (1 - w) * P.pm
    eo = pb * P.bestO.map(dec) - 1; eu = (1 - pb) * P.bestU.map(dec) - 1
    side = np.where(eo >= eu, 'O', 'U'); ev = np.maximum(eo, eu)
    m = (ev > thr).values
    won = np.where(side == 'O', P.y == 1, P.y == 0)
    pay = np.where(side == 'O', P.bestO.map(dec), P.bestU.map(dec))
    pl = np.where(won, pay - 1, -1)[m]
    if m.sum() == 0: return print(f"  w={w} thr={thr}: no bets")
    print(f"  w={w:.1f} EV>{thr:.0%}: {m.sum():4d} bets, win {won[m].mean():.3f}, ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(len(pl)):.3f}  (overs {np.mean(side[m]=='O'):.2f})")
print('betting simulation at the best available price (line shopping across books):')
for w in (.3, .5, .7):
    for thr in (.0, .03, .06):
        sim(w, thr)
pl_u = np.where(P.y == 0, P.bestU.map(dec) - 1, -1); pl_o = np.where(P.y == 1, P.bestO.map(dec) - 1, -1)
print(f"baseline: every under {pl_u.mean():+.3f} ± {pl_u.std()/np.sqrt(len(P)):.3f} | every over {pl_o.mean():+.3f}")
for mk, g in P.groupby('mk'):
    print(f"  {mk}: n={len(g)} over rate {g.y.mean():.3f} market {g.fair.mean():.3f} model {g.pm.mean():.3f}  LL market {ll(g.fair,g.y):.4f} model {ll(g.pm,g.y):.4f} blend {ll(.5*g.fair+.5*g.pm,g.y):.4f}")
P['season'] = P.id.str[:4]
print('by season (every under / 60-40 blend EV>3% / log loss market vs 60-40 blend):')
for s, g in P.groupby('season'):
    pu = np.where(g.y == 0, g.bestU.map(dec) - 1, -1); pb = .6 * g.fair + .4 * g.pm
    eo = pb * g.bestO.map(dec) - 1; eu = (1 - pb) * g.bestU.map(dec) - 1; ev = np.maximum(eo, eu); side = np.where(eo >= eu, 'O', 'U'); m = (ev > .03).values
    won = np.where(side == 'O', g.y == 1, g.y == 0); pay = np.where(side == 'O', g.bestO.map(dec), g.bestU.map(dec)); pl = np.where(won, pay - 1, -1)[m]
    print(f"  {s}: n={len(g)} over rate {g.y.mean():.3f} | unders {pu.mean():+.3f} ± {pu.std()/np.sqrt(len(g)):.3f} | blend bets {m.sum()} ROI {pl.mean() if m.sum() else 0:+.3f} ± {pl.std()/np.sqrt(max(m.sum(),1)):.3f} | LL {ll(g.fair,g.y):.4f} vs {ll(pb,g.y):.4f}")
