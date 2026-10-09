#!/usr/bin/env python3
"""Redzone Desk, research edition. Book line first, facts second, small stated nudges third.

    python3 build.py <nflverse dir> <ext dir> [week]   ->  site/picks_w<week>.json (+ research_w<week>.json)

No simulation, no team ratings, no fitted model. Every number on the page is either
  * a sportsbook price (the starting point), or
  * a count/average of plays and games that already happened (the facts), or
  * a nudge computed from one of those facts with a fixed, written-down weight (RULES below).
"""
import json
import math
import os
import re
import sys
from datetime import datetime, timezone
from statistics import NormalDist

import numpy as np
import pandas as pd

import players as pl
import trends as tr

H = os.path.dirname(os.path.abspath(__file__))
D, EXT = sys.argv[1], sys.argv[2]
WEEK = int(sys.argv[3]) if len(sys.argv) > 3 else 5
SEASON = 2026
N = NormalDist()

# ------------------------------------------------------------------ the rules (every weight on the page) ---------
RULES = {
    'td': {
        '_about': 'Anytime TD. Start: implied chance of the best available price. Each fact moves the log-odds by at most its cap; the sum is capped at +/-0.30 (about +/-6 points on a 30% player).',
        'funnel': {'w': 0.6, 'cap': 0.15, 'shrink_games': 4,
                   'what': "TDs this defense has allowed to the player's position per game this season vs the league, pulled 4 games toward average"},
        'matchup': {'w': 1.0, 'cap': 0.10, 'what': 'coverage fit (WR/TE: his man/zone splits x this defense\'s man rate and yards allowed) or run fit (RB: his inside/outside mix x yards this defense allows inside/outside)'},
        'red_zone_d': {'w': 0.5, 'cap': 0.06, 'shrink_trips': 10, 'what': "share of opponents' red-zone trips this defense turns into TDs vs the league"},
        'vs_team': {'w': 0.15, 'cap': 0.05, 'min_games': 2, 'what': 'his TDs per game against this opponent since 2019 vs his own rate'},
        'form': {'hot': 0.04, 'cold': -0.04, 'what': 'scored in 3+ straight games (+) or no TD in 6+ straight (-)'},
        'total_cap': 0.30,
    },
    'total': {
        '_about': 'Game total. Start: the book total and its no-vig over price. Facts move a Desk total in points; P(over) = no-vig chance shifted by (Desk - book) / 13 points (the spread of NFL totals around the closing line).',
        'red_zone': {'w': 0.5, 'cap': 2.0, 'shrink_trips': 10, 'pts_per_td_swing': 4.0, 'what': 'both offenses\' red-zone TD rate vs the other defense\'s TD rate allowed, times red-zone trips per game'},
        'pace': {'w': 0.5, 'cap': 1.5, 'pts_per_play': 0.33, 'what': 'combined plays per game (offense run + defense faced) vs the league'},
        'ou_form': {'w': 0.15, 'cap': 1.5, 'what': 'how far both teams\' games have landed over/under the closing total this season'},
        'h2h': {'w': 0.15, 'cap': 1.0, 'what': 'last 6 meetings, points vs the closing total'},
        'sd': 13.0,
        'total_cap': 4.0,
    },
    'yards': {
        '_about': 'Player yardage over/under. Start: DraftKings (else FanDuel/BetMGM/...) no-vig over chance. Facts move his expected yards; P(over) = no-vig chance shifted by yards / SD, SD = 0.55 x line + 12 (receiving) or 0.45 x line + 12 (rushing). Sum capped at 15% of the line.',
        'def_pos': {'w': 0.5, 'cap': 0.10, 'shrink_games': 4, 'what': 'yards this defense allows to the position per game vs league'},
        'matchup': {'w': 0.6, 'cap': 0.08, 'what': 'coverage fit or run fit, as above'},
        'hit_rate': {'w': 0.15, 'cap': 0.05, 'min_games': 4, 'what': 'share of his 2025-26 games over this exact line'},
        'vs_team': {'w': 0.10, 'cap': 0.04, 'min_games': 2, 'what': 'his yards per game against this opponent vs the line'},
        'total_cap': 0.15,
    },
    'coverage': {'shrink_targets': 15, 'seasons': '2024-25 receiver splits (nflverse participation charting)',
                 'source_2026': 'Sharp Football Analysis, NFL Man & Zone Coverage Rates (page updated Oct 6 2026, through Week 4): sharp_coverage_2026.csv',
                 'scale': "Sharp's man rate runs lower than the charting behind the receiver splits (league 18% vs 40% on targeted throws), so each defense keeps its distance from Sharp's league average and is placed on the charting scale (log-odds shift). Same for middle-closed (single-high) vs middle-open (two-high).",
                 'fit': 'coverage fit = average of the man/zone fit and the single-high/two-high fit'},
}

BOOK_ORDER = ['DraftKings', 'FanDuel', 'BetMGM', 'BetRivers', 'Bovada', 'BetOnline.ag']


def implied(o):
    o = float(o)
    return 100 / (o + 100) if o > 0 else -o / (-o + 100)


def logit(p):
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def sig(x):
    return 1 / (1 + math.exp(-x))


def clip(x, c):
    return max(-c, min(c, x))


def norm(s):
    s = re.sub(r"[^a-z ]", '', str(s).lower().replace('-', ' '))
    return ' '.join(w for w in s.split() if w not in ('jr', 'sr', 'ii', 'iii', 'iv', 'v'))


def gid(away, home):
    return f'{away.lower()}-{home.lower()}'


def pts(p0, dl):
    """A log-odds nudge shown as percentage points at the starting chance."""
    return 100 * (sig(logit(p0) + dl) - p0)


# ------------------------------------------------------------------ load ------------------------------------------
G = pd.read_csv(f'{D}/games.csv')
G['gametime'] = G.gametime.astype(str)
T = tr.team_games(G)
slate = G[(G.season == SEASON) & (G.week == WEEK)].sort_values(['gameday', 'gametime', 'game_id'])
prime_ids = set(G[G.gametime >= '19:00'].game_id)

pbp = pl.load_pbp(D, range(2019, SEASON + 1))
PG = pl.player_games(pbp, prime_ids)
TG = pl.team_game_totals(pbp[pbp.season == SEASON])

rw = pd.read_parquet(f'{D}/roster_weekly_{SEASON}.parquet')
rw = rw.sort_values('week').groupby('gsis_id').tail(1)
NAME = dict(zip(rw.gsis_id, rw.full_name))
POS = dict(zip(rw.gsis_id, rw.position))
TEAM = dict(zip(rw.gsis_id, rw.team.replace({'LAR': 'LA'})))
BYNAME = {(norm(n), t): g for g, n, t in zip(rw.gsis_id, rw.full_name, rw.team.replace({'LAR': 'LA'}))}

inj = pd.read_parquet(f'{D}/injuries_{SEASON}.parquet')
inj = inj[inj.week == WEEK]
NEWS = json.load(open(os.path.join(H, f'news_w{WEEK}.json')))
REPORTED = json.load(open(os.path.join(H, f'reported_w{WEEK}.json')))
OUT = {n for n, x in NEWS['players'].items() if x['s'] == 'out'} | set(inj[inj.report_status == 'Out'].full_name)

# book prices: anytime TD (best US price, jaredpatchett/NFL-Model live pull) and yardage lines (nfl-player-prop-opportunity)
tdj = json.load(open(f'{EXT}/jp/data/player_td.json'))
TDP = {}
for p in tdj['players']:
    m = p.get('market') or {}
    if m.get('anytime_td_price') is not None:
        TDP[p['player_id']] = dict(odds=int(m['anytime_td_price']), team=p['team'], pos=p['position'], opp=p['opponent'])
TD_AT = tdj['generated_at']

pp = pd.read_csv(f'{EXT}/pp/data/latest/player_props.csv')
pp = pp[(pp.Week == WEEK) & (pp['Market Window'] == 'Full Game') & pp.Bookmaker.isin(BOOK_ORDER)]
PROPS = {}
for (player, mk, home, away), grp in pp.groupby(['Player', 'Market Key', 'Home', 'Away']):
    for bk in BOOK_ORDER:
        b = grp[grp.Bookmaker == bk]
        o, u = b[b.Side == 'Over'], b[b.Side == 'Under']
        if len(o) and len(u):
            line = o.Line.iloc[0]
            u = u[u.Line == line]
            if not len(u):
                continue
            io, iu = implied(o['American Odds'].iloc[0]), implied(u['American Odds'].iloc[0])
            PROPS[(norm(player), mk)] = dict(line=float(line), over=int(o['American Odds'].iloc[0]), under=int(u['American Odds'].iloc[0]),
                                              p_over=io / (io + iu), book=bk, home=home, away=away, name=player)
            break
PROPS_AT = pp['Last Update'].max()

# ------------------------------------------------------------------ league tables ---------------------------------
cov_r, cov_sh, cov_d, cov_lg, cov_qb = pl.coverage_tables(D, [2024, 2025], pbp)
cov_r = cov_r.set_index('pid')
cov_d = cov_d.set_index('defteam')
# 2026 coverage from Sharp Football (through Week 4), moved onto the scale of the charting behind the receiver splits
FULL = {v: k for k, v in tr.NAMES.items()}
SH = pd.read_csv(os.path.join(H, 'sharp_coverage_2026.csv'))
SH['team'] = SH.Team.map(lambda s: FULL[s.split()[-1]])
SH = SH.set_index('team')
SH['mz'] = SH['Man Rate'] / (SH['Man Rate'] + SH['Zone Rate'])
SH['hi'] = SH['Middle Closed Rate'] / (SH['Middle Closed Rate'] + SH['Middle Open Rate'])
SH['man_rk'] = SH['Man Rate'].rank(ascending=False, method='min').astype(int)
SH['hi_rk'] = SH['Middle Closed Rate'].rank(ascending=False, method='min').astype(int)
HI_SHELLS, LO_SHELLS = {'COVER_0', 'COVER_1', 'COVER_3'}, {'COVER_2', 'COVER_4', 'COVER_6', 'COVER_9', '2_MAN'}
_sh = cov_sh.groupby('defense_coverage_type').n.sum()
LG_HI = _sh[_sh.index.isin(HI_SHELLS)].sum() / _sh[_sh.index.isin(HI_SHELLS | LO_SHELLS)].sum()
to_scale = lambda x, lg_src, lg_dst: sig(logit(lg_dst) + logit(x) - logit(lg_src))
MAN, HI = {}, {}
for t in SH.index:
    MAN[t] = (to_scale(SH.loc[t, 'mz'], SH.mz.mean(), cov_lg['man']), SH.loc[t])
    HI[t] = to_scale(SH.loc[t, 'hi'], SH.hi.mean(), LG_HI)

ftn = pd.read_parquet(f'{D}/ftn_charting_{SEASON}.parquet')
O, Dd, slg = pl.style_tables(pbp, ftn, SEASON)

p26 = pbp[(pbp.season == SEASON) & (pbp.season_type == 'REG')]
games_def = p26.groupby('defteam').game_id.nunique()
games_off = p26.groupby('posteam').game_id.nunique()

# defense allowed by position this season
g26 = PG[PG.season == SEASON].copy()
g26['pos'] = g26.pid.map(POS)
g26.loc[g26.pos == 'FB', 'pos'] = 'RB'
ALLOW = g26.groupby(['defteam', 'pos']).agg(td=('td', 'sum'), recY=('recY', 'sum'), rushY=('rushY', 'sum')).reset_index()
ALLOW['g'] = ALLOW.defteam.map(games_def)
LGPOS = ALLOW.groupby('pos').agg(td=('td', 'sum'), recY=('recY', 'sum'), rushY=('rushY', 'sum'), g=('g', 'sum'))
LGPOS = LGPOS.div(LGPOS.g, axis=0)
ALLOW = ALLOW.set_index(['defteam', 'pos'])

# red zone and pace this season
tg = TG.copy()
OFF = tg.groupby('posteam').agg(plays=('plays', 'sum'), trips=('rzTrips', 'sum'), rztd=('rzTD', 'sum'), g=('game_id', 'nunique'))
DEF = tg.groupby('defteam').agg(plays=('plays', 'sum'), trips=('rzTrips', 'sum'), rztd=('rzTD', 'sum'), g=('game_id', 'nunique'))
LG_RZ = OFF.rztd.sum() / OFF.trips.sum()
LG_TRIPS = OFF.trips.sum() / OFF.g.sum()
LG_PLAYS = OFF.plays.sum() / OFF.g.sum()

# run direction: yards per carry this defense allows inside / outside, and each back's inside share (2025-26)
ru = pbp[(pbp.rush_attempt == 1) & (pbp.qb_scramble != 1) & pbp.run_location.notna() & (pbp.two_point_attempt != 1)].copy()
ru['inside'] = ru.run_gap.isin(['guard']) | (ru.run_location == 'middle')
r26 = ru[(ru.season == SEASON) & (ru.season_type == 'REG')]
LG_YPC = r26.groupby('inside').yards_gained.mean()
DYPC = r26.groupby(['defteam', 'inside']).yards_gained.agg(['sum', 'size']).unstack('inside')
RB_IN = ru[ru.season >= SEASON - 1].groupby('rusher_player_id').inside.agg(['mean', 'size'])


def def_ypc(team, inside):
    s, n = DYPC.loc[team, ('sum', inside)], DYPC.loc[team, ('size', inside)]
    return pl.shrink(s, n, LG_YPC[inside], 40), int(n)


# ------------------------------------------------------------------ player facts ----------------------------------

def team_looks(team, games):
    t = PG[(PG.posteam == team) & PG.game_id.isin(games)]
    return t.tgt.sum(), (t.rzT + t.rzC).sum()


def player_facts(pid, team, opp, prime):
    """(facts, numbers) for one player. Facts are sentences; numbers feed the nudges."""
    me = PG[PG.pid == pid]
    s26 = me[me.season == SEASON]
    pos = POS.get(pid, TDP.get(pid, {}).get('pos', ''))
    name = NAME.get(pid, pid)
    f, num = [], {}
    if len(s26):
        n = len(s26)
        ttg, trz = team_looks(s26.posteam.iloc[-1], s26.game_id)
        rz = int((s26.rzT + s26.rzC).sum())
        if pos in ('WR', 'TE'):
            f.append(f"2026: {int(s26.tgt.sum())} targets in {n} games ({s26.tgt.sum() / max(1, ttg):.0%} of the team's targets when he played), "
                     f"{int(s26.rec.sum())} catches, {int(s26.recY.sum())} yds, {int(s26.td.sum())} TD.")
        elif pos == 'RB':
            f.append(f"2026: {int(s26.car.sum())} carries for {int(s26.rushY.sum())} yds ({s26.rushY.sum() / max(1, s26.car.sum()):.1f} per carry), "
                     f"{int(s26.tgt.sum())} targets, {int(s26.td.sum())} TD in {n} games.")
        elif pos == 'QB':
            f.append(f"2026 rushing: {int(s26.car.sum())} carries, {int(s26.rushY.sum())} yds, {int(s26.rushTD.sum())} TD in {n} games.")
        if rz and trz:
            i5 = int(s26.i5C.sum())
            ez = int(s26.ezT.sum())
            f.append(f"Red zone 2026: {rz} of his team's {int(trz)} red-zone looks ({rz / trz:.0%})" +
                     (f", {i5} carr{'y' if i5 == 1 else 'ies'} inside the 5" if i5 else '') + (f", {ez} end-zone target{'' if ez == 1 else 's'}" if ez else '') + '.')
        num['rz_share'] = rz / trz if trz else 0
    else:
        f.append('No offensive touches yet in 2026 (injury, new role or rookie).')
    # TD streak / drought across seasons, games he got the ball in
    seq = me.td.tolist()
    if seq:
        run = 0
        hot = seq[-1] > 0
        for x in reversed(seq):
            if (x > 0) == hot:
                run += 1
            else:
                break
        num['streak'] = run if hot else -run
        last10 = me.tail(10)
        if hot and run >= 2:
            f.append(f"Has scored in {run} straight games; TDs in {int((last10.td > 0).sum())} of his last {len(last10)}.")
        elif not hot and run >= 4:
            f.append(f"No TD in his last {run} games.")
        else:
            f.append(f"Scored in {int((last10.td > 0).sum())} of his last {len(last10)} games.")
    vs = me[me.defteam == opp]
    if len(vs) >= 2:
        avg_all = me[me.season >= SEASON - 2].scrimY.mean()
        f.append(f"Vs {opp} since 2019: {len(vs)} games, {vs.scrimY.mean():.0f} scrimmage yds per game (his 2024-26 average {avg_all:.0f}), {int(vs.td.sum())} TD.")
        num['vs'] = dict(n=len(vs), td_pg=vs.td.mean(), base_td=me[me.season >= SEASON - 2].td.mean(), recY=vs.recY.mean(), rushY=vs.rushY.mean())
    if prime:
        pr = me[(me.season >= SEASON - 3) & me.prime]
        if len(pr) >= 3:
            np_ = me[(me.season >= SEASON - 3) & ~me.prime]
            f.append(f"Prime time since {SEASON - 3}: {pr.scrimY.mean():.0f} scrimmage yds and {pr.td.mean():.2f} TD per game in {len(pr)} games "
                     f"(other games {np_.scrimY.mean():.0f} and {np_.td.mean():.2f}).")
    return f, num, pos, name


def coverage_matchup(pid, pos, name, team, opp, gname):
    if pid not in cov_r.index or opp not in cov_d.index:
        return None
    r = cov_r.loc[pid]
    nm, nz = r.get('n_man', 0), r.get('n_zone', 0)
    if nm + nz < 20:
        return None
    k = RULES['coverage']['shrink_targets']
    ypt = (r.yds_man + r.yds_zone) / (nm + nz)
    ym = pl.shrink(r.yds_man, nm, ypt, k)
    yz = pl.shrink(r.yds_zone, nz, ypt, k)
    m, sr = MAN[opp]
    h = HI[opp]
    fit_mz = math.log((m * ym + (1 - m) * yz) / ypt)
    s = cov_sh[cov_sh.receiver_player_id == pid]
    nh, yh = s[s.defense_coverage_type.isin(HI_SHELLS)].n.sum(), s[s.defense_coverage_type.isin(HI_SHELLS)].yds.sum()
    nl, yl = s[s.defense_coverage_type.isin(LO_SHELLS)].n.sum(), s[s.defense_coverage_type.isin(LO_SHELLS)].yds.sum()
    fit_hi = math.log((h * pl.shrink(yh, nh, ypt, k) + (1 - h) * pl.shrink(yl, nl, ypt, k)) / ypt) if nh + nl >= 20 else 0.0
    fit = (fit_mz + fit_hi) / 2
    dm = pl.shrink(cov_d.loc[opp, 'ypt_man'] * 60, 60, cov_lg['ypt_man'], 60) if pd.notna(cov_d.loc[opp, 'ypt_man']) else cov_lg['ypt_man']
    dz = pl.shrink(cov_d.loc[opp, 'ypt_zone'] * 150, 150, cov_lg['ypt_zone'], 150) if pd.notna(cov_d.loc[opp, 'ypt_zone']) else cov_lg['ypt_zone']
    q = 0.5 * math.log((m * dm + (1 - m) * dz) / (m * cov_lg['ypt_man'] + (1 - m) * cov_lg['ypt_zone']))
    score = fit + q
    rk_m = int(cov_d.ypt_man.rank().get(opp, 0))
    rk_z = int(cov_d.ypt_zone.rank().get(opp, 0))
    why = [f"{name} 2024-25: {r.yds_man / max(1, nm):.1f} yds/target vs man ({int(nm)} targets, {int(r.td_man)} TD), "
           f"{r.yds_zone / max(1, nz):.1f} vs zone ({int(nz)} targets, {int(r.td_zone)} TD)."]
    if pd.notna(r.get('share_man')) and pd.notna(r.get('share_zone')):
        why.append(f"He drew {r.share_man:.0%} of his team's targets against man and {r.share_zone:.0%} against zone in games he played.")
    if nh + nl >= 20:
        why.append(f"Vs single-high shells (Cover 0/1/3): {yh / max(1, nh):.1f} yds/target ({int(nh)}); vs two-high (Cover 2/4/6, 2-Man): {yl / max(1, nl):.1f} ({int(nl)}).")
    why.append(f"{opp} this season (Sharp Football, through Week 4): man {sr['Man Rate']:.1f}% ({pl.ordinal(sr.man_rk)} of 32), zone {sr['Zone Rate']:.1f}%, "
               f"middle closed {sr['Middle Closed Rate']:.1f}% ({pl.ordinal(sr.hi_rk)} of 32), middle open {sr['Middle Open Rate']:.1f}%. "
               f"On the scale of his splits that is about {m:.0%} man and {h:.0%} single-high (league {cov_lg['man']:.0%} and {LG_HI:.0%}).")
    why.append(f"{opp} in 2025 allowed {cov_d.loc[opp, 'ypt_man']:.1f} yds/target vs man ({pl.ordinal(rk_m)} fewest) and {cov_d.loc[opp, 'ypt_zone']:.1f} vs zone ({pl.ordinal(rk_z)} fewest).")
    sh = cov_sh[(cov_sh.receiver_player_id == pid) & (cov_sh.n >= 10)].copy()
    if len(sh) >= 2:
        sh['ypt'] = sh.yds / sh.n
        best, worst = sh.sort_values('ypt').iloc[-1], sh.sort_values('ypt').iloc[0]
        lab = lambda c: c.replace('COVER_', 'Cover ').replace('2_MAN', '2-Man')
        use = lambda c: cov_d.loc[opp].get(f'shell_{c}', np.nan)
        why.append(f"Best shell: {lab(best.defense_coverage_type)} ({best.ypt:.1f} yds/target, {int(best.n)} targets; {opp} used it on {use(best.defense_coverage_type):.0%} in 2025). "
                   f"Worst: {lab(worst.defense_coverage_type)} ({worst.ypt:.1f}; {opp} {use(worst.defense_coverage_type):.0%}).")
    why.append(f"Effect: coverage fit {100 * fit:+.0f}% (man/zone {100 * fit_mz:+.0f}%, single/two-high {100 * fit_hi:+.0f}%), defense quality {100 * q:+.0f}% on his yards per target.")
    lean = 'man-heavy' if sr.man_rk <= 8 else 'zone-heavy' if sr.man_rk >= 25 else 'mixed'
    return mu_row(pid, name, pos, team, opp, gname, f"{opp} {lean} coverage ({sr['Man Rate']:.0f}% man, {sr['Middle Closed Rate']:.0f}% single-high)",
                  'coverage', score, why)


def coverage_facts(off, dfn, qb, mus):
    """Coverage matchup facts for one offense: its QB vs this defense's 2026 coverage mix, the defense itself, and the best
    and worst receiver fits. cls 'o' = favors the offense, 'd' = favors the defense."""
    out = []
    if dfn not in SH.index:
        return out
    sr, m, h = SH.loc[dfn], MAN[dfn][0], HI[dfn]
    k = 60
    pid = BYNAME.get((norm(qb), off)) if isinstance(qb, str) else None
    if pid is not None and pid in cov_qb.index and cov_qb.loc[pid, ['n_man', 'n_zone']].sum() >= 60:
        r = cov_qb.loc[pid]
        ypa = (r.yds_man + r.yds_zone) / (r.n_man + r.n_zone)
        ym, yz = pl.shrink(r.yds_man, r.n_man, ypa, k), pl.shrink(r.yds_zone, r.n_zone, ypa, k)
        fit_mz = math.log((m * ym + (1 - m) * yz) / ypa)
        nh, nl = r.get('n_hi', 0), r.get('n_lo', 0)
        fit_hi = math.log((h * pl.shrink(r.get('yds_hi', 0), nh, ypa, k) + (1 - h) * pl.shrink(r.get('yds_lo', 0), nl, ypa, k)) / ypa) if nh + nl >= 60 else 0.0
        fit = (fit_mz + fit_hi) / 2
        vm, vz = r.yds_man / max(1, r.n_man), r.yds_zone / max(1, r.n_zone)
        lean = (f"{dfn} is man-heavy ({sr['Man Rate']:.0f}% man, {pl.ordinal(sr.man_rk)} of 32)" if sr.man_rk <= 8 else
                f"{dfn} is zone-heavy ({sr['Zone Rate']:.0f}% zone, {pl.ordinal(33 - sr.man_rk)} most)" if sr.man_rk >= 25 else
                f"{dfn} is near average ({sr['Man Rate']:.0f}% man, {pl.ordinal(sr.man_rk)} of 32)")
        shell = (f" {dfn} sits in single-high {sr['Middle Closed Rate']:.0f}% of the time ({pl.ordinal(sr.hi_rk)} of 32)." if sr.hi_rk <= 8 or sr.hi_rk >= 25 else '')
        verdict = ('a wash' if abs(fit) < .01 else f"{'helps' if fit > 0 else 'hurts'} him ({100 * fit:+.0f}% on yards per attempt)")
        txt = (f"{qb} 2024-25: {vm:.1f} yds/att vs man ({int(r.n_man)} att, {r.epa_man / max(1, r.n_man):+.2f} EPA/att), "
               f"{vz:.1f} vs zone ({int(r.n_zone)}, {r.epa_zone / max(1, r.n_zone):+.2f})"
               + (f"; {r.yds_hi / max(1, nh):.1f} vs single-high, {r.yds_lo / max(1, nl):.1f} vs two-high" if nh + nl >= 60 else '')
               + f". {lean}.{shell} Coverage mix {verdict}.")
        out.append(dict(text=txt, cls='o' if fit >= .02 else 'd' if fit <= -.02 else '', score=fit))
    elif isinstance(qb, str):
        out.append(dict(text=f"{qb}: fewer than 60 charted attempts in 2024-25, so no man/zone split.", cls='', score=0))
    rk = lambda c: pl.ordinal(int(cov_d[c].rank().get(dfn, 0)))
    out.append(dict(text=f"{dfn} defense 2026 (Sharp, through Week 4): man {sr['Man Rate']:.1f}% ({pl.ordinal(sr.man_rk)} of 32), zone {sr['Zone Rate']:.1f}%, "
                         f"single-high {sr['Middle Closed Rate']:.1f}% ({pl.ordinal(sr.hi_rk)}), two-high {sr['Middle Open Rate']:.1f}%. "
                         f"Last year it allowed {cov_d.loc[dfn, 'ypt_man']:.1f} yds/target vs man ({rk('ypt_man')} fewest) and {cov_d.loc[dfn, 'ypt_zone']:.1f} vs zone ({rk('ypt_zone')} fewest).",
                    cls='', score=0))
    mine = sorted([x for x in mus if x['off'] == off and x['role'] == 'coverage'], key=lambda x: -x['score'])
    for x in [x for x in mine if x['score'] >= .02][:3] + [x for x in reversed(mine) if x['score'] <= -.02][:2]:
        first = x['why'][0].split(': ', 1)[-1]
        out.append(dict(text=f"{x['n']} ({x['pos']}): {first.rstrip('.')}; {x['edge'].lower()} vs this coverage, {100 * x['score']:+.0f}% on his yards per target.",
                        cls='o' if x['score'] >= .03 else 'd' if x['score'] <= -.03 else '', score=x['score']))
    return out


def run_matchup(pid, name, team, opp, gname):
    if pid not in RB_IN.index or RB_IN.loc[pid, 'size'] < 25 or opp not in DYPC.index:
        return None
    sin = RB_IN.loc[pid, 'mean']
    di, ni = def_ypc(opp, True)
    do, no = def_ypc(opp, False)
    score = sin * math.log(di / LG_YPC[True]) + (1 - sin) * math.log(do / LG_YPC[False])
    why = [f"Run mix 2025-26: {sin:.0%} inside (middle/guard), {1 - sin:.0%} outside ({int(RB_IN.loc[pid, 'size'])} carries).",
           f"{opp} 2026: {DYPC.loc[opp, ('sum', True)] / max(1, ni):.1f} yds/carry allowed inside ({ni} carries; league {LG_YPC[True]:.1f}), "
           f"{DYPC.loc[opp, ('sum', False)] / max(1, no):.1f} outside ({no}; league {LG_YPC[False]:.1f}). Pulled 40 carries toward league average.",
           f"Effect: {100 * score:+.0f}% on his yards per carry."]
    return mu_row(pid, name, 'RB', team, opp, gname, f"{opp} run defense", f"{sin:.0%} inside / {1 - sin:.0%} outside", score, why)


def mu_row(pid, name, pos, team, opp, gname, vs, role, score, why):
    edge = 'Edge' if score >= .08 else 'Slight edge' if score >= .03 else 'Tough' if score <= -.08 else 'Slightly tough' if score <= -.03 else 'Even'
    return dict(pid=pid, id=f'{SEASON}w{WEEK}-{gname}-mu-{pid}', n=name, pos=pos, off=team, dfn=opp, vs=vs, role=role,
                edge=edge, score=round(score, 3), why=why, side=None, week=WEEK)


# ------------------------------------------------------------------ book-anchored picks -----------------------------

def td_pick(pid, info, facts, num, mu, opp, gname, gtxt):
    p0 = implied(info['odds'])
    R = RULES['td']
    pos = info['pos'] if info['pos'] != 'FB' else 'RB'
    why = [f"Book: best available price {'+' if info['odds'] > 0 else ''}{info['odds']} = {p0:.0%} implied."]
    dl = 0.0
    # funnel
    if (opp, pos) in ALLOW.index or pos in LGPOS.index:
        a = ALLOW.loc[(opp, pos)] if (opp, pos) in ALLOW.index else None
        g = games_def.get(opp, 0)
        td = a.td if a is not None else 0
        lg = LGPOS.loc[pos, 'td'] if pos in LGPOS.index else None
        if lg:
            r = pl.shrink(td, g, lg, R['funnel']['shrink_games']) / lg
            d = clip(R['funnel']['w'] * math.log(r), R['funnel']['cap'])
            dl += d
            why.append(f"{opp} has allowed {int(td)} TDs to {pos}s in {g} games ({td / max(1, g):.2f}/game; league {lg:.2f}): {pts(p0, d):+.1f} pts.")
    if mu:
        d = clip(R['matchup']['w'] * mu['score'], R['matchup']['cap'])
        dl += d
        why.append(f"{'Coverage' if mu['role'] == 'coverage' else 'Run'} fit vs {opp} ({mu['edge'].lower()}; {mu['why'][-1].replace('Effect: ', '').rstrip('.')}): {pts(p0, d):+.1f} pts.")
    if opp in DEF.index:
        dd = DEF.loc[opp]
        r = pl.shrink(dd.rztd, dd.trips, LG_RZ, R['red_zone_d']['shrink_trips'])
        d = clip(R['red_zone_d']['w'] * (r - LG_RZ) / LG_RZ, R['red_zone_d']['cap'])
        dl += d
        why.append(f"{opp} red zone: {int(dd.rztd)} TDs on {int(dd.trips)} trips allowed ({dd.rztd / max(1, dd.trips):.0%}; league {LG_RZ:.0%}): {pts(p0, d):+.1f} pts.")
    v = num.get('vs')
    if v and v['n'] >= R['vs_team']['min_games'] and v['base_td'] > 0:
        d = clip(R['vs_team']['w'] * math.log((v['td_pg'] + .1) / (v['base_td'] + .1)), R['vs_team']['cap'])
        dl += d
        why.append(f"Vs {opp}: {v['td_pg']:.2f} TD/game in {v['n']} games vs his {v['base_td']:.2f} since 2024: {pts(p0, d):+.1f} pts.")
    st = num.get('streak', 0)
    if st >= 3 or st <= -6:
        d = R['form']['hot'] if st >= 3 else R['form']['cold']
        dl += d
        why.append(f"Form: {'scored in ' + str(st) + ' straight' if st > 0 else 'no TD in ' + str(-st) + ' straight'}: {pts(p0, d):+.1f} pts.")
    dl = clip(dl, R['total_cap'])
    p = sig(logit(p0) + dl)
    why.append(f"Desk: {p:.0%} ({100 * (p - p0):+.1f} pts vs the book).")
    why += [x for x in facts if not x.startswith('2026:')][:3]
    return dict(id=f'{SEASON}w{WEEK}-{gname}-td-{pid}', type='Anytime TD', game=gtxt, gameId=gname, player=NAME.get(pid, pid),
                team=info['team'], pos=pos, text=f"{NAME.get(pid, pid)} anytime TD", prob=round(p, 4), book=round(p0, 4),
                price=dict(odds=info['odds'], implied=round(p0, 4), src='best US price'), why=why, pid=pid)


def yards_pick(pid, mk, prop, pos, num, mu, opp, gname, gtxt):
    R = RULES['yards']
    line = prop['line']
    rec = mk == 'player_reception_yds'
    col, lab = ('recY', 'receiving') if rec else ('rushY', 'rushing')
    sd = (0.55 if rec else 0.45) * line + 12
    p0 = prop['p_over']
    why = [f"Book: {prop['book']} {line} {lab} yds, over {prop['over']:+d} / under {prop['under']:+d} = {p0:.0%} over after removing the margin."]
    shift = 0.0
    ppos = 'RB' if pos == 'FB' else pos
    if pos in LGPOS.index:
        a = ALLOW.loc[(opp, ppos)] if (opp, ppos) in ALLOW.index else None
        g = games_def.get(opp, 0)
        lg = LGPOS.loc[ppos, col]
        y = a[col] if a is not None else 0
        r = pl.shrink(y, g, lg, R['def_pos']['shrink_games']) / lg
        d = clip(R['def_pos']['w'] * (r - 1), R['def_pos']['cap']) * line
        shift += d
        why.append(f"{opp} allows {y / max(1, g):.0f} {lab} yds per game to {ppos}s (league {lg:.0f}): {d:+.1f} yds.")
    if mu and ((rec and mu['role'] == 'coverage') or (not rec and mu['pos'] == 'RB')):
        d = clip(R['matchup']['w'] * mu['score'], R['matchup']['cap']) * line
        shift += d
        why.append(f"{'Coverage' if mu['role'] == 'coverage' else 'Run'} fit vs {opp} ({mu['edge'].lower()}): {d:+.1f} yds.")
    hist = PG[(PG.pid == pid) & (PG.season >= SEASON - 1)]
    # a line far above what he has been producing means a new role (starter out, trade): his old games don't apply
    role_change = len(hist) and line > 1.6 * max(1.0, hist.tail(6)[col].mean())
    if role_change:
        why.append(f"Hit rate not used: the line ({line}) is far above his recent {lab} average ({hist.tail(6)[col].mean():.0f}), so his role has changed.")
    elif len(hist) >= R['hit_rate']['min_games']:
        hr = (hist[col] > line).mean()
        h26 = hist[hist.season == SEASON]
        d = clip(R['hit_rate']['w'] * (hr - .5), R['hit_rate']['cap']) * line
        shift += d
        why.append(f"Over {line} in {int((h26[col] > line).sum())} of {len(h26)} games this season and {int((hist[col] > line).sum())} of {len(hist)} since 2025: {d:+.1f} yds.")
    v = num.get('vs')
    if v and v['n'] >= R['vs_team']['min_games']:
        vy = v['recY'] if rec else v['rushY']
        d = clip(R['vs_team']['w'] * (vy - line) / line, R['vs_team']['cap']) * line
        shift += d
        why.append(f"Vs {opp}: {vy:.0f} {lab} yds per game in {v['n']} games: {d:+.1f} yds.")
    shift = clip(shift, R['total_cap'] * line)
    p_over = N.cdf(N.inv_cdf(min(max(p0, .01), .99)) + shift / sd)
    side = 'over' if p_over >= .5 else 'under'
    prob = p_over if side == 'over' else 1 - p_over
    why.append(f"Desk: expected yards {shift:+.1f} vs the line, {p_over:.0%} over ({100 * (p_over - p0):+.1f} pts vs the book).")
    odds = prop['over'] if side == 'over' else prop['under']
    return dict(id=f"{SEASON}w{WEEK}-{gname}-{'recYds' if rec else 'rushYds'}-{pid}-{side}-{line}", type='Yards', game=gtxt, gameId=gname,
                text=f"{NAME.get(pid, prop['name'])} {side} {line} {lab} yds", prob=round(prob, 4),
                book=round(p0 if side == 'over' else 1 - p0, 4),
                price=dict(odds=odds, implied=round(implied(odds), 4), src=prop['book']), why=why, pid=pid)


def total_pick(g, away, home, gname, gtxt):
    R = RULES['total']
    line = g.total_line
    io, iu = implied(g.over_odds if pd.notna(g.over_odds) else -110), implied(g.under_odds if pd.notna(g.under_odds) else -110)
    p0 = io / (io + iu)
    why = [f"Book: total {line}, over {int(g.over_odds) if pd.notna(g.over_odds) else -110:+d} / under {int(g.under_odds) if pd.notna(g.under_odds) else -110:+d} = {p0:.0%} over after removing the margin."]
    adj = 0.0
    # red zone finishing
    rz = 0.0
    parts = []
    for off, dfn in ((away, home), (home, away)):
        if off in OFF.index and dfn in DEF.index:
            o, d = OFF.loc[off], DEF.loc[dfn]
            ro = pl.shrink(o.rztd, o.trips, LG_RZ, R['red_zone']['shrink_trips'])
            rd = pl.shrink(d.rztd, d.trips, LG_RZ, R['red_zone']['shrink_trips'])
            trips = (o.trips / o.g + d.trips / d.g) / 2
            rz += trips * ((ro - LG_RZ) + (rd - LG_RZ)) * R['red_zone']['pts_per_td_swing']
            parts.append(f"{off} offense {int(o.rztd)}/{int(o.trips)} red-zone TDs ({o.rztd / max(1, o.trips):.0%}) vs {dfn} defense {int(d.rztd)}/{int(d.trips)} ({d.rztd / max(1, d.trips):.0%})")
    d = clip(R['red_zone']['w'] * rz, R['red_zone']['cap'])
    adj += d
    why.append(f"Red zone: {'; '.join(parts)}; league {LG_RZ:.0%}: {d:+.1f} pts.")
    pace = 0.0
    if all(t in OFF.index and t in DEF.index for t in (away, home)):
        plays = (OFF.loc[away].plays / OFF.loc[away].g + DEF.loc[home].plays / DEF.loc[home].g +
                 OFF.loc[home].plays / OFF.loc[home].g + DEF.loc[away].plays / DEF.loc[away].g) / 2
        pace = (plays - 2 * LG_PLAYS) * R['pace']['pts_per_play']
        d = clip(R['pace']['w'] * pace, R['pace']['cap'])
        adj += d
        why.append(f"Pace: these offenses and defenses average {plays:.0f} combined plays a game (league {2 * LG_PLAYS:.0f}): {d:+.1f} pts.")
    tt = T[(T.season == SEASON) & T.team.isin([away, home]) & (T.date < g.gameday)]
    if len(tt):
        ou = tt.ou.mean()
        d = clip(R['ou_form']['w'] * ou, R['ou_form']['cap'])
        adj += d
        why.append(f"This season both teams' games average {ou:+.1f} pts vs the closing total ({away} {T[(T.season == SEASON) & (T.team == away) & (T.date < g.gameday)].ou.mean():+.1f}, {home} {T[(T.season == SEASON) & (T.team == home) & (T.date < g.gameday)].ou.mean():+.1f}): {d:+.1f} pts.")
    h = T[(T.team == home) & (T.opp == away) & (T.date < g.gameday)].tail(6)
    if len(h) >= 3 and h.ou.notna().all():
        d = clip(R['h2h']['w'] * h.ou.mean(), R['h2h']['cap'])
        adj += d
        why.append(f"Last {len(h)} meetings: {h.total.mean():.1f} pts per game, {h.ou.mean():+.1f} vs the closing total: {d:+.1f} pts.")
    adj = clip(adj, R['total_cap'])
    desk = line + adj
    p_over = N.cdf(N.inv_cdf(p0) + adj / R['sd'])
    side = 'Over' if p_over >= .5 else 'Under'
    prob = p_over if side == 'Over' else 1 - p_over
    why.append(f"Desk total {desk:.1f} vs book {line}: {p_over:.0%} over ({100 * (p_over - p0):+.1f} pts vs the book).")
    odds = int(g.over_odds if side == 'Over' else g.under_odds) if pd.notna(g.over_odds) else -110
    return dict(id=f'{SEASON}w{WEEK}-{gname}-tot-{side.lower()}', type='Total', game=gtxt, gameId=gname, line=line, side=side,
                text=f"{side} {line}", prob=round(prob, 4), book=round(p0 if side == 'Over' else 1 - p0, 4),
                price=dict(odds=odds, implied=round(implied(odds), 4), src='consensus (nflverse)'), why=why, desk=round(desk, 1))


def book_side_picks(g, away, home, gname, gtxt, facts):
    """Spread and moneyline at the book's no-vig numbers. No nudge: the facts are shown, the number is the book's."""
    ih, ia = implied(g.home_moneyline), implied(g.away_moneyline)
    ph = ih / (ih + ia)
    fav = home if ph >= .5 else away
    pf = max(ph, 1 - ph)
    ml = dict(id=f'{SEASON}w{WEEK}-{gname}-ml-{fav.lower()}', type='Winner', game=gtxt, gameId=gname, team=fav, text=f'{fav} win',
              prob=round(pf, 4), book=round(pf, 4),
              price=dict(odds=int(g.home_moneyline if fav == home else g.away_moneyline), implied=round(ih if fav == home else ia, 4), src='consensus (nflverse)'),
              why=[f"Book: {home} {int(g.home_moneyline):+d} / {away} {int(g.away_moneyline):+d} = {fav} {pf:.0%} after removing the margin. The Desk does not move sides; the facts are below."] + facts)
    hl = -g.spread_line
    dog = home if hl > 0 else away
    dl = abs(g.spread_line)
    so = g.home_spread_odds if dog == home else g.away_spread_odds
    oo = g.away_spread_odds if dog == home else g.home_spread_odds
    i1, i2 = implied(so if pd.notna(so) else -110), implied(oo if pd.notna(oo) else -110)
    pd_ = i1 / (i1 + i2)
    ats = dict(id=f'{SEASON}w{WEEK}-{gname}-ats-{dog.lower()}', type='Spread', game=gtxt, gameId=gname, team=dog, line=dl,
               text=f"{dog} +{dl:g}", prob=round(pd_, 4), book=round(pd_, 4),
               price=dict(odds=int(so) if pd.notna(so) else -110, implied=round(i1, 4), src='consensus (nflverse)'),
               why=[f"Book: {dog} +{dl:g} at {int(so) if pd.notna(so) else -110:+d} = {pd_:.0%} after removing the margin. The Desk does not move spreads; the facts are below."] + facts)
    return ml, ats


# ------------------------------------------------------------------ assemble ------------------------------------------
out_games, picks, coverage_rows, research = [], [], [], {}
lab = lambda gt, wd: {'Thursday': 'Thu', 'Sunday': 'Sun', 'Monday': 'Mon', 'Saturday': 'Sat'}.get(wd, wd[:3]) + ' ' + \
    datetime.strptime(gt, '%H:%M').strftime('%-I:%M') + ' ET'

for g in slate.itertuples():
    away, home = tr.FRANCHISE.get(g.away_team, g.away_team), tr.FRANCHISE.get(g.home_team, g.home_team)
    gname, gtxt = gid(away, home), f'{away} @ {home}'
    prime = tr.primetime(g.gametime)
    Tb = T[T.date < g.gameday]
    # ---- game facts
    side_facts = {}
    for team, opp, qb, coach in ((away, home, g.away_qb_name, g.away_coach), (home, away, g.home_qb_name, g.home_coach)):
        side_facts[team] = dict(team=tr.pick(tr.team_facts(Tb, team, opp, g), 5),
                                qb=tr.pick(tr.qb_facts(Tb, qb, team, opp, g), 3),
                                coach=tr.pick(tr.coach_facts(Tb, coach, team, g), 2))
    h2h = tr.pick(tr.h2h_facts(Tb, away, home, g), 3)
    styles = {away: pl.style_facts(O, Dd, slg, away, home)[:4], home: pl.style_facts(O, Dd, slg, home, away)[:4]}
    reported = [dict(text=t, src=s) for t, s in REPORTED.get(gname, [])]
    flat = [f['text'] for t in (away, home) for k in ('team', 'qb', 'coach') for f in side_facts[t][k]] + [f['text'] for f in h2h]
    kick = lab(g.gametime, g.weekday) + (' · London' if g.location == 'Neutral' else '')
    game = dict(id=gname, gid=f'{SEASON}w{WEEK}-{gname}', away=away, home=home, awayName=tr.NAMES[away], homeName=tr.NAMES[home],
                kick=kick, prime=prime,
                line=dict(spread=-g.spread_line, total=g.total_line, ml=dict(home=int(g.home_moneyline), away=int(g.away_moneyline)), src='consensus'),
                qbs={away: g.away_qb_name, home: g.home_qb_name},
                facts=dict(sides=side_facts, h2h=h2h, styles=styles, reported=reported))
    if pd.notna(g.result):
        game['final'] = dict(away=int(g.away_score), home=int(g.home_score))
        game['mu'] = []
        game['keys'] = []
        out_games.append(game)
        continue
    ml, ats = book_side_picks(g, away, home, gname, gtxt, flat[:8])
    tot = total_pick(g, away, home, gname, gtxt)
    game.update(ml=ml, ats=ats, tot=tot, deskTotal=tot['desk'])
    picks += [ml, ats, tot]
    # ---- players: everyone with a posted TD price, plus the starting QB
    priced = [(pid, x) for pid, x in TDP.items() if x['team'] in (away, home) and x['opp'] in (away, home)]
    priced.sort(key=lambda kv: -implied(kv[1]['odds']))
    mus, keys = [], []
    for pid, info in priced:
        name = NAME.get(pid, pid)
        team, opp = info['team'], (home if info['team'] == away else away)
        facts, num, pos, name = player_facts(pid, team, opp, prime)
        pos = info['pos'] if pos in ('', None) else pos
        mu = None
        if pos in ('WR', 'TE'):
            mu = coverage_matchup(pid, pos, name, team, opp, gname)
        elif pos in ('RB', 'FB'):
            mu = run_matchup(pid, name, team, opp, gname)
        if mu:
            mu['game'] = gtxt
            mu['side'] = 'away' if team == away else 'home'
            mus.append(mu)
        tdp = td_pick(pid, dict(info, pos=pos if pos in ('QB', 'RB', 'WR', 'TE') else info['pos']), facts, num, mu, opp, gname, gtxt)
        if name in OUT:
            tdp['out'] = True
        picks.append(tdp)
        if len([k for k in keys if k['team'] == team]) < 6 or pos == 'QB':
            keys.append(dict(pid=pid, name=name, team=team, pos=pos, facts=facts))
        for mk in ('player_reception_yds', 'player_rush_yds'):
            prop = PROPS.get((norm(name), mk))
            if prop and (mk == 'player_reception_yds' or pos in ('RB', 'QB')):
                yp = yards_pick(pid, mk, prop, pos, num, mu, opp, gname, gtxt)
                if name in OUT:
                    yp['out'] = True
                picks.append(yp)
    game['mu'] = sorted(mus, key=lambda m: -m['score'])
    game['facts']['coverage'] = {away: coverage_facts(away, home, g.away_qb_name, mus), home: coverage_facts(home, away, g.home_qb_name, mus)}
    game['keys'] = keys
    for t, o in ((away, home), (home, away)):
        if o in SH.index:
            r = SH.loc[o]
            coverage_rows.append(dict(team=o, opp=t, man=round(r['Man Rate'] / 100, 3), zone=round(r['Zone Rate'] / 100, 3),
                                      hi=round(r['Middle Closed Rate'] / 100, 3), lo=round(r['Middle Open Rate'] / 100, 3),
                                      manRk=int(r.man_rk), hiRk=int(r.hi_rk),
                                      manRk2025=int(cov_d.man.rank(ascending=False, method='min').get(o, 0)),
                                      blitz=round(Dd.loc[o, 'blitz'], 3) if o in Dd.index else None))
    out_games.append(game)

# ---- top plays: the largest moves off the book that land on the right side of 50% (TDs: Desk above book)
live = [p for p in picks if not p.get('out')]
tds = sorted([p for p in live if p['type'] == 'Anytime TD' and p['prob'] - p['book'] >= .02], key=lambda p: -(p['prob'] - p['book']))[:10]
tots = sorted([p for p in live if p['type'] == 'Total' and p['prob'] - p['book'] >= .02], key=lambda p: -(p['prob'] - p['book']))[:6]
yds = sorted([p for p in live if p['type'] == 'Yards' and p['prob'] - p['book'] >= .04], key=lambda p: -(p['prob'] - p['book']))[:10]
board = [p['id'] for p in sorted(tds + tots + yds, key=lambda p: -(p['prob'] - p['book']))]

# league-wide defense vs style table for the Matchups tab
dtab = []
for t in Dd.index:
    row = dict(team=t)
    for key, _, dlab in pl.STYLE:
        row[key] = None if pd.isna(Dd.loc[t, key + '_epa']) else round(float(Dd.loc[t, key + '_epa']), 3)
        row[key + '_rk'] = None if pd.isna(Dd.loc[t, key + '_rk']) else int(Dd.loc[t, key + '_rk'])
    for c in ('epa_pass', 'epa_rush'):
        row[c] = round(float(Dd.loc[t, c]), 3)
        row[c + '_rk'] = int(Dd.loc[t, c + '_rk'])
    dtab.append(row)

data = dict(season=SEASON, week=WEEK, label=f'Week {WEEK} · Oct 8–12', edition='research',
            generated=datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z'),
            prices=dict(td=TD_AT, props=PROPS_AT, lines='nflverse schedule consensus'),
            rules=RULES, games=out_games, board=board, picks=picks, coverage=coverage_rows,
            styles=dict(keys=[dict(key=k, off=o, dfn=d) for k, o, d in pl.STYLE], lg={k: round(float(v), 3) for k, v in slg.items() if pd.notna(v)}, defense=dtab))
os.makedirs(os.path.join(H, 'site'), exist_ok=True)


def clean(x):
    if isinstance(x, dict):
        return {k: clean(v) for k, v in x.items()}
    if isinstance(x, list):
        return [clean(v) for v in x]
    if isinstance(x, (np.floating,)):
        return None if np.isnan(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, float) and math.isnan(x):
        return None
    return x


json.dump(clean(data), open(os.path.join(H, 'site', f'picks_w{WEEK}.json'), 'w'), separators=(',', ':'))
json.dump(clean(NEWS), open(os.path.join(H, 'site', f'news_w{WEEK}.json'), 'w'), separators=(',', ':'))
n = lambda t: sum(p['type'] == t for p in picks)
print(f"week {WEEK}: {len(out_games)} games, {n('Anytime TD')} TD picks, {n('Yards')} yardage picks, {n('Total')} totals, board {len(board)}")
