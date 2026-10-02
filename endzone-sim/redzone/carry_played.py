"""Keep picks for games that already kicked off. gen_nfl.py drops played games from the slate, so a mid-week rebuild
would otherwise delete their picks, along with anything tracked or graded on them. Each game the previous build had and
this one doesn't is copied over unchanged (its picks, matchups and projections as they stood at kickoff).
Usage: python3 redzone/carry_played.py PREVIOUS.json NEW.json   (NEW is updated in place)"""
import json, sys
prev, new = (json.load(open(f)) for f in sys.argv[1:3])
if (prev.get('season'), prev.get('week')) != (new.get('season'), new.get('week')): sys.exit(0)
have = {g['id'] for g in new['games']}
gone = [g for g in prev['games'] if g['id'] not in have]
if gone:
    ids = {g['id'] for g in gone}
    new['games'] = gone + new['games']
    new['picks'] = [p for p in prev['picks'] if p['gameId'] in ids] + new['picks']
    new['label'] = prev.get('label', new['label'])        # keep the full week's dates
    json.dump(new, open(sys.argv[2], 'w'), separators=(',', ':'))
print('carried over (already kicked off):', [g['id'] for g in gone] or 'none')
