"""One combined fair line: fair = a * ratings (books+stats+QB) + (1-a) * stats-only (stats+QB). Choose the blend a and the
flag threshold on 2016-20 only, then report 2021-25 untouched. Graded vs closing spreads at closing prices."""
import numpy as np, pandas as pd, model2, model4
D = model4.add(pd.read_parquet('D.parquet'))
R = model2.walk(D, 2016, 2025, RHL=8.0, cols=model4.F4)[['game_id', 'season', 'result', 'spread_line', 'm']]
S = model2.walk(D, 2016, 2025, RHL=8.0, cols=[c for c in model4.F4 if c != 'mkt'])[['game_id', 'm']].rename(columns={'m': 'ms'})
G = pd.read_csv('../../data/games.csv')[['game_id', 'home_spread_odds', 'away_spread_odds']]
E = R.merge(S, on='game_id').merge(G, on='game_id').dropna(subset=['home_spread_odds']); E = E[E.result != E.spread_line]
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
def rec(d, a, t):
    gap = a * d.m + (1 - a) * d.ms - d.spread_line; k = (gap.abs() >= t).values
    won = np.where(gap > 0, d.result > d.spread_line, d.result < d.spread_line)[k]
    pay = np.where(gap > 0, dec(d.home_spread_odds.values), dec(d.away_spread_odds.values))[k]; pl = np.where(won, pay - 1, -1)
    return k.sum(), (won.mean() if k.sum() else np.nan), (pl.mean() if k.sum() else np.nan), (pl.std() / np.sqrt(max(1, k.sum())))
tr, te = E[E.season <= 2020], E[E.season >= 2021]
print("fit years 2016-20 (cover rate / games), flag thresholds 3-6:")
grid = []
for a in (0, .25, .5, .75, 1):
    row = [rec(tr, a, t) for t in (3, 4, 5, 6)]
    print(f"  a={a:.2f} " + " | ".join(f"{t}+: {r[1]:.3f} ({r[0]})" for t, r in zip((3, 4, 5, 6), row)))
    for t, r in zip((3, 4, 5, 6), row):
        if r[0] >= 60: grid.append((r[2], a, t))      # need at least ~12 flags a season to pick it
best = max(grid); print('chosen on 2016-20: a =', best[1], 'threshold', best[2], f"(ROI {best[0]:+.3f})")
for a, t in ((best[1], best[2]), (0, 5), (1, 3), (.5, 4)):
    n, c, r, se = rec(te, a, t); n2, c2, r2, se2 = rec(E, a, t)
    print(f"  2021-25 check a={a} t={t}: n={n} covered {c:.3f} ROI {r:+.3f}±{se:.3f}   | all 2016-25 n={n2} {c2:.3f}")
