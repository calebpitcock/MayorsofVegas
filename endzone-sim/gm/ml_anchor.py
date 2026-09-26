import numpy as np, pandas as pd
G = pd.read_csv('../../data/games.csv'); G = G[(G.game_type == 'REG') & G.result.notna() & (G.result != 0) & (G.season.between(2006, 2020))]
sig = lambda z: 1 / (1 + np.exp(-z)); lg = lambda p: np.log(p / (1 - p))
x = G.spread_line.values; y = (G.result > 0).astype(float).values; b = 0.0
for _ in range(50):
    p = sig(b * x); b -= ((p - y) @ x) / ((p * (1 - p)) @ (x * x))
print(f'P(home win) = logistic({b:.4f} x home points expected), fit 2006-20; 7-pt favorite -> {sig(b*7):.3f}; normal sd13.3 says 0.700')
# cover: how fast the cover chance moves per point of disagreement near the line (fit 2006-20 using the spread line itself shifted)
G['d'] = G.result - G.spread_line
dens = {}
for L in (0, 1, 2, 3, 4, 5, 6, 7):
    dens[L] = np.mean(np.abs(np.abs(G.d) - 0) < .5)
# slope of P(cover) per point: P(d > -delta) - P(d > 0) over delta=1, averaged over lines
sl = np.mean([(np.mean(G.d > -1.0) - np.mean(G.d > 0.0)), (np.mean(G.d >= 0) - np.mean(G.d >= 1))])
print(f'cover chance moves about {sl:.3f} per point near the line')
E = pd.read_parquet('wf2.parquet'); T = pd.read_parquet('tue_dk.parquet')
M = E.merge(T, left_on=['season', 'home_team', 'away_team'], right_on=['season', 'home', 'away']); M['tue'] = -M.sp_h; M = M[M.tue.notna() & M.ml_h.notna() & (M.result != 0) & (M.season >= 2022)].copy()
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0)); dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
M['pk'] = imp(M.ml_h.values) / (imp(M.ml_h.values) + imp(M.ml_a.values)); yy = M.result.values > 0
for k in (0.1, 0.15, 0.2, 0.3):
    M['pw'] = sig(lg(M.pk) + b * k * (M.m - M.tue))
    br = lambda p: float(np.mean((p - yy) ** 2))
    out = f'k={k}: Brier DK {br(M.pk):.4f} anchored model {br(M.pw):.4f}'
    for thr in (0.0, .03):
        eh = M.pw * dec(M.ml_h.values) - 1; ea = (1 - M.pw) * dec(M.ml_a.values) - 1; side = np.where(eh >= ea, 'h', 'a'); m = np.maximum(eh, ea) > thr
        won = np.where(side == 'h', yy, ~yy)[m]; pay = np.where(side == 'h', dec(M.ml_h.values), dec(M.ml_a.values))[m]; pl = np.where(won, pay - 1, -1.0)
        out += f' | EV>{thr:.0%} n={m.sum()} ROI {pl.mean():+.3f}±{pl.std()/np.sqrt(max(1,m.sum())):.3f} {pd.Series(pl).groupby(M.season.values[m]).mean().round(2).to_dict()}'
    print(out)
    # spread anchored
    ps = imp(M.spo_h.values) / (imp(M.spo_h.values) + imp(M.spo_a.values)) + sl * k * (M.m - M.tue)
    eh = ps * dec(M.spo_h.values) - 1; ea = (1 - ps) * dec(M.spo_a.values) - 1; side = np.where(eh >= ea, 'h', 'a'); m = (np.maximum(eh, ea) > 0) & (M.result + M.sp_h != 0)
    won = np.where(side == 'h', M.result + M.sp_h > 0, M.result + M.sp_h < 0)[m]; pay = np.where(side == 'h', dec(M.spo_h.values), dec(M.spo_a.values))[m]; pl = np.where(won, pay - 1, -1.0)
    print(f'      spread anchored EV>0: n={m.sum()} cover {won.mean():.3f} ROI {pl.mean():+.3f}±{pl.std()/np.sqrt(max(1,m.sum())):.3f} {pd.Series(pl).groupby(M.season.values[m]).mean().round(2).to_dict()}')
import json; json.dump(dict(b=float(b), slope=float(sl)), open('anchor.json', 'w'))
