import pandas as pd, numpy as np
T=pd.read_parquet('team_games_hab.parquet'); T=T[T.season<=2025]
def agg(d): return pd.Series(dict(go=d.go.sum()/max(1,d.g4.sum()), g4=d.g4.sum(), tds=d.td.sum()/max(1,(d.td+d.fg).sum()),
    rztd=d.rztd.sum()/max(1,d.rzn.sum()), prate=d.np_.sum()/max(1,d.nn.sum()), n=len(d), coach=d.coach.mode().iloc[0]))
def rel(a,b,lab):
    m=a.notna()&b.notna(); r=np.corrcoef(a[m],b[m])[0,1]; print(f"   {lab:44s} r={r:+.2f}  (n={m.sum()})"); return r
print("SPLIT-HALF within a season (odd vs even weeks) -> how much of a team's number is real, not noise")
odd=T[T.week%2==1].groupby(['posteam','season']).apply(agg); even=T[T.week%2==0].groupby(['posteam','season']).apply(agg)
J=odd.join(even,lsuffix='_o',rsuffix='_e')
res={}
for k,lab in (('go','4th-down go rate (4th & <=3, own 35+)'),('tds','TD share of scores (TD / (TD+FG))'),('rztd','red-zone TD rate'),('prate','neutral-situation pass rate')):
    r=rel(J[k+'_o'],J[k+'_e'],lab); res[k]=2*r/(1+r)
print("   -> full-season reliability (Spearman-Brown):",{k:round(v,2) for k,v in res.items()})
print("\nYEAR TO YEAR, same head coach vs new head coach")
S=T.groupby(['posteam','season']).apply(agg).reset_index().sort_values(['posteam','season'])
for k in ('go','tds','rztd','prate'): S[k+'_prev']=S.groupby('posteam')[k].shift(1)
S['coach_prev']=S.groupby('posteam').coach.shift(1); S=S.dropna(subset=['coach_prev'])
same=S[S.coach==S.coach_prev]; new=S[S.coach!=S.coach_prev]
for k,lab in (('go','4th-down go rate'),('tds','TD share of scores'),('rztd','red-zone TD rate'),('prate','neutral pass rate')):
    # remove the league-wide trend first (go rates rose every year)
    S[k+'_d']=S[k]-S.groupby('season')[k].transform('mean'); S[k+'_pd']=S[k+'_prev']-S.groupby('season')[k+'_prev'].transform('mean')
    a=S[S.coach==S.coach_prev]; b=S[S.coach!=S.coach_prev]
    print(f"   {lab:22s} same coach r={np.corrcoef(a[k+'_d'],a[k+'_pd'])[0,1]:+.2f} (n={len(a)})   new coach r={np.corrcoef(b[k+'_d'],b[k+'_pd'])[0,1]:+.2f} (n={len(b)})")
# does going for it more produce more TDs per score (the thing anytime-TD prices hang on)?
S['tds_d']=S.tds-S.groupby('season').tds.transform('mean'); S['go_d']=S.go-S.groupby('season').go.transform('mean')
b=np.polyfit(S.go_d,S.tds_d,1)[0]; print(f"\nTD share vs go rate (season level, league-trend removed): +10 pts of go rate -> {10*b:+.3f} TD share  corr {np.corrcoef(S.go_d,S.tds_d)[0,1]:+.2f}")
print("\nspread of true team TD share (signal SD after removing noise):", round(float(np.sqrt(res['tds'])*S.groupby('season').tds.std().mean()),3),
      " league mean", round(float(S.tds.mean()),3))
L=T.groupby('season').apply(lambda d: d.go.sum()/d.g4.sum()); print("\nleague go rate, 4th & <=3 from own 35 or closer:", L.round(2).to_dict())
Z=T[T.season==2025].groupby('posteam').apply(agg).sort_values('go'); print("\n2025 go rate extremes:\n", Z[['coach','go','g4','tds','prate']].iloc[list(range(4))+list(range(-4,0))].round(3).to_string())
