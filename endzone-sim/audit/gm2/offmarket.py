"""When DraftKings is off the market: consensus fair odds from every other book (de-vigged, median) vs DraftKings'
price for the same spread point / moneyline. Bet DK when its price beats consensus fair by a threshold. Graded on
results. Tuesday snapshots 2021-25 (jaredpatchett historical odds)."""
import json, numpy as np, pandas as pd
ABBR = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS','Washington Football Team':'WAS'}
imp = lambda o: -o / (-o + 100) if o < 0 else 100 / (o + 100); dec = lambda o: 1 + (o / 100 if o > 0 else 100 / -o)
G = pd.read_csv('/home/user/MayorsofVegas/data/games.csv'); G = G[G.result.notna()]
res = {(r.season, r.home_team, r.away_team): r.result for r in G.itertuples()}
rows = []
for f in ('/home/user/MayorsofVegas/data/hist_odds_2021_2023.jsonl', '/home/user/MayorsofVegas/data/hist_odds_2024_2025.jsonl'):
    for l in open(f):
        r = json.loads(l); h, a = ABBR.get(r['home_team']), ABBR.get(r['away_team'])
        y = res.get((r['season'], h, a))
        if y is None: continue
        hrs = (pd.Timestamp(r['commence_time']) - pd.Timestamp(r['snapshot_iso'])).total_seconds() / 3600
        if hrs <= 0: continue
        bk = {}
        for b in r['bookmakers']:
            for m in b['markets']:
                o = {('h' if x['name'] == r['home_team'] else 'a'): (x.get('point'), x['price']) for x in m['outcomes']}
                if len(o) == 2: bk.setdefault(m['key'], {})[b['key']] = o
        for mk in ('h2h', 'spreads'):
            if 'draftkings' not in bk.get(mk, {}): continue
            dk = bk[mk]['draftkings']; pt = dk['h'][0]
            fair = [imp(v['h'][1]) / (imp(v['h'][1]) + imp(v['a'][1])) for k, v in bk[mk].items() if k != 'draftkings' and v['h'][0] == pt]
            if len(fair) < 4: continue
            q = float(np.median(fair))
            for side, p in (('h', q), ('a', 1 - q)):
                price = dk[side][1]; ev = p * dec(price) - 1
                if mk == 'h2h': won = (y > 0) if side == 'h' else (y < 0); push = y == 0
                else: m_ = y + pt; won = (m_ > 0) if side == 'h' else (m_ < 0); push = m_ == 0
                rows.append(dict(season=r['season'], mk=mk, side=side, ev=ev, p=p, price=price, won=won, push=push, hrs=hrs, nb=len(fair)))
R = pd.DataFrame(rows); R = R[~R.push]
R['pl'] = np.where(R.won, R.price.map(dec) - 1, -1.0)
print(f"{len(R)//2} game-markets; DK vs consensus, Tuesday snapshots (median {R.hrs.median():.0f}h before kickoff)")
for mk in ('spreads', 'h2h'):
    x = R[R.mk == mk]
    for thr in (0.0, 0.01, 0.02, 0.03):
        s = x[x.ev > thr]
        print(f"  {mk:7s} DK EV>{thr:.0%} vs consensus: n={len(s):4d} win {s.won.mean():.3f} (consensus said {s.p.mean():.3f}) ROI {s.pl.mean():+.3f} ± {s.pl.std()/np.sqrt(max(1,len(s))):.3f} by season {s.groupby('season').pl.mean().round(3).to_dict()}")
    print(f"  {mk:7s} consensus calibration: predicted {x.p.mean():.3f} actual {x.won.mean():.3f}; every DK bet ROI {x.pl.mean():+.3f}")
