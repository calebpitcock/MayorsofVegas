import pandas as pd, numpy as np
COLS=['game_id','season','season_type','week','posteam','defteam','play_type','qb_scramble','qb_kneel','two_point_attempt','rushing_yards','receiving_yards',
      'pass_attempt','sack','receiver_player_id','rush_touchdown','pass_touchdown']
P=pd.concat([pd.read_csv(f'play_by_play_{s}.csv.gz',usecols=COLS,low_memory=False) for s in range(2016,2026)]); P=P[P.season_type=='REG']
pos=pd.read_csv('players.csv',usecols=['gsis_id','position']).set_index('gsis_id').position.replace({'FB':'RB'})
two=P.two_point_attempt.fillna(0)==1
runs=P[(P.play_type=='run')&(P.qb_scramble.fillna(0)==0)&(P.qb_kneel.fillna(0)==0)&~two]
tg=P[(P.play_type=='pass')&(P.pass_attempt==1)&(P.sack.fillna(0)==0)&~two&P.receiver_player_id.notna()]
tg=tg.assign(rp=tg.receiver_player_id.map(pos))
td=P[((P.rush_touchdown==1)|(P.pass_touchdown==1))&~two]; td=td.assign(rp=td.receiver_player_id.map(pos))
def metr(r,t,d):
    o=dict(ypc=r.rushing_yards.mean(), ypt=t.receiving_yards.fillna(0).mean())
    for k in ('RB','WR','TE'): o['tgt_'+k]=(t.rp==k).mean()
    o['rtd']=(d.rush_touchdown==1).mean()
    pt=d[d.pass_touchdown==1]
    for k in ('RB','WR','TE'): o['tdpos_'+k]=(pt.rp==k).mean() if len(pt) else np.nan
    return pd.Series(o)
def by(mask_r,mask_t,mask_d):
    R=runs[mask_r(runs)];Tt=tg[mask_t(tg)];D=td[mask_d(td)]
    keys=sorted(set(zip(R.defteam,R.season)))
    gr=R.groupby(['defteam','season']);gt=Tt.groupby(['defteam','season']);gd=D.groupby(['defteam','season'])
    return pd.DataFrame({k:metr(gr.get_group(k),gt.get_group(k),gd.get_group(k)) for k in keys if k in gt.groups and k in gd.groups}).T
odd=by(lambda d:d.week%2==1,lambda d:d.week%2==1,lambda d:d.week%2==1); even=by(lambda d:d.week%2==0,lambda d:d.week%2==0,lambda d:d.week%2==0)
full=by(lambda d:d.week>0,lambda d:d.week>0,lambda d:d.week>0)
print("Defense-vs-position inputs the live page applies (opp:1). How much is real?")
print(f"{'metric':12s} {'split-half r':>12s} {'season rel.':>11s} {'yr->yr r':>9s}")
fs=full.reset_index().rename(columns={'level_0':'team','level_1':'season'}).sort_values(['team','season'])
for c in full.columns:
    r=np.corrcoef(odd[c].astype(float),even[c].astype(float))[0,1]
    prev=fs.groupby('team')[c].shift(1); m=prev.notna()&fs[c].notna()
    y=np.corrcoef(fs[c][m].astype(float),prev[m].astype(float))[0,1]
    print(f"{c:12s} {r:+12.2f} {2*r/(1+r):11.2f} {y:+9.2f}")
