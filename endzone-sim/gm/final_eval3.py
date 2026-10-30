"""Honest test of game model v2 on 2022-2025 against DraftKings' Tuesday lines, same protocol as final_eval.py:
walk-forward margins; the lean weight k is fitted only on earlier seasons; bets at DraftKings' Tuesday prices.
Old model (model2) side by side."""
import numpy as np, pandas as pd, model2, model3
from math import erf
import os
D0 = pd.read_parquet('D.parquet') if os.path.exists('D.parquet') else model2.build(dict(HG=14.0, CARRY=0.85, M0=3.0), dict(QHL=1500.0, QCARRY=0.8, QM0=100.0))
T = pd.read_parquet('tue_dk.parquet'); sig = lambda z: 1 / (1 + np.exp(-z)); lg = lambda p: np.log(p / (1 - p))
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o); imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0))
B, SL = 0.1439, 0.0436
def run(O, lab):
    M = O.merge(T, left_on=['season', 'home_team', 'away_team'], right_on=['season', 'home', 'away']); M['tue'] = -M.sp_h; M = M[M.tue.notna()].copy()
    rows = []
    for S in (2022, 2023, 2024, 2025):
        tr, te = M[M.season < S], M[M.season == S].copy(); x = (tr.m - tr.tue).values; y = (tr.result - tr.tue).values
        te['k'] = float(np.clip((x @ y) / (x @ x), 0, 1)); rows.append(te)
    E = pd.concat(rows); E['edge'] = E.k * (E.m - E.tue)
    mv = np.sign(E.spread_line - E.tue); side = np.sign(E.m - E.tue)
    out = f"{lab}: k by season {E.groupby('season').k.first().round(3).to_dict()} | MAE Tue {np.mean(np.abs(E.result-E.tue)):.3f} leaned {np.mean(np.abs(E.result-E.tue-E.edge)):.3f} | line moved our way {np.mean(mv==side):.2f} against {np.mean(mv==-side):.2f}"
    print(out)
    # spread: DK no-vig cover + slope*edge (page's method)
    ok = E.spo_h.notna() & (E.result + E.sp_h != 0)
    F = E[ok]; ps = imp(F.spo_h.values) / (imp(F.spo_h.values) + imp(F.spo_a.values)) + SL * F.edge
    for thr in (0.0, .02, .04):
        eh = ps * dec(F.spo_h.values) - 1; ea = (1 - ps) * dec(F.spo_a.values) - 1; s = np.where(eh >= ea, 'h', 'a'); m = np.maximum(eh, ea) > thr
        won = np.where(s == 'h', F.result + F.sp_h > 0, F.result + F.sp_h < 0)[m]; pay = np.where(s == 'h', dec(F.spo_h.values), dec(F.spo_a.values))[m]; pl = np.where(won, pay - 1, -1.0)
        print(f"   spread EV>{thr:.0%}: n={m.sum()} cover {won.mean():.3f} ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(max(1,m.sum())):.3f} by season {pd.Series(pl).groupby(F.season.values[m]).mean().round(3).to_dict()}")
    N = E[E.ml_h.notna() & E.ml_a.notna() & (E.result != 0)]; y = N.result.values > 0
    pk = imp(N.ml_h.values) / (imp(N.ml_h.values) + imp(N.ml_a.values)); pw = sig(lg(pk) + B * N.edge.values)
    br = lambda p: float(np.mean((p - y) ** 2))
    o = f"   moneyline Brier DK {br(pk):.4f} anchored {br(pw):.4f}"
    for thr in (0.0, .03):
        eh = pw * dec(N.ml_h.values) - 1; ea = (1 - pw) * dec(N.ml_a.values) - 1; s = np.where(eh >= ea, 'h', 'a'); m = np.maximum(eh, ea) > thr
        won = np.where(s == 'h', y, ~y)[m]; pay = np.where(s == 'h', dec(N.ml_h.values), dec(N.ml_a.values))[m]; pl = np.where(won, pay - 1, -1.0)
        o += f" | ML EV>{thr:.0%} n={m.sum()} ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(max(1,m.sum())):.3f}"
    print(o)
run(model2.walk(D0, 2016, 2025, RHL=8.0), 'OLD')
D = model3.add(D0, dict(HLW=4.0, CARRY=0.5, LAM=1.0)); run(model2.walk(D, 2016, 2025, RHL=8.0, cols=model3.F3), 'NEW')
