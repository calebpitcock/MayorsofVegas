import numpy as np, pandas as pd, model2
D=model2.build(dict(HG=14.0,CARRY=0.85,M0=3.0),dict(QHL=1500.0,QCARRY=0.8,QM0=100.0))
O=model2.walk(D,2016,2025,RHL=8.0); O.to_parquet('wf_rebuild.parquet')
G=pd.read_csv('../../data/games.csv'); G=G[G.game_type=='REG']
rep={'OAK':'LV','SD':'LAC','STL':'LA'}
co={}
for r in G.itertuples(): co[(r.season,rep.get(r.home_team,r.home_team))]=co.get((r.season,rep.get(r.home_team,r.home_team)),r.home_coach); co[(r.season,rep.get(r.away_team,r.away_team))]=co.get((r.season,rep.get(r.away_team,r.away_team)),r.away_coach)
last={}
for r in G.sort_values('week').itertuples(): last[(r.season,rep.get(r.home_team,r.home_team))]=r.home_coach; last[(r.season,rep.get(r.away_team,r.away_team))]=r.away_coach
newhc=lambda s,t: co.get((s,t))!=last.get((s-1,t))
O['newhc']=[newhc(s,h) or newhc(s,a) for s,h,a in zip(O.season,O.home_team,O.away_team)]
O=O[O.season>=2016].copy(); O['dis']=O.m-O.spread_line; O['ad']=O.dis.abs()
K=.15; O['lean']=O.spread_line+K*O.dis
push=O.result==O.spread_line
print(f"2016-25 walk-forward, {len(O)} games. MAE close {np.mean(np.abs(O.result-O.spread_line)):.3f}  model {np.mean(np.abs(O.result-O.m)):.3f}  close+15% lean {np.mean(np.abs(O.result-O.lean)):.3f}")
print(f"typical disagreement with the close: median {O.ad.median():.1f} pts, 90th pct {O.ad.quantile(.9):.1f}")
def tab(X,lab):
    print(f"\n{lab}")
    print(f"  {'|model - close|':16s} {'games':>6s} {'model side covers':>18s} {'best k (fit here)':>18s} {'MAE close':>10s} {'MAE lean':>9s}")
    for lo,hi in ((0,2),(2,4),(4,6),(6,99)):
        x=X[(X.ad>=lo)&(X.ad<hi)]; y=x[x.result!=x.spread_line]
        cov=np.mean(np.sign(y.result-y.spread_line)==np.sign(y.dis))
        k=float((x.dis@(x.result-x.spread_line))/(x.dis@x.dis))
        print(f"  {f'{lo}-{hi if hi<99 else chr(43)} pts':16s} {len(x):6d} {cov:18.3f} {k:18.3f} {np.mean(np.abs(x.result-x.spread_line)):10.3f} {np.mean(np.abs(x.result-x.lean)):9.3f}")
tab(O,'All games')
tab(O[O.week<=4],'Weeks 1-4')
tab(O[(O.week<=6)&O.newhc],'Weeks 1-6, a team with a new head coach')
tab(O[(O.week<=6)&~O.newhc],'Weeks 1-6, no new head coach')
