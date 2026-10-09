// Redzone Desk: simulate every game with all Redzone factors on, anchored to the model's own margin and total
// (redzone/points.py), and write the most likely picks with plain-English reasons.
// Usage: node redzone/predict.js slate.json out.json
const E=require('../harness.js'), fs=require('fs'), path=require('path');
const [,,inF,outF]=process.argv;
const S=JSON.parse(fs.readFileSync(inF)), CFG=JSON.parse(fs.readFileSync(process.env.EZRZCFG||path.join(__dirname,'config.json')));
const CAL=JSON.parse(fs.readFileSync(path.join(__dirname,'..','td_cal_nfl.json')));
const lg=q=>{q=Math.min(.999,Math.max(.001,q));return Math.log(q/(1-q));}, sg=z=>1/(1+Math.exp(-z));
const pct=x=>Math.round(100*x)+'%', sgn=x=>(x>=0?'+':'−')+Math.abs(x).toFixed(1), NAME={RB:'running backs',WR:'wide receivers',TE:'tight ends',QB:'quarterbacks'};
const WEEK=S.redzone.week, SEASON=2026, N=CFG.sims;
const ctx={tuning:{},out:new Set(),tune:E.TUNE,opp:1,scheme:CFG.coverage_shells?'data':'off',mw:CFG.matchup_weight,fw:CFG.formation,tdloc:1,tdlocW:CFG.td_location_defense,rzx:true};
/* team matchup bullets from football.py (offense in g[side] against the other team's defense) */
const rel=(x,l)=>l?(x/l-1):0, P1=x=>(100*x).toFixed(1)+'%';
function teamWhy(g,side){
  const f=(g.rzfb||{})[side]; if(!f) return []; const off=g[side], dfn=side==='away'?g.home:g.away, out=[];
  const c=f.cov; if(c) out.push(`${dfn} coverage this season (estimated from tracking data): man ${pct(c.man)} (league ${pct(c.lgMan)}, ${pct(c.man2025)} last year), single-high ${pct(c.hi)} (league ${pct(c.lgHi)}), blitz ${pct(c.blitz)} (league ${pct(c.lgBlitz)})`);
  if(Math.abs(rel(f.pressure,f.lgPressure))>=.08) out.push(`Pass rush vs protection: ${off}'s QB should be pressured on ${pct(f.pressure)} of dropbacks (league ${pct(f.lgPressure)}): ${off} allows ${pct(f.offPress)}, ${dfn} generates ${pct(f.defPress)}`);
  if(Math.abs(f.ybcOff-f.lgYbc)+Math.abs(f.ybcDef-f.lgYbc)>=.25) out.push(`Run blocking: ${off} gets ${f.ybcOff.toFixed(1)} yds before contact per carry, ${dfn} allows ${f.ybcDef.toFixed(1)} (league ${f.lgYbc.toFixed(1)})`);
  if(Math.abs(rel(f.missedTackle,f.lgMissed))>=.12) out.push(`${dfn} misses ${pct(f.missedTackle)} of tackles (league ${pct(f.lgMissed)})`);
  if(Math.abs(rel(f.expOff,f.lgExp))+Math.abs(rel(f.expDef,f.lgExp))>=.2) out.push(`Big plays: ${off} ${P1(f.expOff)} of plays go 10+ run / 20+ pass, ${dfn} allows ${P1(f.expDef)} (league ${P1(f.lgExp)})`);
  const nm={pa:'play-action',motion:'pre-snap motion',screen:'screens'};
  for(const [k,v] of Object.entries(f.style||{})) if(Math.abs(v.rate*v.def_epa)>=.015) out.push(`Play style: ${off} uses ${nm[k]} on ${pct(v.rate)} of dropbacks; ${dfn} is ${v.def_epa>0?'worse':'better'} than average against it (${v.def_epa>0?'+':''}${v.def_epa.toFixed(2)} EPA per dropback)`);
  if(Math.abs(rel(f.intDef,f.lgInt))>=.2) out.push(`${dfn} intercepts ${P1(f.intDef)} of dropbacks (league ${P1(f.lgInt)})`);
  if(Math.abs(rel(f.fumOff,f.lgFum))>=.25) out.push(`${off} loses a fumble on ${P1(f.fumOff)} of plays (league ${P1(f.lgFum)})`);
  return out;
}
function playerStatWhy(p,src,g,side){
  const b=src.fb||{}, out=[], opp=side==='home'?g.away:g.home, dp=(g.defp||{})[side]||{};
  if(b.sep!=null&&Math.abs(b.sep-b.sepLg)>=.3) out.push(`Separation: ${b.sep.toFixed(1)} yds at the catch (${NAME[p.pos]} average ${b.sepLg.toFixed(1)})`);
  if(b.drop!=null&&Math.abs(b.drop-b.dropLg)>=.02) out.push(`Drops ${pct(b.drop)} of catchable targets (league ${pct(b.dropLg)})`);
  if(b.airShare!=null&&b.airShare>=.15) out.push(`Air yards: ${pct(b.airShare)} of his team's; average target ${b.adot} yds downfield (${NAME[p.pos]} ${b.adotLg})`);
  else if(b.adot!=null&&Math.abs(b.adot-b.adotLg)>=2) out.push(`Average target ${b.adot} yds downfield (${NAME[p.pos]} ${b.adotLg})`);
  if(b.ryoe!=null&&Math.abs(b.ryoe)>=.3) out.push(`Rush yards over expected: ${b.ryoe>0?'+':''}${b.ryoe.toFixed(1)} per carry (player tracking)`);
  if(b.cpoe!=null&&Math.abs(b.cpoe)>=2) out.push(`Completion % over expected: ${b.cpoe>0?'+':''}${b.cpoe.toFixed(1)}`);
  if(b.ttt!=null&&Math.abs(b.ttt-b.tttLg)>=.15) out.push(`Time to throw ${b.ttt.toFixed(2)}s (league ${b.tttLg.toFixed(2)}s)`);
  if(b.p2s!=null&&Math.abs(b.p2s-b.p2sLg)>=.04) out.push(`Turns ${pct(b.p2s)} of pressures into sacks (league ${pct(b.p2sLg)})`);
  if(b.intw!=null&&Math.abs(b.intw-b.intwLg)>=.006) out.push(`Interception-worthy throws on ${P1(b.intw)} of dropbacks (league ${P1(b.intwLg)})`);
  if((p.pos==='WR'||p.pos==='TE')&&dp.mofc!=null&&Math.abs(dp.mofc-.48)>=.06) out.push(`${opp} plays single-high ${dp.mofc>.48?'more':'less'} than average: ${dp.mofc>.48?'deep shots open up':'fewer deep shots, more underneath'}`);
  const cp=src.covParts; if(cp&&cp.man&&Math.abs(cp.man.raw-1)>=.02) out.push(`Man vs zone: ${opp} plays man ${pct(cp.man.rate)} (league ${pct(cp.man.lg)}); he gets ${cp.man.split>=1?Math.round(100*(cp.man.split-1))+'% more':Math.round(100*(1-cp.man.split))+'% fewer'} targets vs man than vs zone`);
  return out;
}
const slug=s=>s.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'');
/* ---- sportsbook prices: shown next to each pick, never used by the model ----
   Game lines: the market line in nflverse games.csv. Anytime TD: best US price (jaredpatchett/NFL-Model player_td.json).
   Yards/catches: every book in the davidcantugtr snapshot, averaged (mean implied probability) at the most common line. */
const imp=o=>o<0?-o/(-o+100):100/(o+100), am=p=>p>=.5?-Math.round(100*p/(1-p)):Math.round(100*(1-p)/p);
const price=(o,src)=>o==null||isNaN(o)?null:{odds:Math.round(o),implied:+imp(o).toFixed(3),src};
const EXT='/home/user/ext', TDP={}, PROPS={};
try{ const t=JSON.parse(fs.readFileSync(EXT+'/jaredpatchett_NFL-Model/data/player_td.json','utf8').replace(/:\s*-?NaN\b/g,': null'));   // the upstream file sometimes carries bare NaN
  if(t.week===WEEK) for(const x of t.players){ const o=(x.market||{}).anytime_td_price; if(o!=null) TDP[x.player_id]={o:+o,asOf:t.generated_at.slice(0,10)}; } }catch(e){}
try{ const rows=fs.readFileSync(EXT+'/nfl-player-prop-opportunity/data/latest/player_props.csv','utf8').trim().split('\n');
  const H=rows[0].split(','), ix=k=>H.indexOf(k), MK={player_reception_yds:'recYds',player_rush_yds:'rushYds',player_receptions:'rec'};
  const acc={};
  for(const r of rows.slice(1)){ const c=r.split(','); if(+c[ix('Week')]!==WEEK||!MK[c[ix('Market Key')]]) continue;
    const k=c[ix('Player')]+'|'+MK[c[ix('Market Key')]]; (acc[k]=acc[k]||[]).push({line:+c[ix('Line')],side:c[ix('Side')],o:+c[ix('American Odds')],book:c[ix('Bookmaker')]}); }
  for(const [k,v] of Object.entries(acc)){ const cnt={}; v.forEach(x=>cnt[x.line]=(cnt[x.line]||0)+1);
    const line=+Object.entries(cnt).sort((a,b)=>b[1]-a[1])[0][0], at=v.filter(x=>x.line===line);
    const avg=s=>{const q=at.filter(x=>x.side===s); return q.length?am(q.reduce((a,x)=>a+imp(x.o),0)/q.length):null;};
    PROPS[k]={line,over:avg('Over'),under:avg('Under'),books:new Set(at.map(x=>x.book)).size}; } }catch(e){}
const priceWhy=(pr,prob)=>pr?`Book price ${pr.odds>0?'+':''}${pr.odds} (${pr.src}) implies ${pct(pr.implied)}; the model says ${pct(prob)}`:'No book price posted yet for this pick';
const fmtSpread=x=>x===0?'PK':(x>0?'+':'')+x;
/* results calibration (redzone/calibrate.py): per stat and position, X' = s*(median + w*(X - median)) for every yardage and
   catch distribution, fitted on what actually happened (no sportsbook input); at a posted line the model's distance from
   50% is scaled by `trust`, the share of it that held up when it disagreed with a line. */
let RCAL=null; try{ RCAL=JSON.parse(fs.readFileSync(path.join(__dirname,'calibration.json'))); }catch(e){}
function calHist(h,off,c){ if(!c) return h; let tot=0; for(const x of h) tot+=x; if(!tot) return h;
  let acc=0, m=0; for(let i=0;i<h.length;i++){ acc+=h[i]; if(acc>=tot/2){ m=i-off; break; } }
  const o=new Array(h.length).fill(0);
  for(let i=0;i<h.length;i++){ if(!h[i]) continue; const v=c.s*(m+c.w*((i-off)-m)), j=Math.min(h.length-1,Math.max(0,Math.round(v)+off)); o[j]+=h[i]; }
  return o; }
const trustP=q=>RCAL&&RCAL.trust!=null?sg(RCAL.trust*lg(q)):q;
const games=[], picks=[], DUMP=process.env.EZDUMP?[]:null;   // EZDUMP=file: every player's simulated distributions (redzone/backtest.py)
for(const g of S.games){
  let k=E.calibrateV3(g,ctx,{N:4000,trust:1});
  /* finishing drives (finishing.py): move each team's red-zone TD rate by its tested amount (rzdev), then re-solve the
     offenses so the projected score stays where the scoreboard put it -- more touchdowns, fewer field goals */
  if(g.rzx&&g.rzx.away&&g.rzx.home&&(g.rzx.away.rzdev||g.rzx.home.rzdev)){
    const sd=E.hashStr(g.id+'|fin'), rate=r=>[0,1].map(i=>r.diag.rzTD[i]/Math.max(1,r.diag.rzTrips[i]));
    const b0=rate(E.simGameV3(g,{N:6000,trust:1,k,seed:sd,hist:false},ctx)), tgt=[b0[0]+g.rzx.away.rzdev,b0[1]+g.rzx.home.rzdev];
    for(let it=0;it<3;it++){ const rr=rate(E.simGameV3(g,{N:6000,trust:1,k,seed:sd,hist:false},ctx));
      ['away','home'].forEach((s,i)=>{ g.rzx[s].rzfin=+Math.min(1.5,Math.max(.67,(g.rzx[s].rzfin||1)*Math.exp(2.5*(tgt[i]-rr[i])))).toFixed(4); }); }
    k=E.calibrateV3(g,ctx,{N:4000,trust:1,k0:k});
  }
  const r=E.simGameV3(g,{N,trust:1,k,seed:E.hashStr(g.id+'|rz')},ctx);
  const W=r.G.W, pH=(r.G.win[1]+r.G.tie/2)/W, z=g.rzg, L=g.line, A=g.away, H=g.home;
  const sc={away:Math.round(r.ptsA),home:Math.round(r.ptsH)};
  const gid=`${SEASON}w${WEEK}-${g.id}`, label=`${A} @ ${H}`;
  const gameWhy=[`Model score: ${H} ${sc.home}, ${A} ${sc.away} (${N.toLocaleString()} simulated games)`,
    `Team ratings alone (offense, defense, special teams, QB, home field, rest): ${Math.abs(z.base)<.5?'even':(z.base>0?H:A)+' by '+Math.abs(z.base).toFixed(1)}`];
  for(const w of z.why) gameWhy.push(w.replace(/^(\w[\w ]*?) ([\d.]+) pts to (\w+)$/,(m,a,b,c)=>`${c} +${b} pts on ${a}`));
  for(const a of z.adj) gameWhy.push(a.text);
  const qb=g.qb||{}; for(const s of ['away','home']) if(qb[s]&&qb[s].change) gameWhy.push(`${g[s]} QB: ${qb[s].name} starts. ${qb[s].why}`);
  for(const s of ['away','home']) gameWhy.push(...teamWhy(g,s));
  for(const s of ['away','home']){ const f=(g.fin||{})[s]; if(!f) continue;
    if(Math.abs(f.offLast-f.lgLast)>=.05) gameWhy.push(`Red-zone finishing: ${g[s]} scored TDs on ${pct(f.offLast)} of red-zone trips last season (league ${pct(f.lgLast)}); about a quarter of that carries over, so ${f.dev>0?'more':'fewer'} of its points come as touchdowns`);
    if(Math.abs(f.glpass)>=.03) gameWhy.push(`Goal line: ${g[s]} throws on ${pct(f.offGL)} of plays inside the 10 (league ${pct(f.lgGL)}); here ${f.glpass>0?'+':''}${Math.round(100*f.glpass)} pts of pass rate near the goal line`); }
  if(g.wx) gameWhy.push(`Weather: ${g.wx.roof==='unknown'?'roof status not listed; no forecast available here, treated as normal':g.wx.note}`);
  const gp=[];
  // winner
  const fav=pH>=.5?H:A, pf=Math.max(pH,1-pH);
  const MS='market consensus', ml=g.ml||{};
  const mlP=price(fav===H?ml.home:ml.away,MS);
  gp.push({id:`${gid}-ml-${slug(fav)}`,type:'Winner',game:label,gameId:g.id,team:fav,text:`${fav} win`,prob:pf,price:mlP,
    why:[`${fav} win ${pct(pf)} of simulations`,priceWhy(mlP,pf),...gameWhy]});
  // spread vs the current line (the line is only the target; it never feeds the model)
  const sH=L.spread, ov=E.histOver(r.G.margin,80,-sH), pHc=ov.over/((1-ov.push)||1);
  const side=pHc>=.5?H:A, ps=Math.max(pHc,1-pHc), sp=side===H?sH:-sH;
  const spP=price((g.spreadOdds||{})[side===H?'home':'away'],MS);
  gp.push({id:`${gid}-ats-${slug(side)}`,type:'Spread',game:label,gameId:g.id,team:side,line:sp,text:`${side} ${fmtSpread(sp)}`,prob:ps,price:spP,
    why:[`Model has ${z.margin>=0?H:A} by ${Math.abs(z.margin).toFixed(1)}; the line is ${H} ${fmtSpread(sH)}`,`${side} covers ${pct(ps)} of simulations`,priceWhy(spP,ps),...gameWhy]});
  // total
  const to=E.histOver(r.G.total,0,L.total), pO=to.over/((1-to.push)||1), ou=pO>=.5?'Over':'Under', po=Math.max(pO,1-pO);
  const pr=g.rzt||{}, tw=[`Model total ${z.total.toFixed(1)} vs line ${L.total}`,`${ou} hits ${pct(po)} of simulations`];
  for(const s of ['away','home']) if(pr[s]&&Math.abs(pr[s].proe)>=2) tw.push(`${g[s]} passes ${Math.abs(pr[s].proe).toFixed(1)}% ${pr[s].proe>0?'more':'less'} than expected in the same situations`);
  for(const s of ['away','home']){const f=(g.form||{})[s]; if(f&&Math.abs(f.run-1)>=.02) tw.push(`Formations: ${g[s]} run game ${sgn(100*(f.run-1))}% vs this front`);}
  const toP=price((g.totalOdds||{})[ou.toLowerCase()],MS); tw.splice(2,0,priceWhy(toP,po));
  gp.push({id:`${gid}-tot-${ou.toLowerCase()}`,type:'Total',game:label,gameId:g.id,line:L.total,side:ou,text:`${ou} ${L.total}`,prob:po,price:toP,why:[...tw,...gameWhy.slice(0,1),...z.adj.filter(a=>a.k==='od').map(a=>a.text)]});
  // players
  const pl=[];
  for(const p of r.players){ if(p.field||p.hidden) continue;
    const src=g.players.find(x=>x.n===p.n)||{}, rz=src.rz||{}, side=p.side===H?'home':'away', opp=p.side===H?A:H, dp=(g.defp||{})[side]||{};
    const td=sg(CAL.slope*lg(p.pModel)+(CAL[p.pos]||0));
    if(DUMP) DUMP.push({gid:g.id,id:src.id,n:p.n,t:p.t,pos:p.pos,td,tdRaw:p.pModel,mu:src.mu?src.mu.score:null,cov:src.cov??null,
      rec:Array.from({length:16},(_,k)=>+E.histAtLeast(p.hist.rec,0,k).toFixed(4)),recYds:Array.from({length:201},(_,k)=>+E.histAtLeast(p.hist.recYds,15,k).toFixed(4)),
      rushYds:Array.from({length:201},(_,k)=>+E.histAtLeast(p.hist.rushYds,40,k).toFixed(4))});
    if(RCAL) for(const [key,off] of [['recYds',15],['rushYds',40],['rec',0]]) p.hist[key]=calHist(p.hist[key],off,RCAL.fit[key+'|'+p.pos]);
    const why=[];
    const role=[]; if(src.rec>=.04) role.push(`${pct(src.rec)} of ${p.t} targets`); if(src.rush>=.04) role.push(`${pct(src.rush)} of ${p.t} designed carries`);
    if(role.length) why.push(`Role: ${role.join(' and ')}`);
    if(rz.ez&&Math.abs(rz.ez-1)>=.1&&src.rec>=.08) why.push(`End-zone targets: ${rz.ez.toFixed(2)}× his overall target share`);
    if(rz.i5&&Math.abs(rz.i5-1)>=.1&&src.rush>=.08) why.push(`Carries inside the 5: ${rz.i5.toFixed(2)}× his overall carry share`);
    if(rz.rzs&&Math.abs(rz.rzs-1)>=.08) why.push(`Red-zone snaps and touches: ${rz.rzs.toFixed(2)}× his normal share`);
    const tl=(dp.tdpos||{})[p.pos]; if(tl&&p.pos!=='QB'&&Math.abs(tl-1)>=.15) why.push(`${opp} has given up ${tl.toFixed(2)}× the usual share of receiving TDs to ${NAME[p.pos]}`);
    if(dp.rtd&&(p.pos==='RB'||p.pos==='QB')&&Math.abs(dp.rtd-1)>=.12) why.push(`${opp} gives up rushing TDs at ${dp.rtd.toFixed(2)}× the league rate`);
    const pv=rz.pvo; if(pv){ const bits=[]; if(pv.yprx) bits.push(sgn(pv.recy)+' rec yds'); if(pv.ypcx) bits.push(sgn(pv.ry)+' rush yds');
      if(Math.abs(pv.td)>=.1) bits.push(`scores ${pv.td>0?'more':'less'} often`);
      if(bits.length) why.push(`Past games vs ${pv.opp} (last ${pv.n}): ${bits.join(', ')} vs his usual`); }
    if(rz.yac&&Math.abs(rz.yac)>=.8) why.push(`Yards after catch: ${sgn(rz.yac)} per catch vs expected`);
    if(rz.slot&&p.pos==='WR'&&rz.slot>=.45) why.push(`Works the slot (about ${pct(rz.slot)} of snaps, estimated)`);
    const f=(g.form||{})[side]; if(f&&p.pos==='RB'&&Math.abs(f.run-1)>=.02) why.push(`Formations: ${p.t} run game ${sgn(100*(f.run-1))}% against ${opp}'s boxes`);
    if(f&&f.pos&&f.pos[p.pos]&&Math.abs(f.pos[p.pos].tgt-1)>=.02&&(p.pos==='TE'||p.pos==='RB')) why.push(`Personnel matchup: ${NAME[p.pos]} targets ${sgn(100*(f.pos[p.pos].tgt-1))}%`);
    if(src.mu) why.push(`Matchup: ${src.mu.edge} vs ${src.mu.vs} (${src.mu.role}, likely)`, ...src.mu.why.filter(w=>/^(Style|After|Run style|Inside runs|Outside runs|Formation)/.test(w)));
    why.push(...playerStatWhy(p,src,g,side));
    const fin=(g.fin||{})[side];
    if(fin&&Math.abs(fin.glpass)>=.03&&p.pos!=='QB') why.push(`Goal line: ${p.t} ${fin.glpass>0?'throws':'runs'} more than most teams inside the 10 (${pct(fin.offGL)} pass, league ${pct(fin.lgGL)}), which ${(fin.glpass>0)===(p.pos!=='RB')?'helps':'hurts'} his TD chances`);
    if(fin&&p.pos==='QB'&&Math.abs(fin.qbShare-fin.lgQB)>=.04) why.push(`QB at the goal line: ${p.t}'s quarterbacks take ${pct(fin.qbShare)} of carries inside the 5 (league ${pct(fin.lgQB)}), sneaks included`);
    if(fin&&Math.abs(fin.offLast-fin.lgLast)>=.05) why.push(`Red-zone finishing: ${p.t} ${pct(fin.offLast)} TD rate on red-zone trips last season (league ${pct(fin.lgLast)})`);
    const tw_=teamWhy(g,side).filter(t=>(/Pass rush/.test(t)&&p.pos==='QB')||(/Run blocking/.test(t)&&p.pos==='RB')||(/Big plays/.test(t)&&p.pos!=='QB'));
    why.push(...tw_.slice(0,2));
    if(src.flag) why.push(`Injury: ${src.flag}`);
    why.push(`${p.t} projected ${side==='home'?sc.home:sc.away} points`);
    const m=p.mean;
    pl.push({n:p.n,t:p.t,pos:p.pos,td,rec:+(RCAL?E.histMean(p.hist.rec,0):m.REC).toFixed(1),recY:Math.round(RCAL?E.histMean(p.hist.recYds,15):m.RCY),rushY:Math.round(RCAL?E.histMean(p.hist.rushYds,40):m.RY),passY:Math.round(m.PY),
      medRec:E.histQuantile(p.hist.recYds,15,.5),medRush:E.histQuantile(p.hist.rushYds,40,.5)});
    const base=`${p.n} (${p.t} ${p.pos})`;
    const tp=TDP[src.id], tdP=tp?price(tp.o,`best US price, ${tp.asOf}`):null;
    if(p.pos!=='QB'||td>=.2) gp.push({id:`${gid}-td-${slug(p.n)}`,type:'Anytime TD',game:label,gameId:g.id,player:p.n,team:p.t,pos:p.pos,text:`${p.n} anytime TD`,prob:td,price:tdP,
      why:[`Scores in ${pct(td)} of simulations (calibrated)`,priceWhy(tdP,td),...why]});
    for(const [key,off,lab,min] of [['recYds',15,'receiving yards',35],['rushYds',40,'rushing yards',35],['rec',0,'catches',3.5]]){
      if(p.pos==='QB'&&key!=='rushYds') continue;
      // a posted book line: pick the side the model likes at that line, priced at the books' average
      const bk=PROPS[p.n+'|'+key];
      if(bk&&(bk.over!=null||bk.under!=null)){
        const o=E.histOver(p.hist[key],off,bk.line), pOv=trustP(o.over/((1-o.push)||1)), s=pOv>=.5?'over':'under', pr=Math.max(pOv,1-pOv);
        const bp=price(bk[s],`average of ${bk.books} books`);
        gp.push({id:`${gid}-${key}-${slug(p.n)}-${s}-${bk.line}`,type:key==='rec'?'Catches':'Yards',game:label,gameId:g.id,player:p.n,team:p.t,stat:key,side:s,line:bk.line,
          text:`${p.n} ${s} ${bk.line} ${lab}`,prob:pr,price:bp,why:[`${s==='over'?'Over':'Under'} hits ${pct(pr)} of simulations; projection ${E.histQuantile(p.hist[key],off,.5)} ${lab}`,priceWhy(bp,pr),...why]});
        continue;
      }
      const med=E.histQuantile(p.hist[key],off,.5); if(med<min) continue;
      // the highest DraftKings-style milestone he still reaches in at least 62% of simulations
      const ladder=key==='rec'?[3,4,5,6,7,8,9,10]:[25,40,50,60,70,80,90,100,125,150];
      const ok=ladder.filter(t=>E.histAtLeast(p.hist[key],off,t)>=.62); if(!ok.length) continue;
      const thr=ok[ok.length-1], pr=E.histAtLeast(p.hist[key],off,thr);
      gp.push({id:`${gid}-${key}-${slug(p.n)}-${thr}`,type:key==='rec'?'Catches':'Yards',game:label,gameId:g.id,player:p.n,team:p.t,stat:key,thr,
        text:`${p.n} ${thr}+ ${lab}`,prob:pr,price:null,why:[`Reaches ${thr}+ in ${pct(pr)} of simulations; projection ${med} ${lab}`,priceWhy(null,pr),...why]});
    }
  }
  games.push({id:g.id,gid,away:A,home:H,awayName:g.awayName,homeName:g.homeName,kick:g.kick.replace('Brazil','neutral site'),score:sc,pHome:pH,margin:z.margin,total:z.total,line:L,
    mu:(g.mu||[]).map(m=>({...m,id:`${gid}-mu-${slug(m.n)}`,week:WEEK,game:label})).sort((a,b)=>b.score-a.score),
    ml:gp[0],ats:gp[1],tot:gp[2],why:gameWhy,players:pl.sort((a,b)=>b.td-a.td).slice(0,8)});
  picks.push(...gp);
  process.stderr.write(`${label}: ${H} ${sc.home}-${sc.away} ${A}, ${H} win ${pct(pH)}\n`);
}
// the board: the most likely picks per type
const top=(type,n,min=0)=>picks.filter(p=>p.type===type&&p.prob>=min).sort((a,b)=>b.prob-a.prob).slice(0,n);
const board=[...top('Winner',4),...top('Spread',3),...top('Total',2),...top('Anytime TD',6),...top('Yards',5),...top('Catches',2)].sort((a,b)=>b.prob-a.prob);
// this week's defenses: estimated man / zone / single-high / blitz (coverage_2026.py, football.py)
const coverage=[];
for(const g of S.games) for(const side of ['away','home']){ const c=((g.rzfb||{})[side]||{}).cov; if(!c) continue;
  const dfn=side==='away'?g.home:g.away, opp=g[side];
  coverage.push({team:dfn,opp,man:c.man,man2025:c.man2025,lgMan:c.lgMan,hi:c.hi,hi2025:c.hi2025,lgHi:c.lgHi,blitz:c.blitz,lgBlitz:c.lgBlitz}); }
coverage.sort((a,b)=>b.man-a.man);
const out={season:SEASON,week:WEEK,label:S.label,generated:new Date().toISOString(),config:CFG,games,board:board.map(p=>p.id),picks,coverage};
fs.writeFileSync(outF,JSON.stringify(out));
if(DUMP) fs.writeFileSync(process.env.EZDUMP,JSON.stringify(DUMP));
console.log(`${games.length} games, ${picks.length} picks, board ${board.length}`);
board.forEach(p=>console.log(`${pct(p.prob).padStart(4)}  ${p.type.padEnd(10)} ${p.text}  (${p.game})`));
