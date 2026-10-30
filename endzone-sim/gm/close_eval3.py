"""Kickoff-time test: bet the game model's side against the CLOSING line (nflverse games.csv consensus close and
its prices), walk-forward 2016-25. This is the price the user actually gets when betting right before the game."""
import numpy as np, pandas as pd, model2, model3
import os
D0 = pd.read_parquet('D.parquet') if os.path.exists('D.parquet') else model2.build(dict(HG=14.0, CARRY=0.85, M0=3.0), dict(QHL=1500.0, QCARRY=0.8, QM0=100.0))
G = pd.read_csv('../../data/games.csv')[['game_id', 'home_spread_odds', 'away_spread_odds', 'home_moneyline', 'away_moneyline']]
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
def run(O, lab):
    E = O.merge(G, on='game_id'); E = E[E.home_spread_odds.notna()].copy(); E['dis'] = E.m - E.spread_line; E['ad'] = E.dis.abs()
    E = E[E.result != E.spread_line]; cov_h = E.result > E.spread_line
    won = np.where(E.dis > 0, cov_h, ~cov_h); pay = np.where(E.dis > 0, dec(E.home_spread_odds.values), dec(E.away_spread_odds.values)); pl = np.where(won, pay - 1, -1.0)
    print(f"{lab}: MAE model {np.mean(np.abs(O.result-O.m)):.3f} vs close {np.mean(np.abs(O.result-O.spread_line)):.3f} | median disagreement {E.ad.median():.1f}")
    for lo, hi in ((0, 1.5), (1.5, 3), (3, 5), (5, 99), (3, 99)):
        m = ((E.ad >= lo) & (E.ad < hi)).values
        by = pd.Series(pl[m]).groupby(E.season.values[m]).mean()
        print(f"   disagree {lo}-{hi if hi < 99 else '+'} pts: n={m.sum():4d} cover {won[m].mean():.3f} ROI {pl[m].mean():+.3f} ± {pl[m].std()/np.sqrt(m.sum()):.3f} | seasons up {int((by>0).sum())}/{len(by)} | 2021-25 ROI {pl[m & (E.season.values>=2021)].mean():+.3f}")
run(model2.walk(D0, 2016, 2025, RHL=8.0), 'OLD')
D = model3.add(D0, dict(HLW=4.0, CARRY=0.5, LAM=1.0)); run(model2.walk(D, 2016, 2025, RHL=8.0, cols=model3.F3), 'NEW')
