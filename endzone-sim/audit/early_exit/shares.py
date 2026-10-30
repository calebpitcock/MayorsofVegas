"""Carry/target share error, EZEXIT=0 tree vs EZEXIT=1 tree, 2023-25 weeks 3-18 (who-played actives, as role_data.py).
Each tree's role_{S}.csv holds its model shares before the role correction; the correction is applied held out
(that tree's role_coef_ex{S}.json), as role_adjust does minus the group cap. Subsets: the player's own games within
2 team-games after a flagged exit ('after exit'), his teammates in those games, and all rows. 95% intervals by
bootstrap over team-games. Usage: shares.py <tree0 endzone-sim> <tree1 endzone-sim>"""
import sys, os, json, numpy as np, pandas as pd
T0, T1 = sys.argv[1], sys.argv[2]; H = os.path.dirname(os.path.abspath(__file__))
F = pd.read_csv(f'{H}/flags.csv')
def fe(D, pred):
    trend = (D.s_last - D.s_prev).fillna(0); gap = D.s_last - D.s_all
    q = (D.status == 'Questionable').astype(float); lim = D.practice.fillna('').str.contains('Limited').astype(float)
    dnp = D.practice.fillna('').str.contains('Did Not').astype(float); back = (1 - D.played_last).astype(float); new = (D.g <= 1).astype(float)
    return np.column_stack([np.ones(len(D)), trend, gap, q, lim, dnp, back, trend * D[pred], q * D[pred], lim * D[pred], back * D[pred], new * D[pred]])
def load(T):
    out = []
    for S in (2023, 2024, 2025):
        D = pd.read_csv(f'{T}/role_{S}.csv'); C = json.load(open(f'{T}/role_coef_ex{S}.json'))
        D['rush_c'] = D.rush; D['rec_c'] = D.rec
        for key, pos in (('rush', ['RB']), ('rec', ['WR', 'TE', 'RB'])):
            for p in pos:
                m = D.pos == p; c = C.get(f'{key}_{p}')
                if c is None or not m.any(): continue
                D.loc[m, f'{key}_c'] = np.maximum(.004, D.loc[m, key] + fe(D[m], key) @ np.array(c))
        out.append(D)
    return pd.concat(out)
A, B = load(T0), load(T1)
k = ['season', 'game_id', 'team', 'pid']
M = A.merge(B, on=k, suffixes=('0', '1'))
M['week'] = M.week0; M['n'] = M.n0; M['pos'] = M.pos0; M['ar'] = M.ar0; M['at'] = M.at0
# team-game index to find "within 2 team games after an exit"
tg = M[['season', 'team', 'week']].drop_duplicates().sort_values(['season', 'team', 'week'])
tg['gi'] = tg.groupby(['season', 'team']).cumcount(); M = M.merge(tg, on=['season', 'team', 'week'])
Fx = F.merge(tg, on=['season', 'team', 'week'], how='left')
# exits in week 1-2 are not in tg (role rows start week 3); give them a game index by week order
Fx['gi'] = Fx.gi.fillna(Fx.week - 3)
after, mates = set(), set()
for r in Fx.itertuples():
    for d in (1, 2):
        after.add((r.season, r.team, r.n, r.gi + d)); mates.add((r.season, r.team, r.gi + d))
M['after'] = [(s, t, n, g) in after for s, t, n, g in zip(M.season, M.team, M.n, M.gi)]
M['after'] = M.after.astype(bool); M['mate'] = np.array([(s, t, g) in mates for s, t, g in zip(M.season, M.team, M.gi)]) & ~M.after
def boot(d, col0, col1, act):
    e0 = (d[col0] - d[act]) ** 2; e1 = (d[col1] - d[act]) ** 2; g = d.game_id + d.team
    by = pd.DataFrame({'g': g, 'e0': e0, 'e1': e1}).groupby('g').sum(); n = d.groupby(g).size().reindex(by.index)
    rng = np.random.default_rng(1); idx = np.arange(len(by)); diffs = []
    for _ in range(1000):
        s = rng.choice(idx, len(idx)); diffs.append((by.e1.values[s].sum() - by.e0.values[s].sum()) / n.values[s].sum())
    return e0.mean(), e1.mean(), np.percentile(diffs, 2.5), np.percentile(diffs, 97.5)
print(f'rows {len(M)}; after-exit player rows {M.after.sum()}; teammate rows {M.mate.sum()}')
print('MSE x1000 (EZEXIT=0 -> EZEXIT=1), change with 95% interval; negative = better')
for lab, sel in (('after exit', M.after), ('teammates', M.mate), ('all', M.after | ~M.after)):
    for stage, c in (('raw', ''), ('role-corrected', '_c')):
        for mk, pos, act in (('rush', ['RB'], 'ar'), ('rec', ['WR', 'TE', 'RB'], 'at')):
            d = M[sel & M.pos.isin(pos)]
            if len(d) < 20: continue
            e0, e1, lo, hi = boot(d, mk + c + '0', mk + c + '1', act)
            print(f'  {lab:10s} {stage:15s} {"RB carries" if mk == "rush" else "targets":10s} n={len(d):5d}  {1000*e0:.3f} -> {1000*e1:.3f}  ({1000*(e1-e0):+.3f}, 95% {1000*lo:+.3f} to {1000*hi:+.3f})')
