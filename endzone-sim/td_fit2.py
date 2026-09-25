exec(open('td_vs_book.py').read().split("tr, te = ")[0])
M['lk']=lg(M.dkimp.values); M['lm']=lg(M.pc.values)
P=pd.get_dummies(M.pos).astype(float)
for a,b in ((2023,2024),(2024,2023)):
    tr,te=M[M.season==a],M[M.season==b]
    w1=logit_fit(tr[['lk']].values,tr.td.values); w2=logit_fit(tr[['lk','lm']].values,tr.td.values)
    X3=lambda d: np.column_stack([d.lk,d.lm,P.loc[d.index,['RB','TE','WR']].values])
    w3=logit_fit(X3(tr),tr.td.values)
    p1=sig(w1[0]+te.lk*w1[1]); p2=sig(w2[0]+w2[1]*te.lk+w2[2]*te.lm); p3=sig(np.column_stack([np.ones(len(te)),X3(te)])@w3)
    print(f"fit {a} test {b}: DK {ll(p1,te.td):.5f} +model {ll(p2,te.td):.5f} (w {w2.round(3)}) +model+pos {ll(p3,te.td):.5f} (w {w3.round(3)})")
w=logit_fit(M[['lk','lm']].values,M.td.values); print('pooled',w.round(3))
M['comb']=sig(w[0]+w[1]*M.lk+w[2]*M.lm); M['ev']=M.comb*M.dkdec-1
print(M.ev.describe().round(3).to_dict()); print('share with EV>0', (M.ev>0).mean())
json.dump(dict(a=float(w[0]),bk=float(w[1]),bm=float(w[2]),n=len(M),seasons='2023-2024',src='DraftKings anytime TD ~5 min before kickoff'),open('td_dk_fit.json','w'))
w0=logit_fit(M[['lk']].values,M.td.values); print('pooled DK-alone de-vig',w0.round(3))
f=json.load(open('td_dk_fit.json')); f.update(dva=float(w0[0]),dvb=float(w0[1])); json.dump(f,open('td_dk_fit.json','w')); print(f)
