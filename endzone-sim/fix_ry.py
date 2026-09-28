"""Grading fix: official rushing yards include QB scrambles and kneel-downs (the usage frames count designed runs only)."""
import json, sys, pandas as pd, nfl_build as nb
for f in sys.argv[1:]:
    games = json.load(open(f.replace('_dk_rows.json', '.json'))); R = json.load(open(f))
    season = int(games[0]['id'][:4]); p = nb.pbp(season)
    rr = p[(p.play_type == 'run') & (p.two_point_attempt.fillna(0) != 1) & p.rusher_player_id.notna()]
    off = rr.groupby(['game_id', 'rusher_player_id']).rushing_yards.sum()
    pid = {(g['id'], x['n']): x['id'] for g in games for x in g['players']}
    ch = 0
    for r in R['props']:
        if r['mk'] != 'player_rush_yds': continue
        k = (r['id'], pid.get((r['id'], r['n'])))
        new = int(off.get(k, 0))
        if new != r['actual']: ch += 1
        r['actual'] = new
    json.dump(R, open(f, 'w')); print(f, 'rush-yds actuals changed', ch)
