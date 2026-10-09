"""Player, coverage and defense-style facts from nflverse play-by-play (2019-2026), participation (man/zone charting,
2023-2025) and FTN charting (play-action, motion, shotgun; 2025-2026).

All of these are counts and averages of plays that already happened, with the sample size attached. Nothing is
simulated. The few places a number is pulled toward the league average ("shrunk") are marked; that only keeps a
four-game sample from looking more extreme than it is.
"""
import numpy as np
import pandas as pd

PBP_COLS = ['game_id', 'play_id', 'season', 'week', 'season_type', 'game_date', 'posteam', 'defteam', 'home_team',
            'away_team', 'pass_attempt', 'rush_attempt', 'qb_dropback', 'two_point_attempt', 'sack', 'epa', 'success',
            'yards_gained', 'air_yards', 'pass_length', 'pass_location', 'run_location', 'run_gap', 'complete_pass',
            'receiver_player_id', 'rusher_player_id', 'passer_player_id', 'pass_touchdown', 'rush_touchdown',
            'yardline_100', 'shotgun', 'fixed_drive', 'fixed_drive_result', 'play_type', 'qb_scramble', 'penalty']

LEAGUE_TEAMS = 32


def load_pbp(D, seasons):
    out = []
    for s in seasons:
        p = pd.read_parquet(f'{D}/play_by_play_{s}.parquet', columns=PBP_COLS)
        out.append(p)
    p = pd.concat(out, ignore_index=True)
    for c in ('posteam', 'defteam', 'home_team', 'away_team'):
        p[c] = p[c].replace({'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'})
    return p


def player_games(p, prime_ids):
    """One row per player per game: targets, catches, receiving and rushing yards and TDs, red-zone looks."""
    p = p[(p.two_point_attempt != 1) & p.season_type.isin(['REG', 'POST'])]
    tg = p[(p.pass_attempt == 1) & p.receiver_player_id.notna() & (p.sack != 1)].copy()
    tg['rz'] = tg.yardline_100 <= 20
    tg['ez'] = (tg.yardline_100 - tg.air_yards.fillna(-99)) <= 0
    tg['yds'] = np.where(tg.complete_pass == 1, tg.yards_gained, 0)
    rec = tg.groupby(['game_id', 'receiver_player_id', 'posteam', 'defteam']).agg(
        tgt=('play_id', 'size'), rec=('complete_pass', 'sum'), recY=('yds', 'sum'), recTD=('pass_touchdown', 'sum'),
        rzT=('rz', 'sum'), ezT=('ez', 'sum')).reset_index().rename(columns={'receiver_player_id': 'pid'})
    ru = p[(p.rush_attempt == 1) & p.rusher_player_id.notna()].copy()
    ru['rz'] = ru.yardline_100 <= 20
    ru['i5'] = ru.yardline_100 <= 5
    rus = ru.groupby(['game_id', 'rusher_player_id', 'posteam', 'defteam']).agg(
        car=('play_id', 'size'), rushY=('yards_gained', 'sum'), rushTD=('rush_touchdown', 'sum'),
        rzC=('rz', 'sum'), i5C=('i5', 'sum')).reset_index().rename(columns={'rusher_player_id': 'pid'})
    g = pd.merge(rec, rus, on=['game_id', 'pid', 'posteam', 'defteam'], how='outer').fillna(0)
    meta = p.groupby('game_id').agg(season=('season', 'first'), week=('week', 'first'), date=('game_date', 'first'),
                                     home_team=('home_team', 'first')).reset_index()
    g = g.merge(meta, on='game_id')
    g['home'] = g.posteam == g.home_team
    g['prime'] = g.game_id.isin(prime_ids)
    g['td'] = g.recTD + g.rushTD
    g['scrimY'] = g.recY + g.rushY
    return g.sort_values(['date', 'game_id'])


def team_game_totals(p):
    """Per offense per game: plays, red-zone trips, red-zone TDs, points proxy (for pace and finishing facts)."""
    p = p[p.season_type == 'REG']
    plays = p[(p.pass_attempt == 1) | (p.rush_attempt == 1)].groupby(['game_id', 'posteam', 'defteam']).size().rename('plays')
    d = p[p.fixed_drive.notna() & p.posteam.notna()].groupby(['game_id', 'posteam', 'defteam', 'fixed_drive']).agg(
        minyl=('yardline_100', 'min'), res=('fixed_drive_result', 'first')).reset_index()
    d['rz'] = d.minyl <= 20
    d['rztd'] = d.rz & (d.res == 'Touchdown')
    rz = d.groupby(['game_id', 'posteam', 'defteam']).agg(rzTrips=('rz', 'sum'), rzTD=('rztd', 'sum'))
    return pd.concat([plays, rz], axis=1).reset_index()


def shrink(num, den, prior, k):
    return (num + k * prior) / (den + k)


# ---------------------------------------------------------------- coverage (man/zone) -----------------------------

def coverage_tables(D, seasons, pbp):
    """Targets joined to the man/zone charting. Returns (receiver splits, defense splits, league numbers)."""
    parts = []
    for s in seasons:
        pa = pd.read_parquet(f'{D}/pbp_participation_{s}.parquet',
                             columns=['nflverse_game_id', 'play_id', 'defense_man_zone_type', 'defense_coverage_type'])
        parts.append(pa)
    pa = pd.concat(parts).rename(columns={'nflverse_game_id': 'game_id'})
    t = pbp[(pbp.pass_attempt == 1) & (pbp.sack != 1) & (pbp.two_point_attempt != 1) & pbp.season.isin(seasons)]
    t = t.merge(pa, on=['game_id', 'play_id'], how='inner')
    t = t[t.defense_man_zone_type.isin(['MAN_COVERAGE', 'ZONE_COVERAGE'])].copy()
    t['man'] = t.defense_man_zone_type == 'MAN_COVERAGE'
    t['yds'] = np.where(t.complete_pass == 1, t.yards_gained, 0)
    tt = t[t.receiver_player_id.notna()]
    lg = dict(ypt_man=tt[tt.man].yds.mean(), ypt_zone=tt[~tt.man].yds.mean(), man=t.man.mean())
    # receivers
    r = tt.groupby(['receiver_player_id', 'man']).agg(n=('play_id', 'size'), yds=('yds', 'sum'),
                                                       td=('pass_touchdown', 'sum'), c=('complete_pass', 'sum')).unstack('man').fillna(0)
    r.columns = [f'{a}_{"man" if b else "zone"}' for a, b in r.columns]
    r = r.reset_index().rename(columns={'receiver_player_id': 'pid'})
    # share of the team's targets vs man / vs zone, only in games he was targeted
    tg = tt.groupby(['game_id', 'posteam', 'man']).size().rename('team_n').reset_index()
    pg = tt.groupby(['game_id', 'posteam', 'receiver_player_id', 'man']).size().rename('n').reset_index()
    pg = pg.merge(tg, on=['game_id', 'posteam', 'man'])
    played = pg[['game_id', 'posteam', 'receiver_player_id']].drop_duplicates()
    den = played.merge(tg, on=['game_id', 'posteam']).groupby(['receiver_player_id', 'man']).team_n.sum().unstack().fillna(0)
    num = pg.groupby(['receiver_player_id', 'man']).n.sum().unstack().fillna(0)
    share = (num / den).rename(columns={True: 'share_man', False: 'share_zone'}).reset_index().rename(columns={'receiver_player_id': 'pid'})
    r = r.merge(share, on='pid', how='left')
    # by shell
    sh = tt.groupby(['receiver_player_id', 'defense_coverage_type']).agg(n=('play_id', 'size'), yds=('yds', 'sum')).reset_index()
    # defenses
    dd = t.groupby('defteam').agg(dropbacks=('play_id', 'size'), man=('man', 'mean')).reset_index()
    for k, v in t.groupby(['defteam', 'defense_coverage_type']).size().unstack(fill_value=0).div(
            t.groupby('defteam').size(), axis=0).items():
        dd[f'shell_{k}'] = dd.defteam.map(v)
    a = tt.groupby(['defteam', 'man']).yds.mean().unstack()
    dd['ypt_man'] = dd.defteam.map(a[True])
    dd['ypt_zone'] = dd.defteam.map(a[False])
    return r, sh, dd, lg


# ---------------------------------------------------------------- defense vs offense style ------------------------

STYLE = [  # key, label for the offense's habit, label for what the defense faces
    ('pa', 'play-action passes', 'play-action'),
    ('motion', 'pre-snap motion on dropbacks', 'motion'),
    ('deep', 'deep passes (20+ air yards)', 'deep passes'),
    ('screen', 'screens', 'screens'),
    ('in_run', 'inside runs', 'inside runs'),
    ('out_run', 'outside runs', 'outside runs'),
    ('gun_run', 'shotgun runs', 'shotgun runs'),
    ('uc_run', 'under-center runs', 'under-center runs'),
    ('mid', 'throws over the middle', 'middle-of-field throws'),
]


def style_tables(pbp, ftn, season):
    p = pbp[(pbp.season == season) & (pbp.season_type == 'REG') & ((pbp.pass_attempt == 1) | (pbp.rush_attempt == 1)) &
            (pbp.two_point_attempt != 1) & pbp.epa.notna()].copy()
    f = ftn.rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})[
        ['game_id', 'play_id', 'is_play_action', 'is_motion', 'is_screen_pass', 'qb_location', 'n_pass_rushers']]
    f['play_id'] = pd.to_numeric(f.play_id, errors='coerce')
    p = p.merge(f, on=['game_id', 'play_id'], how='left')
    db = p.qb_dropback == 1
    run = (p.rush_attempt == 1) & (p.qb_scramble != 1)
    p['pa'] = np.where(db, p.is_play_action == True, np.nan)
    p['motion'] = np.where(db, p.is_motion == True, np.nan)
    p['deep'] = np.where((p.pass_attempt == 1) & p.air_yards.notna(), p.air_yards >= 20, np.nan)
    p['screen'] = np.where(db, p.is_screen_pass == True, np.nan)
    inside = p.run_gap.isin(['guard']) | (p.run_location == 'middle')
    p['in_run'] = np.where(run & p.run_location.notna(), inside, np.nan)
    p['out_run'] = np.where(run & p.run_location.notna(), ~inside, np.nan)
    p['gun_run'] = np.where(run & p.qb_location.notna(), p.qb_location.isin(['S', 'P']), np.nan)
    p['uc_run'] = np.where(run & p.qb_location.notna(), p.qb_location == 'U', np.nan)
    p['mid'] = np.where((p.pass_attempt == 1) & p.pass_location.notna(), p.pass_location == 'middle', np.nan)
    p['blitz'] = np.where(db & p.n_pass_rushers.notna(), p.n_pass_rushers >= 5, np.nan)
    p['explosive'] = np.where(run, p.yards_gained >= 10, p.yards_gained >= 20)
    games_off = p.groupby('posteam').game_id.nunique()
    rows_o, rows_d = {}, {}
    for team in sorted(p.posteam.dropna().unique()):
        o, d = p[p.posteam == team], p[p.defteam == team]
        ro = dict(team=team, games=int(games_off.get(team, 0)), pass_rate=(o.pass_attempt == 1).mean() if len(o) else np.nan,
                  plays_pg=len(o) / max(1, games_off.get(team, 1)))
        rd = dict(team=team, epa=d.epa.mean(), epa_pass=d[d.pass_attempt == 1].epa.mean(), epa_rush=d[d.rush_attempt == 1].epa.mean(),
                  explosive=d.explosive.mean(), blitz=d.blitz.mean(), plays_pg=len(d) / max(1, d.game_id.nunique()))
        for key, _, _ in STYLE:
            ro[key] = o[key].mean()
            sub = d[d[key] == 1]
            rd[key + '_epa'] = sub.epa.mean() if len(sub) >= 8 else np.nan
            rd[key + '_n'] = len(sub)
        rows_o[team], rows_d[team] = ro, rd
    O, Dd = pd.DataFrame(rows_o.values()), pd.DataFrame(rows_d.values())
    # ranks: offense habit 1 = uses it most; defense 1 = best (lowest EPA allowed)
    for key, _, _ in STYLE:
        O[key + '_rk'] = O[key].rank(ascending=False, method='min')
        Dd[key + '_rk'] = Dd[key + '_epa'].rank(ascending=True, method='min')
    for c in ('epa', 'epa_pass', 'epa_rush', 'explosive'):
        Dd[c + '_rk'] = Dd[c].rank(ascending=True, method='min')
    Dd['blitz_rk'] = Dd.blitz.rank(ascending=False, method='min')
    O['pass_rate_rk'] = O.pass_rate.rank(ascending=False, method='min')
    O['plays_pg_rk'] = O.plays_pg.rank(ascending=False, method='min')
    lg = {key: p[key].mean() for key, _, _ in STYLE}
    lg.update({key + '_epa': p[p[key] == 1].epa.mean() for key, _, _ in STYLE})
    return O.set_index('team'), Dd.set_index('team'), lg


def ordinal(n):
    n = int(n)
    return f"{n}{'th' if 11 <= n % 100 <= 13 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def style_facts(O, Dd, lg, off, dfn):
    """Where this offense's habits meet this defense's strengths or weak spots (2026 ranks among 32)."""
    out = []
    if off not in O.index or dfn not in Dd.index:
        return out
    o, d = O.loc[off], Dd.loc[dfn]
    for key, olab, dlab in STYLE:
        orank, drank = o[key + '_rk'], d[key + '_rk']
        if pd.isna(drank) or pd.isna(o[key]):
            continue
        uses = orank <= 10
        if uses and drank >= 23:
            out.append(dict(side='off', key=key, score=(drank - 16) / 16 + (11 - orank) / 20,
                            text=f"{off} leans on {olab} ({o[key]:.0%} of plays, {ordinal(orank)} most); {dfn} allows {d[key + '_epa']:+.2f} EPA per play against {dlab} ({ordinal(drank)} of 32)."))
        elif uses and drank <= 8:
            out.append(dict(side='def', key=key, score=-((17 - drank) / 16 + (11 - orank) / 20),
                            text=f"{off} leans on {olab} ({o[key]:.0%}, {ordinal(orank)} most), but {dfn} is {ordinal(drank)} against {dlab} ({d[key + '_epa']:+.2f} EPA per play)."))
    # overall weak/strong units
    for c, lab in (('epa_pass', 'pass defense'), ('epa_rush', 'run defense')):
        rk = d[c + '_rk']
        if rk >= 28:
            out.append(dict(side='off', key=c, score=.6, text=f"{dfn}'s {lab} is {ordinal(rk)} of 32 by EPA allowed per play this season."))
        elif rk <= 4:
            out.append(dict(side='def', key=c, score=-.6, text=f"{dfn}'s {lab} is {ordinal(rk)} of 32 by EPA allowed per play this season."))
    if d['explosive_rk'] >= 28:
        out.append(dict(side='off', key='explosive', score=.5, text=f"{dfn} allows explosive plays (10+ yd runs, 20+ yd passes) on {d['explosive']:.1%} of snaps, {ordinal(d['explosive_rk'])} of 32."))
    return sorted(out, key=lambda x: -abs(x['score']))
