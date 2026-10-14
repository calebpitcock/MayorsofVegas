"""Score a backtest: python3 evaluate.py <BT_OUT>. Board and all-pick records, units, ROI and desk-vs-book log loss."""
import json, math, sys, collections
import pandas as pd
SP=sys.argv[1]
pay=lambda o:o/100 if o>0 else 100/-o
def ll(q,y): q=min(max(q,1e-4),1-1e-4); return -(y*math.log(q)+(1-y)*math.log(1-q))
rows=[]
for v in ('on','off'):
    for wk in (2,3,4,5):
        d=json.load(open(f'{SP}/bt_{v}/desk/site/picks_w{wk}.json')); g=json.load(open(f'{SP}/bt_{v}/grades_w{wk}.json'))['results']
        B=set(d['board'])
        for p in d['picks']:
            r=g.get(p['id'])
            if p['type'] in ('Winner','Spread') or r is None: continue
            rows.append(dict(v=v,wk=wk,type=p['type'],board=p['id'] in B,r=r,prob=p['prob'],book=p['book'],edge=p['prob']-p['book'],
                             odds=p['price']['odds'],imp=p['price']['implied'],u=pay(p['price']['odds']) if r=='W' else -1 if r=='L' else 0))
D=pd.DataFrame(rows); D['y']=(D.r=='W').astype(int); G=D[D.r!='P']
def line(x,lab):
    n=len(x); w=int(x.y.sum()); u=x.u.sum()
    return f"{lab:24} n={n:4}  {w}-{n-w}  {u:+7.1f}u  ROI {100*u/max(n,1):+5.1f}%  desk LL {x.apply(lambda r:ll(r.prob,r.y),axis=1).mean():.4f} book LL {x.apply(lambda r:ll(r.book,r.y),axis=1).mean():.4f}"
for v in ('on','off'):
    print(f'===== matchups {v.upper()} =====')
    b=G[(G.v==v)&G.board]
    print(line(b,'BOARD all'))
    for t in ('Total','Yards','Anytime TD'): print(line(b[b.type==t],'  '+t))
    for wk in (2,3,4,5): print(line(b[b.wk==wk],f'  week {wk}'))
    a=G[G.v==v]
    print(line(a,'ALL picks (calibration)'))
    for t in ('Total','Yards','Anytime TD'): print(line(a[a.type==t],'  all '+t))
    # edge buckets on board
    for lo,hi in ((0,.04),(.04,.06),(.06,.08),(.08,1)):
        x=b[(b.edge>=lo)&(b.edge<hi)]; print(line(x,f'  board edge {int(lo*100)}-{int(hi*100) if hi<1 else "+"} pts'))
    # old caps: top 10 TD / 6 total / 10 yards per week by edge, with old +2 total bar
    cap=[]
    for wk in (2,3,4,5):
        x=b[b.wk==wk]
        for t,k in (('Anytime TD',10),('Total',6),('Yards',10)): cap.append(x[x.type==t].nlargest(k,'edge'))
    print(line(pd.concat(cap),'  OLD CAPS (top 10/6/10)'))
D.to_csv(f'{SP}/bt_rows.csv',index=False)
