import json, numpy as np, pandas as pd, ratings2 as rt, model2
P=dict(HG=14.0,CARRY=0.85,M0=3.0); QP=dict(QHL=1500.0,QCARRY=0.8,QM0=100.0,QPRIOR=-0.02); SEASON=2026; WEEK=3
D=model2.build(P,QP); cols=model2.F
tr=D[(D.week>=3)]; sw=0.5**((SEASON-tr.season)/8.0)
A=np.column_stack([np.ones(len(tr))]+[tr[c] for c in cols]); Wt=sw.values[:,None]
w=np.linalg.solve((A*Wt).T@A+np.diag([0]+[1]*len(cols)),(A*Wt).T@tr.result.values)
print('coef', dict(zip(['hfa']+cols, np.round(w,2))))
_,st=rt.team_ratings(**P); _,_,qs,used=rt.qb_ratings(**QP)
mu=rt.T0[rt.T0.season==SEASON][rt.STATS].mean().values
def team(t):
    s=st[t]; c=P['CARRY'] if s['season']!=SEASON else 1.0
    return (s['so']*c+P['M0']*mu)/(s['wo']*c+P['M0'])-mu, (s['sd']*c+P['M0']*mu)/(s['wd']*c+P['M0'])-mu
R=pd.read_csv('../../data/roster_2026.csv',low_memory=False); R25=pd.read_csv('../../data/roster_2025.csv',low_memory=False)
RR=pd.concat([R25,R]).dropna(subset=['gsis_id']); RR=RR[RR.position=='QB']; n2p=dict(zip(RR.full_name,RR.gsis_id))
def qbr(pid):
    s=qs.get(pid)
    if s is None: return QP['QPRIOR']-0.08, 0
    c=QP['QCARRY'] if s['season']!=SEASON else 1.0
    return (s['x']*c+QP['QM0']*QP['QPRIOR'])/(s['w']*c+QP['QM0']), s['w']
S=json.load(open('../../slate_w3.json'))
G=pd.read_csv('../../data/games.csv'); G=G[(G.season==SEASON)&(G.week==WEEK)]
for g in S['games']:
    h,a=g['home'],g['away']; r=G[(G.home_team==h)&(G.away_team==a)].iloc[0]
    (oh,dh),(oa,da)=team(h),team(a); diff=(oh-da)-(oa-dh)
    ph,pa=n2p.get(g['gm']['qbH']),n2p.get(g['gm']['qbA']); (rh,wh),(ra,wa)=qbr(ph),qbr(pa)
    uh=used[h]['x']/used[h]['w']; ua=used[a]['x']/used[a]['w']
    f=dict(epa=diff[0],pepa=diff[1],repa=diff[2],sr=diff[3],qb=rh-ra,qbd=(rh-uh)-(ra-ua),rest=float(np.clip(r.home_rest-r.away_rest,-7,7)),div=int(r.div_game),neutral=int(r.location=='Neutral'))
    parts={c:w[1+i]*f[c] for i,c in enumerate(cols)}; m=w[0]+sum(parts.values())
    eff=sum(parts[c] for c in ('epa','pepa','repa','sr'))
    print(f"{a}@{h}: rebuilt {m:+.1f} (slate {g['gm']['m']:+.1f}) line {h} {-g['dk']['spread']:+.1f} | hfa {w[0]:+.1f} eff {eff:+.1f} qb {parts['qb']:+.1f} qbd {parts['qbd']:+.1f} rest {parts['rest']:+.1f} | "
          f"{g['gm']['qbH']} {rh:+.3f} ({wh:.0f} db-wt) vs {g['gm']['qbA']} {ra:+.3f} ({wa:.0f}); team's recent QBs {h} {uh:+.3f} {a} {ua:+.3f}")
