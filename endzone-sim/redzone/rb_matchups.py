"""Running back vs run defense matchups for the Redzone Desk.
Run types from play-by-play: inside (middle, guard) vs outside (tackle, end), shotgun vs under center.
Per back: his inside/outside mix and shotgun share, yards after contact per carry (PFR).
Per offensive line: yards per carry by run type. Per defense: yards per carry allowed by run type and by formation,
missed-tackle rate (PFR). All measured from this season to date (1.0) plus last season (0.3), shrunk to the league.
Matchup features for a back (yards per carry vs his own baseline):
  A defense's overall ypc allowed        B the same, split by run type and weighted by HIS inside/outside mix
  C his line's ypc by run type, weighted by his mix
  D his yards after contact x the defense's missed-tackle rate     E his shotgun share x the defense's shotgun/under-center split
Weights are FITTED and only the best-testing set is used (2026-09: B alone; the line term double-counts his own average): back-games with 8+ carries, 2024 and 2025 weeks 4-18, each fitted on one season and scored on the
other (python3 rb_matchups.py test). Live: python3 rb_matchups.py slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import nfl_build as nb
D = nb.D; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
FEATS = ['A', 'B', 'C', 'D', 'E']
clip = lambda x, lo, hi: float(min(hi, max(lo, x)))
_RUNS, _PFR = {}, {}

def runs(s):
    if s not in _RUNS:
        p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'play_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'qb_scramble',
                        'qb_kneel', 'two_point_attempt', 'rusher_player_id', 'rushing_yards', 'run_gap', 'shotgun'], low_memory=False)
        p = p[(p.season_type == 'REG') & (p.play_type == 'run') & (p.qb_scramble.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0) & (p.two_point_attempt.fillna(0) == 0) & p.rusher_player_id.notna()]
        for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
        p['out'] = p.run_gap.isin(['tackle', 'end']).astype(float); p['sg'] = p.shotgun.fillna(0).astype(float); p['y'] = p.rushing_yards.fillna(0)
        _RUNS[s] = p[['game_id', 'season', 'week', 'posteam', 'defteam', 'rusher_player_id', 'out', 'sg', 'y']]
    return _RUNS[s]

def pfr(kind, s):
    if (kind, s) not in _PFR:
        f = f'{D}/advstats_week_{kind}_{s}.csv'
        x = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame()
        if len(x):
            x = x[x.game_type == 'REG']
            for c in ('team', 'opponent'): x[c] = x[c].replace(REP)
        _PFR[(kind, s)] = x
    return _PFR[(kind, s)]

def profiles(s, w):
    """everything measured from season s weeks < w (1.0) and season s-1 (0.3)."""
    r = pd.concat([runs(s - 1).assign(wt=0.3), runs(s)[runs(s).week < w].assign(wt=1.0)])
    r = r.assign(wy=r.wt * r.y)
    lg = {g: float(x.wy.sum() / x.wt.sum()) for g, x in r.groupby('out')}; lg_all = float(r.wy.sum() / r.wt.sum())
    def rate(key, K, by_gap=True):
        out = {}
        grp = r.groupby([key, 'out']) if by_gap else r.groupby(key)
        agg = grp[['wy', 'wt']].sum()
        for idx, row in agg.iterrows():
            base = lg[idx[1]] if by_gap else lg_all
            out[idx] = (row.wy + K * base) / (row.wt + K)
        return out
    dg, og, da = rate('defteam', 60), rate('posteam', 60), rate('defteam', 120, False)
    rb = r.groupby('rusher_player_id').agg(n=('wt', 'sum'), o=('out', lambda x: 0), )
    mix = ((r.wt * r.out).groupby(r.rusher_player_id).sum() + 20 * r.out.mean()) / (r.wt.groupby(r.rusher_player_id).sum() + 20)
    sg = ((r.wt * r.sg).groupby(r.rusher_player_id).sum() + 20 * r.sg.mean()) / (r.wt.groupby(r.rusher_player_id).sum() + 20)
    base = (r.wy.groupby(r.rusher_player_id).sum() + 50 * lg_all) / (r.wt.groupby(r.rusher_player_id).sum() + 50)
    # defense: shotgun minus under-center ypc allowed, relative to the league gap
    lsg = r[r.sg == 1].wy.sum() / r[r.sg == 1].wt.sum() - r[r.sg == 0].wy.sum() / r[r.sg == 0].wt.sum()
    fsplit = {}
    for t, x in r.groupby('defteam'):
        a, b = x[x.sg == 1], x[x.sg == 0]
        fsplit[t] = float(((a.wy.sum() + 40 * lg_all) / (a.wt.sum() + 40) - (b.wy.sum() + 40 * lg_all) / (b.wt.sum() + 40)) - lsg)
    # yards after contact per carry (back) and missed-tackle rate (defense)
    ru = pd.concat([pfr('rush', s - 1).assign(wt=0.3), pfr('rush', s)[pfr('rush', s).week < w].assign(wt=1.0) if len(pfr('rush', s)) else pd.DataFrame()])
    R = nb.rosters(); pfr2g = {v: k for k, v in R['pfr_id'].dropna().items()}
    ru['gid'] = ru.pfr_player_id.map(pfr2g)
    ru = ru.assign(ya=ru.wt * ru.rushing_yards_after_contact.fillna(0), c=ru.wt * ru.carries.fillna(0))
    lya = ru.ya.sum() / ru.c.sum()
    yaco = ((ru.groupby('gid').ya.sum() + 40 * lya) / (ru.groupby('gid').c.sum() + 40)).to_dict()
    de = pd.concat([pfr('def', s - 1).assign(wt=0.3), pfr('def', s)[pfr('def', s).week < w].assign(wt=1.0) if len(pfr('def', s)) else pd.DataFrame()])
    de = de.assign(m=de.wt * de.def_missed_tackles.fillna(0), t=de.wt * (de.def_missed_tackles.fillna(0) + de.def_tackles_combined.fillna(0)))
    lmt = de.m.sum() / de.t.sum()
    mt = ((de.groupby('team').m.sum() + 200 * lmt) / (de.groupby('team').t.sum() + 200)).to_dict()
    return dict(lg=lg, lg_all=lg_all, dg=dg, og=og, da=da, mix=mix.to_dict(), sg=sg.to_dict(), base=base.to_dict(), fsplit=fsplit, yaco=yaco, lya=lya, mt=mt, lmt=lmt)

def feats(P, pid, off, dfn):
    m = P['mix'].get(pid, 0.45); lg = P['lg']
    A = P['da'].get(dfn, P['lg_all']) - P['lg_all']
    B = (1 - m) * (P['dg'].get((dfn, 0.0), lg[0.0]) - lg[0.0]) + m * (P['dg'].get((dfn, 1.0), lg[1.0]) - lg[1.0])
    C = (1 - m) * (P['og'].get((off, 0.0), lg[0.0]) - lg[0.0]) + m * (P['og'].get((off, 1.0), lg[1.0]) - lg[1.0])
    Dx = (P['yaco'].get(pid, P['lya']) - P['lya']) * (P['mt'].get(dfn, P['lmt']) / P['lmt'] - 1) * 10
    E = (P['sg'].get(pid, 0.4) - 0.4) * P['fsplit'].get(dfn, 0.0)
    return dict(A=A, B=B, C=C, D=Dx, E=E)

def dataset(s):
    rows = []
    r = runs(s)
    for w in range(4, 19):
        P = profiles(s, w)
        g = r[r.week == w].groupby(['game_id', 'posteam', 'defteam', 'rusher_player_id']).agg(n=('y', 'size'), y=('y', 'mean')).reset_index()
        g = g[g.n >= 8]
        for x in g.itertuples():
            f = feats(P, x.rusher_player_id, x.posteam, x.defteam)
            rows.append(dict(season=s, week=w, n=x.n, y=x.y - P['base'].get(x.rusher_player_id, P['lg_all']), **f))
    return pd.DataFrame(rows)

def fit(d, cols):
    A = np.column_stack([np.ones(len(d))] + [d[c] for c in cols]); W = d.n.values
    return np.linalg.solve((A * W[:, None]).T @ A + np.diag([0] + [2.0] * len(cols)), (A * W[:, None]).T @ d.y.values)

def test():
    d = pd.concat([dataset(2024), dataset(2025)])
    sets = {'none': [], 'A overall defense': ['A'], 'B run-type defense': ['B'], 'A+B+C line': ['A', 'B', 'C'], 'all (A-E)': FEATS}
    res = {}
    for name, cols in sets.items():
        err = []
        for hold in (2024, 2025):
            tr, te = d[d.season != hold], d[d.season == hold]
            b = fit(tr, cols) if cols else np.array([np.average(tr.y, weights=tr.n)])
            pr = np.column_stack([np.ones(len(te))] + [te[c] for c in cols]) @ b
            err.append(float(np.sqrt(np.average((te.y - pr) ** 2, weights=te.n))))
        res[name] = dict(rmse=[round(e, 4) for e in err], mean=round(float(np.mean(err)), 4))
        print(f'{name:22s} ypc error {np.mean(err):.4f}  {err}')
    best = min((n for n in sets if sets[n]), key=lambda n: res[n]['mean'])          # the matchup version that tested best
    cols = sets[best]; b = fit(d, cols); coef = dict(zip(['c'] + cols, map(float, b)))
    out = dict(test=res, chosen=best, used=cols, coef=coef, n=len(d)); json.dump(out, open(os.path.join(HERE, 'rb_fit.json'), 'w'), indent=1)
    print('chosen', best)
    print('coef', {k: round(v, 3) for k, v in coef.items()}, 'n', len(d))

def live(path, week):
    S = json.load(open(path)); fitj = json.load(open(os.path.join(HERE, 'rb_fit.json'))); c = fitj['coef']
    CFG = json.load(open(os.path.join(HERE, 'config.json'))); W = CFG.get('matchups', {}).get('rb_weight', 1.0)
    P = profiles(2026, week); lg = P['lg']; n_mu = 0
    for g in S['games']:
        g.setdefault('mu', [])
        for side, off, dfn in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            for p in [p for p in g['players'] if p['t'] == off and p['pos'] == 'RB' and p['rush'] >= .15]:
                pid = p.get('id'); f = feats(P, pid, off, dfn)
                d_ypc = W * sum(c[k] * f[k] for k in fitj['used'])
                pct = clip(d_ypc / max(3.0, p['ypc']), -.2, .2)
                p['ypc'] = round(p['ypc'] * (1 + pct), 2)
                m = P['mix'].get(pid, 0.45); ins = 1 - m
                why = [f"Run style: {100 * ins:.0f}% of his carries go inside (middle/guard), {100 * m:.0f}% outside (tackle/end); {100 * P['sg'].get(pid, .4):.0f}% from shotgun"]
                for gname, gk in (('inside', 0.0), ('outside', 1.0)):
                    ol, df_ = P['og'].get((off, gk), lg[gk]), P['dg'].get((dfn, gk), lg[gk])
                    why.append(f"{gname.capitalize()} runs: {off}'s line {ol:.1f} yds/carry, {dfn} allows {df_:.1f} (league {lg[gk]:.1f})")
                ya, mtr = P['yaco'].get(pid, P['lya']), P['mt'].get(dfn, P['lmt'])
                if abs(ya - P['lya']) >= .25 or abs(mtr / P['lmt'] - 1) >= .1:
                    why.append(f"After contact: he gains {ya:.1f} yds per carry after contact (league {P['lya']:.1f}); {dfn} misses {100 * mtr:.0f}% of tackles (league {100 * P['lmt']:.0f}%)")
                fs = P['fsplit'].get(dfn, 0.0)
                if abs(fs) >= .3: why.append(f"Formation: {dfn} is {'weaker' if fs > 0 else 'stronger'} against shotgun runs than under-center runs ({'+' if fs > 0 else ''}{fs:.1f} yds vs the league split)")
                why.append(f"Effect: yards per carry {100 * pct:+.0f}%. Only the defense-vs-run-type part moves the number; it tested best on 2024-25 games (his line and after-contact are already in his own average)")
                edge = 'Edge' if pct >= .08 else 'Slight edge' if pct >= .03 else 'Tough' if pct <= -.08 else 'Slightly tough' if pct <= -.03 else 'Even'
                mu = dict(side=side, off=off, dfn=dfn, n=p['n'], pos='RB', vs=f"{dfn} run defense", role=f"{100 * ins:.0f}% inside / {100 * m:.0f}% outside", edge=edge, score=round(pct, 3), why=why)
                g['mu'].append(mu); p['mu'] = dict(vs=mu['vs'], role=mu['role'], edge=edge, score=mu['score'], why=why[:-1]); n_mu += 1
    json.dump(S, open(path, 'w'))
    print(f'rb matchups: {n_mu}')

if __name__ == '__main__':
    if sys.argv[1] == 'test': test()
    else: live(sys.argv[1], int(sys.argv[2]))
