import pandas as pd, numpy as np
COLS=['season','season_type','down','ydstogo','yardline_100','play_type','posteam','half_seconds_remaining','game_seconds_remaining','score_differential','qtr']
P=pd.concat([pd.read_csv(f'play_by_play_{s}.csv.gz',usecols=COLS,low_memory=False).assign(season=s) for s in (2024,2025,2026)])
P=P[(P.season_type=='REG')&(P.down==4)&P.play_type.isin(['run','pass','punt','field_goal'])&(P.qtr<=4)]
# engine's non-late branches only: exclude the last 7 minutes of the 4th quarter (engine 'late' logic) and last 12s of halves
P=P[~((P.qtr==4)&(P.game_seconds_remaining<420))&(P.half_seconds_remaining>12)]
P['go']=P.play_type.isin(['run','pass'])
yl,tg=P.yardline_100,P.ydstogo; fg=yl+17
b=np.select([ (tg<=1)&(yl<=50), (tg<=1)&(yl<=72), (tg<=2)&(yl<=50), (yl<=4)&(tg<=4), (tg<=4)&(fg>58)&(yl<=48), (tg<=3)&(yl<=30)],
            ['4th&1, opp half','4th&1, own 28-50','4th&2, opp half','goal-to-go <=4 inside 5','4th&3-4, 41-48 (no FG)','4th&3, inside 30 (FG range)'],'other (engine: never)')
eng={'4th&1, opp half':.80,'4th&1, own 28-50':.55,'4th&2, opp half':.58,'goal-to-go <=4 inside 5':.50,'4th&3-4, 41-48 (no FG)':.55,'4th&3, inside 30 (FG range)':.22,'other (engine: never)':0}
P['b']=b
out=P.groupby(['b']).agg(n=('go','size'),actual=('go','mean')).assign(engine=lambda d: d.index.map(eng))
for s in (2024,2025,2026): out[f'act{s}']=P[P.season==s].groupby('b').go.mean()
print(out.round(2).to_string())
