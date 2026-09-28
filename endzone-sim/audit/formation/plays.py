"""Play table 2022-25 for the formation tests: offense personnel (RB/TE/WR counts), defense DB count, defenders in
the box (participation, FTN fallback), designed-run yards, target position. Writes ../data/formation_plays.parquet."""
import os, re, numpy as np, pandas as pd
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', 'data')
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
def cnt(s, keys):
    if not isinstance(s, str): return np.nan
    return sum(int(n) for n, k in re.findall(r'(\d+) ([A-Z]+)', s) if k in keys)
out = []
for s in range(2022, 2026):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', low_memory=False, usecols=['game_id', 'play_id', 'season', 'week', 'season_type', 'posteam', 'defteam',
        'play_type', 'rush_attempt', 'qb_scramble', 'rushing_yards', 'rusher_player_id', 'pass_attempt', 'sack', 'receiver_player_id', 'receiving_yards',
        'complete_pass', 'two_point_attempt', 'down', 'ydstogo', 'yardline_100', 'rush_touchdown', 'pass_touchdown'])
    p = p[(p.season_type == 'REG') & p.play_type.isin(['run', 'pass']) & (p.two_point_attempt.fillna(0) == 0)].copy()
    for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
    pa = pd.read_parquet(f'{D}/pbp_participation_{s}.parquet', columns=['nflverse_game_id', 'play_id', 'offense_personnel', 'defense_personnel', 'defenders_in_box'])
    pa = pa.rename(columns={'nflverse_game_id': 'game_id'})
    pa['nRB'] = pa.offense_personnel.map(lambda x: cnt(x, {'RB', 'FB'})); pa['nTE'] = pa.offense_personnel.map(lambda x: cnt(x, {'TE'}))
    pa['nWR'] = pa.offense_personnel.map(lambda x: cnt(x, {'WR'})); pa['nDB'] = pa.defense_personnel.map(lambda x: cnt(x, {'DB', 'CB', 'FS', 'SS', 'S', 'SAF'}))
    p = p.merge(pa[['game_id', 'play_id', 'nRB', 'nTE', 'nWR', 'nDB', 'defenders_in_box']], on=['game_id', 'play_id'], how='left')
    ft = pd.read_parquet(f'{D}/ftn_charting_{s}.parquet', columns=['nflverse_game_id', 'nflverse_play_id', 'n_defense_box']).rename(columns={'nflverse_game_id': 'game_id', 'nflverse_play_id': 'play_id'})
    p = p.merge(ft, on=['game_id', 'play_id'], how='left')
    p['box'] = p.defenders_in_box.fillna(p.n_defense_box)
    ro = pd.read_csv(f'{D}/roster_{s}.csv', usecols=['gsis_id', 'position']).drop_duplicates('gsis_id').set_index('gsis_id').position
    p['rpos'] = p.receiver_player_id.map(ro); p['rupos'] = p.rusher_player_id.map(ro)
    p['drun'] = ((p.rush_attempt == 1) & (p.qb_scramble.fillna(0) == 0)).astype(int)
    p['tgt'] = ((p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & p.receiver_player_id.notna()).astype(int)
    out.append(p.drop(columns=['defenders_in_box', 'n_defense_box', 'season_type']))
    print(s, len(p), 'personnel', round(p.nWR.notna().mean(), 3), 'box', round(p.box.notna().mean(), 3), flush=True)
P = pd.concat(out); P.to_parquet(f'{D}/formation_plays.parquet'); print(len(P))
