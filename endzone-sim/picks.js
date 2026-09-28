// Run the page's player model on the slate: anytime-TD chances (DK blend) and prop values (80% DK no-vig + 20% sim).
const E=require('/home/user/MayorsofVegas/endzone-sim/harness.js'), fs=require('fs');
const S=JSON.parse(fs.readFileSync('/home/user/MayorsofVegas/endzone-sim/slate_nfl.json'));
const CAL=JSON.parse(fs.readFileSync('/home/user/MayorsofVegas/endzone-sim/td_cal_nfl.json')), FIT=JSON.parse(fs.readFileSync('/home/user/MayorsofVegas/endzone-sim/td_dk_fit.json'));
const lg=q=>{q=Math.min(.999,Math.max(.001,q));return Math.log(q/(1-q));}, sg=z=>1/(1+Math.exp(-z));
const imp=o=>o<0?-o/(-o+100):100/(o+100), dec=o=>o>0?1+o/100:1+100/-o;
const ctx={tuning:{},out:new Set(),tune:E.TUNE,opp:1,scheme:'off'};
const td=[], props=[];
for(const g of S.games){
  const gi={...g,players:g.players.map(p=>({...p}))};
  const r=E.simGameV3(gi,{N:6000,trust:1,k:g.k,seed:E.hashStr(g.id+'|main')},ctx);
  for(const p of r.players){ if(p.field||p.hidden) continue;
    const m=sg(CAL.slope*lg(p.pModel)+(CAL[p.pos]||0)); const src=g.players.find(x=>x.n===p.n)||{};
    const price=src.mkt; const fin=price!=null?sg(FIT.a+FIT.bk*lg(imp(price))+FIT.bm*lg(m)):m;
    td.push({g:`${g.away}@${g.home}`,n:p.n,t:p.t,pos:p.pos,p:fin,price,ev:price!=null?fin*dec(price)-1:null});
    for(const [mk,h,off] of [['recYds','recYds',15],['rushYds','rushYds',40],['rec','rec',0]]){ const b=(src.book||{})[mk]; if(!b) continue;
      const dk=(b.books||{}).draftkings; if(!dk) continue; const o=E.histOver(p.hist[h],off,b.line); const sim=o.over/(1-o.push||1);
      const pov=.8*b.fair+.2*sim; const eo=pov*dec(dk[0])-1, eu=(1-pov)*dec(dk[1])-1;
      props.push({g:`${g.away}@${g.home}`,n:p.n,mk,line:b.line,side:eo>=eu?'over':'under',price:eo>=eu?dk[0]:dk[1],p:eo>=eu?pov:1-pov,ev:Math.max(eo,eu),med:E.histQuantile(p.hist[h],off,.5)});
    }
  }
}
td.sort((a,b)=>b.p-a.p); props.sort((a,b)=>b.ev-a.ev);
console.log('TOP ANYTIME TD CHANCES'); td.slice(0,15).forEach(x=>console.log(`${(100*x.p).toFixed(0)}%  ${x.n} (${x.t} ${x.pos}, ${x.g})  DK ${x.price!=null?(x.price>0?'+':'')+x.price+'≈':'—'}  EV ${x.ev!=null?(100*x.ev).toFixed(1)+'%':'—'}`));
console.log('\nTD with positive EV at the estimated DK price'); td.filter(x=>x.ev>0).sort((a,b)=>b.ev-a.ev).slice(0,10).forEach(x=>console.log(`${x.n} (${x.g}) ${(100*x.p).toFixed(0)}% at ${x.price>0?'+':''}${x.price}≈ EV +${(100*x.ev).toFixed(1)}%`));
console.log('\nPROP VALUES (DK Thursday lines), EV>0'); props.filter(x=>x.ev>0).slice(0,15).forEach(x=>console.log(`${x.n} ${x.mk} ${x.side} ${x.line} at ${x.price>0?'+':''}${x.price}  chance ${(100*x.p).toFixed(1)}%  EV +${(100*x.ev).toFixed(1)}%  (sim median ${x.med})  ${x.g}`));
console.log('\nprops priced', props.length, 'with EV>0', props.filter(x=>x.ev>0).length);
// ---- TD board: for each player, the lowest DraftKings price at which the blended chance still breaks even
const am=p=>p>=.5?-Math.round(100*p/(1-p)):Math.round(100*(1-p)/p);
function fin(m,price){ return sg(FIT.a+FIT.bk*lg(imp(price))+FIT.bm*lg(m)); }
function breakeven(m){ // smallest payout (as American odds) where fin(m,P)*dec(P)>=1
  for(let P=-1000;P<=3000;P+=5){ if(P>-100&&P<100) continue; if(fin(m,P)*dec(P)>=1) return P; } return null; }
const board=[];
for(const g of S.games){ const gi={...g,players:g.players.map(p=>({...p}))};
  const r=E.simGameV3(gi,{N:6000,trust:1,k:g.k,seed:E.hashStr(g.id+'|main')},ctx);
  for(const p of r.players){ if(p.field||p.hidden) continue; const m=sg(CAL.slope*lg(p.pModel)+(CAL[p.pos]||0)); const src=g.players.find(x=>x.n===p.n)||{};
    const price=src.mkt; const be=breakeven(m); const f=price!=null?fin(m,price):null;
    board.push({g:`${g.away}@${g.home}`,kick:g.kick,n:p.n,t:p.t,pos:p.pos,model:m,price,p:f,ev:price!=null?f*dec(price)-1:null,be,flag:src.flag||''}); } }
console.log('\n=== TD BOARD: EV at estimated DK price ===');
board.filter(x=>x.price!=null).sort((a,b)=>b.ev-a.ev).slice(0,20).forEach(x=>console.log(`${x.n.padEnd(24)} ${x.t} ${x.pos} ${x.g.padEnd(8)} ${x.kick.padEnd(12)} chance ${(100*x.p).toFixed(0)}% (sim ${(100*x.model).toFixed(0)}%) est DK ${x.price>0?'+':''}${x.price} EV ${(100*x.ev).toFixed(1)}%  bet at ${x.be>0?'+':''}${x.be} or better ${x.flag}`));
console.log('\n=== no DK price on file (model chance, price needed) ===');
board.filter(x=>x.price==null&&x.model>.25).sort((a,b)=>b.model-a.model).slice(0,8).forEach(x=>console.log(`${x.n} ${x.t} ${x.g} model ${(100*x.model).toFixed(0)}% need ${x.be>0?'+':''}${x.be} or better`));
console.log('\n=== TD BOARD WITH MATCHUP READS ===');
const MX={}; S.games.forEach(g=>Object.entries((g.mx||{}).players||{}).forEach(([n,v])=>MX[n]=v));
board.filter(x=>x.price!=null&&x.ev>-0.01).sort((a,b)=>b.ev-a.ev).slice(0,10).forEach(x=>{const v=MX[x.n]||{};
  console.log(`${x.n} (${x.g}) ${(100*x.p).toFixed(0)}% at ${x.price>0?'+':''}${x.price}≈ EV ${(100*x.ev).toFixed(1)}% | ${v.text||'—'}`);});
console.log('\n=== Biggest matchup edges for TDs (any price) ===');
Object.entries(MX).sort((a,b)=>b[1].dTD-a[1].dTD).slice(0,6).forEach(([n,v])=>{const b=board.find(x=>x.n===n)||{};console.log(`${n}: ${(100*(b.p??b.model)).toFixed(0)}%${b.price!=null?' at '+(b.price>0?'+':'')+b.price+'≈':' (no DK price)'} | ${v.text}`);});
console.log('\n=== Biggest matchup disadvantages ===');
Object.entries(MX).sort((a,b)=>a[1].dTD-b[1].dTD).slice(0,5).forEach(([n,v])=>console.log(`${n}: ${v.text}`));
