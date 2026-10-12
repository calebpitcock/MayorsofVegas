"""Move the finished games of a slate into site/archive.json as a graded research entry.

    python3 freeze_slate.py <earlier picks_w<week>.json> "<label>"

Use when part of a week is over (e.g. Monday night is all that is left): the earlier build's board and picks for the
games that are now final go to the archive, so tracked picks, grades and the Record tab keep resolving after the next
build carries only the games still to play.
"""
import json
import os
import sys

H = os.path.dirname(os.path.abspath(__file__))
old = json.load(open(sys.argv[1]))
label = sys.argv[2]
cur = json.load(open(os.path.join(H, 'site', f"picks_w{old['week']}.json")))
live = {g['id'] for g in cur['games'] if 'final' not in g}
keep = ('id', 'type', 'text', 'game', 'gameId', 'prob', 'book', 'price', 'team', 'pos', 'player', 'line', 'side', 'pid')
picks = [{**{k: p[k] for k in keep if k in p}, 'why': p.get('why', [])[:6]} for p in old['picks'] if p['gameId'] not in live]
board = [i for i in old['board'] if any(p['id'] == i for p in picks)]
path = os.path.join(H, 'site', 'archive.json')
arch = [a for a in json.load(open(path)) if a.get('label') != label]
arch.append(dict(week=old['week'], label=label, research=True,
                 note='Research desk, built Sunday morning. Graded after the games; the Monday game moved to the current board.',
                 board=board, picks=picks))
json.dump(arch, open(path, 'w'), separators=(',', ':'))
print(f'archived {len(picks)} picks, board {len(board)}, as "{label}"')
