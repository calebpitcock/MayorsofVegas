"""Rebuild each past week's book prices as they stood before each game, in the layout build.py reads.

    python3 prep_prices.py <games.csv> <pp repo> <NFL-Model repo> <out dir> <week>...

  yardage   davidcantugtr/nfl-player-prop-opportunity data/snapshots/2026-Wxx: for each game, the last snapshot
            taken before its kickoff  ->  <out>/w<week>/pp/data/latest/player_props.csv
  anytime TD  jaredpatchett/NFL-Model data/player_td.json git history: for each game, the last commit before its
            kickoff that priced it  ->  <out>/w<week>/jp/data/player_td.json
The repos only need their data files (a blob-less clone; this reads blobs with git show).
"""
import glob
import json
import os
import subprocess
import sys

import pandas as pd

games_csv, PP, JP, OUT = sys.argv[1:5]
WEEKS = [int(w) for w in sys.argv[5:]]
FR = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
G = pd.read_csv(games_csv)
G = G[G.season == 2026]
G['kick'] = pd.to_datetime(G.gameday + ' ' + G.gametime.astype(str)).dt.tz_localize('America/New_York').dt.tz_convert('UTC')

# NFL-Model player_td.json versions, oldest first
log = subprocess.run(['git', '-C', JP, 'log', '--reverse', '--format=%H %cI', '--', 'data/player_td.json'],
                     capture_output=True, text=True, check=True).stdout.split('\n')
versions = [(pd.Timestamp(t).tz_convert('UTC'), h) for h, t in (l.split() for l in log if l.strip())]
cache = {}


def td_version(h):
    if h not in cache:
        cache[h] = json.loads(subprocess.run(['git', '-C', JP, 'show', f'{h}:data/player_td.json'],
                                             capture_output=True, text=True, check=True).stdout)
    return cache[h]


for wk in WEEKS:
    gw = G[G.week == wk]
    # ---- yardage: last snapshot before each game's kickoff
    fs = sorted(glob.glob(f'{PP}/data/snapshots/2026-W{wk:02d}/*_player_props.csv'))
    S = pd.concat([pd.read_csv(f).assign(snap=pd.Timestamp(os.path.basename(f)[:16]).tz_convert('UTC')) for f in fs])
    S['kick'] = pd.to_datetime(S['Commence Time'], utc=True)
    S = S[S.snap < S.kick]
    S = S[S.snap == S.groupby('Event ID').snap.transform('max')]
    d = f'{OUT}/w{wk}/pp/data/latest'
    os.makedirs(d, exist_ok=True)
    S.drop(columns=['snap', 'kick']).to_csv(f'{d}/player_props.csv', index=False)
    # ---- anytime TD: last version before kickoff that priced this matchup
    players, used = [], []
    for r in gw.itertuples():
        a, h = FR.get(r.away_team, r.away_team), FR.get(r.home_team, r.home_team)
        best = None
        for t, sha in versions:
            if t >= r.kick:
                break
            ps = [p for p in td_version(sha)['players'] if {p.get('team'), p.get('opponent')} == {a, h}
                  and (p.get('market') or {}).get('anytime_td_price') is not None]
            if ps:
                best = (t, ps)
        if best:
            players += best[1]
            used.append(best[0])
    d = f'{OUT}/w{wk}/jp/data'
    os.makedirs(d, exist_ok=True)
    gen = max(used).isoformat() if used else gw.kick.min().isoformat()
    json.dump({'generated_at': gen, 'players': players}, open(f'{d}/player_td.json', 'w'))
    print(f'week {wk}: {len(gw)} games | yardage rows {len(S)} for {S["Event ID"].nunique()} games '
          f'(snapshots {sorted(S.snap.dt.strftime("%a %H:%MZ").unique())}) | TD prices for {len(used)} games, {len(players)} players')
