import pandas as pd, numpy as np
G = pd.read_csv('games.csv'); G = G[G.result.notna() & G.spread_line.notna()].copy()
rep = {'OAK':'LV','SD':'LAC','STL':'LA'}
for c in ('home_team','away_team'): G[c] = G[c].replace(rep)
G = G.sort_values(['gameday','game_id']).reset_index(drop=True)
G['ats'] = G.result - G.spread_line          # home margin vs the closing line (+ = home covered by that much)
G['pair'] = [tuple(sorted(x)) for x in zip(G.home_team, G.away_team)]
G['cpair'] = [tuple(sorted(x)) for x in zip(G.home_coach, G.away_coach)]
def prior_feats(key):
    last_ats, mean3, n_prev, same_season = [], [], [], []
    hist = {}
    for r in G.itertuples():
        k = getattr(r, key); h = hist.get(k, [])
        # express prior results from THIS game's home team's point of view
        vals = [(a if ht == r.home_team else -a) if key == 'pair' else (a if hc == r.home_coach else -a) for (a, ht, hc, s) in h]
        last_ats.append(vals[-1] if vals else np.nan); mean3.append(np.mean(vals[-3:]) if vals else np.nan); n_prev.append(len(vals))
        same_season.append(bool(h) and h[-1][3] == r.season)
        hist.setdefault(k, []).append((r.ats, r.home_team, r.home_coach, r.season))
    return np.array(last_ats), np.array(mean3), np.array(n_prev), np.array(same_season)
def report(name, x, y, mask):
    x, y = x[mask], y[mask]; n = len(x)
    b = np.polyfit(x, y, 1)[0]; r = np.corrcoef(x, y)[0, 1]; se = 1 / np.sqrt(n - 3)
    # betting rule: back the side that covered last time
    side = np.sign(x); won = np.sign(y) == side; ok = (y != 0) & (side != 0)
    print(f"{name:52s} n={n:5d}  corr={r:+.3f} (95% ±{1.96*se:.3f})  slope={b:+.3f}  'back the prior winner' covers {won[ok].mean():.3f}")
for key, label in (('pair', 'team vs team'), ('cpair', 'head coach vs head coach')):
    la, m3, npv, ss = prior_feats(key); y = G.ats.values; base = np.isfinite(la)
    print(f"--- {label}: does past ATS result in this matchup predict this game's ATS result? (1999-2025)")
    report('last meeting ATS margin', la, y, base)
    report('mean of last 3 meetings ATS margin', m3, y, base & (npv >= 3))
    report('last meeting, same season (division rematch)', la, y, base & ss)
    report('last meeting, 2015+', la, y, base & (G.season.values >= 2015))
# straight-up version: does last meeting's raw margin predict this game's margin BEYOND the spread?
la, _, _, _ = prior_feats('pair')
m = np.isfinite(la)
X = np.c_[np.ones(m.sum()), G.spread_line.values[m], la[m]]
w, *_ = np.linalg.lstsq(X, G.result.values[m], rcond=None)
print(f"\nresult ~ spread + last-meeting ATS: spread coef {w[1]:.3f}, last-meeting coef {w[2]:+.4f}")
