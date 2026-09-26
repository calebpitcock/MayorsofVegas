"""Historical sportsbook props (Odds API snapshots, Tuesday 14:00 UTC) -> per game/player/market consensus + best prices."""
import json, collections, numpy as np, pandas as pd, re, os, glob
# EZBOOK=draftkings restricts everything to one sportsbook: its own line, its own no-vig price, its own over/under prices.
BOOK = os.environ.get('EZBOOK')
ABBR = {v: k for k, v in dict(ARI='Arizona Cardinals',ATL='Atlanta Falcons',BAL='Baltimore Ravens',BUF='Buffalo Bills',CAR='Carolina Panthers',CHI='Chicago Bears',
  CIN='Cincinnati Bengals',CLE='Cleveland Browns',DAL='Dallas Cowboys',DEN='Denver Broncos',DET='Detroit Lions',GB='Green Bay Packers',HOU='Houston Texans',
  IND='Indianapolis Colts',JAX='Jacksonville Jaguars',KC='Kansas City Chiefs',LA='Los Angeles Rams',LAC='Los Angeles Chargers',LV='Las Vegas Raiders',
  MIA='Miami Dolphins',MIN='Minnesota Vikings',NE='New England Patriots',NO='New Orleans Saints',NYG='New York Giants',NYJ='New York Jets',PHI='Philadelphia Eagles',
  PIT='Pittsburgh Steelers',SEA='Seattle Seahawks',SF='San Francisco 49ers',TB='Tampa Bay Buccaneers',TEN='Tennessee Titans',WAS='Washington Commanders').items()}
def dv(o): return (-o) / (-o + 100) if o < 0 else 100 / (o + 100)
def records_2026():
    """2026 snapshots (nfl-player-prop-opportunity): for each game, the last snapshot taken before kickoff."""
    fs = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../data/snap26/*_player_props.csv')))
    D = pd.concat([pd.read_csv(f).assign(snap=pd.Timestamp(os.path.basename(f)[:16].replace('T', ' ').replace('Z', ''), tz='UTC')) for f in fs])
    D = D[D['Market Window'] == 'Full Game']
    D['kick'] = pd.to_datetime(D['Commence Time'], utc=True)
    D = D[D.snap < D.kick]
    D = D[D.snap == D.groupby('Event ID').snap.transform('max')]
    for (ev, wk, home, away), g in D.groupby(['Event ID', 'Week', 'Home', 'Away']):
        bms = collections.defaultdict(lambda: collections.defaultdict(list))
        for x in g.itertuples():
            bms[x._6][x._14].append(dict(name=x.Side, description=x.Player, point=x.Line, price=int(x._18)))
        yield dict(season=2026, week=int(wk), home_team=ABBR[home], away_team=ABBR[away], snap=str(g.snap.iloc[0]),
                   bookmakers=[dict(key=b, markets=[dict(key=k, outcomes=v) for k, v in ms.items()]) for b, ms in bms.items()])
def load(season):
    out = []
    src = records_2026() if season == 2026 else (json.loads(l) for l in open('../data/historical_player_props_2024_2025.jsonl'))
    for r in src:
        if r['season'] != season: continue
        by = collections.defaultdict(lambda: collections.defaultdict(dict))   # (player, market) -> line -> book -> {Over,Under}
        for b in r['bookmakers']:
            if BOOK and b['key'] != BOOK: continue
            for m in b['markets']:
                for o in m['outcomes']:
                    if o.get('point') is None: continue
                    by[(o['description'], m['key'])][o['point']].setdefault(b['key'], {})[o['name']] = o['price']
        for (pl, mk), lines in by.items():
            # consensus line: the one the most books hang with both sides (one book: its main line, the one priced nearest even)
            key = lambda kv: (sum(1 for v in kv[1].values() if 'Over' in v and 'Under' in v),
                              -min((abs(dv(v['Over']) - dv(v['Under'])) for v in kv[1].values() if 'Over' in v and 'Under' in v), default=9))
            best = max(lines.items(), key=key)
            L, books = best
            pairs = {k: v for k, v in books.items() if 'Over' in v and 'Under' in v}
            if not pairs: continue
            fair = np.mean([dv(v['Over']) / (dv(v['Over']) + dv(v['Under'])) for v in pairs.values()])
            out.append(dict(season=season, week=r['week'], home=r['home_team'], away=r['away_team'], n=pl, mk=mk, line=float(L),
                            fair=float(fair), nb=len(pairs), bestO=max(v['Over'] for v in pairs.values()), bestU=max(v['Under'] for v in pairs.values()),
                            books={k: [v['Over'], v['Under']] for k, v in pairs.items()}))
    return pd.DataFrame(out)
if __name__ == '__main__':
    d = load(2025); print(len(d), d.mk.value_counts().to_dict(), d.nb.describe().round(2).to_dict()); print(d.head(3).T)
