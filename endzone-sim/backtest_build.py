import json, sys, os, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import nfl_build as nb
import props_hist
MODE = os.environ.get('EZMODE', 'actual')
SEASON = int(os.environ.get('EZSEASON', 2025)); W0, W1 = int(sys.argv[1]) if len(sys.argv) > 1 else 4, int(sys.argv[2]) if len(sys.argv) > 2 else 18
b = nb.Builder(SEASON)
try:
    PROPS = props_hist.load(SEASON)
except Exception:
    PROPS = None
if PROPS is None or len(PROPS) == 0:
    import pandas as _pd; PROPS = _pd.DataFrame(columns=['week','home','away','n','mk','line','fair','bestO','bestU','nb'])
db_ = nb.DefBook(b)
G = pd.read_csv(f'{nb.D}/games.csv'); G = G[(G.season == SEASON) & (G.game_type == 'REG')]
out = []
for w in range(W0, W1 + 1):
    AGG = nb.coach_agg(SEASON, w)
    for r in G[G.week == w].itertuples():
        gid = r.game_id
        if pd.isna(r.spread_line) or pd.isna(r.home_score): continue
        g = dict(id=gid, league='NFL', away=r.away_team, home=r.home_team, spread=-float(r.spread_line), total=float(r.total_line),
                 ml=dict(away=None if pd.isna(r.away_moneyline) else int(r.away_moneyline), home=None if pd.isna(r.home_moneyline) else int(r.home_moneyline)),
                 result=dict(hs=int(r.home_score), as_=int(r.away_score)), passRate={}, pace={}, qb={}, players=[], week=w,
                 defp=dict(away=db_.profile(r.home_team, w), home=db_.profile(r.away_team, w)))
        g['agg'] = dict(away=AGG.get(r.away_team, 0.0), home=AGG.get(r.home_team, 0.0)); g['roof'] = None if pd.isna(r.roof) else r.roof
        if pd.notna(r.wind): g['wind'] = float(r.wind)
        act = {}
        for side, team in (('away', r.away_team), ('home', r.home_team)):
            sn = b.SN[(b.SN.game_id == gid) & (b.SN.team == team)]
            q = b.Q[(b.Q.game_id == gid) & (b.Q.posteam == team)]
            if MODE == 'pregame':
                # only what was knowable early in the week: who played in this team's previous game
                prev = b.SN[(b.SN.team == team) & (b.SN.season == SEASON) & (b.SN.week < w)]
                lastw = prev.week.max() if len(prev) else None
                active = set(prev[prev.week == lastw].pid) if lastw is not None else set(sn.pid)
                qb = b.starter(team, w)
            else:
                active = set(sn.pid)
                qb = q.sort_values('db').pid.iloc[-1] if len(q) else None
            pr, pace = b.team_env(team, w)
            g['passRate'][side] = pr; g['pace'][side] = pace
            rows = [x for x in b.team_players(team, w, active_pids=active, qb_pid=qb) if x['pos'] == 'QB' or x['rush'] >= .04 or x['rec'] >= .04]
            # QB change flag from data
            qh = b.Q[(b.Q.posteam == team) & (b.Q.season == SEASON) & (b.Q.week < w)]
            tot = qh.groupby('week').db.sum(); mine = qh[qh.pid == qb].groupby('week').db.sum()
            n_s = len(tot); prior = float((mine.reindex(tot.index).fillna(0) / tot).sum()) if n_s else 0
            if n_s and prior < n_s - 0.5:
                g['qb'][side] = dict(change=True, priorGames=min(2, prior), tier=0)
            g['players'] += rows
            u = b.U[(b.U.game_id == gid) & (b.U.posteam == team)].set_index('pid')
            for x in rows:
                pid = x['id']; a = dict(car=0, ry=0, tgt=0, rec=0, recy=0, td=0)
                if pid in u.index:
                    uu = u.loc[pid]; a = dict(car=int(uu.car), ry=int(uu.ry), tgt=int(uu.tgt), rec=int(uu.rec), recy=int(uu.recy), td=int(uu.rtd + uu.ctd))
                if x['pos'] == 'QB' and len(q):
                    qq = q[q.pid == pid]
                    a.update(att=int(qq.att.sum()), cmp=int(qq.cmp.sum()), py=int(qq.py.sum()), ptd=int(qq.ptd.sum()), ints=int(qq.ints.sum()))
                act[x['n']] = a
        g['actual'] = act
        pr = PROPS[(PROPS.week == w) & (PROPS.home == r.home_team) & (PROPS.away == r.away_team)]
        names = {x['n'] for x in g['players']}
        g['props'] = [dict(n=x.n, mk=x.mk, line=x.line, fair=x.fair, bestO=int(x.bestO), bestU=int(x.bestU), nb=int(x.nb)) for x in pr.itertuples() if x.n in names]
        out.append(g)
    print('week', w, len(out), file=sys.stderr)
def fix(o):
    if isinstance(o, dict): return {('as' if k == 'as_' else k): fix(v) for k, v in o.items()}
    if isinstance(o, list): return [fix(x) for x in o]
    return o
json.dump(fix(out), open(os.path.join(os.path.dirname(__file__), f'bt_{SEASON}_{W0}_{W1}{"_pre" if MODE=="pregame" else ""}{"_"+props_hist.BOOK if props_hist.BOOK else ""}{"_r"+nb.ROLE if "EZROLE" in os.environ else ""}.json'), 'w'))
print('props attached', sum(len(g['props']) for g in out))
print(len(out), 'games')
