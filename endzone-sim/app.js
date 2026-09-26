/* ================================ STATE ================================== */
const $=s=>document.querySelector(s);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const idOf=k=>hashStr(k).toString(36);
const SL={NFL:JSON.parse(JSON.stringify(BASE_NFL))};
const SRC={NFL:"baseline"};
const RES={NFL:{}};
let SPORT="NFL", TAB="games", N=5000, running=false, runToken=0;
let TRUST=1, LAMP=.8;
const OUT=new Set(), IN=new Set();       // manual scratches / manual restores
let LEGS=[];
let grades=null, ledger={bets:[]}, suggested=null, dbRef=null;
let LINES={};                            // user-entered book lines, shared through the db
const TUNING={posBias:{},schemeScale:1,notes:[]};
let PFILT={market:"td", game:"all"};
const MEM={};   /* keeps this visit working when browser storage is blocked */
const store={get(k,d){ if(k in MEM) return MEM[k]; try{const v=localStorage.getItem("ez:"+k);return v==null?d:JSON.parse(v);}catch(e){return d;}},
             set(k,v){ MEM[k]=v; try{localStorage.setItem("ez:"+k,JSON.stringify(v));}catch(e){}}};
TAB=store.get("tab","games"); PFILT=store.get("pfilt",PFILT);

const slate=()=>SL[SPORT], games=()=>slate().games;
const gameById=id=>games().find(g=>g.id===id);
const leagueOf=gid=>"NFL";
const initials=n=>n.split(" ").filter(w=>w&&!/^(I{1,3}|IV|V|Jr\.?|Sr\.?)$/.test(w)).slice(0,2).map(w=>w[0]).join("");
const POSCOLOR={QB:"var(--qb)",RB:"var(--rb)",WR:"var(--wr)",TE:"var(--te)",FLD:"var(--fld)"};
const ctx=()=>({tuning:TUNING,out:outSet(),tune:TUNE,opp:1,scheme:"off"});
function outSet(){ const s=new Set(OUT); return s; }
function isOut(p){ return (p.out&&!IN.has(p.n))||OUT.has(p.n); }

/* ============================== odds math ================================ */
const toDec=o=>o==null?null:(o>0?1+o/100:1+100/(-o));
const impl=o=>o==null?null:(o<0?(-o)/((-o)+100):100/(o+100));
function fairAm(p){ if(!(p>0)||p>=.999) return null; return p>=.5?-Math.round(100*p/(1-p)):Math.round(100*(1-p)/p); }
const fmtOdds=o=>o==null?"—":(o>0?"+"+o:""+o);
const pct=(x,d=0)=>(100*x).toFixed(d)+"%";
function devig2(a,b){ const pa=impl(a), pb=impl(b); if(pa==null||pb==null) return null; return pa/(pa+pb); }
function ev(p,price){ const d=toDec(price); return d==null?null:p*d-1; }
function evTag(e){ if(e==null) return `<span class="tagpill flat">no price</span>`;
  const cls=e>=.03?"up":(e<=-.03?"dn":"flat"); return `<span class="tagpill ${cls}">${e>=0?"+":"−"}${Math.abs(100*e).toFixed(1)}% EV</span>`; }

/* ============================== simulation =============================== */
function gameInputs(g){
  const gi=JSON.parse(JSON.stringify(g));
  gi.players=gi.players.map(p=>({...p,out:isOut(p)}));
  return gi;
}
function needsCal(g){ const touched=g.players.some(p=>OUT.has(p.n)||IN.has(p.n));
  return !(g.k&&g.kFor&&g.kFor[0]===g.spread&&g.kFor[1]===g.total&&(g.kTrust??1)===TRUST&&!touched); }
function simOne(g,n,legs){
  const gi=gameInputs(g);
  let k=g._k;
  if(!k){ k=needsCal(g)?calibrateV3(gi,ctx(),{N:1800,iters:3,iters2:4,trust:TRUST}):g.k; g._k=k; }
  const r=simGameV3(gi,{N:n,trust:TRUST,k,seed:hashStr(g.id+"|main"),legs},ctx());
  r.players.forEach(p=>p.league=g.league||"NFL"); return r;
}
function invalidate(g){ if(g) delete g._k; else for(const x of SL.NFL.games) delete x._k; }
function runAll(){
  const tok=++runToken, lg=SPORT, gs=games().filter(g=>(g.live||{}).status!=="post"||true);
  running=true; const bar=$("#prog i");
  const passes=[Math.min(1200,N),N].filter((x,i,a)=>i===0||x!==a[0]);
  let pi=0,i=0;
  (function step(){
    if(tok!==runToken) return;
    const g=gs[i]; RES[lg][g.id]=simOne(g,passes[pi]); RES[lg][g.id].pass=pi;
    i++; bar.style.width=(100*((pi*gs.length+i)/(passes.length*gs.length))).toFixed(0)+"%";
    if(i>=gs.length){ render(); i=0; pi++; if(pi>=passes.length){ running=false; setTimeout(()=>bar.style.width="0%",300); return; } }
    setTimeout(step,0);
  })();
}
function rerunGame(g){ invalidate(g); RES[leagueOf(g.id)][g.id]=simOne(g,N); render(); }

/* =========================== market extraction =========================== */
const STATS={
  value:{label:"Best value", short:""},
  td:{label:"Anytime TD", short:"TD"},
  recYds:{label:"Receiving yards",hist:"recYds",short:"rec yds"},
  rushYds:{label:"Rushing yards",hist:"rushYds",short:"rush yds"},
  rec:{label:"Catches",hist:"rec",short:"catches"},
};
const SLOT={passYds:"PY",passTD:"PTD",passAtt:"PA",rushYds:"RY",recYds:"RCY",rec:"REC"};
function statVal(st,b,stat){ if(stat==="rrYds") return st[b+S.RY]+st[b+S.RCY];
  if(stat==="td") return st[b+S.RTD]+st[b+S.RCTD]; return st[b+S[SLOT[stat]]]; }
function pOver(p,stat,line){ const h=p.hist[STATS[stat].hist], off=HIST[STATS[stat].hist][0]; return histOver(h,off,line); }
function fairLine(p,stat){
  const h=p.hist[STATS[stat].hist], off=HIST[STATS[stat].hist][0];
  const med=histQuantile(h,off,.5); let best=med+.5,bd=9;
  for(let L=Math.floor(med)-3.5;L<=med+3.5;L+=1){ const o=histOver(h,off,L).over; if(Math.abs(o-.5)<bd){bd=Math.abs(o-.5);best=L;} }
  return Math.max(.5,best);
}
function volume(p,stat){ const m=p.mean;
  return {rushYds:m.RA, recYds:m.TGT, rec:m.TGT}[stat]||0; }
function relevant(p,stat){
  if(p.field||p.hidden) return false;
  if(stat==="value") return false;
  const m=p.mean;
  if(stat==="rushYds") return m.RA>=3.5;
  if(stat==="recYds"||stat==="rec") return m.TGT>=2.5&&!p.isQB;
  return true;
}
const lineKey=(gid,pn,stat)=>`${gid}|${pn}|${stat}`;

/* ===================== game model: moneyline and spread =====================
   Separate from the player simulation. g.gm.m is the game model's home margin from team efficiency, quarterbacks,
   rest and home field (no betting line in it). Chances start from DraftKings' own no-vig price and move by the
   model's disagreement with DraftKings' spread, scaled by GMFIT.k (the weight that tested best) and converted with
   rates fitted on 2006-20 results: GMFIT.b per point for winning, GMFIT.slope per point for covering. */
const lgt_=q=>{q=Math.min(.999,Math.max(.001,q)); return Math.log(q/(1-q));}, sgm_=z=>1/(1+Math.exp(-z));
function gmLine(g){ return g.dk&&g.dk.spread!=null?-g.dk.spread:(g.spread!=null?-g.spread:0); }   // home points DraftKings expects
function gmEdge(g){ return g.gm&&g.gm.m!=null?GMFIT.k*(g.gm.m-gmLine(g)):0; }                   // points the lean moves the line
function gmHat(g){ return gmLine(g)+gmEdge(g); }
function gmWin(g,side){ const d=g.dk||{}, ml=d.ml||{};
  const pk=ml.home!=null&&ml.away!=null?devig2(ml.home,ml.away):sgm_(GMFIT.b*gmLine(g));
  const ph=sgm_(lgt_(pk)+GMFIT.b*gmEdge(g)); return side==="home"?ph:1-ph; }
function gmCover(g,side){ const d=g.dk||{}, o=d.spo||{};
  const ps=o.home!=null&&o.away!=null?devig2(o.home,o.away):.5;
  const ph=Math.min(.97,Math.max(.03,ps+GMFIT.slope*gmEdge(g))); return {p:side==="home"?ph:1-ph, push:0}; }
const half=x=>Math.round(x*2)/2;

/* ===================== team values and the "line doesn't match the teams" flag =====================
   ONE combined value per team (slate.teams, gm/game_live.py): the books' rating (25%), the stats view: offense, defense,
   special teams and this week's quarterback (75%), then the published power ranking at 10% when available. Each home
   team adds its own home field. A game's fair line is home field + value(home) - value(away) + rest. When DraftKings'
   spread sits FLAGAT+ points from it, the game is flagged. Flags say the line doesn't match how good the teams are;
   they aren't picks. The record (gm/flag_record.py, closing spreads 2016-25, each season rated only from earlier ones,
   blend and threshold chosen on 2016-20) shows with the flags. */
const GF=()=>slate().gmfit||{};
const FLAGAT=()=>GF().flagAt||4;
function lineGap(g){ if(!g.gm||g.gm.m==null) return null; return g.gm.m-gmLine(g); }   // + = the teams' values like the home side more than DraftKings does
const says=(g,x)=>x>=0?`${esc(g.home)} by ${Math.abs(x).toFixed(1)}`:`${esc(g.away)} by ${Math.abs(x).toFixed(1)}`;
function flagOf(g){ const gap=lineGap(g); if(gap==null||(g.dk||{}).spread==null||Math.abs(gap)<FLAGAT()) return null; return {gap:Math.abs(gap)}; }
function flagRecord(){ const F=GF().flags, k=F&&F.byGap&&F.byGap[String(FLAGAT())]; if(!k||!k.all) return "";
  const a=k.all, h=k.heldOut;
  return `<b>Record of ${FLAGAT()}+ point flags</b> since ${F.since}: the side the team values liked covered the closing spread ${pct(a.cover,1)} of the time (${a.n} games, ${a.seasonsUp} of ${a.seasons} seasons above 50%, about ${Math.max(1,Math.round(a.perSeason/17))} a week). In 2021–25, years not used to choose the blend or the threshold: ${pct(h.cover,1)} (${h.n} games). Break-even at DraftKings' usual price is 52.4%. Public opinion has no history, so it isn't in this record.`; }
function flagBox(){ const fl=games().map(g=>({g,f:flagOf(g)})).filter(x=>x.f).sort((a,b)=>b.f.gap-a.f.gap);
  return `<div class="flagbox"><h3>Lines that don't match the teams · ${fl.length}</h3>${fl.length?fl.map(({g,f})=>
    `<div class="flagline"><span><b>${esc(g.away)} @ ${esc(g.home)}</b><span class="sub">DraftKings ${says(g,gmLine(g))} · team values say ${says(g,g.gm.m)}</span></span><span class="lineflag">${f.gap.toFixed(1)} pts apart</span></div>`).join(""):`<p class="empty">Every DraftKings spread is within ${FLAGAT()} points of the team values this week.</p>`}
    <p class="tiny" style="margin:8px 0 0">${flagRecord()}</p></div>`; }
function renderTeams(){ const T=slate().teams||[]; const opp={}, SR=slate().sources||{}, P=SR.public;
  games().forEach(g=>{opp[g.home]={g,vs:g.away,home:1}; opp[g.away]={g,vs:g.home,home:0};});
  const sg=x=>x==null?"—":`<span class="${x>0.05?"up":x<-0.05?"dn":""}">${x>0?"+":x<0?"−":""}${Math.abs(x).toFixed(1)}</span>`;
  $("#tab-teams").innerHTML=`<p class="lead">One value per team: points better or worse than an average team on a neutral field. It combines <b>Books</b> (how the betting market has rated the team from past lines, ${Math.round(100*(SR.booksWeight??.25))}%), <b>Stats</b> (offense, defense and special teams, each measured against the quality of opponents) and <b>QB</b> (this week's starter against the team's recent quarterbacks) for the rest, and <b>Public</b> opinion at 10%${P?` (${esc(P.source)})`:": no published ranking was reachable at the last refresh, so it's left out"}. <b>Home</b> is what the team gets at home: the league's home field plus ${Math.round(100*(SR.hfaShare??.5))}% of the team's own edge (${esc(SR.hfa||"")}), capped at a point either way. A game's fair line is the home team's Home plus the difference in values.</p>
  ${T.length?`<div class="gcard"><div class="tscroll"><table class="teams"><thead><tr><th>Team</th><th>Value</th><th>Books</th><th>Stats</th><th>QB</th><th>Home</th>${P?"<th>Pub.</th>":""}<th>Week</th></tr></thead><tbody>${T.map(x=>{const o=opp[x.t], f=o?flagOf(o.g):null;
    return `<tr><td><span class="rank">${x.rank}</span> ${esc(x.t)} <span class="tiny">${esc(x.qbName||"")}</span></td><td class="v">${sg(x.value)}</td>
      <td>${sg(x.books)} <span class="tiny">#${x.booksRank}</span></td>
      <td class="sv">${sg(x.stats)} <span class="tiny">#${x.statsRank}</span><span class="sub">off ${sg(x.off)}<br>def ${sg(x.dfn)}<br>st ${sg(x.st)}</span></td>
      <td>${sg(x.qb)}</td><td>${x.home!=null?x.home.toFixed(1):"—"}</td>${P?`<td>${x.publicRank?"#"+x.publicRank:"—"}</td>`:""}
      <td>${o?`${o.home?"vs":"@"} ${esc(o.vs)}${f?` <span class="lineflag">flag</span>`:""}`:"<span class=\"tiny\">bye / played</span>"}</td></tr>`;}).join("")}</tbody></table></div></div>`:`<p class="empty">Team values arrive with the next refresh.</p>`}
  ${flagBox()}`; }

/* =============================== TD pricing ============================== */
/* DraftKings anytime-TD pricing, fitted on 8,422 DK prices 2023-24 (about 5 minutes before kickoff):
   fair(DK alone) = logistic(dva + dvb·logit(implied)); best estimate = logistic(a + bk·logit(implied) + bm·logit(model)). */
const lgt=q=>{q=Math.min(.999,Math.max(.001,q)); return Math.log(q/(1-q));}, sgm=z=>1/(1+Math.exp(-z));
function tdPrice(p){ return p.mkt!=null?p.mkt:null; }
function tdMarket(p,price=tdPrice(p)){ return price==null?null:sgm(TDFIT.dva+TDFIT.dvb*lgt(impl(price))); }
/* backtest recalibration (2025, logistic on the simulated probability with a position offset) */
function tdCal(p){ const c=(TDCAL[p.league||"NFL"]||{})[p.pos]; const C=TDCAL[p.league||"NFL"]; if(!C||c==null) return p.pModel;
  const q=Math.min(.999,Math.max(.001,p.pModel)); const z=C.slope*Math.log(q/(1-q))+c; return 1/(1+Math.exp(-z)); }
function tdFinal(p,price=tdPrice(p)){ const m=tdCal(p); return price==null?m:sgm(TDFIT.a+TDFIT.bk*lgt(impl(price))+TDFIT.bm*lgt(m)); }

/* ============================== rendering ================================ */
function avatar(p,sm){ return `<div class="av${sm?" sm":""}" style="background:${POSCOLOR[p.pos]||"var(--fld)"}">${esc(initials(p.n))}<span class="pos">${esc(p.pos)}</span></div>`; }
function render(){
  $("#slateLabel").textContent=`${slate().label||""} · ${games().length} games`;
  $("#srcText").textContent=SRC[SPORT]==="feed"?"live":"built in";
  $("#srcChip").className="pill "+(SRC[SPORT]==="feed"?"on":"");
  if(TAB==="games") renderGames(); if(TAB==="props") renderProps(); if(TAB==="slip") renderSlip();
  if(TAB==="bets") renderBets(); if(TAB==="model") renderModel(); if(TAB==="teams") renderTeams();
}
function showTab(t){ TAB=t; store.set("tab",t);
  document.querySelectorAll('[role="tablist"] button').forEach(b=>b.setAttribute("aria-selected",String(b.dataset.tab===t)));
  ["games","teams","props","slip","bets","model"].forEach(k=>{$("#tab-"+k).hidden=(k!==t);}); render(); }

/* ------------------------------- games ---------------------------------- */
function mrow(label,side,pModel,price,fair,legSpec,extra){
  const e=ev(pModel,price), inS=legSpec&&LEGS.some(l=>l.key===legKey(legSpec));
  return `<button class="mrow" ${legSpec?`data-leg='${esc(JSON.stringify(legSpec))}'`:""}>
    <span class="ml">${label}${extra?`<span class="sub">${extra}</span>`:""}</span>
    <span class="mv n">${pct(pModel,1)}</span><span class="mf n">${fmtOdds(fair)}</span>
    <span class="mb n">${price!=null?fmtOdds(price):"—"}</span>${evTag(price!=null?e:null)}${inS?`<span class="tagpill up">✓</span>`:""}</button>`;
}
function renderGames(){
  const lg=SPORT, R=RES[lg];
  $("#tab-games").innerHTML=`<p class="lead">Each game shows DraftKings\' line next to the fair line from the team values (Teams tab), and flags games where they sit ${FLAGAT()}+ points apart. Flags aren\'t picks. Moneyline and spread chances start from DraftKings\' own price and move ${Math.round(100*GMFIT.k)}% toward the team values. None of this touches the player numbers.</p>`+
  flagBox()+games().map(g=>{
    const r=R[g.id], d=g.dk||{}, sp=d.spread, spo=d.spo||{}, ml=d.ml||{};
    const L=gmLine(g), hat=gmHat(g), m=g.gm?g.gm.m:null;
    const fav=sp==null?"":(sp<0?g.home:g.away);
    const qbc=r&&r.qb&&(r.qb.away.change||r.qb.home.change);
    const row=(label,p,price,spec,extra)=>mrow(label,spec.side,p,price,fairAm(p),spec,extra);
    let mk="";
    if(sp!=null){
      const ch=gmCover(g,"home"), ca=gmCover(g,"away");
      mk=`${row(`${esc(g.away)} moneyline`,gmWin(g,"away"),ml.away,{kind:"ml",gid:g.id,side:"away",price:ml.away})}
        ${row(`${esc(g.home)} moneyline`,gmWin(g,"home"),ml.home,{kind:"ml",gid:g.id,side:"home",price:ml.home})}
        ${row(`${esc(g.away)} ${-sp>0?"+":"−"}${Math.abs(sp)}`,ca.p,spo.away,{kind:"spread",gid:g.id,side:"away",line:-sp,price:spo.away},ca.push>.01?`push ${pct(ca.push,1)}`:"")}
        ${row(`${esc(g.home)} ${sp>0?"+":"−"}${Math.abs(sp)}`,ch.p,spo.home,{kind:"spread",gid:g.id,side:"home",line:sp,price:spo.home})}`;
    }
    const tm=x=>x>=0?`${esc(g.home)} by ${Math.abs(x).toFixed(1)}`:`${esc(g.away)} by ${Math.abs(x).toFixed(1)}`;
    return `<article class="gcard" id="g-${g.id}">
      <div class="ghead"><div><div class="gt">${esc(g.awayName||g.away)} @ ${esc(g.homeName||g.home)}</div>
        <div class="gm">${esc(g.kick||"")}${sp!=null?` · ${esc(fav)} −${Math.abs(sp)}`:""} · ${d.src==="dk"?"DraftKings":"<b class=\"warnc\">consensus line, not DraftKings yet</b>"}</div></div>
        <div class="scorestack">${m!=null?`${tm(m)}<br><span class="tiny">game model</span>`:""}</div></div>
      ${qbc?`<div class="flagrow"><span class="qbflag">QB change</span> ${[[g.away,r.qb.away],[g.home,r.qb.home]].filter(x=>x[1].change).map(([t,q])=>`${esc(t)}: ${esc(q.name||"new starter")}`).join(" · ")}</div>`:""}
      <div class="mtable">
        <div class="mhead"><span>Market</span><span>Chance</span><span>Fair</span><span>DK</span><span>Value</span></div>
        ${mk||'<p class="empty">No line posted yet.</p>'}
      </div>
      ${g.gm?`<div class="fairrow">DraftKings <b>${tm(L)}</b> · team values <b>${tm(m)}</b>${flagOf(g)?` <span class="lineflag">${flagOf(g).gap.toFixed(1)} pts apart</span>`:` <span class="tiny">${Math.abs(lineGap(g)).toFixed(1)} pts apart</span>`}</div><p class="tiny gmwhy">${g.gm.why?esc(g.gm.why):"no single factor stands out"}</p>`:""}
      ${r?`<div class="plist">${r.players.filter(p=>!p.field&&!p.hidden).sort((a,b)=>tdFinal(b)-tdFinal(a)).slice(0,8).map(p=>{
        const main=p.mean.RA>=6?`${Math.round(fairLine(p,"rushYds"))} rush yds`:(p.isQB?`${Math.round(fairLine(p,"rushYds"))} rush yds`:`${fairLine(p,"rec")} catches · ${Math.round(fairLine(p,"recYds"))} yds`);
        return `<button class="prow ${isOut(p)?"out":""}" data-goprops="${g.id}|${esc(p.n)}">${avatar(p,1)}
          <span><span class="pn">${esc(p.n)}</span><span class="ps">${esc(p.t)} ${esc(p.pos)} · ${main}${p.flag?` · <b class="warnc">${esc(p.flag)}</b>`:""}</span></span>
          <span class="pv">${pct(tdFinal(p),0)}</span><span class="pe">TD</span></button>`;}).join("")}</div>`:`<p class="empty">simulating players…</p>`}
      <details class="sp"><summary>Scratch or restore a player</summary><div class="scratch">${
        g.players.filter(p=>p.pos==="QB"||p.rush>=.08||p.rec>=.08||p.out).map(p=>`<label><input type="checkbox" data-out="${esc(p.n)}" ${isOut(p)?"checked":""}>
          ${esc(p.n)} <span class="tiny">${esc(p.t)} ${esc(p.pos)}${p.out?" · listed out":""}</span></label>`).join("")}
        <p class="empty">A scratched player's work goes 72% to his position group and the rest to everyone else, then the players re-simulate. Moneyline and spread don't change.</p></div></details>
      ${g.note?`<p class="note">${esc(g.note)}</p>`:""}
    </article>`;}).join("");
  const tg=$("#tab-games");
  tg.querySelectorAll("input[data-out]").forEach(el=>el.onchange=()=>{const n=el.dataset.out, g=games().find(x=>x.players.some(p=>p.n===n)), p=g.players.find(q=>q.n===n);
    if(el.checked){ IN.delete(n); if(!p.out) OUT.add(n); } else { OUT.delete(n); if(p.out) IN.add(n); }
    LEGS=LEGS.filter(l=>l.pn!==n); rerunGame(g);});
}
function defBlocks(g,r){
  if(leagueOf(g.id)!=="NFL") return "";
  const blk=(team,def,facing)=>{const s=def.src||"lg"; return `<div class="defcard"><div class="defhead"><span class="defname">${esc(team)} defense <span class="tiny">· ${esc(facing)} attacks it</span></span>
    <span class="srctag ${s}">${{w1:"2026 data","25":"2025 base",dc:"coordinator",lg:"league avg"}[s]}</span></div>
    <div class="cov"><span>man <b>${Math.round(100*def.man)}%</b></span><span>blitz <b>${Math.round(100*def.blitz)}%</b></span><span>single-high <b>${Math.round(100*def.mofc)}%</b></span></div>
    <div class="defread">${esc(def.note||schemeRead(def,team))}</div></div>`;};
  return `<details class="sp"><summary>Coverage and pressure</summary><div class="scripts defwrap">${blk(g.home,r.def.away,g.away)}${blk(g.away,r.def.home,g.home)}</div></details>`;
}

/* ------------------------------- props ---------------------------------- */
function propRows(){
  const out=[], lg=SPORT;
  for(const g of games()){ const r=RES[lg][g.id]; if(!r) continue; if(PFILT.game!=="all"&&PFILT.game!==g.id) continue;
    for(const p of r.players){ if(!relevant(p,PFILT.market)) continue; out.push({g,p}); } }
  return out;
}
function renderProps(){
  const mk=PFILT.market, rows=mk==="value"?[]:propRows();
  const chips=Object.entries(STATS).map(([k,v])=>`<button class="chip" data-mk="${k}" aria-pressed="${k===mk}">${v.label}</button>`).join("");
  const gsel=`<select id="pgame" aria-label="Game"><option value="all">All games</option>${games().map(g=>`<option value="${g.id}" ${PFILT.game===g.id?"selected":""}>${esc(g.away)} @ ${esc(g.home)}</option>`).join("")}</select>`;
  let body="";
  if(mk==="td"){
    rows.sort((a,b)=>tdFinal(b.p)-tdFinal(a.p));
    body=rows.slice(0,60).map(({g,p})=>{
      const f=tdFinal(p), fair=tdMarket(p), price=tdPrice(p), e=price!=null?ev(f,price):null;
      const spec={kind:"td",gid:g.id,pn:p.n,price};
      const inS=LEGS.some(l=>l.key===legKey(spec));
      return `<li><button class="row" data-leg='${esc(JSON.stringify(spec))}'>${avatar(p)}
        <span class="who"><span class="nm">${esc(p.n)} ${isOut(p)?'<span class="verdict pricey">out</span>':""}</span>
          <span class="sub">${esc(p.t)} vs ${esc(p.t===g.home?g.away:g.home)} · ${esc(g.kick||"")}${price!=null?` · DK ${p.mktSrc==="est"?"≈":""}${fmtOdds(price)}`:" · no price on file"}${p.flag?` · <b class="warnc">${esc(p.flag)}</b>`:""}</span>
          <span class="bar"><i style="width:${(100*f).toFixed(1)}%;background:${POSCOLOR[p.pos]}"></i></span>
          <span class="sub">${tdWhy(p,g)} ${inS?'<span class="tagpill up">✓ in slip</span>':""}</span></span>
        <span class="rt"><span class="big">${(100*f).toFixed(0)}<i>%</i></span><span class="sub">fair ${fmtOdds(fairAm(f))}</span>${evTag(e)}</span>
      </button></li>`;}).join("");
  } else if(mk==="value"){
    const vr=valueRows();
    body=vr.slice(0,40).map(({g,p,mk:m})=>propRowHTML(g,p,m)).join("");
  } else {
    rows.sort((a,b)=>volume(b.p,mk)-volume(a.p,mk));
    body=rows.slice(0,80).map(({g,p})=>propRowHTML(g,p,mk)).join("");
  }
  $("#tab-props").innerHTML=`<div class="chips" role="group" aria-label="Market">${chips}</div>
    <div class="pfbar">${gsel}<span class="tiny">${mk==="value"?"DraftKings prices as of "+esc(((games().find(g=>g.propsAsOf)||{}).propsAsOf||"—").slice(0,16).replace("T"," "))+" UTC":rows.length+" players"}</span></div>
    <p class="lead">${mk==="value"?`Every DraftKings prop on file, sorted by expected value at DraftKings' price. The chance shown is ${Math.round(100*LAMP)}% DraftKings' no-vig price and ${Math.round(100-100*LAMP)}% simulation. Across 938 graded DraftKings props (2024–26), bets this list would have made returned +7.5% ± 6%, but they're losing so far in 2026 (−7%). Unproven: small stakes only. Props where the simulation and DraftKings disagree by more than 22 points are left off, because that's usually news. So are questionable players.`:mk==="td"?`The chance he scores a rushing or receiving touchdown. Where a DraftKings price is on file, it's combined with the simulation using weights fitted on 8,422 real DraftKings prices. ≈ means the price is estimated from the best price across books, so tap the player and type DraftKings' real price in the slip. At kickoff prices, fewer than 1 in 20 players clear DraftKings' hold.`:
      `Fair line is where the simulation has over and under at 50/50. DraftKings' line and prices are filled in where the snapshot has them; type them yourself for anything missing. The chance shown is ${Math.round(100*LAMP)}% DraftKings' no-vig price and ${Math.round(100-100*LAMP)}% simulation. Lines you type are saved and shared.`}</p>
    <ol class="board">${body||'<li class="empty">No players for this market.</li>'}</ol>`;
  const tp=$("#tab-props");
  tp.querySelectorAll("[data-mk]").forEach(b=>b.onclick=()=>{PFILT.market=b.dataset.mk; store.set("pfilt",PFILT); renderProps();});
  $("#pgame").onchange=e=>{PFILT.game=e.target.value; store.set("pfilt",PFILT); renderProps();};
  tp.querySelectorAll("input[data-line]").forEach(el=>el.onchange=()=>{ saveLine(el.dataset.line,el.dataset.f,el.value); });
}
function tdWhy(p,g){
  const r=RES[leagueOf(g.id)][g.id], m=p.mean;
  const bits=[];
  if(m.RA>=4) bits.push(`${m.RA.toFixed(0)} carries`);
  if(m.TGT>=2) bits.push(`${m.TGT.toFixed(1)} targets`);
  if(p.gl>=1.25) bits.push("heavy red-zone role");
  else if(p.gl<=.75&&!p.isQB) bits.push("light red-zone role");
  if(p.isQB&&p.gl>=1.4) bits.push("goal-line runner");
  const imp=p.side===g.home?r.ptsH:r.ptsA; bits.push(`team ~${imp.toFixed(0)} pts`);
  if(p.conf==="low") bits.push("thin sample");
  return esc(bits.join(" · "));
}
/* A prop's price: the line you typed wins; otherwise DraftKings' line and prices from this week's snapshot. */
function propQuote(g,p,mk){
  const L=LINES[lineKey(g.id,p.n,mk)]||{};
  if(L.line!=null&&L.line!==""){ const oo=L.o!=null&&L.o!==""?+L.o:-110, uo=L.u!=null&&L.u!==""?+L.u:-110;
    return {line:+L.line, oo, uo, mkt:devig2(oo,uo), src:"you"}; }
  const b=p.book&&p.book[mk], dk=b&&b.books&&b.books.draftkings; if(!dk) return null;
  return {line:b.line, oo:dk[0], uo:dk[1], mkt:devig2(dk[0],dk[1]), src:"dk"};
}
/* Chance of the over: DraftKings' no-vig price blended with the simulation (LAMP = weight on DraftKings, 80% by default).
   Held out one season at a time on 938 graded DK props (2024-26), that weight beat DraftKings alone in 2024 and 2025
   and lost slightly in 2026 Weeks 1-2. */
function propOverP(mk,mkt,raw){ return LAMP*mkt+(1-LAMP)*raw; }
function propEval(p,mk,q){
  const o=pOver(p,mk,q.line), po=o.over/(1-o.push||1);
  const bo=propOverP(mk,q.mkt,po), bu=1-bo;
  return {po, push:o.push, bo, bu, eo:ev(bo,q.oo), eu:ev(bu,q.uo)};
}
function propRowHTML(g,p,mk){
  const key=lineKey(g.id,p.n,mk), L=LINES[key]||{}, fl=fairLine(p,mk), q=propQuote(g,p,mk);
  const qs=[.1,.9].map(x=>histQuantile(p.hist[STATS[mk].hist],HIST[STATS[mk].hist][0],x));
  let detail="";
  if(q){
    const e=propEval(p,mk,q);
    const so={kind:"prop",gid:g.id,pn:p.n,stat:mk,side:"over",line:q.line,price:q.oo}, su={...so,side:"under",price:q.uo};
    detail=`<span class="ouw">
      <button class="oubtn ${e.eo>=.03?"good":""} ${LEGS.some(l=>l.key===legKey(so))?"on":""}" data-leg='${esc(JSON.stringify(so))}'>Over ${q.line} <b>${pct(e.bo,0)}</b> ${fmtOdds(q.oo)} ${evTag(e.eo)}</button>
      <button class="oubtn ${e.eu>=.03?"good":""} ${LEGS.some(l=>l.key===legKey(su))?"on":""}" data-leg='${esc(JSON.stringify(su))}'>Under ${q.line} <b>${pct(e.bu,0)}</b> ${fmtOdds(q.uo)} ${evTag(e.eu)}</button></span>
      ${Math.abs(e.po-q.mkt)>.22?`<span class="tiny warnc">The simulation and DraftKings disagree by ${Math.round(100*Math.abs(e.po-q.mkt))} points. That's usually a role change or injury the data hasn't caught yet, so check the news before betting it.</span>`:""}
      <span class="tiny">${q.src==="dk"?`DraftKings · no-vig ${pct(q.mkt,0)} over`:"your line"} · simulation ${pct(e.po,0)} over${e.push>.005?` · push ${pct(e.push,0)}`:""}</span>`;
  }
  const b=p.book&&p.book[mk];
  return `<li class="prop">${avatar(p)}
    <span class="who"><span class="nm">${esc(p.n)} ${isOut(p)?'<span class="verdict pricey">out</span>':""}</span>
      <span class="sub">${esc(p.t)} vs ${esc(p.t===g.home?g.away:g.home)} · ${esc(STATS[mk].label.toLowerCase())} · 10–90%: ${qs[0]}–${qs[1]}${p.flag?` · <b class="warnc">${esc(p.flag)}</b>`:""}${p.conf==="low"?' · <b class="warnc">thin sample</b>':""}</span>
      ${detail}
      <details class="mine"><summary class="tiny">${L.line!=null?"Your line":"Use your own line"}</summary><span class="lin">
        <label class="tiny" for="ln-${idOf(key)}">Line</label><input id="ln-${idOf(key)}" inputmode="decimal" data-line="${esc(key)}" data-f="line" value="${L.line??""}" placeholder="${b?b.line:fl}">
        <label class="tiny" for="lo-${idOf(key)}">Over</label><input id="lo-${idOf(key)}" inputmode="numeric" data-line="${esc(key)}" data-f="o" value="${L.o??""}" placeholder="-110">
        <label class="tiny" for="lu-${idOf(key)}">Under</label><input id="lu-${idOf(key)}" inputmode="numeric" data-line="${esc(key)}" data-f="u" value="${L.u??""}" placeholder="-110"></span></details></span>
    <span class="rt"><span class="big">${fl}</span><span class="sub">fair line</span></span></li>`;
}
function valueRows(){
  const out=[];
  for(const g of games()){ const r=RES.NFL[g.id]; if(!r) continue; if(PFILT.game!=="all"&&PFILT.game!==g.id) continue;
    for(const p of r.players){ if(p.field||p.hidden||isOut(p)||p.flag) continue;   // injury-driven gaps aren't value
      for(const mk of ["recYds","rushYds","rec"]){ if(!relevant(p,mk)) continue; const q=propQuote(g,p,mk); if(!q) continue;
        const e=propEval(p,mk,q); if(Math.abs(e.po-q.mkt)>.22) continue;   // a gap this big is usually news the data hasn't caught
        out.push({g,p,mk,best:Math.max(e.eo??-1,e.eu??-1)}); } } }
  return out.sort((a,b)=>b.best-a.best);
}
function saveLine(key,f,v){
  const L=LINES[key]||(LINES[key]={}); L[f]=v===""?null:+v; if(L.line==null&&L.o==null&&L.u==null) delete LINES[key];
  store.set("lines",LINES); renderProps(); persistLines();
}
let lineTimer=null;
function persistLines(){ clearTimeout(lineTimer); lineTimer=setTimeout(async()=>{ try{ const db=await getDb(); if(db) await db.doc("lines/current").set({lines:LINES,updated:new Date().toISOString()}); }catch(e){} },800); }

/* ------------------------------- slip ----------------------------------- */
function legKey(l){ return [l.kind,l.gid,l.side||"",l.pn||"",l.stat||"",l.line??""].join("|"); }
function legDesc(l){ const g=gameById(l.gid)||{away:"",home:""};
  if(l.kind==="ml") return `${l.side==="home"?g.home:g.away} moneyline`;
  if(l.kind==="spread") return `${l.side==="home"?g.home:g.away} ${l.line>0?"+":""}${l.line}`;
  if(l.kind==="td") return `${l.pn} anytime TD`;
  if(l.kind==="prop") return `${l.pn} ${l.side} ${l.line} ${STATS[l.stat].short}`;
  return l.pn||"";
}
function legMarginal(l){ /* the displayed probability of one bet, and the raw model number */
  const g=gameById(l.gid);
  if(l.kind==="ml"){ const p=gmWin(g,l.side); return {p,raw:p}; }
  if(l.kind==="spread"){ const p=gmCover(g,l.side).p; return {p,raw:p}; }
  const r=RES[leagueOf(l.gid)][l.gid]; if(!r) return {p:0,raw:0};
  const p=r.players.find(x=>x.n===l.pn); if(!p) return {p:0,raw:0};
  if(l.kind==="td") return {p:tdFinal(p),raw:p.pModel};
  const o=pOver(p,l.stat,l.line), raw=(l.side==="over"?o.over:1-o.over-o.push)/(1-o.push||1);
  const q=propQuote(gameById(l.gid),p,l.stat); const mkt=q&&q.line===l.line?q.mkt:null;
  const ov=mkt==null?null:propOverP(l.stat,mkt,l.side==="over"?raw:1-raw);   // raw is this side's chance, so 1-raw is the over's for an under
  const b=ov==null?raw:(l.side==="over"?ov:1-ov);
  return {p:b,raw};
}
function legPred(l,roster){
  const ix=l.pn?roster.findIndex(x=>x.n===l.pn):-1, b=ix*S.NS;
  if(l.kind==="ml") return (st,sc)=>l.side==="home"?(sc[1]>sc[0]||(sc[1]===sc[0]&&Math.random()<.5)):(sc[0]>sc[1]||(sc[1]===sc[0]&&Math.random()<.5));
  if(l.kind==="spread") return (st,sc)=>{ const m=l.side==="home"?sc[1]-sc[0]+l.line:sc[0]-sc[1]+l.line; return m>0; };
  if(l.kind==="total") return (st,sc)=>l.side==="over"?sc[0]+sc[1]>l.line:sc[0]+sc[1]<l.line;
  if(l.kind==="td") return st=>ix>=0&&st[b+S.RTD]+st[b+S.RCTD]>0;
  return st=>{ if(ix<0) return false; const v=statVal(st,b,l.stat); return l.side==="over"?v>l.line:v<l.line; };
}
const jointCache={};
function slipProb(){
  const byG={}; LEGS.forEach(l=>(byG[l.gid]=byG[l.gid]||[]).push(l));
  let joint=1, indep=1, rawProd=1;
  for(const gid in byG){
    const ls=byG[gid], g=gameById(gid);
    let pj;
    if(ls.length===1){ pj=legMarginal(ls[0]).p; }
    else{
      const ck=gid+"#"+N+"#"+ls.map(legKey).join("~")+"#"+g.spread+"#"+g.total+"#"+[...OUT].join(",")+[...IN].join(",");
      if(!(ck in jointCache)){
        const roster=rosterV3(gameInputs(g),TRUST,ctx());
        const r=simOne(g,N,ls.map(l=>legPred(l,roster)));
        const need=(1<<ls.length)-1; let hit=0,tot=0;
        for(let i=0;i<r.N;i++){ tot+=r.wts[i]; if((r.masks[i]&need)===need) hit+=r.wts[i]; }
        let raw=1; ls.forEach(l=>raw*=legMarginal(l).raw);
        jointCache[ck]={sim:hit/tot, rawProd:raw};
      }
      const J=jointCache[ck]; let ratio=1; ls.forEach(l=>{const m=legMarginal(l); ratio*=m.p/Math.max(1e-6,m.raw);});
      pj=Math.min(1,J.sim*ratio);
    }
    joint*=pj; ls.forEach(l=>indep*=legMarginal(l).p);
  }
  return {joint,indep,corr:indep>0?joint/indep-1:0};
}
function slipDec(){ let d=1; LEGS.forEach(l=>{ d*=toDec(l.price)||1/Math.max(.02,legMarginal(l).p); }); return d; }
function renderSlip(){
  const el=$("#tab-slip");
  if(!LEGS.length){ el.innerHTML=`<div class="slip"><div class="sliphead"><h3>Your bet</h3></div>
    <p class="empty">Tap a moneyline or spread in Games, a touchdown row, or an Over/Under button in Props. The slip holds one bet at a time. Each bet type has its own model, and they aren't combined into parlays.</p></div>`; return; }
  const l=LEGS[0], key="sgp:"+legKey(l), typed=store.get(key,"");
  let p=legMarginal(l).p;
  if(l.kind==="td"&&typed!==""&&typed!=null){ const r=RES[leagueOf(l.gid)][l.gid], pl=r&&r.players.find(x=>x.n===l.pn); if(pl) p=tdFinal(pl,+typed); }
  const price=typed!==""&&typed!=null?+typed:l.price, e=price!=null?ev(p,price):null;
  el.innerHTML=`<div class="slip"><div class="sliphead"><h3>${esc(legDesc(l))}</h3>
      <div class="ra"><div class="slipnum">${pct(p,1)}</div><div class="sub n">chance · fair ${fmtOdds(fairAm(p))}</div></div></div>
    <div class="stakebox"><label class="tiny" for="sgp">DraftKings price</label>
      <input type="number" id="sgp" value="${esc(typed)}" placeholder="${l.price!=null?fmtOdds(l.price):"type it"}">
      ${evTag(e)}<button class="pill" id="clearSlip">clear</button></div>
    <p class="empty">${l.kind==="td"?"Typing DraftKings' real price re-blends the chance at that price.":"Check the price in the DraftKings app before betting; the one shown is from the latest snapshot."}</p>
    <div class="stakebox"><label for="stake" class="tiny">UNITS</label><input type="number" id="stake" min="0.25" step="0.25" value="1">
      <button class="logbtn" id="logBet">Log this bet</button></div><p class="empty" id="logMsg"></p></div>`;
  $("#clearSlip").onclick=()=>{LEGS=[];renderSlip();};
  $("#sgp").onchange=ev_=>{store.set(key,ev_.target.value);renderSlip();};
  $("#logBet").onclick=logBet;
}
function toggleLeg(spec){
  const k=legKey(spec), i=LEGS.findIndex(l=>l.key===k);
  if(i>=0) LEGS.splice(i,1); else LEGS=[{...spec,key:k}];     // singles only: each bet type stands on its own
  render(); flashSlip();
}
function flashSlip(){ const b=document.querySelector('nav.bot [data-tab="slip"]'); if(!b) return; b.dataset.count=LEGS.length||""; }
function suggestedCard(){
  if(!suggested||!Array.isArray(suggested.legs)||!suggested.legs.length) return "";
  return `<div class="slip sug"><div class="sliphead"><h3>Claude's card${suggested.label?" · "+esc(suggested.label):""}</h3></div>
    <div class="legs">${suggested.legs.map(l=>`<div class="leg"><span><b>${esc(l.desc||l.name)}</b><span class="tiny"> ${esc(l.team||"")} ${l.price?"· "+fmtOdds(l.price):""}</span></span></div>`).join("")}</div>
    ${suggested.why?`<p class="empty">${esc(suggested.why)}</p>`:""}<div class="stakebox"><button class="logbtn" id="loadSug">Load into slip</button></div></div>`;
}
function loadSuggested(){ if(!suggested) return; LEGS=[];
  suggested.legs.forEach(l=>{ const spec=l.kind?l:null; if(spec){LEGS.push({...spec,key:legKey(spec)});return;}
    for(const g of SL.NFL.games){ if(g.players.some(p=>p.n===l.name)){ const s={kind:"td",gid:g.id,pn:l.name,price:l.price}; LEGS.push({...s,key:legKey(s)}); return; } } });
  showTab("slip"); }
async function logBet(){
  const stake=Math.max(.25,+($("#stake").value||1)), sgp=$("#sgp").value, l0=LEGS[0];
  let joint=legMarginal(l0).p; if(l0.kind==="td"&&sgp!==""){ const r=RES[leagueOf(l0.gid)][l0.gid], pl=r&&r.players.find(x=>x.n===l0.pn); if(pl) joint=tdFinal(pl,+sgp); }
  const dec=sgp!==""?toDec(+sgp):(toDec(l0.price)||1/Math.max(.02,joint));
  const bet={id:"b"+Date.now(), week:slate().label||"", league:SPORT, placed:new Date().toISOString(),
    legs:LEGS.map(l=>{const g=gameById(l.gid); return {kind:l.kind,desc:legDesc(l),name:l.pn||legDesc(l),team:l.pn?(g.players.find(p=>p.n===l.pn)||{}).t:(l.side==="home"?g.home:l.side==="away"?g.away:""),
      game:l.gid,side:l.side||null,line:l.line??null,stat:l.stat||null,price:l.price??null,modelP:+legMarginal(l).p.toFixed(4)};}),
    stake, decimal:+dec.toFixed(3), modelP:+joint.toFixed(4), result:"pending"};
  ledger.bets=[bet].concat(ledger.bets||[]);
  const ok=await saveLedger();
  $("#logMsg").textContent=ok?"Logged. It's under My bets.":"Saved on this device only. The shared ledger wasn't reachable.";
  LEGS=[]; setTimeout(()=>showTab("bets"),700);
}
async function getDb(){ try{ return dbRef||(dbRef=await window.claude?.use?.("db")); }catch(e){ return null; } }
async function saveLedger(){ try{ const db=await getDb(); if(!db) return false;
  await db.doc("ledger/current").set({bets:ledger.bets,updated:new Date().toISOString()}); return true; }catch(e){ return false; } }
async function settleBet(id,result){ const b=(ledger.bets||[]).find(x=>x.id===id); if(!b) return; b.result=result; b.settled=new Date().toISOString(); await saveLedger(); renderBets(); }

/* ------------------------------- bets ----------------------------------- */
function betPL(b){ if(b.result==="win") return b.stake*((b.decimal||2)-1); if(b.result==="loss") return -b.stake; return 0; }
function renderBets(){
  const bets=ledger.bets||[], done=bets.filter(b=>b.result==="win"||b.result==="loss");
  const w=done.filter(b=>b.result==="win").length, l=done.length-w;
  const staked=done.reduce((a,b)=>a+b.stake,0), pl=done.reduce((a,b)=>a+betPL(b),0), roi=staked>0?pl/staked:0;
  const exp=done.reduce((a,b)=>a+b.stake*((b.modelP||0)*(b.decimal||2)-1),0);
  /* closing-line value: did you beat the price the market settled on? Positive CLV over many bets is the best early sign of a real edge. */
  const clvOf=b=>b.close!=null&&b.legs.length===1&&b.decimal?b.decimal/toDec(b.close)-1:null;
  const cl=bets.map(clvOf).filter(x=>x!=null), clv=cl.length?cl.reduce((a,x)=>a+x,0)/cl.length:null;
  $("#tab-bets").innerHTML=`<div class="rec">
      <div class="recbox"><b>${w}–${l}</b><span>record</span></div>
      <div class="recbox"><b class="${pl>=0?"pos":"neg"}">${pl>=0?"+":"−"}${Math.abs(pl).toFixed(2)}</b><span>units</span></div>
      <div class="recbox"><b class="${clv==null?"":clv>=0?"pos":"neg"}">${clv==null?"—":(clv>=0?"+":"−")+Math.abs(100*clv).toFixed(1)+"%"}</b><span>avg CLV${cl.length?` · ${cl.length}`:""}</span></div></div>
    <p class="empty">${done.length<30?`${done.length} settled bets tells you almost nothing about skill; a real 5% edge takes several hundred bets to show up in the record. Closing-line value shows up much sooner. Type the price each bet closed at, and if you're consistently getting better numbers than the close, that's the edge. Model expected value on settled bets: ${exp>=0?"+":"−"}${Math.abs(exp).toFixed(2)}u.`:
      `ROI ${roi>=0?"+":"−"}${Math.abs(100*roi).toFixed(1)}% on ${staked.toFixed(1)} units staked.`}</p>
    <div class="slip"><div class="sliphead"><h3>Bets</h3><span class="sub">${bets.length} logged${bets.some(b=>b.result==="pending")?" · "+bets.filter(b=>b.result==="pending").length+" open":""}</span></div>
      ${bets.length?bets.map(b=>`<div class="betrow"><div class="minw"><div class="bn">${b.legs.map(x=>esc(x.desc||x.name)).join(" + ")}</div>
        <div class="sub">${b.stake}u · ${fmtOdds(b.decimal>=2?Math.round((b.decimal-1)*100):-Math.round(100/(b.decimal-1)))} · model ${pct(b.modelP||0,0)} · ${esc(b.week||"")}${
          b.result!=="pending"?` · <b class="${b.result==="win"?"pos":"neg"}">${b.result.toUpperCase()} ${betPL(b)>=0?"+":"−"}${Math.abs(betPL(b)).toFixed(2)}u</b>`:""}</div></div>
        <div class="settle">${b.legs.length===1?`<input class="closein" data-close="${b.id}" inputmode="numeric" placeholder="close" value="${b.close??""}" aria-label="Closing price">`:""}
          ${b.result==="pending"?`<button class="w" data-win="${b.id}">Won</button><button class="l" data-loss="${b.id}">Lost</button>`:""}</div></div>`).join(""):
        `<p class="empty">Nothing logged yet.</p>`}</div>`;
  $("#tab-bets").querySelectorAll("[data-win]").forEach(b=>b.onclick=()=>settleBet(b.dataset.win,"win"));
  $("#tab-bets").querySelectorAll("[data-loss]").forEach(b=>b.onclick=()=>settleBet(b.dataset.loss,"loss"));
  $("#tab-bets").querySelectorAll("[data-close]").forEach(el=>el.onchange=async()=>{ const b=(ledger.bets||[]).find(x=>x.id===el.dataset.close); if(!b) return;
    b.close=el.value===""?null:+el.value; await saveLedger(); renderBets(); });
}

/* ------------------------------- model ---------------------------------- */
function renderModel(){ $("#tab-model").innerHTML=MODEL_HTML()+notesHTML();
  const kp=$("#kProp"),kt=$("#kTrust");
  const bind=(el,set,lab,fmt,rerun)=>{ if(!el) return; el.oninput=()=>{set(+el.value);$(lab).textContent=fmt(+el.value);}; el.onchange=()=>{ if(rerun){invalidate();runAll();} else render(); }; };
  bind(kp,v=>LAMP=v/100,"#vProp",v=>v+"%"); bind(kt,v=>TRUST=v/100,"#vTrust",v=>v+"%",true);
}
function notesHTML(){
  return `<div class="prose"><h3>What we've learned</h3>${TUNING.notes&&TUNING.notes.length?`<ul>${TUNING.notes.slice(0,10).map(nt=>`<li><b>${esc(nt.week||"")}</b> — ${esc(nt.text||"")}</li>`).join("")}</ul>`:"<p>Nothing logged yet.</p>"}
  ${grades?`<h3>Graded so far</h3><p>Brier <b>${grades.brier}</b> · log loss <b>${grades.logloss}</b> · ${grades.n} graded touchdown picks. ${esc(grades.note||"")}</p>`:""}
  <p class="tiny">Not financial advice. A simulated probability is not a promise, and the house edge on these markets is real.</p></div>`;
}

/* ============================== wiring =================================== */
document.addEventListener("click",e=>{
  const t=e.target.closest("[data-tab]"); if(t&&t.closest('[role="tablist"]')){ showTab(t.dataset.tab); window.scrollTo({top:0}); return; }
  const lg=e.target.closest("[data-leg]"); if(lg&&!e.target.closest("input")){ try{ toggleLeg(JSON.parse(lg.dataset.leg)); }catch(_){} return; }
  const gp=e.target.closest("[data-goprops]"); if(gp){ const [gid]=gp.dataset.goprops.split("|"); PFILT.game=gid; store.set("pfilt",PFILT); showTab("props"); return; }
});
$("#nsims").onchange=e=>{N=+e.target.value; store.set("n",N); runAll();};
N=store.get("n",5000); $("#nsims").value=String(N);
LINES=store.get("lines",{});
showTab(TAB);
runAll();

(async()=>{ try{
  const db=await getDb(); if(!db) return;
  db.doc("ledger/current").onSnapshot(s=>{const d=s&&s.exists?s.data():null; if(d&&Array.isArray(d.bets)){ledger={bets:d.bets}; if(TAB==="bets")renderBets();}},()=>{});
  db.doc("slip/suggested").onSnapshot(s=>{const d=s&&s.exists?s.data():null; if(d&&Array.isArray(d.legs)){suggested=d; if(TAB==="slip")renderSlip();}},()=>{});
  db.doc("lines/current").onSnapshot(s=>{const d=s&&s.exists?s.data():null; if(d&&d.lines){LINES=Object.assign({},d.lines); store.set("lines",LINES); if(TAB==="props")renderProps();}},()=>{});
  db.doc("tuning/current").onSnapshot(s=>{const d=s&&s.exists?s.data():null; if(!d) return;
    TUNING.posBias=d.posBias||{}; TUNING.schemeScale=d.schemeScale??1; TUNING.notes=d.notes||[];
    if(d.propWeight!=null) LAMP=d.propWeight; if(d.usageTrust!=null) TRUST=d.usageTrust;
    invalidate(); runAll();},()=>{});
  const takeSlate=(lg)=>s=>{ const d=s&&s.exists?s.data():null; if(!d||!Array.isArray(d.games)||!d.games.length||!d.engine) return;
    SL[lg]=JSON.parse(JSON.stringify(d)); SRC[lg]="feed"; LEGS=LEGS.filter(l=>leagueOf(l.gid)!==lg); RES[lg]={}; if(SPORT===lg) runAll(); };
  db.doc("slate/current").onSnapshot(takeSlate("NFL"),()=>{});
  db.doc("grades/current").onSnapshot(s=>{const d=s&&s.exists?s.data():null; if(d&&d.brier!=null){grades=d; if(TAB==="model")renderModel();}},()=>{});
}catch(e){} })();
