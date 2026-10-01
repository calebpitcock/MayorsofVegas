"""Receiver vs defensive-back matchups for the Redzone Desk.
Defender coverage stats: PFR advanced defense (targets, catches, yards, TDs, INTs, air yards and YAC allowed per defender),
2025 at 0.3 per game and 2026 at 1.0, shrunk toward the league for his position group (a corner's numbers are noisy).
Roles: this week's ESPN depth chart (LCB/RCB outside, NB nickel, FS/SS), skipping anyone not on the active roster or
officially Out/Doubtful. Size and speed: roster height/weight, combine 40 and vertical.
Likely matchups (nobody publishes who covers whom for free): the most slot-heavy WR (slot share >= 45%) -> the nickel,
the other WRs -> the two outside corners, TEs -> the safeties. Each matchup changes the receiver's target share, catch
rate, yards per catch, deep-ball tail and red-zone weight (config.json "matchups"), and is written to g.mu for the page.
Usage: python3 db_matchups.py slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import nfl_build as nb
D = nb.D; S0 = 2026; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
CFG = json.load(open(os.path.join(HERE, 'config.json'))); W = CFG.get('matchups', {}).get('weight', 1.0)
clip = lambda x, lo, hi: float(min(hi, max(lo, x)))
K = dict(tgt=35.0)          # pseudo-targets of league-average coverage

def ht_in(h):
    if isinstance(h, str) and '-' in h: a, b = h.split('-'); return int(a) * 12 + int(b)
    try: return float(h)
    except (TypeError, ValueError): return np.nan

def main(path, week):
    S = json.load(open(path))
    R = nb.rosters(); pfr2g = {v: k for k, v in R['pfr_id'].dropna().items()}
    grp = lambda p: 'S' if p in ('S', 'SS', 'FS') else ('CB' if p in ('CB', 'DB', 'NB') else None)
    R = R.assign(position=R['depth_chart_position'].where(R['position'].isin(['DB']) & R['depth_chart_position'].notna(), R['position']))   # rosters list DBs as 'DB'
    # ---- defender coverage, shrunk by position group ----
    d = pd.concat([pd.read_csv(f'{D}/advstats_week_def_{s}.csv') for s in (S0 - 1, S0)])
    d = d[(d.game_type == 'REG') & (((d.season == S0) & (d.week < week)) | (d.season == S0 - 1))]
    d['w'] = np.where(d.season == S0, 1.0, 0.3); d['gid'] = d.pfr_player_id.map(pfr2g)
    d['grp'] = d.gid.map(R['position']).map(grp)
    d = d[d.grp.notna()].fillna({'def_targets': 0, 'def_completions_allowed': 0, 'def_yards_allowed': 0, 'def_receiving_td_allowed': 0, 'def_ints': 0,
                                 'def_air_yards_completed': 0, 'def_yards_after_catch': 0, 'def_missed_tackles': 0, 'def_tackles_combined': 0})
    d['air'] = d.def_adot.fillna(0) * d.def_targets
    for c in ('def_targets', 'def_completions_allowed', 'def_yards_allowed', 'def_receiving_td_allowed', 'def_ints', 'air', 'def_yards_after_catch', 'def_missed_tackles', 'def_tackles_combined'):
        d[c] = d[c] * d.w
    a = d.groupby(['gid', 'grp'])[['def_targets', 'def_completions_allowed', 'def_yards_allowed', 'def_receiving_td_allowed', 'def_ints', 'air', 'def_yards_after_catch', 'def_missed_tackles', 'def_tackles_combined']].sum().reset_index()
    raw26 = d[d.season == S0].groupby('gid').agg(t26=('def_targets', 'sum'), y26=('def_yards_allowed', 'sum'), c26=('def_completions_allowed', 'sum'), td26=('def_receiving_td_allowed', 'sum'))
    lg = {}
    for gname, x in a.groupby('grp'):
        t = x.def_targets.sum()
        lg[gname] = dict(ypt=x.def_yards_allowed.sum() / t, cr=x.def_completions_allowed.sum() / t, td=x.def_receiving_td_allowed.sum() / t,
                         int=x.def_ints.sum() / t, adot=x.air.sum() / t, yac=x.def_yards_after_catch.sum() / max(1, x.def_completions_allowed.sum()),
                         mt=x.def_missed_tackles.sum() / max(1, x.def_missed_tackles.sum() + x.def_tackles_combined.sum()))
    prof = {}
    for r in a.itertuples():
        L = lg[r.grp]; t = r.def_targets
        sh = lambda num, rate, k=K['tgt']: (num + k * rate) / (t + k)
        prof[r.gid] = dict(grp=r.grp, tgt=round(t, 1), ypt=sh(r.def_yards_allowed, L['ypt']), cr=sh(r.def_completions_allowed, L['cr']),
                           td=sh(r.def_receiving_td_allowed, L['td'], 80), int=sh(r.def_ints, L['int'], 80), adot=sh(r.air, L['adot'], 25),
                           yac=(r.def_yards_after_catch + 20 * L['yac']) / (r.def_completions_allowed + 20),
                           mt=(r.def_missed_tackles + 20 * L['mt']) / (r.def_missed_tackles + r.def_tackles_combined + 20))
    # ---- size and speed ----
    cb = pd.read_parquet(f'{D}/combine.parquet').dropna(subset=['pfr_id']).drop_duplicates('pfr_id', keep='last').set_index('pfr_id')
    # the normal size/speed gap between a position and the defenders who cover it (corners run faster 40s than
    # receivers, receivers are taller); only the difference beyond that is a mismatch
    cbm = cb[cb.season >= 2012].assign(h=cb.ht.map(ht_in))
    avg = {q: dict(forty=float(cbm[cbm.pos == q].forty.mean()), ht=float(cbm[cbm.pos == q].h.mean())) for q in ('WR', 'TE', 'CB', 'S')}
    gap = {('WR', 'CB'): {k: avg['CB'][k] - avg['WR'][k] for k in ('forty', 'ht')}, ('TE', 'S'): {k: avg['S'][k] - avg['TE'][k] for k in ('forty', 'ht')}}
    def meas(gid):
        h = R.loc[gid, 'height'] if gid in R.index else np.nan; w_ = R.loc[gid, 'weight'] if gid in R.index else np.nan
        pf = R.loc[gid, 'pfr_id'] if gid in R.index else None; f = v = np.nan
        if isinstance(pf, str) and pf in cb.index:
            f, v = cb.loc[pf, 'forty'], cb.loc[pf, 'vertical']
            if pd.isna(h): h = ht_in(cb.loc[pf, 'ht'])
        return dict(ht=None if pd.isna(h) else float(h), wt=None if pd.isna(w_) else float(w_), forty=None if pd.isna(f) else float(f), vert=None if pd.isna(v) else float(v))
    # ---- who is available and in which role ----
    dc = pd.read_csv(f'{D}/depth_charts_{S0}.csv', low_memory=False); dc = dc[dc.dt == dc.dt.max()]
    dc = dc[dc.pos_abb.isin(['LCB', 'RCB', 'NB', 'FS', 'SS'])].dropna(subset=['gsis_id']).sort_values('pos_rank')
    wk = pd.read_csv(f'{D}/roster_weekly_{S0}.csv', low_memory=False); wk = wk[wk.week == wk.week.max()]
    act = set(wk[wk.status == 'ACT'].gsis_id.dropna())
    out = set()
    fi = f'{D}/injuries_{S0}.csv'
    if os.path.exists(fi):
        ij = pd.read_csv(fi); out = set(ij[(ij.week == week) & ij.report_status.isin(['Out', 'Doubtful'])].gsis_id)
    # defenders ruled out before the official game statuses reach nflverse: overrides.json DEF_OUT = [[name, team], ...]
    _ov = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'overrides.json')
    for n_, t_ in (json.load(open(_ov)).get('DEF_OUT', []) if os.path.exists(_ov) else []):
        out |= set(R[(R.full_name == n_) & (R.team == t_)].index)
    name = R['full_name'].to_dict()
    def room(team):
        x = dc[dc.team.replace(REP) == team]; roles = {}; used = set()
        for role in ('LCB', 'RCB', 'NB', 'FS', 'SS'):
            for r in x[x.pos_abb == role].itertuples():
                if r.gsis_id in act and r.gsis_id not in out and r.gsis_id not in used:
                    roles[role] = r.gsis_id; used.add(r.gsis_id); break
        return roles
    # the yardstick is the average STARTER at his position (a receiver's own numbers already came mostly against starters)
    st_ids = {v for t in set(dc.team.replace(REP)) for v in room(t).values() if v in prof}
    for gname in ('CB', 'S'):
        xs = [prof[i] for i in st_ids if prof[i]['grp'] == gname]
        if xs: lg[gname] = {k: float(np.mean([x[k] for x in xs])) for k in ('ypt', 'cr', 'td', 'int', 'adot', 'yac', 'mt')}
    def dline(gid):
        p = prof.get(gid); L = lg[p['grp']] if p else None; m = meas(gid)
        return dict(id=gid, n=name.get(gid, gid), p=p, L=L, m=m, t26=float(raw26.t26.get(gid, 0)) if gid in raw26.index else 0.0,
                    y26=float(raw26.y26.get(gid, 0)) if gid in raw26.index else 0.0, c26=float(raw26.c26.get(gid, 0)) if gid in raw26.index else 0.0,
                    td26=float(raw26.td26.get(gid, 0)) if gid in raw26.index else 0.0)
    ngs = pd.read_parquet(f'{D}/ngs_receiving.parquet'); ngs = ngs[ngs.season.isin([S0 - 1, S0])]
    # ---- matchups ----
    n_mu = 0
    for g in S['games']:
        g['mu'] = []
        for side, off, dfn in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            rm = room(dfn)
            outs = [dline(rm[k]) for k in ('LCB', 'RCB') if k in rm]; nick = dline(rm['NB']) if 'NB' in rm else None
            saf = [dline(rm[k]) for k in ('FS', 'SS') if k in rm]
            recv = sorted([p for p in g['players'] if p['t'] == off and not p.get('out') and p['pos'] in ('WR', 'TE') and p['rec'] >= .06], key=lambda p: -p['rec'])
            wrs = [p for p in recv if p['pos'] == 'WR']; tes = [p for p in recv if p['pos'] == 'TE'][:2]
            slot_wr = max(wrs, key=lambda p: (p.get('rz') or {}).get('slot', 0), default=None)
            if slot_wr is not None and (slot_wr.get('rz') or {}).get('slot', 0) < .45: slot_wr = None
            for p in wrs[:4] + tes:
                if p['pos'] == 'TE': vs, role = saf, 'safeties'
                elif p is slot_wr and nick: vs, role = [nick], 'nickel (slot)'
                else: vs, role = outs, 'outside corners'
                vs = [v for v in vs if v['p']]
                if not vs: continue
                # averaged defender: rates relative to his group's league
                rel = lambda k: float(np.mean([v['p'][k] / v['L'][k] for v in vs]))
                ypt, cr, td, adot, yac, mt, it = rel('ypt'), rel('cr'), rel('td'), float(np.mean([v['p']['adot'] - v['L']['adot'] for v in vs])), rel('yac'), rel('mt'), rel('int')
                me = meas(p.get('id')); why = []; mult = dict(rec=1.0, cat=1.0, ypr=1.0, deep=1.0, gl=1.0)
                # coverage quality
                mult['ypr'] *= ypt ** (0.5 * W); mult['cat'] *= cr ** (0.6 * W); mult['gl'] *= td ** (0.35 * W); mult['rec'] *= ypt ** (0.35 * W)
                mult['cat'] *= it ** (-0.1 * W)
                # YAC: his yards after catch over expected vs what these defenders allow / missed tackles
                yoe = (p.get('rz') or {}).get('yac', 0.0)
                mult['ypr'] *= (yac * mt ** 0.3) ** (0.25 * W) * (1 + 0.02 * W * yoe * (yac - 1) * 5)
                # size and speed
                dh = [v['m']['ht'] for v in vs if v['m']['ht']]; df = [v['m']['forty'] for v in vs if v['m']['forty']]
                gp = gap[('TE', 'S') if p['pos'] == 'TE' else ('WR', 'CB')]
                size_raw = (me['ht'] - np.mean(dh)) if me['ht'] and dh else None; speed_raw = (np.mean(df) - me['forty']) if me['forty'] and df else None
                size = size_raw + gp['ht'] if size_raw is not None else None          # vs the usual height gap
                speed = speed_raw - gp['forty'] if speed_raw is not None else None     # vs the usual 40 gap
                if size is not None: mult['gl'] *= clip(1 + 0.02 * W * size, .88, 1.12); mult['cat'] *= clip(1 + 0.004 * W * size, .97, 1.03)
                if speed is not None: mult['deep'] *= clip(1 + 1.2 * W * speed, .85, 1.18); mult['ypr'] *= clip(1 + 0.3 * W * speed, .95, 1.06)
                # style: how deep defenders get tested vs how deep he runs
                ad = (p.get('fb') or {}).get('adot'); adl = (p.get('fb') or {}).get('adotLg')
                if ad is not None and adl is not None and abs(adot) >= 1.0:
                    fit = np.sign(ad - adl) * np.sign(adot)          # deep receiver vs defenders who get tested deep = good for him
                    mult['deep'] *= clip(1 + 0.06 * W * fit * min(2, abs(adot)), .9, 1.1)
                for k in mult: mult[k] = clip(mult[k], .7, 1.35)
                # apply
                p['rec'] = round(max(.004, p['rec'] * mult['rec']), 3); p['cat'] = round(clip(p['cat'] * mult['cat'], .3, .95), 3)
                p['ypr'] = round(p['ypr'] * mult['ypr'], 2); p['deep'] = round(clip(p['deep'] * mult['deep'], .5, 2.2), 3); p['gl'] = round(clip(p['gl'] * mult['gl'], .3, 3.5), 3)
                score = mult['rec'] * mult['cat'] * mult['ypr'] * mult['deep'] ** 0.3 - 1
                edge = 'Edge' if score >= .08 else 'Slight edge' if score >= .03 else 'Tough' if score <= -.08 else 'Slightly tough' if score <= -.03 else 'Even'
                names = ' / '.join(v['n'] for v in vs)
                for v in vs:
                    t26 = v['t26']; line = f"{v['n']} ({'safety' if v['p']['grp'] == 'S' else 'corner'}): "
                    line += (f"this season {t26:.0f} targets, {v['c26']:.0f} catches, {v['y26']:.0f} yds, {v['td26']:.0f} TD allowed; " if t26 else "no targets yet this season; ")
                    line += f"blended {v['p']['ypt']:.1f} yds/target (average starter {v['L']['ypt']:.1f}), {100 * v['p']['cr']:.0f}% caught (average starter {100 * v['L']['cr']:.0f}%)"
                    why.append(line)
                one = len(vs) == 1
                style = 'deeper (tested deep)' if adot >= 1 else 'shorter (gives up the underneath throws)' if adot <= -1 else 'about as deep'
                why.append(f"Style: passes thrown at {names if one else 'these defenders'} go {style} than at the average starter ({'+' if adot >= 0 else ''}{adot:.1f} yds)"
                           + (f"; {p['n']} averages {ad} yds downfield per target (league {adl})" if ad is not None else ''))
                if abs(yac - 1) >= .08: why.append(f"After the catch: {'these defenders allow' if len(vs) > 1 else 'he allows'} {100 * (yac - 1):+.0f}% yards after catch vs the average starter")
                why.append(f"Effect: targets {100 * (mult['rec'] - 1):+.0f}%, catch rate {100 * (mult['cat'] - 1):+.0f}%, yards per catch {100 * (mult['ypr'] - 1):+.0f}%, red-zone {100 * (mult['gl'] - 1):+.0f}%")
                why.append('Likely matchup, not confirmed: who covers whom is not published for free (based on alignment and the depth chart)')
                mu = dict(side=side, off=off, dfn=dfn, n=p['n'], pos=p['pos'], vs=names, role=role, edge=edge, score=round(float(score), 3), why=why)
                g['mu'].append(mu); p['mu'] = dict(vs=names, role=role, edge=edge, score=round(float(score), 3), why=why[:-2]); n_mu += 1
    json.dump(S, open(path, 'w'))
    print(f'matchups: {n_mu}; defenders with coverage stats {len(prof)}; league CB {lg["CB"]["ypt"]:.1f} yds/target, S {lg["S"]["ypt"]:.1f}')

if __name__ == '__main__': main(sys.argv[1], int(sys.argv[2]))
