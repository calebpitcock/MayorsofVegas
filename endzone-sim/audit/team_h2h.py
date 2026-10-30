"""Team offense vs a specific defense: does how many points a team scored vs this opponent relative to its implied
team total before predict how it does vs that implied total again? Same for team rushing/passing yards vs its own
recent average."""
import pandas as pd, numpy as np
G=pd.read_csv('games.csv'); G=G[G.result.notna()&G.spread_line.notna()&G.total_line.notna()].copy()
rep={'OAK':'LV','SD':'LAC','STL':'LA'}
for c in ('home_team','away_team'): G[c]=G[c].replace(rep)
h=G.assign(off=G.home_team,dfn=G.away_team,pts=G.home_score,imp=(G.total_line+G.spread_line)/2,coach=G.away_coach)
a=G.assign(off=G.away_team,dfn=G.home_team,pts=G.away_score,imp=(G.total_line-G.spread_line)/2,coach=G.home_coach)
T=pd.concat([h,a])[['gameday','game_id','season','off','dfn','pts','imp','coach']].sort_values(['gameday','game_id'])
T['r']=T.pts-T.imp
def test(key,lab):
    H={}; x=[]; n=[]
    for r in T[['off',key,'r']].itertuples(index=False):
        v=H.get((r[0],r[1]),[]); x.append(np.mean(v[-3:]) if v else np.nan); n.append(len(v)); H.setdefault((r[0],r[1]),[]).append(r[2])
    x=np.array(x); n=np.array(n); y=T.r.values
    for mn in (1,3):
        m=np.isfinite(x)&(n>=mn); c=np.corrcoef(x[m],y[m])[0,1]
        hi=m&(x>4); lo=m&(x<-4)
        print(f"  {lab:40s} >= {mn} prior: n={m.sum():5d} corr {c:+.3f} (±{1.96/np.sqrt(m.sum()):.3f}) | beat it by 4+ before -> over {np.mean(y[hi]>0):.3f} (n={hi.sum()}), under by 4+ before -> over {np.mean(y[lo]>0):.3f}")
print("team points vs its implied team total (1999-2025), history vs this opponent:")
test('dfn','offense vs this defense (team)'); test('coach','offense vs this opposing head coach')
