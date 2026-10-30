"""DraftKings spread and moneyline as of Tuesday 14:00 UTC of game week (jaredpatchett/NFL-Model snapshots, 2021-2025)."""
import json, pandas as pd, numpy as np
ABBR = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS','Washington Football Team':'WAS'}
rows = []
for f in ('../../data/hist_odds_2021_2023.jsonl', '../../data/hist_odds_2024_2025.jsonl'):
    for l in open(f):
        r = json.loads(l)
        dk = [b for b in r['bookmakers'] if b['key'] == 'draftkings']
        if not dk: continue
        h, a = ABBR.get(r['home_team']), ABBR.get(r['away_team'])
        rec = dict(season=r['season'], week=r['week'], home=h, away=a, snap=r['snapshot_iso'], kick=r['commence_time'])
        for m in dk[0]['markets']:
            for o in m['outcomes']:
                side = 'h' if o['name'] == r['home_team'] else 'a'
                if m['key'] == 'spreads': rec[f'sp_{side}'] = o['point']; rec[f'spo_{side}'] = o['price']
                if m['key'] == 'h2h': rec[f'ml_{side}'] = o['price']
        rows.append(rec)
T = pd.DataFrame(rows)
T['hours'] = (pd.to_datetime(T.kick) - pd.to_datetime(T.snap)).dt.total_seconds() / 3600
T = T[T.hours > 0].sort_values('hours').drop_duplicates(['season', 'home', 'away'], keep='first')   # nearest Tuesday before kickoff
print(len(T), T.groupby('season').size().to_dict(), T.hours.describe().round(0).to_dict())
T.to_parquet('tue_dk.parquet')
