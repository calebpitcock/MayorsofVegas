import numpy as np, pandas as pd, model2, os
if os.path.exists('D.parquet'): D=pd.read_parquet('D.parquet')
else: D=model2.build(dict(HG=14.0,CARRY=0.85,M0=3.0),dict(QHL=1500.0,QCARRY=0.8,QM0=100.0)); D.to_parquet('D.parquet')
def mae(cols,S0=2016,S1=2025,**kw):
    O=model2.walk(D,S0,S1,RHL=8.0,cols=cols,**kw); return O, float(np.mean(np.abs(O.result-O.m)))
base,mb=mae(model2.F); print(f"live features          MAE {mb:.3f}  (close {np.mean(np.abs(base.result-base.spread_line)):.3f})")
for cols in (['sr','qb','qbd','rest','div','neutral'],['epa','qb','qbd','rest','div','neutral'],['sr','epa','qb','rest','div','neutral']):
    O,m=mae(cols); print(f"{'+'.join(c for c in cols if c not in ('rest','div','neutral')):22s} MAE {m:.3f}")
# home field by era: fitted intercept vs what home teams actually did relative to the model
O=base.copy(); O['res']=O.result-O.m
print("\nhome-field: intercept the walk-forward used vs home residual (actual - model) by season")
print(O.groupby('season').agg(hfa_used=('hfa','first'),home_resid=('res','mean'),n=('res','size')).round(2).T.to_string())
# second-year / young QB: are young starters underrated?
Q=pd.read_parquet('qb_games.parquet'); first=Q.groupby('qb').season.min()
G=pd.read_csv('../../data/games.csv')[['game_id','home_qb_id','away_qb_id']]
O=O.merge(G,on='game_id',how='left')
O['hy']=O.season-O.home_qb_id.map(first); O['ay']=O.season-O.away_qb_id.map(first)
first_in=first[first>2012]   # careers that start inside the data
rows=[]
for side,sgn in (('h',1),('a',-1)):
    q=O[f'{"home" if side=="h" else "away"}_qb_id']; yrs=O[f'{side}y']; ok=q.isin(first_in.index)
    rows.append(pd.DataFrame(dict(yr=yrs[ok],res=sgn*O.res[ok],week=O.week[ok])))
R=pd.concat(rows)
print("\nmodel error by the QB's career year (+ = team did better than the model said), careers starting 2013+")
print(R[R.yr<=5].groupby('yr').res.agg(['mean','count','sem']).round(2).T.to_string())
print("career year 1 (2nd season), weeks 1-8:", R[(R.yr==1)&(R.week<=8)].res.agg(['mean','count','sem']).round(2).to_dict())
