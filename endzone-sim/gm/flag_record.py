"""History of the page's 'line doesn't add up' flags: walk-forward game model (2016-25, each season predicted from
earlier seasons only) vs the closing line, bucketed by how far the line sits from the ratings' fair line. Spread bets
graded at the closing spread prices; moneylines at the closing moneylines. Writes flag_record.json for the page."""
import json, numpy as np, pandas as pd, model2, model3
D = model3.add(pd.read_parquet('D.parquet'), model3.MP); O = model2.walk(D, 2016, 2025, RHL=8.0, cols=model3.F3)
G = pd.read_csv('../../data/games.csv')[['game_id', 'home_spread_odds', 'away_spread_odds']]
E = O.merge(G, on='game_id').dropna(subset=['home_spread_odds', 'home_moneyline']); E['gap'] = E.m - E.spread_line; E['a'] = E.gap.abs()
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
h = E.gap > 0
sp = E[E.result != E.spread_line]; hs = sp.gap > 0
cov = np.where(hs, sp.result > sp.spread_line, sp.result < sp.spread_line); spl = np.where(cov, np.where(hs, dec(sp.home_spread_odds.values), dec(sp.away_spread_odds.values)) - 1, -1.0)
ml = E[E.result != 0]; hm = ml.gap > 0
win = np.where(hm, ml.result > 0, ml.result < 0); mpl = np.where(win, np.where(hm, dec(ml.home_moneyline.values), dec(ml.away_moneyline.values)) - 1, -1.0)
rec = {}
print(f"{len(E)} games 2016-25; MAE model {np.mean(np.abs(O.result-O.m)):.3f} close {np.mean(np.abs(O.result-O.spread_line)):.3f}")
for lo in (2, 3, 4, 5, 6):
    k = (sp.a >= lo).values; j = (ml.a >= lo).values
    r = dict(n=int(k.sum()), cover=round(float(cov[k].mean()), 3), spreadROI=round(float(spl[k].mean()), 3), spreadSE=round(float(spl[k].std() / np.sqrt(k.sum())), 3),
             mlN=int(j.sum()), mlWin=round(float(win[j].mean()), 3), mlROI=round(float(mpl[j].mean()), 3), mlSE=round(float(mpl[j].std() / np.sqrt(j.sum())), 3),
             seasonsUp=int((pd.Series(spl[k]).groupby(sp.season.values[k]).mean() > 0).sum()), perSeason=round(k.sum() / 10, 1))
    rec[str(lo)] = r; print(lo, r)
json.dump(dict(since=2016, until=2025, byGap=rec), open('flag_record.json', 'w'))
