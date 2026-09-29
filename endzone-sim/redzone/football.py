"""Redzone Desk football stats (the user's list of 10) plus this season's coverage. Each stat is measured from 2025 (weight
0.3 per game) and 2026 to date (1.0 per game), shrunk toward the league, and written onto the slate:
  g.rzx[side]   team matchup multipliers the engine applies to that offense: sack, pass, run, exp (big plays), int, fum
  g.rzfb[side]  the numbers behind them, for the pick explanations
  g.defp[side]  man / single-high / blitz for the coverage-shell layer, from redzone/coverage_2026.json (this season)
  p.cat/acc/sack/int/ypc/rec/deep/align, p.fb   player stats (separation, drops, CPOE, time to throw, bad throws,
                pressure-to-sack, interception-worthy throws, rush yards over expected, air-yard share, depth of target)
Weights are in config.json ("stats"). Sources: nflverse play-by-play, FTN charting, Next Gen Stats, PFR advanced stats.
Weather: forecasts need api.weather.gov, which this environment blocks; domes are marked and outdoor games are left neutral.
Usage: python3 football.py slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..'); sys.path.insert(0, ROOT)
import nfl_build as nb, scheme_match as sm
D = nb.D; S0 = 2026
CFG = json.load(open(os.path.join(HERE, 'config.json'))); W = CFG['stats']
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
LEAGUE_JS = dict(man=.33, blitz=.25, mofc=.48)          # scheme.js LEAGUE: the engine's coverage baseline
clip = lambda x, lo, hi: float(min(hi, max(lo, x)))

def wt(df, week):
    df = df[((df.season == S0) & (df.week < week)) | (df.season == S0 - 1)]
    return df.assign(w=np.where(df.season == S0, 1.0, 0.3))

def shrunk(df, key, num, den, K):
    """weighted num/den per key, shrunk toward the league rate with K units of den."""
    g = df.assign(n=df.w * df[num], d=df.w * df[den]).groupby(key)[['n', 'd']].sum()
    lg = g.n.sum() / g.d.sum()
    return ((g.n + K * lg) / (g.d + K)).to_dict(), float(lg)

def pbp(week):
    cols = ['game_id', 'play_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'qb_dropback', 'pass_attempt',
            'sack', 'rushing_yards', 'receiving_yards', 'complete_pass', 'yards_gained', 'fumble_lost', 'interception', 'epa',
            'passer_player_id', 'two_point_attempt']
    p = pd.concat([pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=cols, low_memory=False) for s in (S0 - 1, S0)])
    p = p[(p.season_type == 'REG') & p.play_type.isin(['run', 'pass']) & (p.two_point_attempt.fillna(0) == 0)]
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
    p['exp'] = (((p.play_type == 'run') & (p.yards_gained >= 10)) | ((p.play_type == 'pass') & (p.yards_gained >= 20))).astype(float)
    p['one'] = 1.0
    return wt(p, week)

def ftn(p):
    f = pd.concat([pd.read_parquet(f'{D}/ftn_charting_{s}.parquet') for s in (S0 - 1, S0)]).rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})
    f = f.drop(columns=['season', 'week']).merge(p, on=['game_id', 'play_id'])
    for c in ('is_play_action', 'is_motion', 'is_screen_pass', 'is_interception_worthy'): f[c] = f[c].astype(float)
    return f

def pfr(kind, week):
    x = pd.concat([pd.read_csv(f'{D}/advstats_week_{kind}_{s}.csv') for s in (S0 - 1, S0) if os.path.exists(f'{D}/advstats_week_{kind}_{s}.csv')])
    x = x[x.game_type == 'REG']
    for c in ('team', 'opponent'): x[c] = x[c].replace(REP)
    return wt(x, week)

def ngs(kind, week):
    x = pd.read_parquet(f'{D}/ngs_{kind}.parquet'); x = x[(x.season_type == 'REG') & (x.week > 0) & x.season.isin([S0 - 1, S0])]
    return wt(x, week)

def split_effect(f, flag, K=80):
    """defense EPA per dropback allowed on plays with `flag` minus without, relative to the league's gap (shrunk)."""
    db = f[f.qb_dropback == 1]
    lg_on, lg_off = db[db[flag] == 1].epa.mean(), db[db[flag] == 0].epa.mean()
    out = {}
    for t, d in db.groupby('defteam'):
        on, off = d[d[flag] == 1], d[d[flag] == 0]
        n_on = on.w.sum()
        e_on = ((on.w * on.epa).sum() + K * lg_on) / (n_on + K); e_off = ((off.w * off.epa).sum() + K * lg_off) / (off.w.sum() + K)
        out[t] = float((e_on - e_off) - (lg_on - lg_off))
    rate, _ = shrunk(db.assign(x=db[flag]), 'posteam', 'x', 'one', 60)
    return out, rate

def main(path, week):
    S = json.load(open(path))
    p = pbp(week); db = p[p.qb_dropback == 1]
    # ---- 1. pass rush vs pass protection (PFR pressures over dropbacks) ----
    pq = pfr('pass', week); pdf = pfr('def', week)
    dbk = db.groupby(['season', 'week', 'posteam']).one.sum().rename('db').reset_index()
    op = pq.groupby(['season', 'week', 'team']).agg(pr=('times_pressured', 'sum'), w=('w', 'first')).reset_index().merge(dbk, left_on=['season', 'week', 'team'], right_on=['season', 'week', 'posteam'])
    press_off, lg_press = shrunk(op, 'team', 'pr', 'db', 150)
    dp_ = pdf.groupby(['season', 'week', 'team', 'opponent']).agg(pr=('def_pressures', 'sum'), mt=('def_missed_tackles', 'sum'), tk=('def_tackles_combined', 'sum'), w=('w', 'first')).reset_index()
    dp_ = dp_.merge(dbk, left_on=['season', 'week', 'opponent'], right_on=['season', 'week', 'posteam'])
    press_def, lg_pd = shrunk(dp_, 'team', 'pr', 'db', 150)
    dp_['mtt'] = dp_.mt + dp_.tk
    mtp, lg_mt = shrunk(dp_, 'team', 'mt', 'mtt', 200)
    # ---- 3. run blocking (yards before contact) vs run defense ----
    ru = pfr('rush', week)
    ybc_off, lg_ybc = shrunk(ru, 'team', 'rushing_yards_before_contact', 'carries', 120)
    ybc_def, _ = shrunk(ru, 'opponent', 'rushing_yards_before_contact', 'carries', 120)
    # ---- 6. big plays ----
    exp_off, lg_exp = shrunk(p, 'posteam', 'exp', 'one', 250); exp_def, _ = shrunk(p, 'defteam', 'exp', 'one', 250)
    # ---- 9. turnovers ----
    fum_off, lg_fum = shrunk(p, 'posteam', 'fumble_lost', 'one', 600); fum_def, _ = shrunk(p, 'defteam', 'fumble_lost', 'one', 600)
    int_def, lg_int = shrunk(db.assign(i=db.interception.fillna(0)), 'defteam', 'i', 'one', 400)
    # ---- 7. play-action, motion, screens (FTN) ----
    f = ftn(p)
    styles = {k: split_effect(f, c) for k, c in (('pa', 'is_play_action'), ('motion', 'is_motion'), ('screen', 'is_screen_pass'))}
    iw = f[(f.qb_dropback == 1) & f.passer_player_id.notna()]
    intw, lg_iw = shrunk(iw.assign(x=iw.is_interception_worthy), 'passer_player_id', 'x', 'one', 150)
    # ---- player tracking: separation, air yards, RYOE, CPOE, time to throw ----
    nr = ngs('receiving', week); nr = nr.assign(tw=nr.w * nr.targets)
    def ngs_mean(x, key, col, wcol, K, lg=None):
        g = x.assign(n=x[wcol] * x[col]).groupby(key)[['n', wcol]].sum(); lg = g.n.sum() / g[wcol].sum() if lg is None else lg
        return ((g.n + K * lg) / (g[wcol] + K)).to_dict(), float(lg)
    sep, lg_sep = ngs_mean(nr, 'player_gsis_id', 'avg_separation', 'tw', 25)
    adot, _ = ngs_mean(nr, 'player_gsis_id', 'avg_intended_air_yards', 'tw', 25)
    ays, _ = ngs_mean(nr, 'player_gsis_id', 'percent_share_of_intended_air_yards', 'w', 3, lg=0.0)
    pos_of = nb.rosters()['position'].replace({'FB': 'RB'})
    nr['pos'] = nr.player_gsis_id.map(pos_of)
    lg_sep_pos = (nr.tw * nr.avg_separation).groupby(nr.pos).sum() / nr.tw.groupby(nr.pos).sum()
    lg_adot_pos = (nr.tw * nr.avg_intended_air_yards).groupby(nr.pos).sum() / nr.tw.groupby(nr.pos).sum()
    nu = ngs('rushing', week); nu = nu.assign(aw=nu.w * nu.rush_attempts)
    ryoe, _ = ngs_mean(nu, 'player_gsis_id', 'rush_yards_over_expected_per_att', 'aw', 40, lg=0.0)
    npass = ngs('passing', week); npass = npass.assign(aw=npass.w * npass.attempts)
    cpoe, _ = ngs_mean(npass, 'player_gsis_id', 'completion_percentage_above_expectation', 'aw', 120, lg=0.0)
    ttt, lg_ttt = ngs_mean(npass, 'player_gsis_id', 'avg_time_to_throw', 'aw', 120)
    # PFR per player: drops, bad throws, pressure-to-sack (pfr ids -> gsis)
    R = nb.rosters(); pfr2g = {v: k for k, v in R['pfr_id'].dropna().items()}
    rc = pfr('rec', week); rc['gid'] = rc.pfr_player_id.map(pfr2g)
    tg = p[(p.pass_attempt == 1)].groupby(['season', 'week', 'posteam']).one.sum()
    pq['gid'] = pq.pfr_player_id.map(pfr2g)
    bad, lg_bad = shrunk(pq.assign(att=pq.passing_bad_throws / pq.passing_bad_throw_pct.replace(0, np.nan)).dropna(subset=['att']), 'gid', 'passing_bad_throws', 'att', 150)
    p2s, lg_p2s = shrunk(pq, 'gid', 'times_sacked', 'times_pressured', 60)
    rc = rc.assign(tgt=rc.receiving_drop / (rc.receiving_drop_pct.replace(0, np.nan) / (1 if rc.receiving_drop_pct.max() <= 1 else 100))).dropna(subset=['tgt'])
    drops, lg_drop = shrunk(rc, 'gid', 'receiving_drop', 'tgt', 60)
    # ---- coverage this season (coverage_2026.py) ----
    cov = json.load(open(os.path.join(HERE, 'coverage_2026.json')))['teams']
    lg_man = np.mean([v['man'] for v in cov.values()]); lg_hi = np.mean([v['hi'] for v in cov.values()])
    COV = sm.week_tables(S0, week)
    for t, v in cov.items(): COV['man']['d'][t] = v['man']
    COV['man']['lg'] = float(lg_man)
    blitz_d, lg_bl = COV['blitz']['d'], COV['blitz']['lg']

    for g in S['games']:
        g['rzx'], g['rzfb'] = {}, {}
        roof = g.get('roof'); roof = roof.lower() if isinstance(roof, str) else ''
        g['wx'] = dict(roof=roof or 'unknown', note='Indoors: no weather' if roof in ('dome', 'closed') else 'Outdoor: forecast not available here (weather service blocked), treated as normal')
        for side, off, dfn in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            pr = lg_press * (press_off.get(off, lg_press) / lg_press) * (press_def.get(dfn, lg_pd) / lg_pd)
            sackM = (pr / lg_press) ** W['pass_rush']
            passM = 1 - 0.30 * W['pass_rush'] * (pr / lg_press - 1)
            mt = mtp.get(dfn, lg_mt) / lg_mt
            runM = 1 + W['run_blocking'] * ((ybc_off.get(off, lg_ybc) - lg_ybc) + (ybc_def.get(dfn, lg_ybc) - lg_ybc)) / 4.3
            runM *= 1 + 0.15 * W['run_blocking'] * (mt - 1); passM *= 1 + 0.10 * W['run_blocking'] * (mt - 1)
            expM = ((exp_off.get(off, lg_exp) / lg_exp) * (exp_def.get(dfn, lg_exp) / lg_exp)) ** (0.5 * W['big_plays'])
            sty = {}
            for k, (eff, rate) in styles.items():
                d_ = rate.get(off, 0) * eff.get(dfn, 0); sty[k] = dict(rate=round(rate.get(off, 0), 3), def_epa=round(eff.get(dfn, 0), 3))
                passM *= 1 + 0.8 * W['play_style'] * d_
            intM = (int_def.get(dfn, lg_int) / lg_int) ** (0.5 * W['turnovers'])
            fumM = ((fum_off.get(off, lg_fum) / lg_fum) * (fum_def.get(dfn, lg_fum) / lg_fum)) ** (0.5 * W['turnovers'])
            g['rzx'][side] = {k: round(clip(v, .6, 1.6), 4) for k, v in dict(sack=sackM, pass_=passM, run=runM, exp=expM, int=intM, fum=fumM).items()}
            g['rzx'][side]['pass'] = g['rzx'][side].pop('pass_')
            g['rzfb'][side] = dict(pressure=round(pr, 3), lgPressure=round(lg_press, 3), offPress=round(press_off.get(off, lg_press), 3), defPress=round(press_def.get(dfn, lg_pd), 3),
                                   ybcOff=round(ybc_off.get(off, lg_ybc), 2), ybcDef=round(ybc_def.get(dfn, lg_ybc), 2), lgYbc=round(lg_ybc, 2), missedTackle=round(mtp.get(dfn, lg_mt), 3), lgMissed=round(lg_mt, 3),
                                   expOff=round(exp_off.get(off, lg_exp), 3), expDef=round(exp_def.get(dfn, lg_exp), 3), lgExp=round(lg_exp, 3), style=sty,
                                   intDef=round(int_def.get(dfn, lg_int), 4), lgInt=round(lg_int, 4), fumOff=round(fum_off.get(off, lg_fum), 4), lgFum=round(lg_fum, 4))
            # coverage this season, on the engine's baseline (scheme.js LEAGUE)
            c = cov.get(dfn)
            if c and g.get('defp', {}).get(side) is not None:
                dpx = g['defp'][side]
                dpx['man'] = round(clip(LEAGUE_JS['man'] + (c['man'] - lg_man), .05, .8), 3)
                dpx['mofc'] = round(clip(LEAGUE_JS['mofc'] + (c['hi'] - lg_hi), .1, .9), 3)
                dpx['blitz'] = round(clip(LEAGUE_JS['blitz'] + (blitz_d.get(dfn, lg_bl) - lg_bl), .05, .8), 3)
                g['rzfb'][side]['cov'] = dict(man=c['man'], man2025=c['man2025'], lgMan=round(float(lg_man), 3), hi=c['hi'], hi2025=c['hi2025'], lgHi=round(float(lg_hi), 3),
                                               blitz=round(blitz_d.get(dfn, lg_bl), 3), lgBlitz=round(lg_bl, 3))
                g.setdefault('defScheme', {})[side] = dict(man=c['man'], blitz=round(blitz_d.get(dfn, lg_bl), 3), hi=c['hi'])
        for pl in g['players']:
            pid, pos = pl.get('id'), pl['pos']; opp = g['home'] if pl['t'] == g['away'] else g['away']; fb = {}
            if pos in ('WR', 'TE', 'RB'):
                # coverage matchup redone with this season's man rates, at full strength (Redzone weight)
                m, parts = sm.multiplier(COV, pid, opp); raw = 1.0
                for k in parts: raw *= parts[k]['raw']
                pl['cov'] = round(float(raw ** W['coverage_matchups']), 4); pl['covParts'] = parts
                s_ = sep.get(pid); lp = lg_sep_pos.get(pos, lg_sep)
                if s_ is not None:
                    pl['cat'] = round(clip(pl['cat'] * (1 + 0.05 * W['separation'] * (s_ - lp)), .3, .95), 3); fb['sep'] = round(s_, 2); fb['sepLg'] = round(float(lp), 2)
                dr = drops.get(pid)
                if dr is not None:
                    pl['cat'] = round(clip(pl['cat'] * ((1 - dr) / (1 - lg_drop)) ** W['drops'], .3, .95), 3); fb['drop'] = round(dr, 3); fb['dropLg'] = round(lg_drop, 3)
                a = ays.get(pid)
                if a is not None and pl['rec'] > .02:
                    share = a / 100 if a > 1.5 else a
                    pl['rec'] = round(max(.004, pl['rec'] + W['air_yards'] * 0.16 * (share - pl['rec'])), 3); fb['airShare'] = round(share, 3)
                ad = adot.get(pid)
                if ad is not None:
                    la = lg_adot_pos.get(pos, 8.0); pl['deep'] = round(clip(pl['deep'] * (max(ad, 1) / la) ** (0.3 * W['air_yards']), .5, 2.0), 3); fb['adot'] = round(ad, 1); fb['adotLg'] = round(float(la), 1)
                al = {}
                if pos == 'WR' and pl.get('rz', {}).get('slot') is not None: al.update(slot=pl['rz']['slot'], wide=round(1 - pl['rz']['slot'], 2))
                if s_ is not None: al['sep'] = round(clip(.5 + (s_ - lp) / 1.2, .1, .95), 2)
                if ad is not None: al['vert'] = round(clip(.5 + (ad - lg_adot_pos.get(pos, 8.0)) / 8, .1, .95), 2)
                if al: pl['align'] = al
            if pos in ('RB', 'QB', 'WR'):
                r_ = ryoe.get(pid)
                if r_ is not None and pl['rush'] > .03:
                    pl['ypc'] = round(pl['ypc'] * clip(1 + 0.5 * W['ryoe'] * r_ / max(3.0, pl['ypc']), .8, 1.25), 2); fb['ryoe'] = round(r_, 2)
            if pos == 'QB':
                c_ = cpoe.get(pid); b_ = bad.get(pid); t_ = ttt.get(pid); s2 = p2s.get(pid); iw_ = intw.get(pid)
                if c_ is not None: pl['acc'] = round(pl.get('acc', 1) * (1 + W['qb'] * c_ / 100), 3); fb['cpoe'] = round(c_, 1)
                if b_ is not None: pl['acc'] = round(pl.get('acc', 1) * (1 - W['qb'] * (b_ - lg_bad)), 3); fb['bad'] = round(b_, 3); fb['badLg'] = round(lg_bad, 3)
                if t_ is not None: pl['sack'] = round(pl.get('sack', .066) * (t_ / lg_ttt) ** W['qb'], 4); fb['ttt'] = round(t_, 2); fb['tttLg'] = round(lg_ttt, 2)
                if s2 is not None: pl['sack'] = round(pl.get('sack', .066) * (s2 / lg_p2s) ** (0.5 * W['qb']), 4); fb['p2s'] = round(s2, 3); fb['p2sLg'] = round(lg_p2s, 3)
                if iw_ is not None: pl['int'] = round(pl.get('int', .022) * (iw_ / lg_iw) ** W['turnovers'], 4); fb['intw'] = round(iw_, 3); fb['intwLg'] = round(lg_iw, 3)
            if fb: pl['fb'] = fb
    # points: each team-level edge also moves that offense's scoring (points.py reads g.rzx)
    json.dump(S, open(path, 'w'))
    print(f"football: pressure lg {lg_press:.3f}, ybc lg {lg_ybc:.2f}, explosive lg {lg_exp:.3f}; {sum('fb' in p_ for g in S['games'] for p_ in g['players'])} players with tracking/PFR stats")

if __name__ == '__main__': main(sys.argv[1], int(sys.argv[2]))
