import pandas as pd, numpy as np
D='/home/user/MayorsofVegas/data'; out=[]
for s in range(2022,2026):
    pa=pd.read_parquet(f'{D}/pbp_participation_{s}.parquet',columns=['nflverse_game_id','play_id','possession_team','offense_players'])
    p=pd.read_csv(f'{D}/play_by_play_{s}.csv.gz',usecols=['game_id','play_id','season','week','season_type','play_type','yardline_100','posteam'],low_memory=False)
    p=p[(p.season_type=='REG')&p.play_type.isin(['run','pass'])]
    m=p.merge(pa.rename(columns={'nflverse_game_id':'game_id'}),on=['game_id','play_id'])
    m['rz']=(m.yardline_100<=10); m['i5']=(m.yardline_100<=5)
    m=m[m.offense_players.notna()&(m.offense_players!='')]
    tot=m.groupby(['game_id','posteam']).agg(t_pl=('rz','size'),t_rz=('rz','sum'),t_i5=('i5','sum')).reset_index()
    e=m.assign(pid=m.offense_players.str.split(';')).explode('pid')
    g=e.groupby(['game_id','season','week','posteam','pid']).agg(pl=('rz','size'),rzs=('rz','sum'),i5s=('i5','sum')).reset_index().merge(tot,on=['game_id','posteam'])
    out.append(g); print(s,len(g))
pd.concat(out).to_parquet('rz_snaps.parquet')
