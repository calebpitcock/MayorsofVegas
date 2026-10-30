"""Attach formation.py's g.form to a backtest slate, walk-forward: week w's inputs are that season's weeks < w from
nflverse participation (formation_plays.parquet from plays.py), same definitions as the live file (3+ WR share;
defense light box <= 6, stacked 8+, nickel/dime = 5+ DBs), with the defense's real play count.
Usage: attach_bt.py bt_XXXX.json [out.json]   (in place when no out)"""
import os, sys, json, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(H, '..', '..'))
import formation
D = os.path.join(H, '..', '..', '..', 'data')
P = pd.read_parquet(f'{D}/formation_plays.parquet')
P['w3'] = (P.nWR >= 3).astype(float); P['light'] = (P.box <= 6).astype(float); P['stack'] = (P.box >= 8).astype(float); P['sub'] = (P.nDB >= 5).astype(float)
f = sys.argv[1]; G = json.load(open(f)); n = 0
for w in sorted({g['week'] for g in G}):
    season = int(G[0]['id'][:4]); q = P[(P.season == season) & (P.week < w)]
    if q.empty: continue
    o = q.groupby('posteam').agg(p3=('w3', 'mean'), n=('w3', 'size'))
    d = q.groupby('defteam').agg(l=('light', 'mean'), h=('stack', 'mean'), s=('sub', 'mean'), n=('w3', 'size'))
    F = dict(off={t: [float(r.p3), int(r.n)] for t, r in o.iterrows()}, **{'def': {t: [0.0, float(r.l), float(r.h), float(r.s), int(r.n)] for t, r in d.iterrows()}})
    wk = [g for g in G if g['week'] == w]; formation.attach(wk, F, {}); n += sum(len(g['form']) for g in wk)
json.dump(G, open(sys.argv[2] if len(sys.argv) > 2 else f, 'w')); print(f, 'form sides attached', n)
