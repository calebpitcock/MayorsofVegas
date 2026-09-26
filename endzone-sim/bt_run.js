const E=require('./harness.js');const fs=require('fs');
const f=process.argv[2]||'bt_2025_4_18.json';
const tuning=JSON.parse(process.argv[3]||'{}');
const V=JSON.parse(process.env.EZV||'{}');
const ctx={tuning,out:new Set(),tune:{},opp:V.opp??1,scheme:V.scheme||'data'};   // data-driven gl/deep only; hand TUNE ignored
const games=JSON.parse(fs.readFileSync(f));
const rows=[], grows=[], propRows=[];
let t0=Date.now();
const cdf=(h,off,x)=>{let lo=0,eq=0,t=0;for(let i=0;i<h.length;i++){const v=i-off;t+=h[i];if(v<x)lo+=h[i];else if(v===x)eq+=h[i];}return (lo+eq*0.5)/t;};
for(const g of games){
  g.live={status:'pre'};
  const k=E.calibrateV3(g,ctx,{N:2500,iters:3,iters2:4,trust:1});
  const r=E.simGameV3(g,{N:4000,trust:1,k,seed:E.hashStr(g.id)},ctx);
  const W=r.W,G=r.G;
  const pH=(G.win[1]+G.tie/2)/W;
  grows.push({id:g.id,week:g.week,spread:g.spread,total:g.total,pH,mlH:g.ml.home,mlA:g.ml.away,hs:g.result.hs,as:g.result.as});
  for(const pr of (g.props||[])){ const p=r.players.find(x=>x.n===pr.n); const a=g.actual[pr.n]; if(!p||!a) continue;
    const key={player_reception_yds:["recYds",15,"recy"],player_receptions:["rec",0,"rec"],player_rush_yds:["rushYds",40,"ry"]}[pr.mk]; if(!key) continue;
    const o=E.histOver(p.hist[key[0]],key[1],pr.line);
    propRows.push({...pr,week:g.week,id:g.id,pos:p.pos,pOver:o.over,pPush:o.push,actual:a[key[2]],played:(a.car+a.tgt)>0}); }
  for(const p of r.players){ if(p.field||p.hidden) continue; const a=g.actual[p.n]; if(!a) continue;
    const h=p.hist, row={id:g.id,week:g.week,n:p.n,t:p.t,pos:p.pos,rush:p.wRun,rec:p.wTgt,conf:p.conf,pTD:p.pModel,td:a.td>0?1:0,
      mRY:p.mean.RY,mRCY:p.mean.RCY,mREC:p.mean.REC,mRA:p.mean.RA,mTGT:p.mean.TGT,
      aRY:a.ry,aRCY:a.recy,aREC:a.rec,aRA:a.car,aTGT:a.tgt,
      pitRY:cdf(h.rushYds,40,a.ry),pitRCY:cdf(h.recYds,15,a.recy),pitREC:cdf(h.rec,0,a.rec),
      medRY:E.histQuantile(h.rushYds,40,.5),medRCY:E.histQuantile(h.recYds,15,.5),medREC:E.histQuantile(h.rec,0,.5),
      q10RCY:E.histQuantile(h.recYds,15,.1),q90RCY:E.histQuantile(h.recYds,15,.9),q10RY:E.histQuantile(h.rushYds,40,.1),q90RY:E.histQuantile(h.rushYds,40,.9)};
    if(p.isQB&&a.att!=null){ Object.assign(row,{mPY:p.mean.PY,aPY:a.py,pitPY:cdf(h.passYds,40,a.py),medPY:E.histQuantile(h.passYds,40,.5),
      q10PY:E.histQuantile(h.passYds,40,.1),q90PY:E.histQuantile(h.passYds,40,.9),mPA:p.mean.PA,aPA:a.att,mPTD:p.mean.PTD,aPTD:a.ptd,
      pitPTD:cdf(h.passTD,0,a.ptd),pitPA:cdf(h.passAtt,0,a.att)}); }
    rows.push(row);
  }
}
fs.writeFileSync(f.replace('.json',(process.env.EZTAG||'')+'_rows.json'),JSON.stringify({rows,grows,props:propRows}));
console.log('done',games.length,'games',rows.length,'player rows',((Date.now()-t0)/1000).toFixed(0)+'s');
