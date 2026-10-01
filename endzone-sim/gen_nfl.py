"""Generate the live NFL slate (engine format) for the week in overrides.json from nflverse data. Games already
played are skipped, so a refresh right before kickoff shows only what is left."""
import json, pandas as pd, numpy as np, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import nfl_build as nb

NAMES = dict(ARI='Cardinals',ATL='Falcons',BAL='Ravens',BUF='Bills',CAR='Panthers',CHI='Bears',CIN='Bengals',CLE='Browns',DAL='Cowboys',
  DEN='Broncos',DET='Lions',GB='Packers',HOU='Texans',IND='Colts',JAX='Jaguars',KC='Chiefs',LA='Rams',LAC='Chargers',LV='Raiders',
  MIA='Dolphins',MIN='Vikings',NE='Patriots',NO='Saints',NYG='Giants',NYJ='Jets',PHI='Eagles',PIT='Steelers',SEA='Seahawks',SF='49ers',
  TB='Buccaneers',TEN='Titans',WAS='Commanders')

SEASON = 2026
WEEK = int(os.environ.get('EZWEEK') or json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))['week'])
b = nb.Builder(SEASON)
dbk = nb.DefBook(b)
R = b.R
def pid_of(name, team=None):
    m = R[R.full_name == name]
    if team is not None and len(m) > 1: m = m[m.team == team]
    if len(m) > 1 and m.position.isin(['QB', 'RB', 'FB', 'WR', 'TE']).any(): m = m[m.position.isin(['QB', 'RB', 'FB', 'WR', 'TE'])]   # e.g. CLE LB Justin Jefferson
    return m.index[-1]

# ---- this week's availability (practice reports + news, Thursday Oct 1 midday: Wednesday practice, TNF final statuses) ----
OUT = {  # confident enough to remove; the page lets the user restore anyone
  'Jayden Daniels': 'elbow — out, Mariota starts', 'Caleb Williams': 'hamstring — out (grade 2, 3-4 weeks)',
  'Jaxson Dart': 'knee — season-ending surgery', 'Baker Mayfield': 'thumb — dislocated, out about three weeks; Jalon Daniels starts',
  'Jayden Reed': 'neck — season-ending surgery', "De'Von Achane": 'out for the season',
  'Rico Dowdle': 'toe — ruled out', 'Tylan Wallace': 'ruled out',
  'Breece Hall': 'quad — not expected to play', 'Adonai Mitchell': 'finger — week-to-week', 'Mason Taylor': 'thumb — week-to-week',
  'Travis Etienne': 'hamstring — out multiple weeks', 'Terrance Ferguson': 'ankle — aggravated, not expected to play',
  'Dallas Goedert': 'knee — missed Week 3 and Wednesday, expected to miss multiple games',
  'Marquise Brown': 'ankle — missed Week 3 and Wednesday',
}
QUESTIONABLE = {  # kept in; flagged
  'Justin Jefferson': 'ankle sprain — DNP Wed, day-to-day; Friday status not out yet', 'DeVonta Smith': 'hamstring — DNP Wed (same path as Week 3, when he played)',
  'Will Shipley': 'foot — DNP Wed (played Week 3)', 'Chris Godwin Jr.': 'ankle — DNP Wed (new injury)', 'Rachaad White': 'shoulder — DNP Wed',
  'Mike Evans': 'rib — DNP Wed, reportedly minor', 'Keon Coleman': 'ankle — DNP Wed', 'Xavier Legette': 'knee — DNP Wed',
  'Jalen Coker': 'quad — DNP Wed, probably out', 'Caleb Douglas': 'ankle — DNP Wed, sat Week 3', 'Colby Parkinson': 'knee/shoulder — DNP Wed',
  'Charlie Kolar': 'forearm — DNP Wed', 'Brenen Thompson': 'quad — DNP Wed', 'Tony Pollard': 'foot — DNP Wed (played hurt Week 3)',
  'Tyjae Spears': 'ankle — DNP Wed (played hurt Week 3)', 'Tyrone Tracy Jr.': 'DNP Wed',
}
# skill players in OUT stay on the slate marked out, so the engine's scratch rule hands their carries and targets to the
# next men up at their position (72%, by share) instead of to the anonymous Field. QBs are replaced through STARTER.
SKILL_OUT = {}
for _n in OUT:
    try: _p = pid_of(_n)
    except Exception: continue
    if R.loc[_p, 'position'] in ('RB', 'FB', 'WR', 'TE'): SKILL_OUT[_p] = _n
if b.ACT is not None: b.ACT |= set(SKILL_OUT)      # reserve-list players (Achane, Reed) still need their share computed
# Official report (nflverse injuries, game statuses post Friday afternoon): Out and Doubtful are removed, Questionable
# is flagged. The hand lists above win for anyone named in them, except that an official Out/Doubtful overrides a hand
# 'questionable'. Keyed by gsis id, so same-name players can't be confused.
OFFICIAL_OUT = {}
_f = f'{nb.D}/injuries_{SEASON}.csv'
if os.path.exists(_f):
    _i = pd.read_csv(_f); _i = _i[(_i.week == WEEK) & (_i.game_type == 'REG') & _i.position.isin(['QB', 'RB', 'FB', 'WR', 'TE'])]
    for r in _i.itertuples():
        inj = r.report_primary_injury.lower() if isinstance(r.report_primary_injury, str) else 'injury'
        if r.report_status in ('Out', 'Doubtful') and r.full_name not in OUT:
            OFFICIAL_OUT[r.gsis_id] = (r.full_name, r.team, f"{inj} — {r.report_status.lower()} (official)"); QUESTIONABLE.pop(r.full_name, None)
        elif r.report_status == 'Questionable' and r.full_name not in OUT and r.full_name not in QUESTIONABLE:
            QUESTIONABLE[r.full_name] = f"{inj} — questionable (official)"
    # the official report comes out after the hand list was written: a player it lists as Questionable (practising,
    # undecided) is kept and flagged rather than removed on older news. No game status yet (Monday games) leaves the hand list.
    for r in _i.itertuples():
        if r.report_status == 'Questionable' and r.full_name in OUT:
            print(f'official Questionable overrides hand out: {r.full_name}'); OUT.pop(r.full_name)
            QUESTIONABLE[r.full_name] = f"{r.report_primary_injury.lower() if isinstance(r.report_primary_injury, str) else 'injury'} — questionable (official)"
print('official report: out/doubtful', len(OFFICIAL_OUT), [v[0] for v in OFFICIAL_OUT.values()])
# official game statuses post Friday afternoon; until then the flagged list stands in for 'Questionable' in the role correction
b.status_override = {}
for _n in QUESTIONABLE:
    try: b.status_override[pid_of(_n)] = 'Questionable'
    except Exception: pass
STARTER = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))['STARTER']   # shared with gm/game_live.py
TIER = {'WAS': -1, 'CHI': -1, 'NYG': 0, 'MIN': 1, 'TB': -1}
QBWHY = {
  'WAS': "Daniels dislocated his elbow; Mariota starts. He threw 17 of Washington's 40 dropbacks in Week 2 after Daniels left, so the priors are about 20% his.",
  'CHI': "Caleb Williams (hamstring) and Tyson Bagent (concussion) both out — Case Keenum starts with zero snaps in the sample behind Chicago's usage.",
  'NYG': "Dart is out for the season. Winston started Week 2 (11 of 29, 111 yards), so roughly half the sample is his.",
  'SEA': "Darnold is back from the glute injury (full practice, no game status, depth-chart QB1). He left Week 1 after 5 snaps and Lock started Week 2, so Seattle's 2026 sample is almost all Lock.",
  'TB': "Baker Mayfield dislocated his right thumb (out about three weeks). Undrafted rookie Jalon Daniels makes his first NFL start with no regular-season snaps, so none of Tampa Bay's usage sample is his.",
  'MIN': "Murray is back from the concussion. He took 7 dropbacks in Week 1 before leaving; Wentz generated almost all of Minnesota's priors.",
}

_oldf = os.path.join(os.path.dirname(__file__), '..', 'db', 'slate', 'current.json')   # the page's last slate (kept prices); absent in a fresh session
old = json.load(open(_oldf)) if os.path.exists(_oldf) else {'games': []}
oldp = {}
for g in old['data']['games'] if 'data' in old else old['games']:
    for p in g['players']:
        if p.get('mktP') is not None or p.get('mkt') is not None:
            oldp[p['n']] = {k: p[k] for k in ('mktP', 'mkt') if p.get(k) is not None}

L = nb.lines_for(SEASON, WEEK)
AGG = nb.coach_agg(SEASON, WEEK)          # head coach fourth-down aggressiveness (log-odds shift)
import scheme_match as sm
COV = sm.week_tables(SEASON, WEEK)        # coverage/blitz matchups (charting data)
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
    g['agg'] = dict(away=AGG.get(a, 0.0), home=AGG.get(h, 0.0))
    g['defScheme'] = dict(away={k: round(COV[k]['d'].get(h, COV[k]['lg']), 3) for k in ('man', 'blitz')}, home={k: round(COV[k]['d'].get(a, COV[k]['lg']), 3) for k in ('man', 'blitz')}, lg={k: round(COV[k]['lg'], 3) for k in ('man', 'blitz')})
    if pd.notna(r.wind): g['wind'] = float(r.wind)
    notes = []
    g['defp'] = dict(away=dbk.profile(h, WEEK), home=dbk.profile(a, WEEK))   # the defense each offense faces
    for side, team in (('away', a), ('home', h)):
        pr, pace = b.team_env(team, WEEK)
        g['passRate'][side] = pr; g['pace'][side] = pace
        excl = [pid_of(n) for n in OUT if (R.full_name == n).any() and R.loc[pid_of(n), 'team'] == team and pid_of(n) not in SKILL_OUT]
        excl += [pid for pid, (n, t, _) in OFFICIAL_OUT.items() if t == team]
        skill_out = [pid_of(n) for n in OUT if pid_of(n) in SKILL_OUT and R.loc[pid_of(n), 'team'] == team]
        qb_pid = pid_of(STARTER[team]) if team in STARTER else b.live_starter(team, WEEK, excl + skill_out)
        rows = [x for x in b.team_players(team, WEEK, qb_pid=qb_pid, exclude=excl) if x['pos']=='QB' or x['rush']>=.04 or x['rec']>=.04]
        # next men up: 72% of an out player's carries/targets (the engine's scratch share) goes to teammates at his position,
        # split by what they have actually done this season (recency-weighted carries or targets, +1 each) rather than
        # by model share, which gives backups with no 2026 snaps their position prior (NYJ: Davis and Nwangwu ~18% each).
        u26 = b.U[(b.U.posteam == team) & (b.U.season == SEASON) & (b.U.week < WEEK)]
        u26 = u26.assign(rw=np.power(0.5, (WEEK - u26.week) / nb.HL))
        used = {k: (u26.rw * u26[c]).groupby(u26.pid).sum().to_dict() for k, c in (('rush', 'car'), ('rec', 'tgt'))}
        for o in [x for x in rows if x['id'] in skill_out]:
            o['out'] = True; o['flag'] = OUT[SKILL_OUT[o['id']]]; o['outShare'] = dict(rush=o['rush'], rec=o['rec'])
            for k in ('rush', 'rec'):
                peers = [x for x in rows if x['id'] not in skill_out and x['pos'] == o['pos'] and x[k] > 0]
                wt = {x['id']: used[k].get(x['id'], 0.0) + 1.0 for x in peers}; tw = sum(wt.values())
                for x in peers: x[k] = round(x[k] + .72 * o[k] * wt[x['id']] / tw, 3)
                o[k] = 0.0          # already handed out; the engine's own scratch rule then has nothing left to move
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
            if p['n'] in QUESTIONABLE and not p.get('out'): p['flag'] = QUESTIONABLE[p['n']]
            if p['pos'] in ('WR', 'TE', 'RB'):
                opp = h if side == 'away' else a
                mult, parts = sm.multiplier(COV, p['id'], opp); p['cov'] = round(float(mult), 4); p['covParts'] = parts
        outs = [n for n in OUT if (R.full_name == n).any() and R.loc[pid_of(n), 'team'] == team]
        for n in outs:
            notes.append(f"{team} without {n} ({OUT[n].split(' —')[0]}).")
        offs = [(n, w) for pid, (n, t, w) in OFFICIAL_OUT.items() if t == team and n not in outs]
        if offs: notes.append(f"{team} officially out/doubtful: " + ', '.join(f"{n} ({w.split(' —')[0]})" for n, w in offs) + '.')
        g['players'] += rows
    g['note'] = ' '.join(notes) if notes else ''
    games.append(g)

def fix(o):
    if isinstance(o, dict): return {('pass' if k == 'pass_' else 'as' if k == 'as_' else k): fix(v) for k, v in o.items()}
    if isinstance(o, list): return [fix(x) for x in o]
    return o
_days = pd.to_datetime(L[L.home_score.isna()].gameday)
_lab = f"Week {WEEK}" + (f" · {_days.min():%b} {_days.min().day}" + (f"–{_days.max().day}" if _days.max() != _days.min() else "") if len(_days) else "")
_old = old.get('data', old)
slate = fix(dict(label=_lab, league='NFL', updated=pd.Timestamp.now('UTC').isoformat(), version=int(_old.get('version', 0)) + 1, engine=3,
                 source='nflverse play-by-play 2025–26 and snap counts (usage and role trends), practice reports + news (availability), DraftKings props and game lines via davidcantugtr/nfl-player-prop-opportunity, anytime-TD prices via jaredpatchett/NFL-Model (DraftKings estimated)',
                 games=games))
out = os.environ.get('EZOUT') or os.path.join(os.path.dirname(__file__), 'slate_nfl.json')
json.dump(slate, open(out, 'w'), indent=1)
print(len(games), 'games;', sum(len(g['players']) for g in games), 'players ->', out)
for g in games: print(g['id'], g['spread'], g['total'], g['ml'], len(g['players']), g['qb'].keys(), g['note'][:120])
