"""Do nflfastR's expected-pass and expected-YAC stats, end-zone targets or inside-5 carries add information the model
doesn't have? Every stat is computed from games before kickoff (this season to date + last season at weight .3).
TD: held-out log loss of td ~ model (+ stat), leave-one-season-out 2023/2024/2025, and td ~ DK + model (+ stat) on
2023-24 kickoff DK prices (fit one season, test the other). Bootstrap over games for the 90% interval.
Yards: receiving-yard residual (actual - model) on prior YAC over expected. Pass rate: game dropback rate on prior
neutral pass rate vs prior pass-over-expected, with the spread and total as controls."""
import json, re, numpy as np, pandas as pd
V = '/home/user/work/v34'; D = '/home/user/MayorsofVegas/data'
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4))); sig = lambda z: 1 / (1 + np.exp(-z))
ll = lambda p, y: -(y * np.log(np.clip(p, 1e-6, 1)) + (1 - y) * np.log(np.clip(1 - p, 1e-6, 1)))
PW = 0.3
PG = pd.read_parquet('player_games.parquet'); TG = pd.read_parquet('team_games.parquet')
# team totals per game for shares
tt = PG.groupby(['game_id', 'posteam'])[['tgt', 'ez', 'car', 'i5', 'i10', 'rzt']].sum().add_prefix('t_').reset_index()
PG = PG.merge(tt, on=['game_id', 'posteam'])
def prior(df, S, w):
    x = df[((df.season == S) & (df.week < w)) | (df.season == S - 1)]
    return x.assign(wt=np.where(x.season == S, 1.0, PW))
cache = {}
def feats(S, w):
    if (S, w) in cache: return cache[(S, w)]
    x = prior(PG, S, w); c = ['tgt', 'ez', 'car', 'i5', 'i10', 'rzt', 'rec', 'yac', 'xyac', 'nyac', 't_tgt', 't_ez', 't_car', 't_i5', 't_i10', 't_rzt', 'ctd', 'rtd']
    # team-specific shares (player's current team = team of his latest game)
    last = x.sort_values(['season', 'week']).groupby('pid').posteam.last()
    xs = x[x.posteam == x.pid.map(last)]
    g = xs[c].mul(xs.wt, axis=0).assign(pid=xs.pid).groupby('pid').sum()
    y = x[['yac', 'xyac', 'nyac']].mul(x.wt, axis=0).assign(pid=x.pid).groupby('pid').sum()   # YAC over expected follows the player
    ts = g.tgt / g.t_tgt.clip(lower=1); cs = g.car / g.t_car.clip(lower=1)
    f = pd.DataFrame(index=g.index)
    # end-zone target share relative to overall target share, shrunk to 1 with 6 team end-zone targets
    f['ez_rel'] = np.log(((g.ez + 6 * ts) / (g.t_ez + 6)).clip(lower=1e-3) / ts.clip(lower=1e-3))
    f['i5_rel'] = np.log(((g.i5 + 6 * cs) / (g.t_i5 + 6)).clip(lower=1e-3) / cs.clip(lower=1e-3))
    f['ez_sh'] = (g.ez + 6 * ts) / (g.t_ez + 6); f['i5_sh'] = (g.i5 + 6 * cs) / (g.t_i5 + 6)
    f['yacoe'] = ((y.yac - y.xyac) / (y.nyac + 30)).reindex(g.index).fillna(0)
    t = prior(TG, S, w); tg = t.assign(a=t.wt * (t.ndb - t.nx), b=t.wt * t.nn, c=t.wt * t.ndb).groupby('posteam')[['a', 'b', 'c']].sum()
    team = pd.DataFrame(dict(proe=tg.a / (tg.b + 150), npr=tg.c / (tg.b + 1e-9)))
    cache[(S, w)] = (f, team); return f, team
def rows(fn):
    r = pd.DataFrame(json.load(open(f'{V}/{fn}'))['rows']); r['season'] = r.id.str[:4].astype(int); return r
R = pd.concat([rows('bt_2023_3_18_rex2023_dk_rows.json'), rows('bt_2024_3_18_rex2024_dk_rows.json'), rows('bt_2025_1_18_pre_draftkings_rex2025_dk_rows.json')])
R = R[R.week >= 3]
ro = pd.concat([pd.read_csv(f'{D}/roster_{y}.csv', usecols=['season', 'team', 'full_name', 'gsis_id'], low_memory=False) for y in (2023, 2024, 2025)])
ro['team'] = ro.team.replace({'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'})
ro = ro.drop_duplicates(['season', 'team', 'full_name'])
R = R.merge(ro, left_on=['season', 't', 'n'], right_on=['season', 'team', 'full_name'], how='left')
print('rows', len(R), 'matched to ids', R.gsis_id.notna().mean().round(3))
R = R[R.gsis_id.notna()]
F = []
for (S, w), grp in R.groupby(['season', 'week']):
    f, team = feats(S, w)
    F.append(grp.join(f, on='gsis_id').join(team, on='t'))
R = pd.concat(F).fillna({'ez_rel': 0, 'i5_rel': 0, 'ez_sh': 0, 'i5_sh': 0, 'yacoe': 0, 'proe': 0})
R['recv'] = R.pos.isin(['WR', 'TE']).astype(float); R['rb'] = (R.pos == 'RB').astype(float); R['qb'] = (R.pos == 'QB').astype(float)
R['proe_recv'] = R.proe * R.recv; R['proe_rb'] = R.proe * R.rb
R['ez_rel_r'] = R.ez_rel * (R.pos != 'QB'); R['i5_rel_r'] = R.i5_rel * R.rb
R['lm'] = lg(R.pTD)
def fitlr(X, y, l2=1.0):
    X = np.column_stack([np.ones(len(X)), X]); w = np.zeros(X.shape[1])
    for _ in range(60):
        p = sig(X @ w); w -= np.linalg.solve((X * (p * (1 - p))[:, None]).T @ X + l2 * np.eye(len(w)), X.T @ (p - y) + l2 * w)
    return w
pred = lambda w, X: sig(np.column_stack([np.ones(len(X)), X]) @ w)
def boot(d, gid, n=1000):
    rng = np.random.default_rng(7); u = pd.unique(gid); idx = {g: np.where(gid == g)[0] for g in u}; out = []
    for _ in range(n):
        s = np.concatenate([idx[g] for g in rng.choice(u, len(u))]); out.append(d[s].mean())
    return np.percentile(out, [5, 95])
base = ['lm', 'qb', 'rb', 'recv']
tests = {'end-zone target share (vs overall share)': ['ez_rel_r'], 'inside-5 carry share (vs overall share)': ['i5_rel_r'],
         'both end-zone + inside-5': ['ez_rel_r', 'i5_rel_r'], 'end-zone & inside-5 raw shares': ['ez_sh', 'i5_sh'],
         'YAC over expected (xYAC)': ['yacoe'], 'team pass rate over expected (xpass) by position': ['proe_recv', 'proe_rb']}
print('\n== anytime TD: added to the model (held out by season 2023/2024/2025, weeks 3+); + = better, log loss x1000')
for name, fs in tests.items():
    d = np.zeros(len(R)); coefs = []
    for S in (2023, 2024, 2025):
        tr, te = R.season != S, (R.season == S).values
        w0 = fitlr(R.loc[tr, base].values, R.td[tr].values); w1 = fitlr(R.loc[tr, base + fs].values, R.td[tr].values); coefs.append(np.round(w1[-len(fs):], 3))
        d[te] = ll(pred(w0, R.loc[te, base].values), R.td[te].values) - ll(pred(w1, R.loc[te, base + fs].values), R.td[te].values)
    lo, hi = boot(d, R.id.values)
    print(f"  {name:48s} {1000*d.mean():+.3f}  (90% {1000*lo:+.3f} to {1000*hi:+.3f})  coefs {coefs[0]}")
# vs DraftKings kickoff prices
norm = lambda n: re.sub(r"[^a-z]", "", re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", str(n).lower()))
imp = lambda o: np.where(o < 0, -o / (-o + 100.0), 100 / (o + 100.0))
Q = pd.read_csv('/home/user/ext/mogden16_NFL-Wizard-Analysis/reports/phase7/stage_a/all_quotes.csv')
Q = Q[Q.sportsbook == 'draftkings'].copy(); Q['key'] = Q.player.map(norm); Q = Q.drop_duplicates(['game', 'key'])
R['key'] = R.n.map(norm); M = R[R.season < 2025].merge(Q[['game', 'key', 'price']], left_on=['id', 'key'], right_on=['game', 'key'])
M['lk'] = lg(imp(M.price.values)); print(f'\n== anytime TD vs DraftKings kickoff price ({len(M)} quotes 2023-24, fit one season, test the other)')
b2 = ['lk', 'lm']
for name, fs in tests.items():
    d = np.zeros(len(M))
    for S in (2023, 2024):
        tr, te = M.season != S, (M.season == S).values
        w0 = fitlr(M.loc[tr, b2].values, M.td[tr].values); w1 = fitlr(M.loc[tr, b2 + fs].values, M.td[tr].values)
        d[te] = ll(pred(w0, M.loc[te, b2].values), M.td[te].values) - ll(pred(w1, M.loc[te, b2 + fs].values), M.td[te].values)
    lo, hi = boot(d, M.id.values)
    print(f"  {name:48s} {1000*d.mean():+.3f}  (90% {1000*lo:+.3f} to {1000*hi:+.3f})")
# receiving yards residual on YAC over expected
print('\n== receiving yards: does prior YAC over expected predict (actual - model)? players with 3+ model targets')
Y = R[R.mTGT >= 3].copy(); Y['res'] = Y.aRCY - Y.mRCY; Y['x'] = Y.yacoe * Y.mREC
for S in (2023, 2024, 2025):
    tr, te = Y[Y.season != S], Y[Y.season == S]
    b = np.polyfit(tr.x, tr.res, 1); e0 = ((te.res - te.res.mean() * 0 - np.polyval([0, tr.res.mean()], te.x)) ** 2).mean(); e1 = ((te.res - np.polyval(b, te.x)) ** 2).mean()
    print(f"  {S}: slope {b[0]:+.2f} yds per (YACOE x catches) | RMSE {np.sqrt(e0):.2f} -> {np.sqrt(e1):.2f}")
# team pass rate
print('\n== team dropback rate in a game (2023-25 weeks 3+): prior neutral pass rate vs prior pass-over-expected')
G = pd.read_csv(f'{D}/games.csv'); G = G[(G.season.between(2023, 2025)) & (G.game_type == 'REG') & (G.week >= 3)]
tr_ = []
for r in G.itertuples():
    _, team = feats(r.season, r.week)
    for t, o, sp in ((r.home_team, r.away_team, r.spread_line), (r.away_team, r.home_team, -r.spread_line)):
        a = TG[(TG.game_id == r.game_id) & (TG.posteam == t)]
        if not len(a) or t not in team.index: continue
        tr_.append(dict(season=r.season, y=float(a.db.iloc[0] / a.plays.iloc[0]), npr=team.npr[t], proe=team.proe[t], sp=sp, tot=r.total_line, gid=r.game_id))
T2 = pd.DataFrame(tr_)
for name, fs in (('neutral pass rate (current)', ['npr']), ('pass over expected (xpass)', ['proe']), ('both', ['npr', 'proe'])):
    err = []
    for S in (2023, 2024, 2025):
        tr, te = T2[T2.season != S], T2[T2.season == S]
        X = np.column_stack([np.ones(len(tr)), tr[fs + ['sp', 'tot']].values]); b = np.linalg.lstsq(X, tr.y, rcond=None)[0]
        err.append(((te.y - np.column_stack([np.ones(len(te)), te[fs + ['sp', 'tot']].values]) @ b) ** 2).values)
    e = np.concatenate(err); print(f"  {name:32s} RMSE {np.sqrt(e.mean()):.4f}")
