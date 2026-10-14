"""Lock each game's Top plays at kickoff, so the Desk record counts only what was on the board when the game started.

    python3 lock.py <nflverse dir> <week>     lock every game in site/picks_w<week>.json that has kicked off

build.py calls update() before every rebuild: any game whose kickoff has passed is copied from the previous build
(the board that was live at kickoff) into site/locked_w<week>.json and never re-picked. A game is locked once; later
builds can't change it. build_page.py shows each week's locked games as a Record entry. RZ_NOW (ISO time) overrides
the clock for testing.
"""
import json
import os
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

H = os.path.dirname(os.path.abspath(__file__))
SITE = os.path.join(H, 'site')
ET = ZoneInfo('America/New_York')
KEEP = ('id', 'type', 'text', 'game', 'gameId', 'prob', 'book', 'price', 'team', 'pos', 'player', 'line', 'side', 'pid', 'desk')


def now():
    s = os.environ.get('RZ_NOW')
    return datetime.fromisoformat(s.replace('Z', '+00:00')) if s else datetime.now(timezone.utc)


def kickoff(gameday, gametime):
    """nflverse gameday/gametime are US Eastern."""
    return datetime.strptime(f'{gameday} {gametime}', '%Y-%m-%d %H:%M').replace(tzinfo=ET)


def path(week):
    return os.path.join(SITE, f'locked_w{week}.json')


def load(week):
    p = path(week)
    return json.load(open(p)) if os.path.exists(p) else {}


def update(week, kicks, at=None):
    """kicks: {gameId: kickoff datetime}. Locks every kicked-off game from the previous build. Returns the ledger."""
    at = at or now()
    ledger = load(week)
    prev_path = os.path.join(SITE, f'picks_w{week}.json')
    prev = json.load(open(prev_path)) if os.path.exists(prev_path) else None
    if prev and prev.get('week') != week:
        prev = None
    added = []
    for g, k in kicks.items():
        if g in ledger or k > at or prev is None:
            continue
        picks = [p for p in prev['picks'] if p['gameId'] == g]
        if not picks:            # previous build had no picks for it (already final, or never built): nothing to lock
            continue
        ids = {p['id'] for p in picks}
        ledger[g] = dict(kick=k.isoformat(), lockedAt=at.isoformat(timespec='seconds'), built=prev.get('generated'),
                         game=picks[0]['game'], board=[i for i in prev['board'] if i in ids],
                         picks=[{**{x: p[x] for x in KEEP if x in p}, 'why': p.get('why', [])[:6]} for p in picks])
        added.append(g)
    if added:
        os.makedirs(SITE, exist_ok=True)
        json.dump(ledger, open(path(week), 'w'), separators=(',', ':'))
    for g in added:
        print(f"locked {ledger[g]['game']}: {len(ledger[g]['board'])} on the board, {len(ledger[g]['picks'])} picks (built {ledger[g]['built']})")
    return ledger


def kicks_from_games(games_csv, season, week):
    import pandas as pd
    G = pd.read_csv(games_csv)
    G = G[(G.season == season) & (G.week == week)]
    import trends as tr
    out = {}
    for r in G.itertuples():
        away, home = tr.FRANCHISE.get(r.away_team, r.away_team), tr.FRANCHISE.get(r.home_team, r.home_team)
        out[f'{away.lower()}-{home.lower()}'] = kickoff(r.gameday, str(r.gametime))
    return out


def archive_entries():
    """Every week's locked games as Record entries (one per week), for build_page.py."""
    out = []
    for fn in sorted(os.listdir(SITE)):
        if not (fn.startswith('locked_w') and fn.endswith('.json')):
            continue
        week = int(fn[8:-5])
        ledger = json.load(open(os.path.join(SITE, fn)))
        if not ledger:
            continue
        games = sorted(ledger.values(), key=lambda x: x['kick'])
        names = [x['game'] for x in games]
        label = f"Week {week}: " + (', '.join(names) if len(names) <= 2 else f'{len(names)} games') + ' (locked at kickoff)'
        out.append(dict(week=week, label=label, research=True, locked=True,
                        note='Research desk Top plays as they stood at each kickoff. Later rebuilds can\'t change them.',
                        board=[i for x in games for i in x['board']], picks=[p for x in games for p in x['picks']]))
    return out


if __name__ == '__main__':
    D, week = sys.argv[1], int(sys.argv[2])
    sys.path.insert(0, H)
    update(week, kicks_from_games(os.path.join(D, 'games.csv'), 2026, week))
