"""Player-vs-opponent history: does how a player did against THIS defense before predict how he beats his usual
level against it again? Baseline = his own average over his previous 8 games (any opponent), the stand-in for a
projection. Residual = actual - baseline. Test: prior residuals vs this opponent -> this game's residual."""
import pandas as pd, numpy as np
COLS=['game_id','season','season_type','week','posteam','defteam','play_type','pass_attempt','sack','two_point_attempt','receiver_player_id',
      'rusher_player_id','complete_pass','receiving_yards','rushing_yards','rush_touchdown','pass_touchdown','qb_kneel','td_player_id']
P=pd.concat([pd.read_csv(f'play_by_play_{s}.csv.gz',usecols=COLS,low_memory=False) for s in range(2012,2026)]); P=P[P.season_type=='REG']
rep={'OAK':'LV','SD':'LAC','STL':'LA'}
for c in ('posteam','defteam'): P[c]=P[c].replace(rep)
two=P.two_point_attempt.fillna(0)==1
tg=P[(P.play_type=='pass')&(P.pass_attempt==1)&(P.sack.fillna(0)==0)&~two&P.receiver_player_id.notna()]
ru=P[(P.play_type=='run')&(P.qb_kneel.fillna(0)==0)&~two&P.rusher_player_id.notna()]
k=['game_id','season','week','posteam','defteam']
a=tg.groupby(k+['receiver_player_id']).agg(tgt=('play_type','size'),rec=('complete_pass','sum'),recy=('receiving_yards','sum')).reset_index().rename(columns={'receiver_player_id':'pid'})
b=ru.groupby(k+['rusher_player_id']).agg(car=('play_type','size'),ry=('rushing_yards','sum')).reset_index().rename(columns={'rusher_player_id':'pid'})
t=P[(P.td_player_id.notna())&((P.rush_touchdown==1)|(P.pass_touchdown==1))&~two].groupby(k+['td_player_id']).size().rename('td').reset_index().rename(columns={'td_player_id':'pid'})
U=a.merge(b,on=k+['pid'],how='outer').merge(t,on=k+['pid'],how='left').fillna({'tgt':0,'rec':0,'recy':0,'car':0,'ry':0,'td':0})
U=U[(U.tgt+U.car)>=3].copy(); U['anytd']=(U.td>0).astype(float)
G=pd.read_csv('games.csv'); G=G[G.game_type=='REG'][['game_id','gameday','home_team','away_team','home_coach','away_coach']]
U=U.merge(G,on='game_id'); U['oppcoach']=np.where(U.defteam==U.home_team.replace(rep),U.home_coach,U.away_coach)
U=U.sort_values(['pid','gameday']).reset_index(drop=True)
STATS=['recy','rec','ry','anytd']
for s in STATS:
    U[s+'_b']=U.groupby('pid')[s].transform(lambda x: x.shift(1).rolling(8,min_periods=4).mean())
    U[s+'_r']=U[s]-U[s+'_b']
def hist(key):
    out={s:[] for s in STATS}; cnt=[]; H={}
    for r in U[['pid',key]+[s+'_r' for s in STATS]].itertuples(index=False):
        h=H.get((r[0],r[1]),[])
        for i,s in enumerate(STATS): out[s].append(np.nanmean([x[i] for x in h]) if h else np.nan)
        cnt.append(len(h)); H.setdefault((r[0],r[1]),[]).append(r[2:])
    return out,np.array(cnt)
LAB={'recy':'receiving yards','rec':'receptions','ry':'rushing yards','anytd':'anytime TD'}
for key,lab in (('defteam','player vs this defense (team)'),('oppcoach','player vs this opposing head coach')):
    H,cnt=hist(key)
    print(f"\n=== {lab}: prior over/under-performance vs this opponent -> this game's over/under-performance, 2012-25")
    for s in STATS:
        x=np.array(H[s]); y=U[s+'_r'].values
        for mn,tag in ((1,'>=1 prior meeting'),(3,'>=3 prior meetings')):
            m=np.isfinite(x)&np.isfinite(y)&(cnt>=mn)
            r=np.corrcoef(x[m],y[m])[0,1]; sl=np.polyfit(x[m],y[m],1)[0]; n=m.sum()
            # 'bet it' rule: when he beat his baseline vs them before, how often does he beat it again (vs players with no edge)?
            hi=m&(x>np.nanpercentile(x[m],80)); lo=m&(x<np.nanpercentile(x[m],20))
            print(f"  {LAB[s]:16s} {tag:18s} n={n:6d} corr {r:+.3f} (±{1.96/np.sqrt(n):.3f}) slope {sl:+.3f} | top-20% history beat baseline {np.mean(y[hi]>0):.3f}, bottom-20% {np.mean(y[lo]>0):.3f}")
