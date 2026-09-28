import json,sys,numpy as np,pandas as pd
for tag in sys.argv[1:]:
    R=pd.DataFrame(json.load(open(f'bt_2025_4_18_{tag}_rows.json'))['rows'])
    b=lambda p,y: float(np.mean((p-y)**2))
    te=R[R.week>=12]; tr=R[R.week<=11]
    s=f"{tag}: TD Brier all {b(R.pTD,R.td):.5f} (w12-18 {b(te.pTD,te.td):.5f}) logloss {float(-np.mean(R.td*np.log(R.pTD.clip(1e-4))+(1-R.td)*np.log((1-R.pTD).clip(1e-4)))):.5f}"
    def pit(sel,col): v=R[sel][col].dropna(); return float(np.mean(np.abs(np.histogram(v,bins=10,range=(0,1))[0]/len(v)-.1)))
    def crps_proxy(sel,a,med): x=R[sel]; return float(np.mean(np.abs(x[a]-x[med])))
    s+=f" | recYds MAE {crps_proxy(R.pos.isin(['WR','TE'])&(R.rec>=.12),'aRCY','medRCY'):.2f} PITdev {pit(R.pos.isin(['WR','TE'])&(R.rec>=.12),'pitRCY'):.4f}"
    s+=f" | rushYds MAE {crps_proxy(R.pos.eq('RB')&(R.rush>=.25),'aRY','medRY'):.2f} bias {(R[R.pos.eq('RB')&(R.rush>=.25)].aRY-R[R.pos.eq('RB')&(R.rush>=.25)].mRY).mean():+.2f}"
    s+=f" | rec MAE {crps_proxy(R.pos.isin(['WR','TE'])&(R.rec>=.12),'aREC','medREC'):.3f} | pass MAE {crps_proxy(R.pos.eq('QB'),'aPY','medPY'):.2f}"
    print(s)
