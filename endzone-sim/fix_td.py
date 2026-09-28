"""Grading fix: QB scramble touchdowns are rushing touchdowns (the usage frames count designed runs only)."""
import json, sys, nfl_build as nb
for rows_f, games_f in zip(sys.argv[1::2], sys.argv[2::2]):
    games = json.load(open(games_f)); R = json.load(open(rows_f))
    season = int(games[0]['id'][:4]); p = nb.pbp(season)
    s = p[(p.play_type == 'run') & (p.qb_scramble == 1) & (p.rush_touchdown == 1) & (p.two_point_attempt.fillna(0) != 1)]
    have = set(zip(s.game_id, s.rusher_player_id))
    pid = {(g['id'], x['n']): x['id'] for g in games for x in g['players']}
    ch = 0
    for r in R['rows']:
        if r['td'] == 0 and (r['id'], pid.get((r['id'], r['n']))) in have: r['td'] = 1; ch += 1
    json.dump(R, open(rows_f, 'w')); print(rows_f, 'QB scramble TDs added', ch)
