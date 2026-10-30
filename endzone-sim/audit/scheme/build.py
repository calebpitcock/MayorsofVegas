"""Per targeted pass play 2022-26: offense, defense, receiver, coverage (man/zone from participation, 2022-25), blitz and
play-action (FTN). Saved for the split/matchup tests."""
import pandas as pd, numpy as np
D = '/home/user/MayorsofVegas/data'; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
out = []
for s in range(2022, 2027):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'play_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'play_type', 'pass_attempt', 'sack', 'two_point_attempt', 'receiver_player_id', 'yardline_100', 'pass_touchdown', 'rush_touchdown', 'rusher_player_id', 'qb_scramble', 'qb_dropback'], low_memory=False)
    p = p[(p.season_type == 'REG') & p.play_type.isin(['pass', 'run']) & (p.two_point_attempt.fillna(0) == 0)]
    try:
        pa = pd.read_parquet(f'{D}/pbp_participation_{s}.parquet', columns=['nflverse_game_id', 'play_id', 'defense_man_zone_type', 'defense_coverage_type'])
        p = p.merge(pa.rename(columns={'nflverse_game_id': 'game_id'}), on=['game_id', 'play_id'], how='left')
    except Exception: p['defense_man_zone_type'] = None; p['defense_coverage_type'] = None
    f = pd.read_parquet(f'{D}/ftn_charting_{s}.parquet', columns=['nflverse_game_id', 'nflverse_play_id', 'n_blitzers', 'is_play_action', 'is_screen_pass', 'is_motion'])
    p = p.merge(f.rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'}), on=['game_id', 'play_id'], how='left')
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
    p['man'] = np.where(p.defense_man_zone_type == 'MAN_COVERAGE', 1.0, np.where(p.defense_man_zone_type == 'ZONE_COVERAGE', 0.0, np.nan))
    p['blitz'] = np.where(p.n_blitzers.notna(), (p.n_blitzers > 0).astype(float), np.nan)
    out.append(p); print(s, len(p), 'man charted', p.man.notna().mean().round(2), 'blitz charted', p.blitz.notna().mean().round(2), flush=True)
P = pd.concat(out); P.to_parquet('plays.parquet')
