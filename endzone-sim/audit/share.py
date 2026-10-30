import pandas as pd, numpy as np
COLS=['game_id','season','season_type','week','posteam','play_type','pass_attempt','sack','two_point_attempt','receiver_player_id','rusher_player_id','qb_scramble','qb_kneel']
P=pd.concat([pd.read_csv(f'play_by_play_{s}.csv.gz',usecols=COLS,low_memory=False) for s in range(2016,2026)]); P=P[P.season_type=='REG']
rep={'OAK':'LV','SD':'LAC','STL':'LA'}; P['posteam']=P.posteam.replace(rep)
two=P.two_point_attempt.fillna(0)==1
tg=P[(P.play_type=='pass')&(P.pass_attempt==1)&(P.sack.fillna(0)==0)&~two&P.receiver_player_id.notna()].rename(columns={'receiver_player_id':'pid'})
ru=P[(P.play_type=='run')&(P.qb_scramble.fillna(0)==0)&(P.qb_kneel.fillna(0)==0)&~two&P.rusher_player_id.notna()].rename(columns={'rusher_player_id':'pid'})
G=pd.read_csv('games.csv'); G=G[G.game_type=='REG']
co={}
for r in G.itertuples(): co[(r.season,rep.get(r.home_team,r.home_team),r.week)]=r.home_coach; co[(r.season,rep.get(r.away_team,r.away_team),r.week)]=r.away_coach
first={}; last={}
for (s,t,w),c in sorted(co.items()):
    first.setdefault((s,t),c); last[(s,t)]=c
def shares(D, key):
    tot=D.groupby(['season','posteam']).size().rename('tot'); me=D.groupby(['season','posteam','pid']).size().rename('n')
    return (me/tot).rename(key).reset_index()
for D,lab in ((tg,'target share'),(ru,'carry share')):
    prev=shares(D,'prev'); prev['season']+=1
    early=shares(D[D.week<=3],'early'); rest=shares(D[D.week>=4],'rest')
    M=early.merge(prev,on=['season','posteam','pid']).merge(rest,on=['season','posteam','pid'])
    M['newhc']=[first.get((s,t))!=last.get((s-1,t)) for s,t in zip(M.season,M.posteam)]
    M=M[(M.prev>=.05)|(M.early>=.05)]
    print(f"\n{lab}: predicting weeks 4-18 share (players on the same team both years)")
    for f in (False,True):
        x=M[M.newhc==f]
        # best weight on last season vs weeks 1-3, fitted
        A=np.c_[x.prev,x.early]; w,*_=np.linalg.lstsq(A,x.rest,rcond=None)
        e_prev=np.mean(np.abs(x.rest-x.prev)); e_early=np.mean(np.abs(x.rest-x.early))
        print(f"  {'new head coach ' if f else 'same head coach'} n={len(x):4d}  error using last season {e_prev:.4f}, using weeks 1-3 {e_early:.4f}  | best blend: {w[0]/(w.sum()):.0%} last season / {w[1]/(w.sum()):.0%} weeks 1-3")
