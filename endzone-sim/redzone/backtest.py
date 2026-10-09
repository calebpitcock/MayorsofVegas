"""Score Redzone Desk backtest runs (redzone/bt.sh) against what happened.
Usage: python3 redzone/backtest.py BTDIR VARIANT [VARIANT ...]     (BTDIR/<variant>/w<week>/dump.json)
For every player who played (offensive snaps > 0):
  anytime TD           log loss and Brier of the model's chance
  rec yds, rush yds,   at the books' line (the most common line in the last snapshot before kickoff, no-vig average):
  catches              log loss of the model's P(over) vs the book's, the model's side hit rate, and the bias
                       (average P(over) minus how often the over hit; negative = projections run low)
The first variant is the baseline: the other variants get a paired difference with a 90% interval from resampling games."""
import json, os, sys, glob, math, numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, '..', '..', 'data'); S = 2026
SNAP = '/home/user/ext/nfl-player-prop-opportunity/data/snapshots'
FULL = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'}
MK = {'player_reception_yds': 'recYds', 'player_rush_yds': 'rushYds', 'player_receptions': 'rec'}

def outcomes(W):
    P = pd.read_csv(f'{D}/play_by_play_{S}.csv.gz', low_memory=False); P = P[(P.week == W) & (P.two_point_attempt != 1)]
    rec = P[(P.complete_pass == 1) & P.receiver_player_id.notna()]
    o = dict(rushYds=P[P.rusher_player_id.notna()].groupby('rusher_player_id').rushing_yards.sum().to_dict(),
             recYds=rec.groupby('receiver_player_id').receiving_yards.sum().to_dict(), rec=rec.groupby('receiver_player_id').size().to_dict())
    tds = set(P[P.td_player_id.notna()].td_player_id)
    SN = pd.read_csv(f'{D}/snap_counts_{S}.csv'); SN = SN[(SN.season == S) & (SN.week == W) & (SN.offense_snaps > 0)]
    R = pd.read_csv(f'{D}/roster_{S}.csv', low_memory=False); p2g = dict(zip(R.pfr_id, R.gsis_id))
    return o, tds, {p2g.get(x) for x in SN.pfr_player_id}

def lines(W):
    """(game id, player name, stat) -> (line, book no-vig P(over)) from the last snapshot before kickoff."""
    G = pd.read_csv(f'{D}/games.csv'); G = G[(G.season == S) & (G.week == W)]
    gid = {(r.away_team, r.home_team): f'{r.away_team}-{r.home_team}'.lower() for r in G.itertuples()}
    rows = []
    for f in sorted(glob.glob(f'{SNAP}/2026-W*/*_player_props.csv')):
        x = pd.read_csv(f); x = x[x['Market Key'].isin(MK) & (x['Market Window'] == 'Full Game')]
        if not len(x): continue
        x = x.assign(snap=pd.to_datetime(os.path.basename(f).split('_')[0], utc=True), kick=pd.to_datetime(x['Commence Time']))
        x = x[x.snap < x.kick]; x['g'] = [gid.get((FULL.get(a), FULL.get(h))) for a, h in zip(x.Away, x.Home)]
        rows.append(x[x.g.notna()])
    x = pd.concat(rows); x = x[x.snap == x.groupby('g').snap.transform('max')]
    out = {}
    for (g, n, m), y in x.groupby(['g', 'Player', 'Market Key']):
        line = y.Line.mode().iloc[0]; y = y[y.Line == line]; ov = y[y.Side == 'Over']['No-Vig Implied']
        if len(ov): out[(g, n, MK[m])] = (float(line), float(ov.mean()))
    return out

def ll(q, y): q = min(max(q, 1e-3), 1 - 1e-3); return -(y * math.log(q) + (1 - y) * math.log(1 - q))

def rows_for(bt, var, W, cache):
    f = f'{bt}/{var}/w{W}/dump.json'
    if not os.path.exists(f): return None
    if W not in cache: cache[W] = (outcomes(W), lines(W))
    (o, tds, played), L = cache[W]
    out = []
    for p in json.load(open(f)):
        if p['id'] not in played: continue
        k = (p['gid'], p['id'])
        out.append(dict(k=k, g=f"{W}-{p['gid']}", W=W, kind='td', pos=p['pos'], q=p['td'], y=int(p['id'] in tds), b=None))
        for st in ('recYds', 'rushYds', 'rec'):
            if (p['gid'], p['n'], st) not in L or p['pos'] == 'QB' and st != 'rushYds': continue
            line, bk = L[(p['gid'], p['n'], st)]; v = o[st].get(p['id'], 0)
            if v == line: continue
            q = p[st][min(len(p[st]) - 1, math.ceil(line))]
            out.append(dict(k=k + (st,), g=f"{W}-{p['gid']}", W=W, kind=st, pos=p['pos'], q=q, y=int(v > line), b=bk))
    return pd.DataFrame(out)

def summary(df):
    s = {}
    for kind, x in df.groupby('kind'):
        r = dict(n=len(x), ll=x.apply(lambda r: ll(r.q, r.y), axis=1).mean())
        if kind == 'td': r.update(p=x.q.mean(), hit=x.y.mean(), brier=((x.q - x.y) ** 2).mean())
        else:
            r.update(book=x.apply(lambda r: ll(r.b, r.y), axis=1).mean(), side=((x.q > .5) == (x.y == 1)).mean(), bias=x.q.mean() - x.y.mean())
            e = x[(x.q - x.b).abs() >= .08]; r.update(edge_n=len(e), edge_hit=((e.q > e.b) == (e.y == 1)).mean() if len(e) else float('nan'))
        s[kind] = r
    return s

def main():
    bt, vars_ = sys.argv[1], sys.argv[2:]; cache = {}
    frames = {}
    for v in vars_:
        fs = [rows_for(bt, v, W, cache) for W in range(1, 19)]
        fs = [f for f in fs if f is not None]
        if fs: frames[v] = pd.concat(fs)
    base = vars_[0]; B = frames[base]
    for v, df in frames.items():
        print(f'== {v}  weeks {sorted(df.W.unique())}')
        for kind, r in summary(df).items():
            line = f"  {kind:8} n={r['n']:4} logloss {r['ll']:.4f}"
            if kind == 'td': line += f"  avg {r['p']:.3f} hit {r['hit']:.3f} brier {r['brier']:.4f}"
            else: line += f"  book {r['book']:.4f}  side hit {r['side']:.3f}  bias {r['bias']:+.3f}  edges(>=8pt) {r['edge_n']} hit {r['edge_hit']:.3f}"
            if v != base:
                m = df.merge(B, on=['k', 'kind', 'g', 'y'], suffixes=('', '_b')); m = m[m.kind == kind]
                if len(m):
                    m['d'] = [ll(a, y) - ll(b, y) for a, b, y in zip(m.q, m.q_b, m.y)]
                    per = m.groupby('g').d.sum(); gs = per.index.values; rng = np.random.default_rng(0)
                    boots = [per.loc[rng.choice(gs, len(gs))].sum() / len(m) for _ in range(2000)]
                    line += f"  | vs {base}: {m.d.mean():+.4f} [{np.percentile(boots, 5):+.4f}, {np.percentile(boots, 95):+.4f}]"
            print(line)

if __name__ == '__main__': main()
