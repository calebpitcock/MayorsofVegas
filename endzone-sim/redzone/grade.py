"""Grade a week's Redzone Desk picks from nflverse play-by-play and final scores.
Usage: python3 redzone/grade.py WEEK  -> redzone/grades_wWEEK.json ({results: {pick id: W|L|P}}) and a summary.
A player with no offensive snaps that week is a void (P), as books void props for players who don't play.
Rushing yards include scrambles (books count them); two-point tries count for nothing."""
import json, os, sys, math
import pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, '..', '..', 'data'); S = 2026
W = int(sys.argv[1])
picks = json.load(open(os.path.join(H, f'picks_w{W}.json')))
slate = json.load(open(os.path.join(H, f'slate_w{W}.json')))
pid = {(p['n'], p['t']): p['id'] for g in slate['games'] for p in g['players'] if 't' in p}
pid1 = {}
for g in slate['games']:
    for p in g['players']: pid1.setdefault(p['n'], p['id'])

G = pd.read_csv(f'{D}/games.csv'); G = G[(G.season == S) & (G.week == W) & G.home_score.notna()]
score = {f'{r.away_team}-{r.home_team}'.lower(): (r.away_team, r.home_team, r.away_score, r.home_score) for r in G.itertuples()}
P = pd.read_csv(f'{D}/play_by_play_{S}.csv.gz', low_memory=False); P = P[(P.week == W) & (P.two_point_attempt != 1)]
rush = P[P.rusher_player_id.notna()].groupby('rusher_player_id').rushing_yards.sum()
rec = P[(P.complete_pass == 1) & P.receiver_player_id.notna()]
recY = rec.groupby('receiver_player_id').receiving_yards.sum(); recN = rec.groupby('receiver_player_id').size()
tds = set(P[P.td_player_id.notna()].td_player_id)
SN = pd.read_csv(f'{D}/snap_counts_{S}.csv'); SN = SN[(SN.season == S) & (SN.week == W) & (SN.offense_snaps > 0)]
R = pd.read_csv(f'{D}/roster_{S}.csv', low_memory=False)
pfr2gsis = dict(zip(R.pfr_id, R.gsis_id))
for r in R.itertuples(): pid.setdefault((r.full_name, r.team), r.gsis_id)   # games already played drop off the slate
played = {pfr2gsis.get(x) for x in SN.pfr_player_id}

res = {}
for p in picks['picks']:
    gid = p['gameId']
    if gid not in score: continue                      # not final yet
    a, h, sa, sh = score[gid]
    t = p['type']
    if t == 'Winner':
        mine, opp = (sa, sh) if p['team'] == a else (sh, sa); r = 'W' if mine > opp else 'L' if mine < opp else 'P'
    elif t == 'Spread':
        mine, opp = (sa, sh) if p['team'] == a else (sh, sa); m = mine + p['line'] - opp; r = 'W' if m > 0 else 'L' if m < 0 else 'P'
    elif t == 'Total':
        tot = sa + sh; r = 'P' if tot == p['line'] else ('W' if (tot > p['line']) == (p['side'] == 'Over') else 'L')
    else:
        i = pid.get((p['player'], p['team'])) or pid1.get(p['player'])
        if i is None or i not in played: r = 'P'
        elif t == 'Anytime TD': r = 'W' if i in tds else 'L'
        else:
            v = {'rushYds': rush, 'recYds': recY, 'rec': recN}[p['stat']].get(i, 0)
            if 'line' in p: r = 'P' if v == p['line'] else ('W' if (v > p['line']) == (p['side'] == 'over') else 'L')
            else: r = 'W' if v >= p['thr'] else 'L'
    res[p['id']] = r
json.dump({'results': res}, open(os.path.join(H, f'grades_w{W}.json'), 'w'), indent=1)

# summary: record, calibration and log loss by type, against the book where a price was posted
def ll(q, y): q = min(max(q, 1e-4), 1 - 1e-4); return -(y * math.log(q) + (1 - y) * math.log(1 - q))
byid = {p['id']: p for p in picks['picks']}
print(f'week {W}: {len(res)} of {len(picks["picks"])} picks graded')
rows = []
for k, r in res.items():
    if r == 'P': continue
    p = byid[k]; pr = p.get('price')
    rows.append(dict(type=p['type'], q=p['prob'], y=int(r == 'W'), b=pr['implied'] if pr else None, board=k in picks['board']))
df = pd.DataFrame(rows)
for t, x in list(df.groupby('type')) + [('ALL', df), ('Top plays', df[df.board])]:
    s = f"{t:11} n={len(x):4}  {x.y.sum():3}-{len(x)-x.y.sum():<3}  avg prob {x.q.mean():.3f} hit {x.y.mean():.3f}  logloss {x.apply(lambda r: ll(r.q, r.y), axis=1).mean():.4f}"
    xb = x[x.b.notna()]
    if len(xb): s += f"   | priced n={len(xb)} model {xb.apply(lambda r: ll(r.q, r.y), axis=1).mean():.4f} book {xb.apply(lambda r: ll(r.b, r.y), axis=1).mean():.4f}"
    print(s)
