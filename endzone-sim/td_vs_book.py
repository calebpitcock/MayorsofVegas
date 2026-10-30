"""Anytime-TD model vs DraftKings, 2023-2024, prices ~5 minutes before kickoff (mogden16/NFL-Wizard-Analysis quotes).
Fit everything on 2023, test on 2024 (and report both)."""
import json, re, sys, numpy as np, pandas as pd
Q = pd.read_csv('/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/phase7/stage_a/all_quotes.csv')
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
Q['key'] = Q.player.map(norm)
imp = lambda o: np.where(o < 0, -o / (-o + 100), 100 / (o + 100))
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
Q['imp'] = imp(Q.price.values)
dk = Q[Q.sportsbook == 'draftkings'].groupby(['game', 'key']).agg(dk=('price', 'first')).reset_index()
cons = Q.groupby(['game', 'key']).agg(cons=('imp', 'median'), nbooks=('sportsbook', 'nunique')).reset_index()
cal = json.load(open('td_cal_nfl.json'))
rows = []
for f in sys.argv[1:]:
    R = pd.DataFrame(json.load(open(f))['rows']); rows.append(R)
R = pd.concat(rows)
R['season'] = R.id.str[:4].astype(int)
R['key'] = R.n.map(norm)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
sig = lambda z: 1 / (1 + np.exp(-z))
R['pc'] = sig(cal['slope'] * lg(R.pTD) + R.pos.map(cal).fillna(0))
M = R.merge(dk, left_on=['id', 'key'], right_on=['game', 'key']).merge(cons, on=['game', 'key'], how='left')
M['dkimp'] = imp(M.dk.values); M['dkdec'] = dec(M.dk.values)
print(f"matched {len(M)} player-games with a DraftKings price ({M.season.value_counts().to_dict()}); scored {M.td.mean():.3f}; DK implied avg {M.dkimp.mean():.3f}")
ll = lambda p, y: float(-np.mean(y * np.log(np.clip(p, 1e-4, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-4, 1))))
br = lambda p, y: float(np.mean((p - y) ** 2))
def logit_fit(X, y, l2=1e-3, iters=50):
    X = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X.shape[1])
    for _ in range(iters):
        p = sig(X @ w); g = X.T @ (p - y) + l2 * w; H = (X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w)); w -= np.linalg.solve(H, g)
    return w
tr, te = M[M.season == 2023].copy(), M[M.season == 2024].copy()
# de-vig DraftKings with a logistic fit on 2023 (handles the heavier hold on longshots)
wm = logit_fit(lg(tr.dkimp.values)[:, None], tr.td.values)
for d in (tr, te): d['fair'] = sig(wm[0] + wm[1] * lg(d.dkimp.values))
wc = logit_fit(np.column_stack([lg(tr.dkimp.values), lg(tr.pc.values)]), tr.td.values)
for d in (tr, te): d['comb'] = sig(wc[0] + wc[1] * lg(d.dkimp.values) + wc[2] * lg(d.pc.values))
print(f"DK de-vig fit (2023): logit(fair) = {wm[0]:.3f} + {wm[1]:.3f}·logit(implied)   | combined fit weights: DK {wc[1]:.3f}, model {wc[2]:.3f}")
for name, d in (('2023 (fit season)', tr), ('2024 (out of sample)', te)):
    print(f"{name}: n={len(d)}  Brier  DK fair {br(d.fair,d.td):.5f}  model {br(d.pc,d.td):.5f}  combined {br(d.comb,d.td):.5f} | logloss DK {ll(d.fair,d.td):.5f} model {ll(d.pc,d.td):.5f} combined {ll(d.comb,d.td):.5f}")
# bootstrap: does combining beat DK alone out of sample?
rng = np.random.default_rng(3); diffs = []
idx = np.arange(len(te))
for _ in range(2000):
    s = te.iloc[rng.choice(idx, len(idx))]; diffs.append(ll(s.fair, s.td) - ll(s.comb, s.td))
diffs = np.array(diffs); print(f"2024 combined-vs-DK log-loss gain {diffs.mean():.5f} (95% CI {np.percentile(diffs,2.5):.5f} to {np.percentile(diffs,97.5):.5f}); P(gain>0) {np.mean(diffs>0):.3f}")
def bets(d, p, thr, label, extra=None):
    ev = p * d.dkdec - 1; m = np.array(ev > thr)
    if extra is not None: m &= extra
    pl = np.where(d.td.values[m] == 1, d.dkdec.values[m] - 1, -1.0)
    if m.sum() < 5: return print(f"   {label}: {m.sum()} bets");
    print(f"   {label}: {m.sum():4d} bets, hit {d.td.values[m].mean():.3f}, avg price {np.median(d.dk.values[m]):+.0f}, ROI {pl.mean():+.3f} ± {pl.std()/np.sqrt(len(pl)):.3f}")
for name, d in (('2023', tr), ('2024 out of sample', te)):
    print(f"betting at DraftKings, {name}:")
    for thr in (0, .05, .10, .20):
        bets(d, d.comb, thr, f"combined EV>{thr:.0%}")
    for thr in (.05, .10):
        bets(d, .5 * d.fair + .5 * d.pc, thr, f"50/50 blend EV>{thr:.0%}")
    bets(d, d.pc, .10, "model alone EV>10%")
    pl_all = np.where(d.td == 1, d.dkdec - 1, -1.0); print(f"   every DK anytime TD: ROI {pl_all.mean():+.3f}")
    for lo, hi, lab in ((-1000, -101, 'favorites'), (-100, 250, 'even to +250'), (251, 600, '+251 to +600'), (601, 99999, 'longer than +600')):
        m = (d.dk >= lo) & (d.dk <= hi)
        if m.sum():
            pl = np.where(d.td[m] == 1, d.dkdec[m] - 1, -1.0)
            print(f"     {lab:17s} n={m.sum():4d} hit {d.td[m].mean():.3f} DK fair {d.fair[m].mean():.3f} model {d.pc[m].mean():.3f}  ROI blind {pl.mean():+.3f}")
    for pos in ('RB', 'WR', 'TE', 'QB'):
        m = (d.pos == pos).values; ev = d.comb * d.dkdec - 1
        bets(d, d.comb, .05, f"{pos} combined EV>5%", extra=m)
