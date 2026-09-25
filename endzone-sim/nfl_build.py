"""Build engine-ready NFL slates from nflverse play-by-play.

Usage estimates are empirical-Bayes: each player's share of his team's designed
carries and targets is estimated from the games he actually played for that
team, current season weighted 1.0 per game and the prior season 0.12 per game,
shrunk toward a small positional prior. Efficiency (YPC, catch rate, yards per
catch) travels with the player across teams; red-zone role (gl) does not.
"""
import pandas as pd, numpy as np, json, sys, os
D = os.path.join(os.path.dirname(__file__), '..', 'data')

PBP_COLS = ['play_id','game_id','season','season_type','week','posteam','defteam','play_type','down','ydstogo','yardline_100',
  'qb_scramble','qb_kneel','qb_spike','sack','pass_attempt','complete_pass','rushing_yards','receiving_yards','passing_yards',
  'yards_gained','rush_touchdown','pass_touchdown','interception','qb_dropback','two_point_attempt','rusher_player_id',
  'receiver_player_id','passer_player_id','wp','half_seconds_remaining','game_seconds_remaining','drive','fumble_lost',
  'air_yards','home_team','away_team','score_differential']

_cache = {}
def pbp(season):
    if season not in _cache:
        p = pd.read_csv(f'{D}/play_by_play_{season}.csv.gz', usecols=PBP_COLS, low_memory=False)
        p = p[p.season_type == 'REG'].copy()
        _cache[season] = p
    return _cache[season]

def rosters():
    frames = []
    for s in (2022, 2023, 2024, 2025, 2026):
        f = f'{D}/roster_{s}.csv'
        if os.path.exists(f):
            r = pd.read_csv(f, low_memory=False); r['rs'] = s; frames.append(r)
    r = pd.concat(frames).sort_values('rs')
    r = r.dropna(subset=['gsis_id']).drop_duplicates('gsis_id', keep='last')
    return r.set_index('gsis_id')

def snaps(season):
    s = pd.read_csv(f'{D}/snap_counts_{season}.csv')
    return s[(s.game_type == 'REG') & (s.offense_snaps > 0)]

HL = 2.0; PRIOR_W = 0.04; PSEUDO = 0.3
# early-season check (weeks 2-4 of 2025): last season's target shares help, last season's carry shares hurt
# Role correction (role_fit.py): snap-share trend, practice report and returning-player signals. EZROLE = all | ex2024 | off
ROLE = os.environ.get("EZROLE", "all")
FIELD_FLOOR3_PY = {'rush': .03, 'rec': .07}   # same floors the engine keeps for unlisted players
ROLE_COEF = None if ROLE == "off" else json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), f"role_coef_{ROLE}.json")))
PRIOR_REC_EARLY, EARLY_WEEKS = float(os.environ.get("EZPRE", 0.25)), 3   # weeks 4-5 tested worse for touchdowns; weeks 2-4 share check supported it
STRETCH = {'rush': 1.3, 'rec': 1.05}      # residual compression measured in the 2025 backtest
POS_PRIOR = {'RB': (.18, .06), 'WR': (.02, .10), 'TE': (0, .08), 'QB': (.08, 0)}
POS_EFF = {  # league baselines used for shrinkage (NFL 2024-25 means, designed runs / targets)
  'RB': dict(ypc=4.3, cat=.77, ypr=7.6), 'WR': dict(ypc=6.5, cat=.64, ypr=12.9),
  'TE': dict(ypc=3.5, cat=.72, ypr=10.4), 'QB': dict(ypc=4.4, cat=.5, ypr=8)}

def usage_frames(p):
    """per (game, team, player) counts"""
    two = p.two_point_attempt.fillna(0) == 1
    runs = p[(p.play_type == 'run') & (p.qb_scramble.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0) & ~two & p.rusher_player_id.notna()]
    tg = p[(p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & ~two & p.receiver_player_id.notna()]
    RZL = int(os.environ.get('EZGL', 10))
    rz = lambda d: d.yardline_100 <= RZL
    r = runs.assign(rz=rz(runs), exp=(runs.rushing_yards >= 12), td=runs.rush_touchdown).groupby(['game_id','season','week','posteam','rusher_player_id']).agg(
        car=('play_type','size'), rzcar=('rz','sum'), ry=('rushing_yards','sum'), rexp=('exp','sum'), rtd=('td','sum')).reset_index().rename(columns={'rusher_player_id':'pid'})
    t = tg.assign(rz=rz(tg), exp=(tg.receiving_yards >= 20), td=tg.pass_touchdown).groupby(['game_id','season','week','posteam','receiver_player_id']).agg(
        tgt=('play_type','size'), rztgt=('rz','sum'), rec=('complete_pass','sum'), recy=('receiving_yards','sum'), cexp=('exp','sum'), ctd=('td','sum')).reset_index().rename(columns={'receiver_player_id':'pid'})
    team = pd.concat([
        runs.groupby(['game_id','posteam']).agg(tcar=('play_type','size'), trzcar=('yardline_100', lambda x: (x <= RZL).sum())),
        tg.groupby(['game_id','posteam']).agg(ttgt=('play_type','size'), trztgt=('yardline_100', lambda x: (x <= RZL).sum()))], axis=1).reset_index()
    u = r.merge(t, on=['game_id','season','week','posteam','pid'], how='outer').fillna(0)
    return u, team

def qb_frames(p):
    two = p.two_point_attempt.fillna(0) == 1
    db = p[(p.qb_dropback == 1) & ~two & (p.qb_spike.fillna(0) == 0)]
    pid = db.passer_player_id.fillna(db.rusher_player_id)
    g = db.assign(pid=pid).groupby(['game_id','season','week','posteam','pid']).agg(
        db=('play_type','size'), sacks=('sack','sum'), scr=('qb_scramble','sum'), att=('pass_attempt','sum'),
        cmp=('complete_pass','sum'), ints=('interception','sum'), py=('passing_yards','sum'), ptd=('pass_touchdown','sum')).reset_index()
    return g

def neutral_pass(p):
    n = p[(p.down.isin([1, 2])) & (p.wp.between(.2, .8)) & (p.half_seconds_remaining > 120) & (p.play_type.isin(['run','pass'])) & (p.two_point_attempt.fillna(0) == 0)]
    return n.groupby(['game_id','season','week','posteam']).agg(np=('qb_dropback','sum'), nn=('play_type','size')).reset_index()

def pace_frames(p):
    q = p[p.play_type.isin(['run','pass'])].sort_values(['game_id','drive','game_seconds_remaining'], ascending=[True, True, False])
    q = q.assign(prev=q.groupby(['game_id','drive']).game_seconds_remaining.shift(1),
                 prevrun=q.groupby(['game_id','drive']).play_type.shift(1), prevcmp=q.groupby(['game_id','drive']).complete_pass.shift(1))
    q = q[(q.prev.notna()) & ((q.prevrun == 'run') | (q.prevcmp == 1)) & (q.wp.between(.2, .8)) & (q.half_seconds_remaining > 300)]
    q = q.assign(dt=(q.prev - q.game_seconds_remaining)).query('dt>10 and dt<60')
    return q.groupby(['game_id','season','week','posteam']).agg(sdt=('dt','sum'), ndt=('dt','size')).reset_index()

def shrink(num, den, prior, m):
    return (num + prior * m) / (den + m)

class Builder:
    def __init__(self, season):
        self.season = season
        frames = [pbp(s) for s in (season - 1, season) if os.path.exists(f'{D}/play_by_play_{s}.csv.gz')]
        self.P = pd.concat(frames)
        self.U, self.T = usage_frames(self.P)
        self.Q = qb_frames(self.P)
        self.NP = neutral_pass(self.P)
        self.PACE = pace_frames(self.P)
        self.R = rosters()
        sn = pd.concat([snaps(s) for s in (season - 1, season) if os.path.exists(f'{D}/snap_counts_{s}.csv')])
        pfr2g = {v: k for k, v in self.R['pfr_id'].dropna().items()}
        sn = sn.assign(pid=sn.pfr_player_id.map(pfr2g)).dropna(subset=['pid'])
        self.SN = sn[['game_id','season','week','team','pid','offense_snaps','offense_pct']]
        lg = self.NP[self.NP.season == season - 1]
        self.lg_np = lg.np.sum() / max(1, lg.nn.sum())
        lp = self.PACE[self.PACE.season == season - 1]
        self.lg_pace = lp.sdt.sum() / max(1, lp.ndt.sum())
        # league catch rate on targets (for the throwaway-adjusted accuracy constant)
        self.lg_cat = self.U[self.U.season == season - 1].rec.sum() / max(1, self.U[self.U.season == season - 1].tgt.sum())
        fw = f'{D}/roster_weekly_{season}.csv'
        self.ACT = None
        if os.path.exists(fw):
            rw = pd.read_csv(fw, low_memory=False); rw = rw[rw.week == rw.week.max()]
            self.ACT = set(rw[rw.status == 'ACT'].gsis_id.dropna())

    def weight(self, season, week, cut_week):
        if season == self.season:
            return 1.0 + 0.04 * (week - cut_week)          # a little recency inside the season
        return 0.12

    def hist_mask(self, df, week):
        S = self.season
        return ((df.season == S) & (df.week < week)) | (df.season == S - 1)

    def starter(self, team, week):
        q = self.Q[(self.Q.posteam == team) & self.hist_mask(self.Q, week)]
        if q.empty: return None
        last = q[q.season == q.season.max()]
        last = last[last.week == last.week.max()]
        return last.sort_values('db').pid.iloc[-1]

    def team_players(self, team, week, active_pids=None, qb_pid=None, exclude=()):
        """active_pids: players available this week (None = anyone who played for the team in-season)."""
        S = self.season
        SN = self.SN[(self.SN.team == team) & self.hist_mask(self.SN, week)]
        if active_pids is None:
            active = set(SN[SN.season == S].pid)
            if self.ACT is not None: active &= self.ACT      # drop injured reserve, cuts, practice squad
        else:
            active = set(active_pids)
        active -= set(exclude)
        if qb_pid is None: qb_pid = self.starter(team, week)
        if qb_pid is not None: active.add(qb_pid)
        SN = SN[SN.pid.isin(active)]
        U = self.U[self.hist_mask(self.U, week)]
        T = self.T[self.T.posteam == team]
        G = SN.merge(U[U.posteam == team][['game_id','pid','car','tgt','rzcar','rztgt']], on=['game_id','pid'], how='left').fillna(0)
        G = G.merge(T[['game_id','tcar','ttgt','trzcar','trztgt']], on='game_id', how='inner')
        G['w'] = np.where(G.season == S, np.power(0.5, (week - G.week) / HL), 1.0)
        prr = np.where(G.season == S, 1.0, PRIOR_W)
        prt = np.where(G.season == S, 1.0, PRIOR_REC_EARLY if week <= EARLY_WEEKS else PRIOR_W)
        def aggregate(G, wr, wt):
            for c in ['car','rzcar','tcar','trzcar']: G['w' + c] = G.w * wr * G[c]
            for c in ['tgt','rztgt','ttgt','trztgt']: G['w' + c] = G.w * wt * G[c]
            return G.groupby('pid').agg(**{k: ('w' + k, 'sum') for k in ['car','tgt','rzcar','rztgt','tcar','ttgt','trzcar','trztgt']},
                                        g26=('season', lambda x: int((x == S).sum())))
        agg = aggregate(G, prr, prt)
        # Games that look like this week count more. A backup's share from the games the
        # starter missed says little about a week the starter plays, so each game is
        # down-weighted for every current big-role teammate who was absent from it.
        raw_r = (agg.car / agg.tcar.clip(lower=1)); raw_t = (agg.tgt / agg.ttgt.clip(lower=1))
        big_r = set(raw_r[raw_r >= .15].index); big_t = set(raw_t[raw_t >= .12].index)
        pres = SN.groupby('pid').game_id.apply(set).to_dict()
        def mod(row, big):
            m = 1.0
            for j in big:
                if j != row.pid and row.game_id not in pres.get(j, ()): m *= .25
            return m
        wr = G.apply(lambda r: mod(r, big_r), axis=1); wt = G.apply(lambda r: mod(r, big_t), axis=1)
        agg = aggregate(G, wr.values * prr, wt.values * prt)
        EU = U.groupby('pid').agg(car=('car','sum'), ry=('ry','sum'), tgt=('tgt','sum'), rec=('rec','sum'), recy=('recy','sum'),
                                  rexp=('rexp','sum'), cexp=('cexp','sum'))
        rows = []
        for pid, a in agg.iterrows():
            if pid not in self.R.index: continue
            pos = self.R.loc[pid, 'position']
            if pos == 'FB': pos = 'RB'
            if pos not in ('RB','WR','TE','QB'): continue
            if pos == 'QB' and pid != qb_pid: continue
            pc, pt = POS_PRIOR[pos]
            rush = shrink(a.car, a.tcar, pc, PSEUDO * 26)
            rec = shrink(a.tgt, a.ttgt, pt, PSEUDO * 32)
            e = POS_EFF[pos]
            eu = EU.loc[pid] if pid in EU.index else pd.Series(dict(car=0, ry=0, tgt=0, rec=0, recy=0, rexp=0, cexp=0))
            ypc = shrink(eu.ry, eu.car, e['ypc'], 45)
            cat = shrink(eu.rec, eu.tgt, e['cat'], 35)
            ypr = shrink(eu.recy, eu.rec, e['ypr'], 25)
            gl_r = ((a.rzcar + 8 * rush) / (a.trzcar + 8)) / rush if rush > .02 else 1
            gl_t = ((a.rztgt + 8 * rec) / (a.trztgt + 8)) / rec if rec > .02 else 1
            wr = (rush * a.tcar) / max(1e-6, rush * a.tcar + rec * a.ttgt)
            gl = float(np.clip(wr * gl_r + (1 - wr) * gl_t, .45, 2.6))
            ber = .085 if pos != 'QB' else .10
            bec = {'WR': .19, 'TE': .12, 'RB': .06, 'QB': .1}[pos]
            exr = shrink(eu.rexp, eu.car, ber, 60) / ber
            exc = shrink(eu.cexp, eu.rec, bec, 40) / bec
            deep = float(np.clip((wr * exr + (1 - wr) * exc) ** .8, .6, 1.8))
            if rush < .015 and rec < .02 and pos != 'QB': continue
            g26 = int(a.g26)
            conf = 'high' if g26 >= 2 and (a.car + a.tgt) >= 10 else ('med' if g26 >= 1 else 'low')
            row = dict(n=self.R.loc[pid, 'full_name'], t=team, pos=pos, rush=round(float(rush), 3), rec=round(float(rec), 3),
                       ypc=round(float(ypc), 2), cat=round(float(cat), 3), ypr=round(float(ypr), 2),
                       gl=round(gl, 2), deep=round(deep, 2), conf=conf, g=g26, id=pid)
            if pos == 'QB':
                q = self.Q[(self.Q.pid == pid) & self.hist_mask(self.Q, week)]
                dbk, att = q.db.sum(), q.att.sum()
                row.update(sack=round(float(shrink(q.sacks.sum(), dbk, .066, 150)), 4),
                           scr=round(float(shrink(q.scr.sum(), dbk, .040, 150)), 4),
                           int=round(float(shrink(q.ints.sum(), att, .022, 250)), 4),
                           acc=round(float((q.cmp.sum() + .65 * 200) / (att + 200) / .65), 3), dbk=int(dbk))
            rows.append(row)
        # a starting QB with no history on this team still needs a row
        if qb_pid is not None and not any(r['pos'] == 'QB' for r in rows) and qb_pid in self.R.index:
            q = self.Q[(self.Q.pid == qb_pid) & self.hist_mask(self.Q, week)]
            dbk, att = q.db.sum(), q.att.sum()
            rows.append(dict(n=self.R.loc[qb_pid, 'full_name'], t=team, pos='QB', rush=.08, rec=0, ypc=4.4, cat=.5, ypr=8, gl=1.2, deep=1,
                             conf='low', g=0, id=qb_pid, sack=round(float(shrink(q.sacks.sum(), dbk, .066, 150)), 4),
                             scr=round(float(shrink(q.scr.sum(), dbk, .040, 150)), 4), int=round(float(shrink(q.ints.sum(), att, .022, 250)), 4),
                             acc=round(float((q.cmp.sum() + .65 * 200) / (att + 200) / .65), 3), dbk=int(dbk)))
        # stretch shares around their group mean (backtest: builder shares were ~15% too compressed for backs)
        for key, grp in (('rush', [r for r in rows if r['pos'] == 'RB']), ('rec', [r for r in rows if r['pos'] != 'QB'])):
            if len(grp) >= 2:
                m = np.mean([r[key] for r in grp]); tot = sum(r[key] for r in grp)
                for r in grp: r[key] = max(.004, m + STRETCH[key] * (r[key] - m))
                k = tot / sum(r[key] for r in grp)
                for r in grp: r[key] = round(float(r[key] * k), 3)
        if ROLE_COEF is not None: self.role_adjust(rows, team, week)
        return sorted(rows, key=lambda r: -(r['rush'] * 26 + r['rec'] * 32))

    def role_adjust(self, rows, team, week):
        """Shift each share by the fitted role correction. Held out one season at a time it cut RB carry-share error
        4-5% and target-share error about 1%. Backs were under-predicted as a group, so totals may rise, capped so
        the group leaves room for the quarterback and the field."""
        S = self.season
        if not hasattr(self, '_inj'):
            f = f'{D}/injuries_{S}.csv'
            inj = pd.read_csv(f) if os.path.exists(f) else pd.DataFrame(columns=['gsis_id', 'week', 'report_status', 'practice_status', 'game_type'])
            inj = inj[inj.game_type == 'REG'] if 'game_type' in inj else inj
            self._inj = inj.drop_duplicates(['gsis_id', 'week'], keep='last').set_index(['gsis_id', 'week'])
        hist = self.SN[(self.SN.team == team) & (self.SN.season == S) & (self.SN.week < week)]
        lastw = hist.week.max() if len(hist) else None
        for key, grp in (('rush', [r for r in rows if r['pos'] == 'RB']), ('rec', [r for r in rows if r['pos'] in ('WR', 'TE', 'RB')])):
            if not grp: continue
            before = sum(r[key] for r in grp)
            for r in grp:
                c = ROLE_COEF.get(f'{key}_{r["pos"]}')
                if c is None: continue
                h = hist[hist.pid == r['id']]
                s_last = float(h[h.week == lastw].offense_pct.sum()) if lastw is not None else 0.0
                prev = h[h.week < lastw].sort_values('week').offense_pct.tail(3) if lastw is not None else h.offense_pct
                trend = s_last - float(prev.mean()) if len(prev) else 0.0
                gap = s_last - (float(h.offense_pct.mean()) if len(h) else 0.0)
                inj = self._inj.loc[(r['id'], week)] if (r['id'], week) in self._inj.index else None
                st = getattr(self, 'status_override', {}).get(r['id']) or (inj.report_status if inj is not None and isinstance(inj.report_status, str) else '')
                pr = inj.practice_status if inj is not None and isinstance(inj.practice_status, str) else ''
                q, lim, dnp = float(st == 'Questionable'), float('Limited' in pr), float('Did Not' in pr)
                back = float(lastw is not None and len(h[h.week == lastw]) == 0); new = float(r.get('g', 0) <= 1); v = r[key]
                x = [1, trend, gap, q, lim, dnp, back, trend * v, q * v, lim * v, back * v, new * v]
                r[key] = max(.004, v + float(np.dot(c, x)))
            qb = sum(r['rush'] for r in rows if r['pos'] == 'QB') if key == 'rush' else 0.0
            cap = (1 - FIELD_FLOOR3_PY[key] - qb) if key == 'rush' else (1 - FIELD_FLOOR3_PY[key] - sum(r[key] for r in rows if r['pos'] not in ('WR', 'TE', 'RB')))
            tot = sum(r[key] for r in grp); lim_ = max(cap, before); k = min(1.0, lim_ / tot) if tot > 0 else 1.0
            for r in grp: r[key] = round(float(r[key] * k), 3)

    def team_env(self, team, week):
        S = self.season
        n = self.NP[(self.NP.posteam == team) & (((self.NP.season == S) & (self.NP.week < week)) | (self.NP.season == S - 1))]
        w = np.where(n.season == S, 1.0, 0.15)
        np_ = shrink((w * n.np).sum(), (w * n.nn).sum(), self.lg_np, 120)
        pr = .535 + (np_ - self.lg_np) * .9
        pc = self.PACE[(self.PACE.posteam == team) & (((self.PACE.season == S) & (self.PACE.week < week)) | (self.PACE.season == S - 1))]
        w2 = np.where(pc.season == S, 1.0, 0.15)
        sp = shrink((w2 * pc.sdt).sum(), (w2 * pc.ndt).sum(), self.lg_pace, 60)
        pace = float(np.clip(sp / self.lg_pace, .88, 1.12))
        return round(float(pr), 3), round(pace, 3)

def lines_for(season, week):
    g = pd.read_csv(f'{D}/games.csv')
    return g[(g.season == season) & (g.week == week) & (g.game_type == 'REG')]

if __name__ == '__main__':
    b = Builder(2026)
    print(b.lg_np, b.lg_pace, b.lg_cat)
    print(json.dumps(b.team_players('ATL', 3), indent=0)[:3000])
    print(b.team_env('ATL', 3))


# ======================= defense profiles (v3.1) ===========================
# What each defense has allowed, as of a given week, relative to league:
# yards per designed carry, yards per target, where targets go (RB/WR/TE),
# how touchdowns split between rushing and passing, and — from charting —
# man-coverage, single-high and blitz rates. Everything is shrunk to league.
def _pbp_def(p):
    two = p.two_point_attempt.fillna(0) == 1
    runs = p[(p.play_type == 'run') & (p.qb_scramble.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0) & ~two]
    tg = p[(p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & ~two & p.receiver_player_id.notna()]
    return runs, tg

class DefBook:
    def __init__(self, b):
        self.b = b
        P = b.P
        self.runs, self.tg = _pbp_def(P)
        pos = b.R['position'].replace({'FB': 'RB'})
        self.tg = self.tg.assign(rpos=self.tg.receiver_player_id.map(pos).fillna('WR'))
        self.tds = P[(P.rush_touchdown == 1) | (P.pass_touchdown == 1)]
        self.tds = self.tds.assign(rpos=self.tds.receiver_player_id.map(pos))
        # charting: participation (man/zone, coverage shell) and FTN (blitzers)
        part = []
        for s in (b.season - 1, b.season):
            f = f'{D}/pbp_participation_{s}.parquet'
            if os.path.exists(f):
                x = pd.read_parquet(f, columns=['nflverse_game_id', 'play_id', 'possession_team', 'defense_man_zone_type', 'defense_coverage_type'])
                x['season'] = s; part.append(x)
        self.part = pd.concat(part) if part else None
        ftn = []
        for s in (b.season - 1, b.season):
            f = f'{D}/ftn_charting_{s}.parquet'
            if os.path.exists(f):
                x = pd.read_parquet(f, columns=['nflverse_game_id', 'nflverse_play_id', 'season', 'week', 'n_blitzers', 'n_pass_rushers'])
                ftn.append(x)
        self.ftn = pd.concat(ftn) if ftn else None
        g = P[['game_id', 'week', 'season', 'posteam', 'defteam', 'play_id', 'qb_dropback']].dropna(subset=['defteam'])
        if self.part is not None:
            self.part = self.part.merge(g.rename(columns={'game_id': 'nflverse_game_id'}), on=['nflverse_game_id', 'play_id', 'season'], how='inner')
            self.part = self.part[self.part.defense_man_zone_type.isin(['MAN_COVERAGE', 'ZONE_COVERAGE'])]
        if self.ftn is not None:
            self.ftn = self.ftn.merge(g.rename(columns={'game_id': 'nflverse_game_id', 'play_id': 'nflverse_play_id'}), on=['nflverse_game_id', 'nflverse_play_id', 'season', 'week'], how='inner')
            self.ftn = self.ftn[self.ftn.qb_dropback == 1]
        L = self.b.season - 1
        r, t = self.runs[self.runs.season == L], self.tg[self.tg.season == L]
        self.lg = dict(ypc=r.rushing_yards.mean(), ypt=t.receiving_yards.fillna(0).mean(),
                       share={k: (t.rpos == k).mean() for k in ('RB', 'WR', 'TE')},
                       rtd=(self.tds[self.tds.season == L].rush_touchdown == 1).mean())
        rt = self.tds[(self.tds.season == L) & (self.tds.pass_touchdown == 1)]
        self.lg['tdpos'] = {k: (rt.rpos == k).mean() for k in ('RB', 'WR', 'TE')}
        if self.part is not None:
            pl = self.part[self.part.season == L] if (self.part.season == L).any() else self.part
            self.lg['man'] = (pl.defense_man_zone_type == 'MAN_COVERAGE').mean()
            cov = pl.defense_coverage_type
            self.lg['mofc'] = cov.isin(['COVER_1', 'COVER_3', 'COVER_0']).sum() / max(1, cov.notna().sum())
        if self.ftn is not None:
            fl = self.ftn[self.ftn.season == L] if (self.ftn.season == L).any() else self.ftn
            self.lg['blitz'] = (fl.n_blitzers > 0).mean()

    def _w(self, df, week):
        S = self.b.season
        m = ((df.season == S) & (df.week < week)) | (df.season == S - 1)
        d = df[m]
        return d, np.where(d.season == S, 1.0, 0.35)

    def profile(self, team, week):
        lg = self.lg; out = {}
        r, w = self._w(self.runs[self.runs.defteam == team], week)
        out['ypc'] = float(shrink((w * r.rushing_yards.fillna(0)).sum(), w.sum(), lg['ypc'], 200) / lg['ypc'])
        t, w = self._w(self.tg[self.tg.defteam == team], week)
        out['ypt'] = float(shrink((w * t.receiving_yards.fillna(0)).sum(), w.sum(), lg['ypt'], 200) / lg['ypt'])
        out['tgt'] = {k: float(shrink((w * (t.rpos == k)).sum(), w.sum(), lg['share'][k], 250) / lg['share'][k]) for k in ('RB', 'WR', 'TE')}
        d, w = self._w(self.tds[self.tds.defteam == team], week)
        out['rtd'] = float(shrink((w * (d.rush_touchdown == 1)).sum(), w.sum(), lg['rtd'], 30) / lg['rtd'])
        pt = d.pass_touchdown == 1
        out['tdpos'] = {k: float(shrink((w * (pt & (d.rpos == k))).sum(), (w * pt).sum(), lg['tdpos'][k], 25) / lg['tdpos'][k]) for k in ('RB', 'WR', 'TE')}
        if self.part is not None and 'man' in lg:
            c, w = self._w(self.part[self.part.defteam == team], week)
            out['man'] = float(shrink((w * (c.defense_man_zone_type == 'MAN_COVERAGE')).sum(), w.sum(), lg['man'], 120))
            cv = c.defense_coverage_type.notna()
            out['mofc'] = float(shrink((w * c.defense_coverage_type.isin(['COVER_1', 'COVER_3', 'COVER_0'])).sum(), (w * cv).sum(), lg['mofc'], 120))
        if self.ftn is not None and 'blitz' in lg:
            f, w = self._w(self.ftn[self.ftn.defteam == team], week)
            out['blitz'] = float(shrink((w * (f.n_blitzers > 0)).sum(), w.sum(), lg['blitz'], 120))
        return {k: (round(v, 4) if isinstance(v, float) else {kk: round(vv, 4) for kk, vv in v.items()}) for k, v in out.items()}
