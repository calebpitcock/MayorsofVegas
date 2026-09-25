"""Generate the live NFL slate (engine format) for 2026 Week 3 from nflverse data."""
import json, pandas as pd, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import nfl_build as nb

NAMES = dict(ARI='Cardinals',ATL='Falcons',BAL='Ravens',BUF='Bills',CAR='Panthers',CHI='Bears',CIN='Bengals',CLE='Browns',DAL='Cowboys',
  DEN='Broncos',DET='Lions',GB='Packers',HOU='Texans',IND='Colts',JAX='Jaguars',KC='Chiefs',LA='Rams',LAC='Chargers',LV='Raiders',
  MIA='Dolphins',MIN='Vikings',NE='Patriots',NO='Saints',NYG='Giants',NYJ='Jets',PHI='Eagles',PIT='Steelers',SEA='Seahawks',SF='49ers',
  TB='Buccaneers',TEN='Titans',WAS='Commanders')

SEASON, WEEK = 2026, 3
b = nb.Builder(SEASON)
dbk = nb.DefBook(b)
R = b.R
def pid_of(name, team=None):
    m = R[R.full_name == name]
    if team is not None and len(m) > 1: m = m[m.team == team]
    return m.index[-1]

# ---- this week's availability (practice reports + news, Friday morning) ----
OUT = {  # confident enough to remove; the page lets the user restore anyone
  'Jayden Daniels': 'elbow — out, Mariota starts', 'Caleb Williams': 'hamstring — out', 'Tyson Bagent': 'concussion — out',
  'Jaxson Dart': 'knee — season-ending surgery', 'Nico Collins': 'hamstring — DNP Wed/Thu, not expected to play',
  'Puka Nacua': 'hip — DNP Wed/Thu, McVay: "not making great progress"', 'Zay Flowers': 'hamstring — DNP, brace for absence',
  'Jayden Reed': 'neck — out',
}
QUESTIONABLE = {  # kept in; flagged
  'Mike Evans': 'hip — DNP Wed/Thu, reportedly minor', 'DJ Moore': 'shoulder — DNP Wed/Thu', 'Keon Coleman': 'ankle — DNP Wed/Thu',
  'Xavier Legette': 'knee — DNP Wed/Thu', 'Jalen Coker': 'ankle — DNP Wed/Thu', 'DeVonta Smith': 'hamstring — DNP (plays Monday)',
  'Dallas Goedert': 'knee — DNP (plays Monday)', 'Tank Bigsby': 'abdomen — DNP (plays Monday)', 'Will Shipley': 'foot — DNP (plays Monday)',
  'Rico Dowdle': 'toe — DNP Wed/Thu', 'Tyjae Spears': 'ankle — DNP Wed/Thu', 'Kendre Miller': 'illness — DNP', 'Alec Pierce': 'heel — DNP Wed/Thu',
  'Caleb Douglas': 'ankle — DNP Wed/Thu', 'Mason Taylor': 'thumb — DNP Wed/Thu', 'Andrei Iosivas': 'thumb — DNP',
  'Kyle Monangai': 'knee — DNP', 'Jonah Coleman': 'ankle — DNP', 'Colby Parkinson': 'knee — DNP', 'Chig Okonkwo': 'hamstring — DNP',
  'Saquon Barkley': 'neck — limited', 'Aaron Jones': 'knee — limited', 'Brock Bowers': 'knee — limited', 'Travis Etienne': 'hamstring — limited',
  'Jaylen Warren': 'shoulder — limited', 'Tony Pollard': 'ankle — limited', 'Michael Pittman': 'foot — limited',
}
# official game statuses post Friday afternoon; until then the flagged list stands in for 'Questionable' in the role correction
b.status_override = {}
for _n in QUESTIONABLE:
    try: b.status_override[pid_of(_n)] = 'Questionable'
    except Exception: pass
STARTER = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))['STARTER']   # shared with gm/game_live.py
TIER = {'WAS': -1, 'CHI': -1, 'NYG': 0, 'MIN': 1}
QBWHY = {
  'WAS': "Daniels dislocated his elbow; Mariota starts. He threw 17 of Washington's 40 dropbacks in Week 2 after Daniels left, so the priors are about 20% his.",
  'CHI': "Caleb Williams (hamstring) and Tyson Bagent (concussion) both out — Case Keenum starts with zero snaps in the sample behind Chicago's usage.",
  'NYG': "Dart is out for the season. Winston started Week 2 (11 of 29, 111 yards), so roughly half the sample is his.",
  'MIN': "Murray is back from the concussion. He took 7 dropbacks in Week 1 before leaving; Wentz generated almost all of Minnesota's priors.",
}

old = json.load(open(os.path.join(os.path.dirname(__file__), '..', 'db', 'slate', 'current.json')))
oldp = {}
for g in old['data']['games'] if 'data' in old else old['games']:
    for p in g['players']:
        if p.get('mktP') is not None or p.get('mkt') is not None:
            oldp[p['n']] = {k: p[k] for k in ('mktP', 'mkt') if p.get(k) is not None}

L = nb.lines_for(SEASON, WEEK)
games = []
for r in L.itertuples():
    if pd.notna(r.home_score): continue          # already played
    a, h = r.away_team, r.home_team
    g = dict(id=f'{a}-{h}'.lower(), league='NFL', away=a, home=h, awayName=NAMES[a], homeName=NAMES[h],
             kick=f"{r.weekday[:3]} {int(r.gametime[:2])%12 or 12}:{r.gametime[3:]} ET" + (' · Brazil' if r.location == 'Neutral' else ''),
             spread=-float(r.spread_line), spreadSrc='book', total=float(r.total_line), totalSrc='book',
             ml=dict(away=int(r.away_moneyline), home=int(r.home_moneyline)),
             spreadOdds=dict(away=int(r.away_spread_odds), home=int(r.home_spread_odds)),
             totalOdds=dict(over=int(r.over_odds), under=int(r.under_odds)),
             neutral=bool(r.location == 'Neutral'), roof=None if pd.isna(r.roof) else r.roof,
             soft=dict(away=dict(run=.5, pass_=.5), home=dict(run=.5, pass_=.5)),
             passRate={}, pace={}, qb={}, players=[], live=dict(status='pre', hs=0, as_=0, secs=3600, scored=[]))
    notes = []
    g['defp'] = dict(away=dbk.profile(h, WEEK), home=dbk.profile(a, WEEK))   # the defense each offense faces
    for side, team in (('away', a), ('home', h)):
        pr, pace = b.team_env(team, WEEK)
        g['passRate'][side] = pr; g['pace'][side] = pace
        qb_pid = pid_of(STARTER[team]) if team in STARTER else b.starter(team, WEEK)
        excl = [pid_of(n) for n in OUT if (R.full_name == n).any() and R.loc[pid_of(n), 'team'] == team]
        rows = [x for x in b.team_players(team, WEEK, qb_pid=qb_pid, exclude=excl) if x['pos']=='QB' or x['rush']>=.04 or x['rec']>=.04]
        # QB-change flag computed from data: how much of this team's 2026 sample did the starter take?
        q = b.Q[(b.Q.posteam == team) & (b.Q.season == SEASON) & (b.Q.week < WEEK)]
        tot = q.groupby('week').db.sum()
        mine = q[q.pid == qb_pid].groupby('week').db.sum()
        prior = float((mine.reindex(tot.index).fillna(0) / tot).sum()) if len(tot) else 0.0
        if prior < len(tot) - 0.5:
            g['qb'][side] = dict(change=True, name=R.loc[qb_pid, 'full_name'], priorGames=round(prior, 2), tier=TIER.get(team, 0),
                                 why=QBWHY.get(team, f"{R.loc[qb_pid,'full_name']} took {prior:.1f} games' worth of the {len(tot)} in the sample."))
            notes.append(f"{team}: {R.loc[qb_pid,'full_name']} starts — usage priors discounted.")
        for p in rows:
            if p['n'] in oldp: p.update(oldp[p['n']])
            if p['n'] in QUESTIONABLE: p['flag'] = QUESTIONABLE[p['n']]
        outs = [n for n in OUT if (R.full_name == n).any() and R.loc[pid_of(n), 'team'] == team]
        for n in outs:
            notes.append(f"{team} without {n} ({OUT[n].split(' —')[0]}).")
        g['players'] += rows
    g['note'] = ' '.join(notes) if notes else ''
    games.append(g)

def fix(o):
    if isinstance(o, dict): return {('pass' if k == 'pass_' else 'as' if k == 'as_' else k): fix(v) for k, v in o.items()}
    if isinstance(o, list): return [fix(x) for x in o]
    return o
slate = fix(dict(label='Week 3 · Sept 27–28', league='NFL', updated=pd.Timestamp.now('UTC').isoformat(), version=24, engine=3,
                 source='nflverse play-by-play 2025–26 and snap counts (usage and role trends), practice reports + news (availability), DraftKings props and game lines via davidcantugtr/nfl-player-prop-opportunity, anytime-TD prices via jaredpatchett/NFL-Model (DraftKings estimated)',
                 games=games))
out = os.path.join(os.path.dirname(__file__), 'slate_nfl.json')
json.dump(slate, open(out, 'w'), indent=1)
print(len(games), 'games;', sum(len(g['players']) for g in games), 'players ->', out)
for g in games: print(g['id'], g['spread'], g['total'], g['ml'], len(g['players']), g['qb'].keys(), g['note'][:120])
