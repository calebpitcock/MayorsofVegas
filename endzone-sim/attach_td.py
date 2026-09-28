"""This week's anytime-TD prices. Source: jaredpatchett/NFL-Model data/player_td.json (Odds API, best 'Yes' price across US books).
DraftKings is usually a bit shorter than the best price, so each is converted to an estimated DraftKings price with
logit(DK) = c + d*logit(best), fitted on 402 Week 2 2026 quotes where both were seen (residual sd 0.13)."""
import json, sys, numpy as np
C, D = 0.0704, 0.9462
imp = lambda o: -o / (-o + 100) if o < 0 else 100 / (o + 100)
def am(p): return -round(100 * p / (1 - p) / 5) * 5 if p >= .5 else round(100 * (1 - p) / p / 5) * 5
def attach(slate, path):
    src = json.load(open(path)); by = {x['player_id']: x for x in src['players'] if (x.get('market') or {}).get('anytime_td_price') is not None}
    n = 0
    for g in slate['games']:
        for p in g['players']:
            p.pop('mktP', None); p.pop('mkt', None); p.pop('bestTD', None); p.pop('mktSrc', None)
            x = by.get(p.get('id'))
            if not x: continue
            best = int(x['market']['anytime_td_price']); q = imp(best)
            z = C + D * np.log(q / (1 - q)); pdk = 1 / (1 + np.exp(-z))
            p['bestTD'] = best; p['mkt'] = int(am(pdk)); p['mktSrc'] = 'est'; n += 1
        g['tdAsOf'] = src['generated_at'][:19] + 'Z'
    return n
if __name__ == '__main__':
    s = json.load(open(sys.argv[1])); print('TD prices attached', attach(s, sys.argv[2])); json.dump(s, open(sys.argv[1], 'w'))
