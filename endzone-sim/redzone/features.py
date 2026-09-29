"""Redzone Desk player and team factors. Every factor here was tested and rejected for the DraftKings-anchored model
(HANDOFF.md, audit/tdfeat/RESULTS.md, audit/formation); the user asked to use them all with significant weight.
Weights live in config.json. Writes onto the slate:
  p.gl   x end-zone target share, inside-5 carry share and red-zone snap share (each vs the player's overall share)
  p.ypr  x receiving yards after catch over expected (nflfastR xYAC)
  p.ypc / p.ypr / p.gl  x player-vs-this-defense history (last 5 meetings vs his baseline)
  g.passRate            + team pass rate over expected (nflfastR xpass)
  g.form                formation run term, TE/RB shifts and slot shifts (formation.py, undamped), slot from a proxy
  p.rz                  the numbers behind each adjustment, for the pick explanations
Usage: python3 features.py slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..'); sys.path.insert(0, ROOT)
import nfl_build as nb, formation
D = nb.D
CFG = json.load(open(os.path.join(HERE, 'config.json')))
SEASON = 2026
COLS = ['game_id', 'play_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'yardline_100', 'pass_attempt',
        'sack', 'two_point_attempt', 'qb_scramble', 'qb_kneel', 'rusher_player_id', 'receiver_player_id', 'air_yards',
        'yards_after_catch', 'xyac_mean_yardage', 'complete_pass', 'pass_location', 'pass_oe', 'rushing_yards',
        'receiving_yards', 'rush_touchdown', 'pass_touchdown']
clip = lambda x, lo, hi: float(min(hi, max(lo, x)))

def load(s, week):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=COLS, low_memory=False)
    p = p[p.season_type == 'REG']
    return p[p.week < week] if s == SEASON else p

def frames(p):
    two = p.two_point_attempt.fillna(0) == 1
    runs = p[(p.play_type == 'run') & (p.qb_kneel.fillna(0) == 0) & ~two & p.rusher_player_id.notna()]
    des = runs[runs.qb_scramble.fillna(0) == 0]
    tg = p[(p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & ~two & p.receiver_player_id.notna()]
    return runs, des, tg

def share_ratio(sub, full, pidcol, K):
    """player's weighted share of `sub` plays vs his share of `full` plays, per (team, player), shrunk toward 1."""
    tf = full.groupby('posteam').w.sum(); pf = full.groupby(['posteam', pidcol]).w.sum()
    ts = sub.groupby('posteam').w.sum(); ps = sub.groupby(['posteam', pidcol]).w.sum()
    out = {}
    for (t, pid), x in pf.items():
        sh = x / tf[t]
        if sh < .02: continue
        s_team = ts.get(t, 0.0); s_p = ps.get((t, pid), 0.0)
        out[(t, pid)] = ((s_p + K * sh) / (s_team + K)) / sh
    return out

def main(path, week):
    S = json.load(open(path))
    cur = pd.concat([load(s, week) for s in (SEASON - 1, SEASON)])
    cur['w'] = np.where(cur.season == SEASON, 1.0, 0.3)
    runs, des, tg = frames(cur)
    # ---- red-zone roles ----
    ez = share_ratio(tg[tg.air_yards >= tg.yardline_100], tg, 'receiver_player_id', 6)
    i5 = share_ratio(des[des.yardline_100 <= 5], des, 'rusher_player_id', 5)
    opp = pd.concat([des.rename(columns={'rusher_player_id': 'pid'})[['posteam', 'pid', 'yardline_100', 'w']],
                     tg.rename(columns={'receiver_player_id': 'pid'})[['posteam', 'pid', 'yardline_100', 'w']]])
    rzo = share_ratio(opp[opp.yardline_100 <= 20], opp, 'pid', 10)
    # red-zone snap share from 2025 participation (who was on the field); 2026 participation is published after the season
    rzs = {}
    f = f'{D}/pbp_participation_{SEASON - 1}.parquet'
    if os.path.exists(f):
        pp = pd.read_parquet(f, columns=['nflverse_game_id', 'play_id', 'offense_players'])
        p25 = cur[(cur.season == SEASON - 1) & cur.play_type.isin(['run', 'pass'])][['game_id', 'play_id', 'posteam', 'yardline_100']]
        pp = pp.merge(p25, left_on=['nflverse_game_id', 'play_id'], right_on=['game_id', 'play_id'])
        pp = pp.assign(pid=pp.offense_players.str.split(';')).explode('pid').dropna(subset=['pid'])
        pp = pp[pp.pid.str.len() > 0].assign(w=1.0)
        team_plays = p25.assign(w=1.0)
        tf = team_plays.groupby('posteam').w.sum(); trz = team_plays[team_plays.yardline_100 <= 20].groupby('posteam').w.sum()
        pf = pp.groupby(['posteam', 'pid']).w.sum(); prz = pp[pp.yardline_100 <= 20].groupby(['posteam', 'pid']).w.sum()
        for (t, pid), x in pf.items():
            sh = x / tf[t]
            if sh < .15: continue
            rzs[(t, pid)] = ((prz.get((t, pid), 0.0) + 40 * sh) / (trz.get(t, 0.0) + 40)) / sh
    # ---- yards after catch over expected ----
    c = tg[(tg.complete_pass == 1) & tg.yards_after_catch.notna() & tg.xyac_mean_yardage.notna()]
    c = c.assign(e=c.w * (c.yards_after_catch - c.xyac_mean_yardage))
    yac = (c.groupby('receiver_player_id').e.sum() / (c.groupby('receiver_player_id').w.sum() + 30)).to_dict()
    # ---- team pass rate over expected (nflfastR pass_oe, percentage points) ----
    x = cur[cur.pass_oe.notna() & cur.play_type.isin(['run', 'pass'])]
    proe = ((x.w * x.pass_oe).groupby(x.posteam).sum() / (x.groupby('posteam').w.sum() + 150)).to_dict()
    # ---- slot proxy: share of targets over the middle within 15 air yards (no alignment data is free) ----
    pos = nb.rosters()['position'].replace({'FB': 'RB'})
    t2 = tg.assign(pos=tg.receiver_player_id.map(pos), mid=((tg.pass_location == 'middle') & tg.air_yards.between(-5, 15)).astype(float))
    lgmid = {P: (t2[t2.pos == P].w * t2[t2.pos == P].mid).sum() / t2[t2.pos == P].w.sum() for P in ('WR', 'TE')}
    midp = ((t2.w * t2.mid).groupby(t2.receiver_player_id).sum(), t2.groupby('receiver_player_id').w.sum())
    # ---- player vs this defense: last 5 meetings (2019+) vs his average over the 8 games before each ----
    hist = pd.concat([load(s, week) for s in range(2019, SEASON + 1)])
    hr, _, ht = frames(hist)
    a = hr.groupby(['game_id', 'season', 'week', 'defteam', 'rusher_player_id']).agg(ry=('rushing_yards', 'sum'), rtd=('rush_touchdown', 'sum')).reset_index().rename(columns={'rusher_player_id': 'pid'})
    b = ht.groupby(['game_id', 'season', 'week', 'defteam', 'receiver_player_id']).agg(recy=('receiving_yards', 'sum'), ctd=('pass_touchdown', 'sum')).reset_index().rename(columns={'receiver_player_id': 'pid'})
    pg = a.merge(b, on=['game_id', 'season', 'week', 'defteam', 'pid'], how='outer').fillna({'ry': 0, 'rtd': 0, 'recy': 0, 'ctd': 0})
    pg['td'] = ((pg.rtd + pg.ctd) > 0).astype(float)
    pg = pg[pg.pid.isin({p.get('id') for g in S['games'] for p in g['players']})].sort_values(['pid', 'season', 'week'])
    for k in ('ry', 'recy', 'td'):
        pg['b_' + k] = pg.groupby('pid')[k].transform(lambda s: s.shift(1).rolling(8, min_periods=3).mean())
    last8 = pg.groupby('pid').tail(8).groupby('pid')[['ry', 'recy', 'td']].mean()

    SL = {}
    W = CFG
    for g in S['games']:
        g.setdefault('rzt', {})
        for side, team, opp_t in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            pr = proe.get(team, 0.0)
            if W['pass_rate_over_expected']:
                g['passRate'][side] = round(clip(g['passRate'][side] + clip(W['pass_rate_over_expected'] * pr / 100, -.06, .06), .38, .70), 3)
            g['rzt'][side] = dict(proe=round(pr, 2))
        for p in g['players']:
            t, pid = p['t'], p.get('id'); opp_t = g['home'] if t == g['away'] else g['away']
            rz = {}
            r_ez = clip(ez.get((t, pid), 1.0), .5, 2.0); r_i5 = clip(i5.get((t, pid), 1.0), .5, 2.0)
            r_o = rzo.get((t, pid)); r_s = rzs.get((t, pid))
            parts = [v for v in (r_o, r_s) if v is not None]
            r_rz = clip(float(np.exp(np.mean(np.log(parts)))) if parts else 1.0, .6, 1.7)
            wr = (p['rush'] * 26) / max(1e-6, p['rush'] * 26 + p['rec'] * 32)
            glx = (wr * r_i5 ** W['inside5_carries'] + (1 - wr) * r_ez ** W['ez_targets']) * r_rz ** W['redzone_snaps']
            glx = clip(glx, .5, 2.2)
            rz.update(ez=round(r_ez, 3), i5=round(r_i5, 3), rzs=round(r_rz, 3), glx=round(glx, 3))
            if p['pos'] != 'QB':
                y = yac.get(pid, 0.0); m = clip(1 + W['yac_over_expected'] * y / max(6.0, p['ypr']), .85, 1.15)
                p['ypr'] = round(p['ypr'] * m, 2); rz.update(yac=round(y, 2), yprx=round(m, 3))
            # player vs this defense
            h = pg[(pg.pid == pid) & (pg.defteam == opp_t) & pg.b_ry.notna()].tail(5)
            if len(h):
                n = len(h); shr = n / (n + 2.0); base = last8.loc[pid] if pid in last8.index else None
                dry, drec, dtd = float((h.ry - h.b_ry).mean()), float((h.recy - h.b_recy).mean()), float((h.td - h.b_td).mean())
                pv = dict(n=n, ry=round(dry, 1), recy=round(drec, 1), td=round(dtd, 3), opp=opp_t)
                wv = W['player_vs_team_history']
                if base is not None and base.ry >= 10:
                    m = clip(1 + wv * shr * dry / max(25.0, base.ry), .75, 1.25); p['ypc'] = round(p['ypc'] * m, 2); pv['ypcx'] = round(m, 3)
                if base is not None and base.recy >= 10:
                    m = clip(1 + wv * shr * drec / max(25.0, base.recy), .75, 1.25); p['ypr'] = round(p['ypr'] * m, 2); pv['yprx'] = round(m, 3)
                if base is not None:
                    m = clip(1 + wv * shr * dtd / max(.2, base.td), .6, 1.4); glx *= m; pv['glx'] = round(m, 3)
                rz['pvo'] = pv
            p['gl'] = round(clip(p['gl'] * glx, .3, 3.5), 3)
            if W['slot_proxy'] and p['pos'] in ('WR', 'TE') and pid in midp[1].index:
                mid = (midp[0][pid] + 8 * lgmid[p['pos']]) / (midp[1][pid] + 8)
                SL[p['n']] = clip((0.32 if p['pos'] == 'WR' else 0.30) * mid / lgmid[p['pos']], .05, .9); rz['slot'] = round(SL[p['n']], 2)
            p['rz'] = rz
    if W['formation']:
        formation.DAMP, formation.CAP, formation.PCAP = W['formation_damp'], W['formation_cap'], W['position_shift_cap']
        F = json.load(open(os.path.join(ROOT, 'formation_2026.json')))
        formation.attach(S['games'], F, SL)
    S['redzone'] = dict(config=CFG, week=week)
    json.dump(S, open(path, 'w'))
    n = sum(len(g['players']) for g in S['games'])
    print(f'features: {len(S["games"])} games, {n} players, {len(SL)} slot estimates, {sum(1 for g in S["games"] for p in g["players"] if "pvo" in p.get("rz", {}))} with history vs this defense')

if __name__ == '__main__': main(sys.argv[1], int(sys.argv[2]))
