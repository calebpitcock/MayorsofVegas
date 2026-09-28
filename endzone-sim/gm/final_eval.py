"""Final, honest test of the game model on 2021-2025 (none of it used for tuning): walk-forward margins, then
(a) vs the closing line, (b) vs DraftKings' Tuesday line: line-move prediction, spread bets and moneyline bets at
DraftKings' Tuesday prices, with the lean weight k fitted only on earlier seasons."""
import sys, json, numpy as np, pandas as pd, model2
from math import erf
P = json.loads(sys.argv[1])
cdf = np.vectorize(lambda x: 0.5 * (1 + erf(x / 2 ** .5)))
D = model2.build(dict(HG=P['HG'], CARRY=P['CARRY'], M0=3.0), dict(QHL=P['QHL'], QCARRY=P['QCARRY'], QM0=P['QM0']))
O = model2.walk(D, 2016, 2025, RHL=8.0); O.to_parquet('wf2.parquet')
T = pd.read_parquet('tue_dk.parquet')
M = O.merge(T, left_on=['season', 'home_team', 'away_team'], right_on=['season', 'home', 'away']); M['tue'] = -M.sp_h; M = M[M.tue.notna()].copy()
C = O[(O.season >= 2021) & (O.result != O.spread_line)]
print(f"2021-25 vs close: MAE close {np.mean(np.abs(C.result - C.spread_line)):.3f} model {np.mean(np.abs(C.result - C.m)):.3f}")
print(f"Tuesday games {len(M)}; corr(model-Tue, close-Tue) {np.corrcoef(M.m - M.tue, M.spread_line - M.tue)[0,1]:.3f}")
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0))
SD = 13.3
rows = []
for S in (2022, 2023, 2024, 2025):          # k from Tuesday data of earlier seasons only
    tr = M[M.season < S]; te = M[M.season == S].copy()
    x = (tr.m - tr.tue).values; y = (tr.result - tr.tue).values; k = float(np.clip((x @ y) / (x @ x), 0, 1))
    te['k'] = k; te['hat'] = te.tue + k * (te.m - te.tue); rows.append(te)
E = pd.concat(rows)
print('k by season', E.groupby('season').k.first().round(3).to_dict())
print(f"MAE 2022-25: Tuesday line {np.mean(np.abs(E.result - E.tue)):.3f} | leaned {np.mean(np.abs(E.result - E.hat)):.3f}")
def cover_p(hat, line_home):          # P(home covers), half-point handled, pushes removed
    thr = -line_home
    up = cdf((np.floor(thr) + .5 - hat) / SD)
    integ = np.abs(thr - np.round(thr)) < 1e-9
    up_i = cdf((thr + .5 - hat) / SD); dn_i = cdf((thr - .5 - hat) / SD)
    return np.where(integ, (1 - up_i) / (1 - (up_i - dn_i)), 1 - up)
E['ph'] = cover_p(E.hat.values, E.sp_h.values)
for thr in (0.0, .02, .04, .06):
    eh = E.ph * dec(E.spo_h.values) - 1; ea = (1 - E.ph) * dec(E.spo_a.values) - 1
    side = np.where(eh >= ea, 'h', 'a'); ev = np.maximum(eh, ea); m = (ev > thr) & (E.result + E.sp_h != 0)
    won = np.where(side == 'h', E.result + E.sp_h > 0, E.result + E.sp_h < 0)[m]; pay = np.where(side == 'h', dec(E.spo_h.values), dec(E.spo_a.values))[m]
    pl = np.where(won, pay - 1, -1.0); clv = np.where(side == 'h', E.spread_line - E.tue, E.tue - E.spread_line)[m]
    print(f"  spread EV>{thr:.0%}: n={m.sum()} cover {won.mean():.3f} ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(m.sum()):.3f} | closing line moved our way {np.mean(clv>0):.2f} vs against {np.mean(clv<0):.2f} | by season {pd.Series(pl).groupby(E.season.values[m]).mean().round(3).to_dict()}")
N = E[E.ml_h.notna() & E.ml_a.notna() & (E.result != 0)].copy()
N['pw'] = 1 - cdf((0 - N.hat) / SD); y = N.result.values > 0
N['pk'] = imp(N.ml_h.values) / (imp(N.ml_h.values) + imp(N.ml_a.values))
br = lambda p: float(np.mean((p - y) ** 2))
print(f"moneyline Brier 2022-25: DK Tuesday no-vig {br(N.pk):.4f} | leaned model {br(N.pw):.4f}")
for thr in (.0, .03, .06):
    eh = N.pw * dec(N.ml_h.values) - 1; ea = (1 - N.pw) * dec(N.ml_a.values) - 1
    side = np.where(eh >= ea, 'h', 'a'); m = np.maximum(eh, ea) > thr
    won = np.where(side == 'h', y, ~y)[m]; pay = np.where(side == 'h', dec(N.ml_h.values), dec(N.ml_a.values))[m]; pl = np.where(won, pay - 1, -1.0)
    print(f"  ML EV>{thr:.0%}: n={m.sum()} win {won.mean():.3f} ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(max(1,m.sum())):.3f} | by season {pd.Series(pl).groupby(N.season.values[m]).mean().round(3).to_dict()}")
x = (M.m - M.tue).values; yv = (M.result - M.tue).values; print('k on all Tuesday data', round(float((x @ yv) / (x @ x)), 3))
