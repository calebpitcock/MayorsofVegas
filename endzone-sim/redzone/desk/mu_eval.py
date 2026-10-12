import json,csv,sys,math,collections
S=sys.argv[1]
D=json.load(open(S+'/l195.json'))
st=[r for r in csv.DictReader(open(S+'/dl/stats_player_week_2026.csv')) if r['season_type']=='REG']
f=lambda x:float(x or 0)
base=collections.defaultdict(lambda:dict(tg=0,ry=0,car=0,rush=0,g=0)); wk5={}
for r in st:
    w=int(r['week']); pid=r['player_id']
    if w<=4:
        b=base[pid]; b['tg']+=f(r['targets']); b['ry']+=f(r['receiving_yards']); b['car']+=f(r['carries']); b['rush']+=f(r['rushing_yards']); b['g']+=1
    elif w==5: wk5[pid]=r
rows=[]
for g in D['games']:
    for m in g.get('mu',[]):
        a=wk5.get(m['pid']); b=base[m['pid']]
        rec=m['role']=='coverage'
        row=dict(n=m['n'],pos=m['pos'],game=m['game'],edge=m['edge'],score=m['score'],rec=rec)
        if a is None: row['status']='no line (did not play / no stats)'; rows.append(row); continue
        if rec:
            t=f(a['targets']); y=f(a['receiving_yards'])
            bl=b['ry']/b['tg'] if b['tg'] else None
            row.update(vol=t,yds=y,act=(y/t if t else None),bl=bl,blpg=b['ry']/max(b['g'],1))
        else:
            c=f(a['carries']); y=f(a['rushing_yards'])
            bl=b['rush']/b['car'] if b['car'] else None
            row.update(vol=c,yds=y,act=(y/c if c else None),bl=bl,blpg=b['rush']/max(b['g'],1))
        rows.append(row)
json.dump(rows,open(S+'/work/mu_rows.json','w'))
def corr(x,y):
    n=len(x); mx=sum(x)/n; my=sum(y)/n
    sx=math.sqrt(sum((a-mx)**2 for a in x)); sy=math.sqrt(sum((b-my)**2 for b in y))
    return sum((a-mx)*(b-my) for a,b in zip(x,y))/(sx*sy)
def rank(v):
    o=sorted(range(len(v)),key=lambda i:v[i]); r=[0]*len(v)
    for k,i in enumerate(o): r[i]=k
    return r
for grp,cond,minv in (('Pass catchers (WR+TE)',lambda r:r['rec'],4),('WR only',lambda r:r['rec'] and r['pos']=='WR',4),('TE only',lambda r:r['rec'] and r['pos']=='TE',4),('RBs',lambda r:not r['rec'],6)):
    R=[r for r in rows if cond(r)]
    U=[r for r in R if r.get('vol',0)>=minv and r.get('bl')]
    print(f"\n== {grp}: {len(R)} rated, {sum('status' in r for r in R)} no stats, {len(U)} with >= {minv} {'targets' if R and R[0]['rec'] else 'carries'} and a baseline")
    if not U: continue
    x=[r['score'] for r in U]; y=[r['act']/r['bl']-1 for r in U]
    print(f"  corr(score, actual vs own avg per {'target' if U[0]['rec'] else 'carry'}) = {corr(x,y):+.2f}   rank corr {corr(rank(x),rank(y)):+.2f}")
    W=[r for r in U]
    # volume-weighted: pooled efficiency by bucket
    for lab,ok in (('Edge / Slight edge',lambda s:s>=.03),('Even',lambda s:-.03<s<.03),('Slightly tough / Tough',lambda s:s<=-.03)):
        B=[r for r in U if ok(r['score'])]
        if not B: print(f"  {lab:24} none"); continue
        pooled=sum(r['yds'] for r in B)/sum(r['vol'] for r in B); bpool=sum(r['bl']*r['vol'] for r in B)/sum(r['vol'] for r in B)
        beat=sum(r['act']>r['bl'] for r in B)
        avgpred=sum(r['score'] for r in B)/len(B)
        ypg=sum(r['yds'] for r in B)/len(B); bpg=sum(r['blpg'] for r in B)/len(B)
        print(f"  {lab:24} n={len(B):2}  predicted {100*avgpred:+5.1f}%  actual per-{'tgt' if U[0]['rec'] else 'car'} {pooled:5.2f} vs own avg {bpool:5.2f} ({100*(pooled/bpool-1):+5.1f}%)  beat own avg {beat}/{len(B)}  yds/g {ypg:5.1f} vs avg {bpg:5.1f}")
    # direction hit rate for non-even
    nz=[r for r in U if abs(r['score'])>=.03]
    hit=sum((r['score']>0)==(r['act']>r['bl']) for r in nz)
    print(f"  direction right on {hit}/{len(nz)} non-even calls")
    big=sorted(U,key=lambda r:-abs(r['score']))[:8]
    for r in big: print(f"    {r['n']:22} {r['pos']} {r['game']:10} {r['edge']:15} {100*r['score']:+5.1f}%  wk5 {r['yds']:.0f} yds on {r['vol']:.0f}  ({r['act']:.1f}/per vs avg {r['bl']:.1f})")
