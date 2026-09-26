"""Out-of-sample check on this season: model (pregame-mode backtest, 2026 weeks 1-2) vs DraftKings anytime-TD quotes
(Week 1 ~1 hour before kickoff, Week 2 captured Thursday afternoon). Uses the blend fitted on 2023-24."""
import json, re, glob, numpy as np, pandas as pd, props_hist
R = pd.DataFrame(json.load(open('bt_2026_1_2_pre_draftkings_dk_rows.json'))['rows'])
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
ev = pd.concat([pd.read_csv(f, usecols=['Event ID', 'Home', 'Away', 'Week']) for f in glob.glob('../data/snap26/*.csv')]).drop_duplicates('Event ID')
ev['gid'] = ev.apply(lambda r: f"2026_{int(r.Week):02d}_{props_hist.ABBR[r.Away]}_{props_hist.ABBR[r.Home]}", axis=1)
E = dict(zip(ev['Event ID'], ev.gid))
base = '/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/'
a = pd.read_csv(base + 'phase45_stage_a_all_quotes.csv').rename(columns={'american_odds': 'price'})
b = pd.read_csv(base + 'atd_price_quotes_2026-09-17.csv')
Q = pd.concat([a[['event_id', 'player', 'sportsbook', 'price']], b[['event_id', 'player', 'sportsbook', 'price']]])
Q = Q[Q.sportsbook == 'draftkings'].drop_duplicates(['event_id', 'player'])
Q['gid'] = Q.event_id.map(E); print('DK quotes', len(Q), 'unmapped events', Q.gid.isna().sum())
Q['key'] = Q.player.map(norm); R['key'] = R.n.map(norm)
cal = json.load(open('td_cal_nfl.json')); fit = json.load(open('td_dk_fit.json'))
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))); sig = lambda z: 1 / (1 + np.exp(-z))
R['pc'] = sig(cal['slope'] * lg(R.pTD) + R.pos.map(cal).fillna(0))
M = R.merge(Q, left_on=['id', 'key'], right_on=['gid', 'key'])
M['imp'] = np.where(M.price < 0, -M.price / (-M.price + 100), 100 / (M.price + 100)); M['dec'] = np.where(M.price > 0, 1 + M.price / 100, 1 + 100 / -M.price)
M['dkfair'] = sig(fit['dva'] + fit['dvb'] * lg(M.imp))
w1 = json.load(open('td_dk_fit.json'))
M['comb'] = sig(fit['a'] + fit['bk'] * lg(M.imp) + fit['bm'] * lg(M.pc))
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
print(f"matched {len(M)} (week {M.week.value_counts().to_dict()}), scored {M.td.mean():.3f}, DK implied {M.imp.mean():.3f}, model {M.pc.mean():.3f}")
print(f"log loss: DK de-vigged {ll(M.dkfair,M.td):.4f}  model {ll(M.pc,M.td):.4f}  combined {ll(M.comb,M.td):.4f}")
from numpy.polynomial import polynomial
def fitlr(X, y):
    X = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X.shape[1])
    for _ in range(40):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + 1e-3 * np.eye(len(w)), X.T @ (p - y) + 1e-3 * w)
    return w
print('refit on 2026 alone (DK, model):', fitlr(np.column_stack([lg(M.imp), lg(M.pc)]), M.td.values).round(3))
for thr in (0, .05):
    m = (M.comb * M.dec - 1 > thr).values; pl = np.where(M.td[m] == 1, M.dec[m] - 1, -1.0)
    print(f"combined EV>{thr:.0%}: {m.sum()} bets, ROI {pl.mean() if m.sum() else 0:+.3f} ± {pl.std()/np.sqrt(max(1,m.sum())):.3f}")
pl = np.where(M.td == 1, M.dec - 1, -1.0); print(f"every DK TD: ROI {pl.mean():+.3f}")
