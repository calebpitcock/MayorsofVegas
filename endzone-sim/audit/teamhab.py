import pandas as pd, numpy as np
COLS=['game_id','season','season_type','week','posteam','defteam','play_type','down','ydstogo','yardline_100','wp','half_seconds_remaining',
      'qb_dropback','two_point_attempt','touchdown','td_team','field_goal_attempt','drive','posteam_score_post','defteam_score_post','posteam_score','qb_kneel','qb_spike','game_seconds_remaining','punt_attempt','fixed_drive_result','fixed_drive']
fr=[]
for s in range(2016,2027):
    p=pd.read_csv(f'play_by_play_{s}.csv.gz',usecols=COLS,low_memory=False); p=p[p.season_type=='REG']; fr.append(p)
P=pd.concat(fr)
G=pd.read_csv('games.csv'); coach={}
for r in G.itertuples(): coach[(r.game_id,r.home_team)]=r.home_coach; coach[(r.game_id,r.away_team)]=r.away_coach
rep={'OAK':'LV','SD':'LAC','STL':'LA'}; P['posteam']=P.posteam.replace(rep)
# ---------- per team-game ----------
sc=P[P.play_type.isin(['run','pass'])&(P.two_point_attempt.fillna(0)==0)]
neu=sc[sc.down.isin([1,2])&sc.wp.between(.2,.8)&(sc.half_seconds_remaining>120)]
f4=P[(P.down==4)&(P.ydstogo<=3)&(P.yardline_100.between(1,65))&P.wp.between(.1,.9)&(P.half_seconds_remaining>120)&P.play_type.isin(['run','pass','punt','field_goal'])]
f4=f4.assign(go=f4.play_type.isin(['run','pass']).astype(int))
# drives: points by result
dr=P.dropna(subset=['fixed_drive_result','posteam']).drop_duplicates(['game_id','fixed_drive'])
dr=dr.assign(td=(dr.fixed_drive_result=='Touchdown').astype(int),fg=(dr.fixed_drive_result=='Field goal').astype(int))
rz=P[P.yardline_100<=20].dropna(subset=['posteam']).drop_duplicates(['game_id','fixed_drive']).assign(rzt=1)[['game_id','fixed_drive','rzt']]
dr=dr.merge(rz,on=['game_id','fixed_drive'],how='left').fillna({'rzt':0})
tg=dr.groupby(['game_id','season','week','posteam']).agg(td=('td','sum'),fg=('fg','sum'),trips=('rzt','sum'),
      rztd=('td',lambda x: 0)).reset_index()
rzd=dr[dr.rzt==1].groupby(['game_id','posteam']).agg(rztd=('td','sum'),rzn=('td','size')).reset_index()
tg=tg.drop(columns='rztd').merge(rzd,on=['game_id','posteam'],how='left').fillna({'rztd':0,'rzn':0})
tg=tg.merge(neu.groupby(['game_id','posteam']).agg(np_=('qb_dropback','sum'),nn=('play_type','size')).reset_index(),on=['game_id','posteam'],how='left')
tg=tg.merge(f4.groupby(['game_id','posteam']).agg(go=('go','sum'),g4=('go','size')).reset_index(),on=['game_id','posteam'],how='left').fillna({'go':0,'g4':0})
tg['coach']=[coach.get((g,t)) for g,t in zip(tg.game_id,tg.posteam)]
tg['pts']=7*tg.td+3*tg.fg
tg.to_parquet('team_games_hab.parquet')
print(tg.groupby('season')[['td','fg','go','g4']].sum())
