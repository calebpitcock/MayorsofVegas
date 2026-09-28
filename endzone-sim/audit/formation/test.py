"""Tests of the v3.7 formation terms (formation.py) on 2022-25, walk-forward: every input for week w uses only weeks < w
of the same season, shrunk toward the season-to-date league like formation.py. Weeks 3-18.
  2a  box mix: does the offense's personnel shift the boxes it faces as formation.py says? (fit C)
  2b  run efficiency: does formation.py's run multiplier predict RB yards per carry beyond the offense's and the
      defense's own ypc? The fitted coefficient on log(raw multiplier) is the DAMP the data supports (shipped: 0.4).
  3   TE/RB targets and yards per target vs bv/nh (shipped guesses TE 0.6/-0.4, RB 0.5/0), fit held out by season.
Usage: python3 audit/formation/test.py"""
import os, numpy as np, pandas as pd
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data')
P = pd.read_parquet(f'{D}/formation_plays.parquet')
P['w3'] = (P.nWR >= 3).astype(float); P['light'] = (P.box <= 6).astype(float); P['stack'] = (P.box >= 8).astype(float); P['sub'] = (P.nDB >= 5).astype(float)
P['rbrun'] = ((P.drun == 1) & (P.rupos == 'RB')).astype(int)
for pos in ('TE', 'RB', 'WR'):
    P[f't{pos}'] = ((P.tgt == 1) & (P.rpos == pos)).astype(int); P[f'y{pos}'] = np.where(P[f't{pos}'] == 1, P.receiving_yards.fillna(0), 0)
YPC = dict(light=5.2, base=4.5, heavy=3.8); K_OFF, K_DEF = 150, 150
# per team-game, offense side and defense side
O = P.groupby(['season', 'week', 'game_id', 'posteam', 'defteam']).agg(n=('w3', 'size'), w3=('w3', 'sum'), fl=('light', 'sum'), fs=('stack', 'sum'),
    car=('rbrun', 'sum'), ry=('rushing_yards', lambda x: 0), tTE=('tTE', 'sum'), tRB=('tRB', 'sum'), tWR=('tWR', 'sum'), yTE=('yTE', 'sum'), yRB=('yRB', 'sum'), tg=('tgt', 'sum')).reset_index()
O['ry'] = P[P.rbrun == 1].groupby(['game_id', 'posteam']).rushing_yards.sum().reindex(pd.MultiIndex.from_frame(O[['game_id', 'posteam']])).fillna(0).values
Dg = O.groupby(['season', 'week', 'defteam']).agg(dn=('n', 'sum'), dl=('fl', 'sum'), ds=('fs', 'sum'), dcar=('car', 'sum'), dry=('ry', 'sum')).reset_index()
Dg['dsub'] = P.groupby(['season', 'week', 'defteam'])['sub'].sum().reindex(pd.MultiIndex.from_frame(Dg[['season', 'week', 'defteam']])).values
def cum(df, key, cols):
    df = df.sort_values(['season', key, 'week']).copy()
    for c in cols: df['p_' + c] = df.groupby(['season', key])[c].cumsum() - df[c]
    return df
O = cum(O, 'posteam', ['n', 'w3', 'car', 'ry', 'tTE', 'tRB', 'tWR', 'yTE', 'yRB', 'tg'])
Dg = cum(Dg, 'defteam', ['dn', 'dl', 'ds', 'dsub', 'dcar', 'dry'])
X = O.merge(Dg[['season', 'week', 'defteam'] + [c for c in Dg if c.startswith('p_')]], on=['season', 'week', 'defteam'])
# season-to-date league (weeks < w)
L = O.groupby(['season', 'week'])[['n', 'w3', 'car', 'ry', 'fl', 'fs', 'tTE', 'tRB', 'tg', 'yTE', 'yRB']].sum().groupby(level=0).cumsum().groupby(level=0).shift(1)
Ls = P.groupby(['season', 'week'])['sub'].sum().groupby(level=0).cumsum().groupby(level=0).shift(1)
L['sub'] = Ls; L = L.reset_index().rename(columns=lambda c: c if c in ('season', 'week') else 'L_' + c)
X = X.merge(L, on=['season', 'week']); X = X[(X.week >= 3) & (X.week <= 18)].copy()
lg_heavy = 1 - X.L_w3 / X.L_n; lg_light = X.L_fl / X.L_n; lg_stack = X.L_fs / X.L_n; lg_sub = X.L_sub / X.L_n; lg_ypc = X.L_ry / X.L_car
w = X.p_n / (X.p_n + K_OFF); heavy = w * (1 - X.p_w3 / X.p_n.clip(1)) + (1 - w) * lg_heavy
wd = X.p_dn / (X.p_dn + K_DEF)
L0 = wd * X.p_dl / X.p_dn.clip(1) + (1 - wd) * lg_light; H0 = wd * X.p_ds / X.p_dn.clip(1) + (1 - wd) * lg_stack; sub = wd * X.p_dsub / X.p_dn.clip(1) + (1 - wd) * lg_sub
ypc = lambda l, h: l * YPC['light'] + h * YPC['heavy'] + (1 - l - h) * YPC['base']
def boxes(C):
    d = C * (heavy - lg_heavy); return (L0 + d * sub).clip(0, .9), (H0 + d * (1 - sub)).clip(0, .9)
print(f'team-games {len(X)} (2022-25, weeks 3-18)\n')
print('2a  box mix faced by the offense (share of its plays): weighted MSE x1000 of predicted light / stacked box rate')
for C in (0, .25, .5, 1, 2, 4):
    l, h = boxes(C)
    print(f'   C={C:<4} light {1000*np.average((X.fl/X.n - l)**2, weights=X.n):.3f}  stacked {1000*np.average((X.fs/X.n - h)**2, weights=X.n):.3f}')
# direct regression: residual box rate on offense heaviness (what C would have to be)
for nm, obs, base, lev in (('light', X.fl / X.n, L0, sub), ('stacked', X.fs / X.n, H0, 1 - sub)):
    z = (heavy - lg_heavy) * lev; r = obs - base; b = np.sum(X.n * z * r) / np.sum(X.n * z * z)
    rng = np.random.default_rng(1); bs = []
    for _ in range(500):
        i = rng.integers(0, len(X), len(X)); bs.append(np.sum(X.n.values[i] * z.values[i] * r.values[i]) / np.sum(X.n.values[i] * z.values[i] ** 2))
    print(f'   implied C from {nm} boxes: {b:+.2f} (95% {np.percentile(bs,2.5):+.2f} to {np.percentile(bs,97.5):+.2f}); formation.py sign expects {"+" if nm=="light" else "+"} (heavier offense -> {"more light boxes vs nickel" if nm=="light" else "more stacked vs base"})')
# 2b run efficiency
l, h = boxes(.5); raw = ypc(l, h) / ypc(lg_light, lg_stack)
K = 60   # carries of shrinkage for offense/defense ypc
offy = (X.p_ry + K * lg_ypc) / (X.p_car + K) / lg_ypc; defy = (X.p_dry + K * lg_ypc) / (X.p_dcar + K) / lg_ypc
m = X.car >= 8; Y = np.log((X.ry / X.car.clip(1)).clip(.5) / lg_ypc)
A = np.column_stack([np.ones(len(X)), np.log(offy), np.log(defy), np.log(raw)])[m]; y = Y[m].values; wt = X.car[m].values.astype(float)
def wls(A, y, wt): W = np.sqrt(wt); return np.linalg.lstsq(A * W[:, None], y * W, rcond=None)[0]
b = wls(A, y, wt); rng = np.random.default_rng(2); bs = []
g = X.game_id[m].values; ug = np.unique(g); gi = {k: np.where(g == k)[0] for k in ug}
for _ in range(500):
    i = np.concatenate([gi[k] for k in rng.choice(ug, len(ug))]); bs.append(wls(A[i], y[i], wt[i]))
bs = np.array(bs)
print(f'\n2b  RB yards per carry, log scale, {m.sum()} team-games with 8+ RB carries (C=0.5, shipped box ypc values)')
print(f'   spread of log(raw multiplier): sd {np.log(raw[m]).std():.4f} (so the undamped term moves ypc about +/-{100*np.log(raw[m]).std():.1f}%)')
for j, nm in enumerate(['intercept', 'offense ypc', 'defense ypc allowed', 'formation log(raw)']):
    print(f'   {nm:22s} {b[j]:+.3f}  (95% {np.percentile(bs[:,j],2.5):+.3f} to {np.percentile(bs[:,j],97.5):+.3f})')
print('   -> the formation coefficient is the damp the data supports (formation.py uses 0.4)')
for s in range(2022, 2026):
    mm = (X.season[m] == s).values; bb = wls(A[mm], y[mm], wt[mm]); print(f'   {s}: formation coef {bb[3]:+.3f}')
# 3 position targets
lgTE = X.L_tTE / X.L_tg; lgRB = X.L_tRB / X.L_tg; KT = 60
bv = (1 - heavy) * (1 - sub) - (1 - lg_heavy) * (1 - lg_sub); nh = heavy * sub - lg_heavy * lg_sub
print(f'\n3   bv sd {bv.std():.4f}, nh sd {nh.std():.4f}  (shipped TE target shift = 0.6*bv - 0.4*nh -> sd {(0.6*bv-0.4*nh).std()*100:.2f}%)')
for pos, lgp, guess in (('TE', lgTE, (0.6, -0.4)), ('RB', lgRB, (0.5, 0.0))):
    prior = (X['p_t' + pos] + KT * lgp) / (X.p_tg + KT); act = X['t' + pos] / X.tg.clip(1); wt = X.tg.values.astype(float)
    Z = np.column_stack([prior * bv, prior * nh]); r = (act - prior).values
    def fit(ix): W = np.sqrt(wt[ix]); return np.linalg.lstsq(Z[ix] * W[:, None], r[ix] * W, rcond=None)[0]
    ho = {'none': [], 'shipped': [], 'fitted': []}; coefs = []
    for s in range(2022, 2026):
        tr = (X.season != s).values; te = ~tr; c = fit(tr); coefs.append(c)
        for k, cc in (('none', (0, 0)), ('shipped', guess), ('fitted', c)):
            ho[k].append((np.sum(wt[te] * (r[te] - Z[te] @ np.array(cc)) ** 2), wt[te].sum()))
    call = fit(np.ones(len(X), bool)); rng = np.random.default_rng(3); bs = []
    for _ in range(500):
        bs.append(fit(rng.integers(0, len(X), len(X))))   # row bootstrap
    bs = np.array(bs); mse = {k: sum(a for a, _ in v) / sum(n for _, n in v) for k, v in ho.items()}
    print(f'   {pos} target share: fitted bv {call[0]:+.2f} (95% {np.percentile(bs[:,0],2.5):+.2f} to {np.percentile(bs[:,0],97.5):+.2f}), nh {call[1]:+.2f} (95% {np.percentile(bs[:,1],2.5):+.2f} to {np.percentile(bs[:,1],97.5):+.2f}); shipped {guess}')
    print(f'      held-out weighted MSE x1e4: no shift {1e4*mse["none"]:.4f}  shipped {1e4*mse["shipped"]:.4f}  fitted {1e4*mse["fitted"]:.4f}   per-season fits bv ' + ' '.join(f'{c[0]:+.2f}' for c in coefs))
    # yards per target
    lgy = X['L_y' + pos] / X['L_t' + pos]; py = (X['p_y' + pos] + 40 * lgy) / (X['p_t' + pos] + 40); ok = X['t' + pos] >= 3
    ay = (X['y' + pos] / X['t' + pos].clip(1))[ok] / py[ok] - 1; zz = np.column_stack([bv[ok], nh[ok]]); ww = X['t' + pos][ok].values.astype(float)
    W = np.sqrt(ww); cy = np.linalg.lstsq(zz * W[:, None], ay.values * W, rcond=None)[0]; bsy = []
    for _ in range(500):
        i = rng.integers(0, ok.sum(), ok.sum()); bsy.append(np.linalg.lstsq(zz[i] * W[i, None], ay.values[i] * W[i], rcond=None)[0])
    bsy = np.array(bsy)
    print(f'      {pos} yards/target: fitted bv {cy[0]:+.2f} (95% {np.percentile(bsy[:,0],2.5):+.2f} to {np.percentile(bsy[:,0],97.5):+.2f}), nh {cy[1]:+.2f} (95% {np.percentile(bsy[:,1],2.5):+.2f} to {np.percentile(bsy[:,1],97.5):+.2f}); shipped {"(0.3, -0.2)" if pos=="TE" else "(0.3, 0)"}')
X.assign(raw=raw, bv=bv, nh=nh, heavyp=heavy, L=l, H=h).to_parquet(f'{D}/formation_tg.parquet')
