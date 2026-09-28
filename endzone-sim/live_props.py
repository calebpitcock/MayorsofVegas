"""This week's DraftKings prop prices from the public nfl-player-prop-opportunity snapshot (Odds API)."""
import pandas as pd, numpy as np, json, sys, re, os
FULL = dict(ARI='Arizona Cardinals',ATL='Atlanta Falcons',BAL='Baltimore Ravens',BUF='Buffalo Bills',CAR='Carolina Panthers',CHI='Chicago Bears',
  CIN='Cincinnati Bengals',CLE='Cleveland Browns',DAL='Dallas Cowboys',DEN='Denver Broncos',DET='Detroit Lions',GB='Green Bay Packers',HOU='Houston Texans',
  IND='Indianapolis Colts',JAX='Jacksonville Jaguars',KC='Kansas City Chiefs',LA='Los Angeles Rams',LAC='Los Angeles Chargers',LV='Las Vegas Raiders',
  MIA='Miami Dolphins',MIN='Minnesota Vikings',NE='New England Patriots',NO='New Orleans Saints',NYG='New York Giants',NYJ='New York Jets',PHI='Philadelphia Eagles',
  PIT='Pittsburgh Steelers',SEA='Seattle Seahawks',SF='San Francisco 49ers',TB='Tampa Bay Buccaneers',TEN='Tennessee Titans',WAS='Washington Commanders')
MK = {'player_reception_yds': 'recYds', 'player_rush_yds': 'rushYds', 'player_receptions': 'rec', 'player_pass_yds': 'passYds', 'player_anytime_td': 'td'}
SPORTSBOOKS = {'draftkings'}   # the only book the user can bet
def dv(o): return (-o) / (-o + 100) if o < 0 else 100 / (o + 100)
norm = lambda n: re.sub(r"[.'\s]|jr|sr|iii|ii", "", n.lower())
def attach(slate, csv):
    d = pd.read_csv(csv)
    d = d[d['Book Key'].isin(SPORTSBOOKS)]
    if 'Market Window' in d: d = d[d['Market Window'] == 'Full Game']
    for g in slate['games']:
        for p in g['players']: p.pop('book', None)
    snap = d['Last Update'].max()
    n = 0
    for g in slate['games']:
        sub = d[(d.Home == FULL[g['home']]) & (d.Away == FULL[g['away']])]
        if sub.empty: continue
        g['propsAsOf'] = snap
        for p in g['players']:
            s = sub[sub.Player.map(norm) == norm(p['n'])]
            for mk, grp in s.groupby('Market Key'):
                key = MK.get(mk)
                if not key: continue
                # main line = the two-sided line priced closest to even
                best = None
                for L, gl in grp.groupby('Line'):
                    books = {}
                    for bk, gb in gl.groupby('Book Key'):
                        o = gb[gb.Side == 'Over']['American Odds']; u = gb[gb.Side == 'Under']['American Odds']
                        if len(o) and len(u): books[bk] = [int(o.iloc[0]), int(u.iloc[0])]
                    gap = min(abs(dv(o) - dv(u)) for o, u in books.values()) if books else 9
                    if books and (best is None or gap < best[2]): best = (float(L), books, gap)
                if not best: continue
                L, books, _ = best
                fair = float(np.mean([dv(o) / (dv(o) + dv(u)) for o, u in books.values()]))
                p.setdefault('book', {})[key] = dict(line=L, fair=round(fair, 4), books=books)
                n += 1
    return n, snap
if __name__ == '__main__':
    s = json.load(open('slate_nfl.json'))
    n, snap = attach(s, '/home/user/ext/nfl-player-prop-opportunity/data/latest/player_props.csv')
    json.dump(s, open('slate_nfl.json', 'w'))
    print('attached', n, 'props, snapshot', snap)
