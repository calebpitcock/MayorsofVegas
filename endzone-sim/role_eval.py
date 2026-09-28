import numpy as np, pandas as pd
R = pd.concat([pd.read_csv(f'role_{s}.csv') for s in (2023, 2024, 2025)])
R['trend'] = (R.s_last - R.s_prev).fillna(0); R['gap'] = R.s_last - R.s_all
R['q'] = (R.status == 'Questionable').astype(float); R['dq'] = R.status.isin(['Doubtful']).astype(float)
R['lim'] = R.practice.str.contains('Limited', na=False).astype(float); R['dnp'] = R.practice.str.contains('Did Not', na=False).astype(float)
R['back'] = (1 - R.played_last).astype(float)          # missed last game, active now
R['new'] = (R.g <= 1).astype(float)
def study(sel, pred, act, label):
    D = R[sel].copy(); D['res'] = D[act] - D[pred]
    FE = {'trend': D.trend * D[pred].clip(.02) * 0 + D.trend, 'gap': D.gap, 'q': D.q, 'lim': D.lim, 'dnp': D.dnp, 'back': D.back,
          'trend_x': D.trend * D[pred], 'q_x': D.q * D[pred], 'lim_x': D.lim * D[pred], 'back_x': D.back * D[pred], 'new_x': D.new * D[pred]}
    X = pd.DataFrame(FE)
    base = np.mean(D.res ** 2); out = {}
    tot_b, tot_n = 0, 0
    for s in (2023, 2024, 2025):
        tr, te = D.season != s, D.season == s
        A = np.column_stack([np.ones(tr.sum()), X[tr].values]); w = np.linalg.lstsq(A, D.res[tr].values, rcond=None)[0]
        p = np.column_stack([np.ones(te.sum()), X[te].values]) @ w
        out[s] = (np.mean(D.res[te] ** 2), np.mean((D.res[te] - p) ** 2))
    A = np.column_stack([np.ones(len(D)), X.values]); w = np.linalg.lstsq(A, D.res.values, rcond=None)[0]
    print(f"{label}: n={len(D)} bias {D.res.mean():+.4f} | held-out MSE base vs +roles: " + ", ".join(f"{s} {a:.5f}->{b:.5f} ({100*(a-b)/a:+.1f}%)" for s, (a, b) in out.items()))
    print('   coefs', dict(zip(['c'] + list(FE), np.round(w, 4))))
study(R.pos == 'RB', 'rush', 'ar', 'RB carries')
study(R.pos.isin(['WR', 'TE', 'RB']), 'rec', 'at', 'targets (all)')
for p in ('WR', 'TE', 'RB'): study(R.pos == p, 'rec', 'at', f'targets {p}')
print('status counts', R.status.value_counts().to_dict())
for st in ('Questionable', 'Doubtful', ''):
    for pos, pr, ac in (('RB', 'rush', 'ar'), ('WR', 'rec', 'at'), ('TE', 'rec', 'at')):
        D = R[(R.status == st) & (R.pos == pos) & (R[pr] > .08)]
        if len(D) > 20: print(f'  {st or "no status":12s} {pos}: n={len(D)} actual/pred {D[ac].sum()/D[pr].sum():.3f}')
for pr_ in ('Did Not', 'Limited', 'Full'):
    for pos, pr, ac in (('RB', 'rush', 'ar'), ('WR', 'rec', 'at')):
        D = R[R.practice.str.contains(pr_, na=False) & (R.pos == pos) & (R[pr] > .08)]
        if len(D) > 20: print(f'  practice {pr_:8s} {pos}: n={len(D)} actual/pred {D[ac].sum()/D[pr].sum():.3f}')
