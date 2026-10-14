"""Grade a week's research-desk picks from nflverse play-by-play and final scores.

    python3 grade.py <data dir> <week>   ->  ../grades_w<week>.json  ({results: {pick id: W|L|P}}, merged with what is there)

<data dir> needs games.csv, play_by_play_2026.csv.gz (or .parquet), snap_counts_2026.csv and roster_2026.csv.
Grades every pick in site/picks_w<week>.json, site/locked_w<week>.json and the week's research entries in
site/archive.json. A player with no snaps at all is a push (books void props for players who don't play; special-teams snaps count).
Rushing yards include scrambles; two-point tries count for nothing. Prints the record and units for each board.
Put the result in the page database as grades/w<week>.
"""
import json
import os
import sys

import pandas as pd

import lock
import trends as tr

H = os.path.dirname(os.path.abspath(__file__))
D, W, S = sys.argv[1], int(sys.argv[2]), 2026
SITE = os.path.join(H, 'site')
OUT = os.path.join(H, '..', f'grades_w{W}.json')

# every pick for the week, and each board it was on
boards, picks = {}, {}
cur = os.path.join(SITE, f'picks_w{W}.json')
if os.path.exists(cur):
    c = json.load(open(cur))
    if c['week'] == W:
        picks.update({p['id']: p for p in c['picks']})
        boards['current board (not locked yet)'] = c['board']
for a in json.load(open(os.path.join(SITE, 'archive.json'))) + lock.archive_entries():
    if a['week'] == W and a.get('research'):
        picks.update({p['id']: p for p in a['picks'] if p['id'] not in picks})
        boards[a['label']] = a['board']

G = pd.read_csv(f'{D}/games.csv')
G = G[(G.season == S) & (G.week == W) & G.home_score.notna()]
score = {}
for r in G.itertuples():
    a, h = tr.FRANCHISE.get(r.away_team, r.away_team), tr.FRANCHISE.get(r.home_team, r.home_team)
    score[f'{a.lower()}-{h.lower()}'] = (a, h, r.away_score, r.home_score, r.game_id)

pq = f'{D}/play_by_play_{S}.parquet'
P = pd.read_parquet(pq) if os.path.exists(pq) else pd.read_csv(f'{D}/play_by_play_{S}.csv.gz', low_memory=False)
P = P[(P.week == W) & (P.two_point_attempt != 1)]
rush = P[P.rusher_player_id.notna()].groupby('rusher_player_id').rushing_yards.sum()
recY = P[(P.complete_pass == 1) & P.receiver_player_id.notna()].groupby('receiver_player_id').receiving_yards.sum()
tds = set(P[P.td_player_id.notna()].td_player_id)
SN = pd.read_csv(f'{D}/snap_counts_{S}.csv')
SN = SN[(SN.season == S) & (SN.week == W)]
played_games = set(SN.game_id)
SN = SN[SN[['offense_snaps', 'defense_snaps', 'st_snaps']].fillna(0).sum(axis=1) > 0]   # any snap is action (a return TD counts)
R = pd.read_csv(f'{D}/roster_{S}.csv', low_memory=False)
pfr2gsis = dict(zip(R.pfr_id, R.gsis_id))
played = {pfr2gsis.get(x) for x in SN.pfr_player_id}


def grade(p):
    if p['gameId'] not in score:
        return None                                       # not final yet
    a, h, sa, sh, game_id = score[p['gameId']]
    t = p['type']
    if t in ('Winner', 'Spread'):
        mine, opp = (sa, sh) if p['team'] == a else (sh, sa)
        m = mine - opp + (p['line'] if t == 'Spread' else 0)
        return 'W' if m > 0 else 'L' if m < 0 else 'P'
    if t == 'Total':
        tot = sa + sh
        return 'P' if tot == p['line'] else ('W' if (tot > p['line']) == (p['side'] == 'Over') else 'L')
    if game_id not in played_games:
        return None                                       # snap counts not posted yet: can't tell a void from a zero
    pid = p['pid']
    if pid not in played:
        return 'P'
    if t == 'Anytime TD':
        return 'W' if pid in tds else 'L'
    if t == 'Yards':
        parts = p['id'].split('-')
        stat, side, line = parts[3], parts[-2], float(parts[-1])
        v = {'rushYds': rush, 'recYds': recY}[stat].get(pid, 0)
        return 'P' if v == line else ('W' if (v > line) == (side == 'over') else 'L')
    return None


res = {k: r for k, p in picks.items() if (r := grade(p))}
old = json.load(open(OUT))['results'] if os.path.exists(OUT) else {}
changed = {k: (old[k], v) for k, v in res.items() if k in old and old[k] != v}
json.dump({'results': {**old, **res}}, open(OUT, 'w'), separators=(',', ':'))

pay = lambda o: o / 100 if o > 0 else 100 / -o
print(f'week {W}: graded {len(res)} of {len(picks)} picks -> {os.path.relpath(OUT)} ({len(changed)} differ from what was there)')
for k, (o, n) in list(changed.items())[:20]:
    print(f'  changed {k}: {o} -> {n}')
for label, ids in boards.items():
    w = sum(res.get(i) == 'W' for i in ids)
    l = sum(res.get(i) == 'L' for i in ids)
    pu = sum(res.get(i) == 'P' for i in ids)
    u = sum(pay(picks[i]['price']['odds']) if res.get(i) == 'W' else -1 if res.get(i) == 'L' else 0 for i in ids)
    print(f'  {label}: {w}-{l}' + (f'-{pu}' if pu else '') + f'  {u:+.2f}u  ({len(ids) - w - l - pu} open)')
