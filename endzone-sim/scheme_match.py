"""Coverage and pressure matchups from charting data (nflverse participation = man/zone 2022-25; FTN = blitz 2022-26).
For a week, each receiver's target-share split against man vs zone and blitz vs no blitz (from his own targets, shrunk),
each defense's man and blitz rate (shrunk), and the resulting target multiplier for this matchup.
Held-out 2023-25 (audit): the raw multiplier over-states the effect; about 60% of it is real (DAMP), and together they
cut target-share error ~0.1% - small but consistent. Coverage charting isn't published for 2026 yet, so defenses' man
rates come from 2025 (stale where the coordinator changed)."""
import os, numpy as np, pandas as pd
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'data'); REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
K_P, K_D, DAMP = 40.0, 150.0, 0.6
_T = None
def targets():
    global _T
    if _T is not None: return _T
    cache = f'{D}/scheme_targets.parquet'; fr = []
    for s in range(2022, 2027):
        if not os.path.exists(f'{D}/play_by_play_{s}.csv.gz'): continue
        p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'play_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'pass_attempt', 'sack', 'two_point_attempt', 'receiver_player_id'], low_memory=False)
        p = p[(p.season_type == 'REG') & (p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & (p.two_point_attempt.fillna(0) == 0)]
        f = f'{D}/pbp_participation_{s}.parquet'
        if os.path.exists(f):
            pa = pd.read_parquet(f, columns=['nflverse_game_id', 'play_id', 'defense_man_zone_type']).rename(columns={'nflverse_game_id': 'game_id'})
            p = p.merge(pa, on=['game_id', 'play_id'], how='left')
        else: p['defense_man_zone_type'] = None
        f = f'{D}/ftn_charting_{s}.parquet'
        if os.path.exists(f):
            ft = pd.read_parquet(f, columns=['nflverse_game_id', 'nflverse_play_id', 'n_blitzers']).rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})
            p = p.merge(ft, on=['game_id', 'play_id'], how='left')
        else: p['n_blitzers'] = np.nan
        for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
        p['man'] = np.where(p.defense_man_zone_type == 'MAN_COVERAGE', 1.0, np.where(p.defense_man_zone_type == 'ZONE_COVERAGE', 0.0, np.nan))
        p['blitz'] = np.where(p.n_blitzers.notna(), (p.n_blitzers > 0).astype(float), np.nan)
        fr.append(p[['game_id', 'season', 'week', 'posteam', 'defteam', 'receiver_player_id', 'man', 'blitz']])
    _T = pd.concat(fr); return _T
_POS = None
def positions():
    global _POS
    if _POS is None:
        fr = [pd.read_csv(f'{D}/roster_{y}.csv', usecols=['gsis_id', 'position'], low_memory=False) for y in range(2022, 2027) if os.path.exists(f'{D}/roster_{y}.csv')]
        _POS = pd.concat(fr).dropna().drop_duplicates('gsis_id', keep='last').set_index('gsis_id').position.replace({'FB': 'RB'}).to_dict()
    return _POS
def week_tables(S, w):
    """Receiver splits and defense rates using only data before (S, w): last season plus this season to date."""
    T = targets(); X0 = T[((T.season == S) & (T.week < w)) | (T.season == S - 1)]; out = {}
    for key in ('man', 'blitz'):
        X = X0[X0[key].notna()]
        if not len(X):
            X = T[(T.season == S - 1) & T[key].notna()]          # no charting this season yet: last season only
        lg = float(X[key].mean())
        tx = X[X.receiver_player_id.notna()]
        team = tx.groupby(['game_id', 'posteam', key]).size().rename('tt').reset_index()
        pl = tx.groupby(['game_id', 'posteam', 'receiver_player_id', key]).size().rename('pt').reset_index()
        tp = pl[['game_id', 'receiver_player_id']].drop_duplicates().merge(team, on='game_id')
        a = tp.groupby(['receiver_player_id', key]).tt.sum().unstack(fill_value=0).reindex(columns=[0.0, 1.0], fill_value=0)
        b = pl.groupby(['receiver_player_id', key]).pt.sum().unstack(fill_value=0).reindex(index=a.index, columns=[0.0, 1.0], fill_value=0)
        s_all = ((b[0.0] + b[1.0]) / (a[0.0] + a[1.0]).clip(lower=1)).clip(lower=1e-3)
        # thin samples fall back to the player's POSITION pattern (league-wide, backs get ~60% more of the targets vs zone
        # than vs man, receivers more vs man), not to 'no difference'
        pos = positions(); tx2 = tx.assign(rp=tx.receiver_player_id.map(pos)); pz = tx2.groupby(key).rp.value_counts(normalize=True).unstack(); ov = tx2.rp.value_counts(normalize=True)
        q1, q0 = (pz.loc[1.0] / ov).to_dict(), (pz.loc[0.0] / ov).to_dict(); pp = pd.Series([pos.get(i) for i in a.index], index=a.index)
        p1, p0 = pp.map(q1).fillna(1.0), pp.map(q0).fillna(1.0)
        r1 = ((b[1.0] + K_P * s_all * p1) / (a[1.0] + K_P)) / s_all; r0 = ((b[0.0] + K_P * s_all * p0) / (a[0.0] + K_P)) / s_all
        out.setdefault('pos', {})[key] = dict(q1=q1, q0=q0)
        d = X.groupby('defteam')[key].agg(['sum', 'count']); drate = (d['sum'] + K_D * lg) / (d['count'] + K_D)
        out[key] = dict(r1=r1.to_dict(), r0=r0.to_dict(), d=drate.to_dict(), lg=lg)
    return out
def multiplier(tab, pid, opp):
    """Damped target multiplier for receiver pid against defense opp, plus the parts for display."""
    parts = {}; m = 1.0
    for key in ('man', 'blitz'):
        t = tab[key]; r1, r0 = t['r1'].get(pid, 1.0), t['r0'].get(pid, 1.0); d = t['d'].get(opp, t['lg']); lg = t['lg']
        raw = (d * r1 + (1 - d) * r0) / (lg * r1 + (1 - lg) * r0); m *= raw
        parts[key] = dict(rate=round(d, 3), lg=round(lg, 3), split=round(r1 / r0, 2) if r0 > 0 else 1.0, raw=round(float(raw), 4))
    return 1 + DAMP * (m - 1), parts
