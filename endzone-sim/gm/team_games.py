"""Per team-game efficiency from nflverse play-by-play, 2012-2026: offense and defense EPA/play (pass and rush),
success rate, plus each QB's dropbacks and EPA. Garbage time (win prob outside 5-95%) is dropped."""
import pandas as pd, numpy as np
D = '../../data'
COLS = ['game_id', 'season', 'season_type', 'week', 'posteam', 'defteam', 'epa', 'success', 'wp', 'qb_dropback', 'rush_attempt',
        'play_type', 'passer_player_id', 'rusher_player_id', 'qb_scramble', 'two_point_attempt', 'qb_kneel', 'qb_spike', 'cpoe']
out, qbs = [], []
for s in range(2012, 2027):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=COLS, low_memory=False)
    p = p[p.season_type == 'REG']
    p = p[p.play_type.isin(['pass', 'run']) & p.epa.notna() & (p.two_point_attempt.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0) & (p.qb_spike.fillna(0) == 0)]
    live = p[p.wp.between(.05, .95)]
    live = live.assign(isp=live.qb_dropback.fillna(0) == 1)
    g = live.groupby(['game_id', 'season', 'week', 'posteam', 'defteam'])
    t = g.agg(n=('epa', 'size'), epa=('epa', 'mean'), sr=('success', 'mean'),
              np_=('isp', 'sum')).reset_index()
    pe = live[live.isp].groupby(['game_id', 'posteam']).epa.mean().rename('pepa'); re_ = live[~live.isp].groupby(['game_id', 'posteam']).epa.mean().rename('repa')
    t = t.join(pe, on=['game_id', 'posteam']).join(re_, on=['game_id', 'posteam'])
    out.append(t)
    db = p[p.qb_dropback.fillna(0) == 1].copy()
    db['qb'] = db.passer_player_id.fillna(db.rusher_player_id)
    q = db.groupby(['game_id', 'season', 'week', 'posteam', 'qb']).agg(db=('epa', 'size'), qepa=('epa', 'sum'), cpoe=('cpoe', 'mean')).reset_index()
    qbs.append(q)
    print(s, len(t), flush=True)
pd.concat(out).to_parquet('team_games.parquet'); pd.concat(qbs).to_parquet('qb_games.parquet')
