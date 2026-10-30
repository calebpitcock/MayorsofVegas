const E=require('./harness.js');const ctx={tuning:{},out:new Set(),tune:E.TUNE};
const A="A",H="H";
const mk=(sp,tot)=>({id:"kw"+sp,league:"NFL",away:A,home:H,spread:sp,total:tot,players:[
 {n:"QA",t:A,pos:"QB",rush:.1},{n:"RA",t:A,pos:"RB",rush:.6,rec:.12},{n:"WA",t:A,pos:"WR",rec:.26},{n:"TA",t:A,pos:"TE",rec:.16},
 {n:"QH",t:H,pos:"QB",rush:.1},{n:"RH",t:H,pos:"RB",rush:.6,rec:.12},{n:"WH",t:H,pos:"WR",rec:.26},{n:"TH",t:H,pos:"TE",rec:.16}]});
const mix=[[-1,.25,44],[-3,.22,44],[-5.5,.22,45],[-7.5,.15,44],[-10,.10,46],[-13.5,.06,45]];
const agg=new Float64Array(81);
for(const [sp,wt,tot] of mix){const g=mk(sp,tot);const k=E.calibrateV3(g,ctx);const N=40000;
  const r=E.simGameV3(g,{N,trust:.85,k,seed:7},ctx);
  for(let i=0;i<161;i++){const a=Math.min(80,Math.abs(i-80));agg[a]+=wt*r.G.raw[i]/N;}}
const target={0:.30,1:4.3,2:3.8,3:14.2,4:5.0,5:3.3,6:5.7,7:8.8,8:3.9,9:2.2,10:5.4,11:2.5,12:2.0,13:3.0,14:4.7,15:1.8,16:2.1,17:3.1,18:1.9,19:1.5,20:2.0,21:2.3};
let simIn=0,tgtIn=0;for(const k in target){simIn+=agg[k]*100;tgtIn+=target[k];}
const w=new Array(81).fill(0);
// outside the table: scale so total mass matches (tail gets (100-tgtIn)/(100-simIn))
const tail=(100-tgtIn)/(100-simIn);
for(let i=0;i<=80;i++) w[i]= target[i]!=null ? target[i]/(agg[i]*100) : tail;
console.log("sim vs target:");for(const k in target)console.log(k,(agg[k]*100).toFixed(2),target[k],w[k].toFixed(3));
console.log("tail factor",tail.toFixed(3));
console.log("KEYW=["+w.map(x=>x.toFixed(3)).join(",")+"]");
require('fs').writeFileSync('keyw.json',JSON.stringify(w.map(x=>+x.toFixed(3))));
