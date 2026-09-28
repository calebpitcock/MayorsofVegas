"""Per player-game and team-game counts for the candidate stats, saved to parquet.
Player: targets, end-zone targets (air yards reach the goal line), red-zone (<=10) targets, carries, inside-5 carries,
inside-10 carries, receptions, YAC, expected YAC (nflfastR xyac_mean_yardage), TDs.
Team: plays, dropbacks, sum of xpass (nflfastR expected dropback prob) on early-down neutral plays, neutral dropbacks."""
import pandas as pd, numpy as np
D = '/home/user/MayorsofVegas/data'; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
cols = ['game_id', 'season', 'week', 'season_type', 'posteam', 'play_type', 'pass_attempt', 'sack', 'two_point_attempt', 'receiver_player_id',
        'rusher_player_id', 'qb_scramble', 'qb_kneel', 'air_yards', 'yardline_100', 'xpass', 'pass_oe', 'yards_after_catch', 'xyac_mean_yardage',
        'complete_pass', 'qb_dropback', 'down', 'wp', 'half_seconds_remaining', 'pass_touchdown', 'rush_touchdown', 'receiving_yards']
P, T = [], []
for s in range(2021, 2027):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=cols, low_memory=False); p = p[p.season_type == 'REG']
    p['posteam'] = p.posteam.replace(REP); two = p.two_point_attempt.fillna(0) == 1
    tg = p[(p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & ~two & p.receiver_player_id.notna()].copy()
    tg['ez'] = (tg.air_yards >= tg.yardline_100).astype(float); tg['rz'] = (tg.yardline_100 <= 10).astype(float)
    tg['yac'] = np.where(tg.complete_pass == 1, tg.yards_after_catch, np.nan); tg['xyac'] = np.where((tg.complete_pass == 1) & tg.xyac_mean_yardage.notna() & tg.yards_after_catch.notna(), tg.xyac_mean_yardage, np.nan)
    tg['yac'] = np.where(np.isnan(tg.xyac), np.nan, tg.yac)
    a = tg.groupby(['game_id', 'season', 'week', 'posteam', 'receiver_player_id']).agg(tgt=('ez', 'size'), ez=('ez', 'sum'), rzt=('rz', 'sum'),
        rec=('complete_pass', 'sum'), yac=('yac', 'sum'), xyac=('xyac', 'sum'), nyac=('xyac', 'count'), ctd=('pass_touchdown', 'sum'), recy=('receiving_yards', 'sum')).reset_index().rename(columns={'receiver_player_id': 'pid'})
    ru = p[(p.play_type == 'run') & (p.qb_scramble.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0) & ~two & p.rusher_player_id.notna()].copy()
    ru['i5'] = (ru.yardline_100 <= 5).astype(float); ru['i10'] = (ru.yardline_100 <= 10).astype(float)
    b = ru.groupby(['game_id', 'season', 'week', 'posteam', 'rusher_player_id']).agg(car=('i5', 'size'), i5=('i5', 'sum'), i10=('i10', 'sum'), rtd=('rush_touchdown', 'sum')).reset_index().rename(columns={'rusher_player_id': 'pid'})
    P.append(a.merge(b, on=['game_id', 'season', 'week', 'posteam', 'pid'], how='outer').fillna(0))
    n = p[p.down.isin([1, 2]) & p.wp.between(.2, .8) & (p.half_seconds_remaining > 120) & p.play_type.isin(['run', 'pass']) & ~two & p.xpass.notna()]
    t1 = n.groupby(['game_id', 'season', 'week', 'posteam']).agg(nn=('xpass', 'size'), ndb=('qb_dropback', 'sum'), nx=('xpass', 'sum')).reset_index()
    al = p[p.play_type.isin(['run', 'pass']) & ~two & (p.qb_kneel.fillna(0) == 0)]
    t2 = al.groupby(['game_id', 'posteam']).agg(plays=('qb_dropback', 'size'), db=('qb_dropback', 'sum'), ax=('xpass', 'sum'), axn=('xpass', 'count')).reset_index()
    T.append(t1.merge(t2, on=['game_id', 'posteam'], how='outer'))
    print(s, len(P[-1]), len(T[-1]))
pd.concat(P).to_parquet('player_games.parquet'); pd.concat(T).to_parquet('team_games.parquet')
