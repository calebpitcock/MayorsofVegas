"""History of the page's single 'line doesn't match the teams' flag. The combined fair line is
    BOOKS_W * ratings (books + stats + QB) + (1 - BOOKS_W) * stats view (stats + QB, no books)
with each home team's own home-field edge (HFA_SHARE of its shrunk historical edge, capped). Walk-forward 2016-25:
each season predicted from earlier seasons only; graded against closing spreads at closing prices. The blend and
threshold were chosen on 2016-20 (blend_select.py); 2021-25 is reported separately. Public opinion (10% on the page)
has no history, so it isn't in this record. Writes flag_record.json."""
import json, os, numpy as np, pandas as pd, model2, model4, market
BOOKS_W, FLAG_AT, HFA_SHARE, HFA_CAP = 0.25, 4.0, 0.5, 1.0
D = model4.add(pd.read_parquet('D.parquet') if os.path.exists('D.parquet') else model2.build(dict(HG=14.0, CARRY=0.85, M0=3.0), dict(QHL=1500.0, QCARRY=0.8, QM0=100.0)))
R = model2.walk(D, 2016, 2025, RHL=8.0, cols=model4.F4)[['game_id', 'season', 'home_team', 'neutral', 'result', 'spread_line', 'm']]
S = model2.walk(D, 2016, 2025, RHL=8.0, cols=[c for c in model4.F4 if c != 'mkt'])[['game_id', 'm']].rename(columns={'m': 'ms'})
G = pd.read_csv('../../data/games.csv')[['game_id', 'home_spread_odds', 'away_spread_odds', 'home_moneyline', 'away_moneyline']]
E = R.merge(S, on='game_id').merge(G, on='game_id').dropna(subset=['home_spread_odds', 'home_moneyline'])
Gm = market.load_games(); he = model4.home_edges(Gm[Gm.result.notna()])
E['hfa'] = [0.0 if n else float(np.clip(HFA_SHARE * he.get((s, h), 0.0), -HFA_CAP, HFA_CAP)) for s, h, n in zip(E.season, E.home_team, E.neutral)]
E['fair'] = BOOKS_W * E.m + (1 - BOOKS_W) * E.ms + E.hfa; E['gap'] = E.fair - E.spread_line; E['a'] = E.gap.abs()
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
def rec(d):
    sp = d[d.result != d.spread_line]; h = sp.gap > 0
    cov = np.where(h, sp.result > sp.spread_line, sp.result < sp.spread_line); pl = np.where(cov, np.where(h, dec(sp.home_spread_odds.values), dec(sp.away_spread_odds.values)) - 1, -1.0)
    ml = d[d.result != 0]; hm = ml.gap > 0; win = np.where(hm, ml.result > 0, ml.result < 0); mpl = np.where(win, np.where(hm, dec(ml.home_moneyline.values), dec(ml.away_moneyline.values)) - 1, -1.0)
    by = pd.Series(pl).groupby(sp.season.values).mean()
    return dict(n=int(len(sp)), cover=round(float(cov.mean()), 3), spreadROI=round(float(pl.mean()), 3), spreadSE=round(float(pl.std() / np.sqrt(len(pl))), 3),
                mlROI=round(float(mpl.mean()), 3), seasonsUp=int((by > 0).sum()), seasons=int(len(by)), perSeason=round(len(sp) / max(1, len(by)), 1))
out = dict(since=2016, until=2025, booksWeight=BOOKS_W, flagAt=FLAG_AT, hfaShare=HFA_SHARE, byGap={})
for lo in (3, 4, 5, 6):
    out['byGap'][str(lo)] = dict(all=rec(E[E.a >= lo]), heldOut=rec(E[(E.a >= lo) & (E.season >= 2021)]))
    print(lo, out['byGap'][str(lo)])
print('MAE combined', round(float(np.mean(np.abs(E.result - E.fair))), 3), 'close', round(float(np.mean(np.abs(E.result - E.spread_line))), 3))
json.dump(out, open('flag_record.json', 'w'))
