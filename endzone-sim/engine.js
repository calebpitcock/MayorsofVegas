/* ==========================================================================
   ENGINE v3 — play-level simulation, NFL and college.

   v2 simulated drives: each possession ended in a touchdown, a field goal or
   nothing, and a touchdown was handed to a player by weight. That is enough
   for "who scores" and useless for everything else — it has no yards, no
   receptions, no attempts, no first half.

   v3 plays every snap. Down, distance, field position, clock and score are
   tracked; each play is a run, a dropback (sack / scramble / throw) or a
   kick, and every yard is credited to a named player or to the Field. The
   same simulated games therefore produce the final score, the first half,
   every player's box score and the touchdown scorers, all mutually
   consistent — which is what makes same-game parlays priceable.

   The anchor has not changed: each offense's efficiency is solved so that its
   average points match the market's implied team total. The market decides
   HOW MUCH a team scores; the simulation decides how, when, and through whom.
   ======================================================================== */

/* ------------------------------ seeded RNG ------------------------------ */
function hashStr(s){let h=2166136261>>>0;for(let i=0;i<s.length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return h>>>0;}
function makeRng(seed){
  let a=seed>>>0, spare=0, has=false;
  const u=()=>{a=(a+0x6D2B79F5)|0;let t=Math.imul(a^(a>>>15),1|a);
    t=(t+Math.imul(t^(t>>>7),61|t))^t;return((t^(t>>>14))>>>0)/4294967296;};
  const n=()=>{if(has){has=false;return spare;}let x,y,s;
    do{x=u()*2-1;y=u()*2-1;s=x*x+y*y;}while(!s||s>=1);
    const m=Math.sqrt(-2*Math.log(s)/s);spare=y*m;has=true;return x*m;};
  const gamma=k=>{ if(k<1){const g=gammaGE1(k+1);return g*Math.pow(u()||1e-12,1/k);} return gammaGE1(k); };
  function gammaGE1(k){const d=k-1/3,c=1/Math.sqrt(9*d);
    for(;;){let x,v;do{x=n();v=1+c*x;}while(v<=0);v=v*v*v;const U=u();
      if(U<1-0.0331*x*x*x*x)return d*v; if(Math.log(U)<0.5*x*x+d*(1-v+Math.log(v)))return d*v;}}
  return {u,n,gamma};
}

/* ---------------------------- league rules ------------------------------
   yl = yards to the opponent's goal line (75 = own 25).                   */
const LG={
  NFL:{key:"NFL", passBase:.535, sack:.066, scr:.040, int:.022, acc:1, throwAway:.035,
    T:34.5, incT:6, stT:6, kickTB:.40, tbYl:65, retYl:70, retSD:7,
    xp:.958, two:.48, fgA:6.8, fgB:.112, fgMax:58, puntNet:42.5, puntSD:7.5,
    ot:"nfl", sackAsRush:false, ypcAdj:0, yprAdj:0, catchAdj:0, sigEnv:.03, sigDay:.15, dayMix:.25, dayLo:.60, dayHi:1.67, two0:.07, keyW:true},
  CFB:{key:"CFB", passBase:.42, sack:.063, scr:.055, int:.024, acc:1, throwAway:.04,
    T:30.5, incT:6, stT:6, kickTB:.55, tbYl:75, retYl:73, retSD:8,
    xp:.975, two:.45, fgA:5.4, fgB:.100, fgMax:52, puntNet:39.5, puntSD:8.5,
    ot:"cfb", sackAsRush:true, ypcAdj:.35, yprAdj:1.0, catchAdj:-.015, sigEnv:.04, sigDay:.16, dayMix:.25, dayLo:.60, dayHi:1.67, two0:.06, keyW:false}
};
/* Per-position efficiency defaults. Anything a player row states overrides. */
const POSDEF={
  RB:{ypc:4.3, cat:.77, ypr:7.4, kRun:1.15, kRec:1.05, shift:2},
  WR:{ypc:6.5, cat:.635,ypr:12.9,kRun:.9,  kRec:1.25, shift:0},
  TE:{ypc:3.0, cat:.70, ypr:10.6,kRun:1.2, kRec:1.45, shift:.5},
  QB:{ypc:4.2, cat:.5,  ypr:8,   kRun:1.3, kRec:1.2,  shift:0},
  FLD:{ypc:4.1,cat:.62, ypr:9.8, kRun:1.15,kRec:1.3,  shift:.5}
};
/* The data rates are all-situation averages; the engine re-applies red-zone
   compression and late-down routes on top, which on its own realises ~4% less
   YPC and ~5% fewer catches than the input. These constants undo that. */
const EFFN={ypc:1.04,cat:1.055,ypr:.977};
const ROLE3={RB:{rush:.40,rec:.12}, WR:{rush:.01,rec:.18}, TE:{rush:0,rec:.15}, QB:{rush:.12,rec:0}};
const FIELD_FLOOR3={rush:.03, rec:.07};   // 2025 backtest: listed players were short ~10% on carries, ~4% on targets
const COMMITTEE3=0;   // the Week 2 committee flattening; the 2025 backtest showed it compressed lead backs, so it is off

/* KEYW — key-number correction (NFL only). The simulator produces too few
   3-point finishes (11.2% against ~14.2% in the modern NFL) and too many 5s
   and 7s, because real end-game behaviour (walk-off field goals, missed
   extra points, two-point tries) is richer than the play model. Each simulated
   game is weighted by its final |margin| so the margin distribution matches
   league history; every market — props included — is computed with the same
   weights, so nothing goes out of sync. Targets are 2015-2024 frequencies as
   recalled, not re-derived from data here; weights are capped at 0.6–1.35. */
const KEYW=[0.600,1.178,0.894,1.272,1.034,0.600,1.313,0.867,1.264,0.774,0.870,0.978,0.625,0.834,1.259,0.810,0.906,0.939,0.880,0.921,0.905,1.067,1.080];
/* Stat slots, per player per game. */
const S={PA:0,CMP:1,PY:2,PTD:3,INT:4,RA:5,RY:6,RTD:7,TGT:8,REC:9,RCY:10,RCTD:11,NS:12};
/* Histogram layout: [stat key, offset, size]. Derived stats are computed at record time. */
const HIST={
  passYds:[40,700], passAtt:[0,80], cmp:[0,60], passTD:[0,9], int:[0,7],
  rushYds:[40,380], rushAtt:[0,50], rushTD:[0,6],
  recYds:[15,360], rec:[0,22], tgt:[0,26],
  rrYds:[40,420], prYds:[40,760], anyTD:[0,7]
};
const HKEYS=Object.keys(HIST);

function qbInfo3(g,side){
  const q=g.qb&&(side===g.away?g.qb.away:g.qb.home);
  return {change:!!(q&&q.change), priorGames:(q&&q.priorGames!=null)?q.priorGames:2,
          tier:(q&&q.tier)||0, name:(q&&q.name)||null, why:(q&&q.why)||""};
}
const qbTrust3=q=>q.change?(0.35+0.325*Math.min(2,q.priorGames)):1;

/* ------------------------------- roster ---------------------------------
   `rush` = share of the team's designed carries, `rec` = share of targets.
   Both are shrunk toward a role baseline by `trust`, a scratched player's
   work goes 72% to his position group, backfields are flattened toward each
   other, and the Field keeps a floor share. Same rules the touchdown model
   was graded on, now applied to volume instead of touchdown equity.       */
function rosterV3(g,trust,ctx){
  const L=LG[g.league||"NFL"], tun=ctx.tuning||{}, OUTS=ctx.out||new Set(), TUNEM=ctx.tune||{};
  const all=[];
  for(const side of [g.away,g.home]){
    const qi=qbInfo3(g,side), tSide=trust*qbTrust3(qi), tier=qi.tier;
    const live=g.players.filter(p=>p.t===side&&!p.out&&!OUTS.has(p.n));
    const gone=g.players.filter(p=>p.t===side&&(p.out||OUTS.has(p.n)));
    const freed={rush:0,rec:0}; gone.forEach(p=>{freed.rush+=p.rush||0;freed.rec+=p.rec||0;});
    /* A quarterback change makes the TARGET tree less certain, so target shares
       shrink toward a positional baseline. Carries are left alone:
       shrinking every back toward a fixed 40% role inflated backups and cut the
       starter (the backtest and the Week 3 Giants both showed it). */
    const rows=live.map(p=>{
      const role=ROLE3[p.pos]||{rush:0,rec:0};
      let rush=p.rush||0, rec=tSide*(p.rec||0)+(1-tSide)*role.rec;
      if(!(p.rush>0)) rush=0; if(!(p.rec>0)) rec=0;          // no invented roles
      for(const k of ["rush","rec"]){
        if(freed[k]<=0) continue;
        const pool=gone.filter(q=>(q[k]||0)>0).map(q=>q.pos);
        const peers=pool.length?live.filter(q=>pool.includes(q.pos)&&(q[k]||0)>0):[];
        const den=peers.reduce((a,q)=>a+(q[k]||0),0);
        if(peers.includes(p)&&den>0){const add=freed[k]*.72*((p[k]||0)/den); if(k==="rush")rush+=add; else rec+=add;}
      }
      return {p, rush:rush*(1-tier*.02), rec:rec*(1+tier*.05)};
    });
    const backs=rows.filter(r=>r.p.pos==="RB").sort((a,b)=>b.rush-a.rush);
    if(backs.length>=2&&backs[1].rush>=.15){const mid=(backs[0].rush+backs[1].rush)/2;
      backs[0].rush+=COMMITTEE3*(mid-backs[0].rush); backs[1].rush+=COMMITTEE3*(mid-backs[1].rush);}
    let sr=rows.reduce((a,r)=>a+r.rush,0), sc=rows.reduce((a,r)=>a+r.rec,0);
    const capR=1-FIELD_FLOOR3.rush, capC=1-FIELD_FLOOR3.rec;
    if(sr>capR){const k=capR/sr;rows.forEach(r=>r.rush*=k);sr=capR;}
    if(sc>capC){const k=capC/sc;rows.forEach(r=>r.rec*=k);sc=capC;}
    let hasQB=false;
    rows.forEach(({p,rush,rec})=>{
      const d=POSDEF[p.pos]||POSDEF.WR, t=TUNEM[p.n]||{};
      const bias=(tun.posBias&&tun.posBias[p.pos])||1;   // touchdown calibration lives in the goal-line weight
      if(p.pos==="QB"&&!hasQB) hasQB=true;
      all.push({...p, side, field:false, isQB:p.pos==="QB",
        wRun:rush, wTgt:rec, gl:(p.gl??t.gl??1)*bias, deep:p.deep??t.deep??1,
        /* league adjustments apply only to the positional defaults; measured rates are already in that league's units */
        ypc:(p.ypc??(d.ypc+L.ypcAdj))*EFFN.ypc, cat:Math.min(.95,(p.cat??(d.cat+L.catchAdj))*EFFN.cat), ypr:(p.ypr??(d.ypr+L.yprAdj))*EFFN.ypr,
        kRun:d.kRun, kRec:d.kRec, shift:d.shift,
        qacc:1+((p.acc??1)-1)*.5, qint:p.int??L.int, qsack:p.sack??L.sack, qscr:p.scr??L.scr, qdrop:p.share??1});
    });
    const fd=POSDEF.FLD;
    all.push({n:"Field — rest of "+side, t:side, side, pos:"FLD", field:true, conf:"high",
      wRun:Math.max(0,1-sr), wTgt:Math.max(0,1-sc), gl:1, deep:1,
      ypc:fd.ypc+L.ypcAdj, cat:fd.cat+L.catchAdj, ypr:fd.ypr+L.yprAdj, kRun:fd.kRun, kRec:fd.kRec, shift:fd.shift});
    if(!hasQB) all.push({n:"QB — "+side, t:side, side, pos:"QB", field:true, hidden:true, isQB:true,
      wRun:0, wTgt:0, gl:1, deep:1, ypc:4.2+L.ypcAdj, cat:.5, ypr:8, kRun:1.3, kRec:1.2, shift:0,
      qacc:1, qint:L.int, qsack:L.sack, qscr:L.scr});
  }
  return all;
}

/* -------------------------- the game simulator --------------------------
   opts: N, trust, neutral (league-average scheme), k:[kAway,kHome] offense
   multipliers (from calibrate), seed, hist (collect histograms),
   legs (array of predicates; returns a per-sim bitmask for parlays).     */
function simGameV3(g,opts,ctx){
  const L=LG[g.league||"NFL"], N=opts.N, R=makeRng(opts.seed>>>0);
  const ROS=rosterV3(g,opts.trust,ctx), n=ROS.length;
  const sideIx=[[],[]], qbIx=[-1,-1];
  ROS.forEach((p,i)=>{const s=p.side===g.home?1:0; sideIx[s].push(i); if(p.isQB&&qbIx[s]<0) qbIx[s]=i;});
  const tun=ctx.tuning||{}, SS=tun.schemeScale??1;
  /* matchup layer (v3.1): the defense each side faces, from data (g.defp.away = the defense the AWAY offense faces) */
  const OPP=ctx.opp??1, SCH=ctx.scheme||"data";
  const dp=[(g.defp&&g.defp.away)||null,(g.defp&&g.defp.home)||null];
  const schemeFrom=(i,team)=>{
    if(opts.neutral||SCH==="off") return Object.assign({},LEAGUE);
    if(SCH==="data"&&dp[i]&&dp[i].man!=null) return Object.assign({},LEAGUE,{man:dp[i].man,blitz:dp[i].blitz??LEAGUE.blitz,mofc:dp[i].mofc??LEAGUE.mofc,src:"data",note:null});
    return SCH==="data"?Object.assign({},LEAGUE):schemeFor(team); };
  const defFor=[schemeFrom(0,g.home), schemeFrom(1,g.away)];
  const mix=[mixMult(defFor[0]),mixMult(defFor[1])];
  const qbI=[qbInfo3(g,g.away),qbInfo3(g,g.home)];
  const soft=g.soft||{away:{run:.5,pass:.5},home:{run:.5,pass:.5}};
  const sf=[soft.away||{run:.5,pass:.5}, soft.home||{run:.5,pass:.5}];
  /* scheme multipliers per player: base target share, red-zone share, explosive tail */
  const smB=new Float64Array(n), smRZ=new Float64Array(n), smEX=new Float64Array(n), smXR=new Float64Array(n);
  ROS.forEach((p,i)=>{const s=p.side===g.home?1:0; const m=schemeMult(p,defFor[s]);
    smB[i]=1+(m.base-1)*SS; smRZ[i]=1+(m.rz-1)*SS; smEX[i]=1+(m.ex-1)*SS; smXR[i]=1+(m.exRun-1)*SS;});
  const sig=Float64Array.from(ROS,p=>(p.field?.12:(p.pos==="RB"||p.pos==="QB"?.26:.30))*(qbI[p.side===g.home?1:0].change?1.3:1));
  const K=opts.k||[1,1];
  const pace=[(g.pace&&g.pace.away)||1,(g.pace&&g.pace.home)||1];
  const pBase=[(g.passRate&&g.passRate.away)??L.passBase,(g.passRate&&g.passRate.home)??L.passBase];
  const runEff=[1+(sf[0].run-.5)*.35, 1+(sf[1].run-.5)*.35].map((x,i)=>x*Math.sqrt(mix[i].rush)*(OPP&&dp[i]?Math.pow(dp[i].ypc,.6):1));
  const passEff=[1+(sf[0].pass-.5)*.35, 1+(sf[1].pass-.5)*.35].map((x,i)=>x*(OPP&&dp[i]?Math.pow(dp[i].ypt,.6):1));
  /* where this defense lets targets and receiving touchdowns go, by position */
  /* Where a defense allowed its touchdowns (by position, run vs pass) is not used: split-half reliability over
     2016-25 was ~0 (audit/dvp.py), so it only added noise to touchdown odds. ctx.tdloc=1 restores it for tests. */
  const TDLOC=ctx.tdloc??0;
  const oppT=new Float64Array(n).fill(1), oppRZ=new Float64Array(n).fill(1);
  if(OPP) ROS.forEach((p,i)=>{ const d=dp[p.side===g.home?1:0]; if(!d||p.field||p.pos==="QB") return;
    oppT[i]=Math.pow(d.tgt[p.pos]??1,.7); if(TDLOC) oppRZ[i]=Math.pow(d.tdpos[p.pos]??1,.5); });
  const rzRunLean=[OPP&&TDLOC&&dp[0]?(1-dp[0].rtd)*.25:0, OPP&&TDLOC&&dp[1]?(1-dp[1].rtd)*.25:0];
  /* coaching: each head coach's fourth-down aggressiveness as a log-odds shift on the discretionary go rates
     (g.agg, from nfl_build.coach_agg), and wind, which trims passing at outdoor games (g.wind mph; audit: about
     -2 points of pass rate at 15-20 mph and -3 above 20, beyond what the lower total already says) */
  const AGG=[(g.agg&&g.agg.away)||0,(g.agg&&g.agg.home)||0];
  const goP=(p,ball)=>{const z=Math.log(p/(1-p))+AGG[ball];return 1/(1+Math.exp(-z));};
  const windAdj=(g.wind>10&&g.roof!=="dome"&&g.roof!=="closed")?-Math.min(.04,.0025*(g.wind-10)):0;
  const pressure=[1+(defFor[0].blitz-LEAGUE.blitz)*.9, 1+(defFor[1].blitz-LEAGUE.blitz)*.9];
  const passLean0=[(sf[0].pass-sf[0].run)*.10+qbI[0].tier*.02,(sf[1].pass-sf[1].run)*.10+qbI[1].tier*.02];

  /* live state */
  const live=g.live||{status:"pre"}; const post=live.status==="post", inPlay=live.status==="in";
  const t0=post?0:(inPlay?Math.max(20,live.secs||1800):3600);
  const sc0=(inPlay||post)?[live.as||0,live.hs||0]:[0,0];
  const already=new Set(live.scored||[]);

  /* outputs */
  const H=opts.hist!==false;
  const hist=H?ROS.map(()=>{const o={};for(const k of HKEYS)o[k]=new Float64Array(HIST[k][1]);return o;}):null;
  const sum=new Float64Array(n*S.NS);
  const G={margin:new Float64Array(161), total:new Float64Array(141), pts:[new Float64Array(90),new Float64Array(90)],
    h1margin:new Float64Array(121), h1total:new Float64Array(91), h1pts:[new Float64Array(70),new Float64Array(70)],
    win:[0,0], tie:0, ot:0, h1win:[0,0], h1tie:0, W:0, h1W:0, raw:new Float64Array(161)};
  const firstTD=new Float64Array(n+2);  // n = defense/special teams away, n+1 home
  const legs=opts.legs||null, masks=legs?new Uint32Array(N):null, wts=legs?new Float32Array(N):null;
  const diag={plays:[0,0],passAtt:[0,0],rushAtt:[0,0],sacks:[0,0],punts:[0,0],fga:[0,0],fgm:[0,0],td:[0,0],
    rzTrips:[0,0],rzTD:[0,0],t3n:[0,0,0,0],t3c:[0,0,0,0],t3cur:-1,drives:[0,0],third:[0,0],thirdConv:[0,0],fourthGo:[0,0],to:[0,0],ptsSum:[0,0],dstTD:[0,0]};

  /* per-sim scratch */
  const st=new Int16Array(n*S.NS);
  const wRun=new Float64Array(n), wRZRun=new Float64Array(n), wTgt=new Float64Array(n), wRZTgt=new Float64Array(n);
  const kSim=[1,1];

  let w=1;
  function put(h,key,v){const hk=HIST[key];h[key][v+hk[0]<0?0:(v+hk[0]>=hk[1]?hk[1]-1:v+hk[0])]+=w;}
  function pick(ixs,w){let s=0;for(const i of ixs)s+=w[i];if(s<=0)return ixs[ixs.length-1];
    let x=R.u()*s;for(const i of ixs){x-=w[i];if(x<=0)return i;}return ixs[ixs.length-1];}
  const fgProb=d=>1/(1+Math.exp(-(L.fgA-L.fgB*d)));

  let firstPick=-1, inOTgame=false;
  let t,half,sc,off,yl,down,togo,h1,gameOver,firstDone,inOT,otDone=[0,0],rzFlag,guardHits=0;

  function kickoff(recv){
    if(gameOver) return;
    t-=L.stT; off=recv; down=1; togo=10; rzFlag=false;
    if(R.u()<.004){ /* return touchdown */ tdScored(recv,-1,true); endPoss(recv); kickoff(1-recv); return; }
    yl=R.u()<L.kickTB?L.tbYl:Math.max(40,Math.min(92,Math.round(L.retYl+R.n()*L.retSD)));
    diag.drives[off]++;
  }
  function turnover(newOff,newYl){ if(gameOver) return; off=newOff; yl=Math.max(1,Math.min(99,newYl)); down=1; togo=Math.min(10,yl); rzFlag=false; diag.drives[off]++; }
  /* a possession has ended; in NFL overtime, the game ends once both teams have had the ball and someone leads */
  function endPoss(side){ if(inOT&&L.ot==="nfl"){ otDone[side]++; if(otDone[0]>=1&&otDone[1]>=1&&sc[0]!==sc[1]) gameOver=true; } }
  function addPts(side,p){ sc[side]+=p; }
  function tdScored(side,pi,dst){
    addPts(side,6); diag.td[side]++;
    if(dst) diag.dstTD[side]++;
    if(!firstDone){firstDone=true; firstPick=pi>=0?pi:(n+side);}
    /* try */
    const d=sc[side]-sc[1-side], late=half===2&&t<900;
    let goTwo=R.u()<L.two0;
    if(late&&(d===-2||d===-5||d===-10||d===1||d===5||d===-9||d===-12)) goTwo=true;
    if(inOT&&L.ot==="cfb"&&otPeriod>=2) goTwo=true;
    if(goTwo){ if(R.u()<L.two*Math.sqrt(kSim[side])) addPts(side,2); }
    else if(R.u()<L.xp) addPts(side,1);
    rzFlag=false;
  }
  let otPeriod=0;

  function runPlay(ball){ /* returns yards gained */
    const ix=sideIx[ball];
    const rz=yl<=10;
    const pi=pick(ix,rz?wRZRun:wRun), p=ROS[pi];
    const b=pi*S.NS;
    st[b+S.RA]++;
    if(R.u()<.0072){ /* fumble lost */ st[b+S.RA]+=0; return {fum:true,pi,y:Math.round(R.u()*4)}; }
    let y;
    const mean=p.ypc*kSim[ball]*runEff[ball];
    if(R.u()<.105) y=-(1+((R.u()*4)|0));
    else{
      const comp=yl<12?Math.pow(yl/12,.6):1;
      const kk=p.kRun/Math.pow(p.deep*smXR[pi],.6);
      const m=((mean+.105*2.5)/.895)*comp;
      y=Math.round(R.gamma(kk)*m/kk);
    }
    if(y>=yl) y=yl;
    st[b+S.RY]+=y;
    return {pi,y,run:true};
  }
  function passPlay(ball){
    const qi=qbIx[ball], q=ROS[qi], qb=qi*S.NS, k=kSim[ball];
    const sackP=q.qsack*pressure[ball]/Math.sqrt(k);
    const r=R.u();
    if(r<sackP){
      const y=-Math.round(3+R.gamma(2)*2);
      diag.sacks[ball]++;
      if(L.sackAsRush){st[qb+S.RA]++; st[qb+S.RY]+=y;}
      if(R.u()<.075) return {fum:true,sack:true,y:y};
      return {y,sack:true};
    }
    if(r<sackP+q.qscr){
      let y=Math.round(R.gamma(1.4)*(7.2*k/1.4)); if(y>=yl)y=yl;
      st[qb+S.RA]++; st[qb+S.RY]+=y;
      return {y,pi:qi,run:true,scr:true};
    }
    /* throw */
    st[qb+S.PA]++;
    if(R.u()<L.throwAway) return {inc:true,ti:-1};     // thrown away: an attempt, nobody's target
    const rz=yl<=15;
    const ti=pick(sideIx[ball],rz?wRZTgt:wTgt), p=ROS[ti], tb=ti*S.NS;
    st[tb+S.TGT]++;
    const intP=q.qint/Math.sqrt(k)*(rz?1.15:1);
    if(R.u()<intP){ st[qb+S.INT]++; return {int:true,ti,air:Math.round(4+R.gamma(1.5)*6)}; }
    const rzc=yl<20?(.78+.22*yl/20):1;
    const late=down>=3&&togo>=3;             // routes are run past the sticks on third and long
    const cp=Math.min(.93,p.cat*q.qacc*L.acc*(1+(k*passEff[ball]-1)*.45)*rzc*(late?(togo<=6?1.07:1-.006*Math.min(9,togo-6)):1));
    if(R.u()>=cp) return {inc:true,ti};
    const kk=p.kRec/Math.pow(p.deep*(smEX[ti]/Math.max(.5,smB[ti]))*Math.sqrt(mix[ball].explosive),.7);
    const m=p.ypr*k*passEff[ball]+p.shift+(late?.62*Math.min(15,togo):0);
    let y=Math.round(R.gamma(kk)*m/kk-p.shift);
    if(late&&y<togo&&R.u()<.30) y=togo;      // the sticks: receivers are coached to them
    if(y>=yl) y=yl;
    st[qb+S.CMP]++; st[qb+S.PY]+=y; st[tb+S.REC]++; st[tb+S.RCY]+=y;
    if(R.u()<.0055) return {fum:true,pi:ti,y,cmp:true};
    return {y,pi:ti,ti,cmp:true};
  }

  function passProb(ball){
    const d=sc[ball]-sc[1-ball], gf=Math.max(0,Math.min(1,t/3600));
    let p=pBase[ball]+passLean0[ball]+windAdj;
    if(down===1) p-=.03;
    else if(down===2){ if(togo>=8)p+=.07; else if(togo<=3)p-=.12; }
    else if(down>=3){ if(togo>=5)p+=.30; else if(togo>=3)p+=.12; else p-=.18; }
    if(yl<=3) p-=.15;
    if(yl<=10) p+=rzRunLean[ball];
    const lean=-d*(0.010+0.032*(1-gf)*(1-gf));
    p+=Math.max(-.30,Math.min(.36,lean));
    const hl=half===1?t-1800:t;
    if(hl<=120&&(half===1||d<=0)) p+=.25;
    return Math.max(.08,Math.min(.95,p));
  }
  function tempo(ball){
    const d=sc[ball]-sc[1-ball], hl=half===1?t-1800:t;
    if(inOT) return .8;
    if(hl<=120&&(half===1||d<=0)) return .42;
    if(half===2&&t<600){ if(d<0) return .72-.25*(1-t/600); if(d>0) return 1.2; }
    return 1;
  }

  const scores0=[0,0];
  for(let s=0;s<N;s++){
    st.fill(0);
    /* per-sim draws: game environment (shared), each offense's day, each player's share */
    const env=Math.exp(L.sigEnv*R.n()-L.sigEnv*L.sigEnv/2);
    /* each offense's day: a scale mixture — most days are close to form, some are not.
       This gives the peaked centre and fat tails real margins have. */
    for(let sd=0;sd<2;sd++){ const sg=R.u()<L.dayMix?L.sigDay*L.dayHi:L.sigDay*L.dayLo; kSim[sd]=K[sd]*env*Math.exp(sg*R.n()-sg*sg/2); }
    for(let i=0;i<n;i++){
      const p=ROS[i], sh=Math.exp(sig[i]*R.n()-sig[i]*sig[i]/2);
      wRun[i]=p.wRun*sh; wRZRun[i]=p.wRun*p.gl*sh;
      wTgt[i]=p.wTgt*sh*smB[i]*oppT[i]; wRZTgt[i]=p.wTgt*p.gl*sh*smRZ[i]*oppT[i]*oppRZ[i];
    }
    t=t0; half=t>1800?1:2; sc=[sc0[0],sc0[1]]; h1=null;
    gameOver=post; firstDone=inPlay||post; firstPick=-1; inOT=false; otDone=[0,0]; otPeriod=0;
    const recv1=R.u()<.5?0:1; inOTgame=false;
    if(!post){
      if(t>=3600) kickoff(recv1);
      else { off=R.u()<.5?0:1; yl=75; down=1; togo=10; rzFlag=false; }
    }
    let guard=0;
    while(!gameOver&&guard++<400){
      /* half and game boundaries */
      if(half===1&&t<=1800){ h1=[sc[0],sc[1]]; half=2; t=1800; kickoff(1-recv1); continue; }
      if(!inOT&&half===2&&t<=0){
        if(sc[0]!==sc[1]) break;
        inOTgame=true;
        if(L.ot==="nfl"){ inOT=true; t=600; otDone=[0,0]; kickoff(R.u()<.5?0:1); continue; }
        /* college overtime: alternate possessions from the 25 until someone leads after a pair */
        cfbOT(); break;
      }
      if(inOT&&t<=0){ break; }  // NFL regular-season tie

      const ball=off, d=sc[ball]-sc[1-ball], hl=half===1?t-1800:t;
      /* victory formation */
      if(!inOT&&half===2&&d>0&&t<=40*(5-down)-8){ t=0; continue; }
      if(!rzFlag&&yl<=20){rzFlag=true;diag.rzTrips[ball]++;}
      const fgDist=yl+17;
      /* last-second field goal */
      if(hl<=12&&fgDist<=L.fgMax+2&&(half===1||(d>=-3&&d<=0))){ attemptFG(ball,fgDist); continue; }
      /* fourth down */
      if(down===4){
        const late=half===2&&t<420, needTD=late&&d<-3, needAny=late&&d<0;
        let go=false;
        if(inOT&&otDone[1-ball]>=1&&d<0) go=!(d>=-3&&fgDist<=L.fgMax);
        else if(needTD&&yl<=75) go=true;
        else if(needAny&&fgDist>L.fgMax&&yl<=80) go=true;
        else if(late&&d>0&&yl>40) go=false;
        else if(togo<=1&&yl<=72) go=R.u()<goP(yl<=50?.90:.56,ball);
        else if(togo<=2&&yl<=50) go=R.u()<goP(.60,ball);
        else if(yl<=4&&togo<=4) go=R.u()<goP(.40,ball);
        else if(togo<=4&&fgDist>L.fgMax&&yl<=48) go=R.u()<goP(.55,ball);
        else if(togo<=3&&yl<=30) go=R.u()<goP(.30,ball);
        if(go) diag.fourthGo[ball]++;
        if(!go){
          if(fgDist<=L.fgMax&&!(late&&d<-3)){ attemptFG(ball,fgDist); continue; }
          punt(ball); continue;
        }
      }
      if(down===3){diag.third[ball]++; const b3=togo<=2?0:togo<=6?1:togo<=9?2:3; diag.t3n[b3]++; diag.t3cur=b3;} else diag.t3cur=-1;
      /* scrimmage play */
      const pass=R.u()<passProb(ball);
      const res=pass?passPlay(ball):runPlay(ball);
      diag.plays[ball]++; if(pass&&!res.sack&&!res.scr&&!res.run) diag.passAtt[ball]++; else if(!pass||res.scr) diag.rushAtt[ball]++;
      t-=res.inc?L.incT:L.T*pace[ball]*tempo(ball);
      if(res.int){
        diag.to[ball]++;
        if(R.u()<.055){ turnoverTD(1-ball); continue; }
        endPoss(ball);
        const spot=yl-res.air;               // where the ball was caught, offense's frame
        if(spot<=0) turnover(1-ball,80); else turnover(1-ball,100-spot-Math.round(4+R.gamma(1.2)*5));
        continue;
      }
      if(res.fum){
        diag.to[ball]++;
        const ny=yl-(res.y||0);
        if(R.u()<.04){ turnoverTD(1-ball); continue; }
        endPoss(ball);
        if(ny<=0){ turnover(1-ball,80); continue; }
        turnover(1-ball,100-ny); continue;
      }
      if(res.inc){ advanceDown(ball,0); continue; }
      const y=res.y;
      if(y>=yl){ /* touchdown */
        if(res.pi!=null){ const b=res.pi*S.NS;
          if(res.run) st[b+S.RTD]++; else { st[b+S.RCTD]++; st[qbIx[ball]*S.NS+S.PTD]++; } }
        diag.rzTD[ball]+=rzFlag?1:0;
        tdScored(ball,res.pi!=null?res.pi:-1,false);
        endPoss(ball); kickoff(1-ball);
        continue;
      }
      yl-=y;
      if(yl>=100){ /* safety */ addPts(1-ball,2); endPoss(ball); t-=L.stT; turnover(1-ball,58); continue; }
      advanceDown(ball,y);
    }
    if(guard>=400) guardHits++;
    if(h1==null) h1=[-1,-1];

    /* ---------- record ---------- */
    const m=sc[1]-sc[0], tot=sc[0]+sc[1];
    /* key-number reweighting (NFL): see KEYW */
    w=(L.keyW&&!inPlay&&!post)?(KEYW[Math.min(KEYW.length-1,Math.abs(m))]):1;
    G.W+=w; G.raw[Math.max(0,Math.min(160,m+80))]++;
    G.margin[Math.max(0,Math.min(160,m+80))]+=w; G.total[Math.min(140,tot)]+=w;
    G.pts[0][Math.min(89,sc[0])]+=w; G.pts[1][Math.min(89,sc[1])]+=w;
    if(m>0)G.win[1]+=w; else if(m<0)G.win[0]+=w; else G.tie+=w;
    if(inOTgame) G.ot+=w;
    if(firstPick>=0) firstTD[firstPick]+=w;
    if(h1[0]>=0){const hm=h1[1]-h1[0];G.h1W+=w;G.h1margin[Math.max(0,Math.min(120,hm+60))]+=w;G.h1total[Math.min(90,h1[0]+h1[1])]+=w;
      G.h1pts[0][Math.min(69,h1[0])]+=w;G.h1pts[1][Math.min(69,h1[1])]+=w;
      if(hm>0)G.h1win[1]+=w; else if(hm<0)G.h1win[0]+=w; else G.h1tie+=w;}
    diag.ptsSum[0]+=sc[0]*w; diag.ptsSum[1]+=sc[1]*w;
    for(let i=0;i<n;i++){
      const b=i*S.NS;
      const td=st[b+S.RTD]+st[b+S.RCTD]+(already.has(ROS[i].n)?1:0);
      for(let k=0;k<S.NS;k++) sum[b+k]+=st[b+k]*w;
      if(H){ const h=hist[i];
        if(ROS[i].isQB){ put(h,"passYds",st[b+S.PY]); put(h,"passAtt",st[b+S.PA]); put(h,"cmp",st[b+S.CMP]);
          put(h,"passTD",st[b+S.PTD]); put(h,"int",st[b+S.INT]); put(h,"prYds",st[b+S.PY]+st[b+S.RY]); }
        put(h,"rushYds",st[b+S.RY]); put(h,"rushAtt",st[b+S.RA]); put(h,"rushTD",st[b+S.RTD]);
        put(h,"recYds",st[b+S.RCY]); put(h,"rec",st[b+S.REC]); put(h,"tgt",st[b+S.TGT]);
        put(h,"rrYds",st[b+S.RY]+st[b+S.RCY]); put(h,"anyTD",td);
      }
    }
    if(legs){ let mk=0; for(let j=0;j<legs.length;j++) if(legs[j](st,sc,h1,ROS)) mk|=(1<<j); masks[s]=mk; wts[s]=w; }
  }

  /* ---- helpers that need closure state (hoisted function declarations) ---- */
  function advanceDown(ball,y){
    if(y>=togo){ if(down===3){diag.thirdConv[ball]++; if(diag.t3cur>=0)diag.t3c[diag.t3cur]++;} down=1; togo=Math.min(10,yl); }
    else { down++; togo-=y; if(down>4){ endPoss(ball); turnover(1-ball,100-yl); } }
  }
  function attemptFG(ball,dist){
    t-=L.stT; diag.fga[ball]++;
    if(R.u()<Math.min(.995,fgProb(dist)*Math.pow(kSim[ball],.12))){ diag.fgm[ball]++; addPts(ball,3); endPoss(ball); kickoff(1-ball); }
    else { endPoss(ball); turnover(1-ball,Math.min(80,100-(yl+7))); }
  }
  function punt(ball){
    t-=L.stT; diag.punts[ball]++;
    const net=Math.round(L.puntNet+R.n()*L.puntSD);
    const land=yl-net;
    endPoss(ball); turnover(1-ball,land<=0?80:100-land);
  }
  function turnoverTD(side){ diag.dstTD[side]++; addPts(side,6); diag.td[side]++;
    if(!firstDone){firstDone=true;firstPick=n+side;}
    if(R.u()<L.xp)addPts(side,1);
    endPoss(1-side); kickoff(1-side); }
  function cfbOT(){
    inOT=true;
    for(otPeriod=1;otPeriod<30;otPeriod++){
      const first=R.u()<.5?0:1;
      for(const side of [first,1-first]){
        if(otPeriod>=3){ if(R.u()<L.two*Math.sqrt(kSim[side]))addPts(side,2); continue; }
        off=side; yl=25; down=1; togo=10; let g2=0;
        while(g2++<40){
          const d=sc[side]-sc[1-side];
          if(down===4){ const fd=yl+17;
            if(fd<=L.fgMax&&!(side!==first&&d<-3)){ if(R.u()<fgProb(fd))addPts(side,3); break; }
          }
          const pass=R.u()<passProb(side);
          const res=pass?passPlay(side):runPlay(side);
          if(res.int||res.fum) break;
          if(res.inc){ down++; if(down>4)break; continue; }
          if(res.y>=yl){ if(res.pi!=null){const b=res.pi*S.NS; if(res.run)st[b+S.RTD]++; else {st[b+S.RCTD]++; st[qbIx[side]*S.NS+S.PTD]++;}}
            tdScored(side,res.pi!=null?res.pi:-1,false); break; }
          yl-=res.y; if(yl>=100)break;
          if(res.y>=togo){down=1;togo=Math.min(10,yl);} else {down++;togo-=res.y; if(down>4)break;}
        }
      }
      if(sc[0]!==sc[1]) return;
    }
  }

  /* ------------------------------ summary ------------------------------ */
  const WT=G.W||N;
  const players=ROS.map((p,i)=>{
    const b=i*S.NS, o={...p, mean:{}}; const keys=["PA","CMP","PY","PTD","INT","RA","RY","RTD","TGT","REC","RCY","RCTD"];
    keys.forEach(k=>o.mean[k]=sum[b+S[k]]/WT);
    if(H){ o.hist=hist[i]; o.pModel=1-hist[i].anyTD[0]/WT; o.p2=1-(hist[i].anyTD[0]+hist[i].anyTD[1])/WT; }
    o.pFirst=firstTD[i]/WT; o.idx=i;
    o.sm={rz:smRZ[i],ex:smEX[i],base:smB[i]};
    return o;
  });
  return {gid:g.id, league:L.key, N, W:WT, players, G, masks, wts, firstDST:[firstTD[n]/WT,firstTD[n+1]/WT],
    guardHits, ptsA:diag.ptsSum[0]/WT, ptsH:diag.ptsSum[1]/WT, diag, def:{away:defFor[0],home:defFor[1]},
    qb:{away:qbI[0],home:qbI[1]}, k:K.slice()};
}

/* Solve each offense's efficiency so its mean points match the market's
   implied team total. This is the invariant that stops scheme, quarterback
   and usage layers from inflating scoring: they can only move who scores. */
function impliedTotals(g){ return {home:(g.total-g.spread)/2, away:(g.total+g.spread)/2}; }
/* The value x where P(v > x) = P(v < x): what a book's line should sit at. */
function balancePoint(h,off){
  let tot=0; for(const c of h) tot+=c; if(!tot) return 0;
  let below=0;
  for(let i=0;i<h.length;i++){
    const at=h[i], above=tot-below-at;
    if(below+at>=above){                       // the balance point lies within bin i
      /* under at x=i-.5: below ; over: above+at.  at x=i+.5: under below+at, over above */
      const lo=(above+at)-below, hi=above-(below+at);   // over-minus-under at the two edges
      return (i-off-.5)+(lo/(lo-hi||1));
    }
    below+=at;
  }
  return h.length-1-off;
}
function calibrateV3(g,ctx,opts={}){
  /* Books set the spread and total near the MEDIAN outcome, not the mean —
     scoring is right-skewed, so matching the mean would make every under look
     like value. Stage 1 matches the implied team means; stage 2 shifts those
     targets by the simulated mean-minus-median gap so that the model's own fair
     spread and fair total land on the book's numbers. Same seed every pass, so
     points as a function of k is smooth and the secant converges. */
  let k=(opts.k0||[1,1]).slice(), prev=[null,null];
  const base=hashStr(g.id+"|cal"), n0=opts.N||5000;
  const it=impliedTotals(g);
  let tgt=[Math.max(3,it.away),Math.max(3,it.home)], res=null;
  const step=()=>{
    res=simGameV3({...g,live:{status:"pre"}},{N:n0,trust:opts.trust??.85,k,seed:base,hist:false},ctx);
    const pts=[Math.max(2,res.ptsA),Math.max(2,res.ptsH)], nk=k.slice();
    for(let s=0;s<2;s++){
      let e=1.7;
      if(prev[s]&&Math.abs(Math.log(k[s]/prev[s].k))>.003) e=Math.max(.9,Math.min(3,Math.log(pts[s]/prev[s].p)/Math.log(k[s]/prev[s].k)));
      prev[s]={k:k[s],p:pts[s]};
      nk[s]=Math.max(.4,Math.min(2.6,k[s]*Math.pow(tgt[s]/pts[s],1/e)));
    }
    k=nk;
  };
  for(let r=0;r<(opts.iters||4);r++) step();
  /* stage 2: put the book's own lines at the balance point — at L=-spread the
     home side should win as often as it fails (pushes aside), and the same for
     the total. a moves both offenses together (the total), b moves them apart
     (the margin). Secant per axis, first step from a density estimate. */
  const L=-g.spread, T0=g.total;
  const bal=(h,off,x)=>{let o=0,u=0;for(let i=0;i<h.length;i++){const v=i-off;if(v>x)o+=h[i];else if(v<x)u+=h[i];}const W=o+u;return W?(o-u)/(o+u+1e-9):0;};
  let A=Math.log(Math.sqrt(k[0]*k[1])), B=Math.log(Math.sqrt(k[1]/k[0])), pf=null, pg=null;
  for(let r=0;r<(opts.iters2||6);r++){
    res=simGameV3({...g,live:{status:"pre"}},{N:n0,trust:opts.trust??.85,k:[Math.exp(A-B),Math.exp(A+B)],seed:base,hist:false},ctx);
    const f=bal(res.G.margin,80,L), gg=bal(res.G.total,0,T0);
    let sf=4.2, sg=3.9;
    if(pf&&Math.abs(B-pf.x)>1e-4){const e=(f-pf.v)/(B-pf.x); if(e>.5&&e<20) sf=e;}
    if(pg&&Math.abs(A-pg.x)>1e-4){const e=(gg-pg.v)/(A-pg.x); if(e>.5&&e<20) sg=e;}
    pf={x:B,v:f}; pg={x:A,v:gg};
    if(Math.abs(f)<.004&&Math.abs(gg)<.004) break;
    B-=Math.max(-.08,Math.min(.08,f/sf)); A-=Math.max(-.08,Math.min(.08,gg/sg));
  }
  k=[Math.exp(A-B),Math.exp(A+B)].map(x=>Math.max(.4,Math.min(2.6,x)));
  return k;
}

/* --------------------------- market helpers ---------------------------- */
function histAtLeast(h,off,x){ /* P(value >= x) for integer histogram with offset */
  let s=0,tot=0; for(let i=0;i<h.length;i++){tot+=h[i]; if(i-off>=x)s+=h[i];} return tot?s/tot:0; }
function histOver(h,off,line){ /* P(value > line), P(value == line) */
  let over=0,push=0,tot=0; for(let i=0;i<h.length;i++){const v=i-off;tot+=h[i]; if(v>line)over+=h[i]; else if(v===line)push+=h[i];}
  return {over:tot?over/tot:0, push:tot?push/tot:0}; }
function histQuantile(h,off,q){ let tot=0; for(const c of h)tot+=c; let acc=0;
  for(let i=0;i<h.length;i++){acc+=h[i]; if(acc>=q*tot) return i-off;} return h.length-1-off; }
function histMean(h,off){let s=0,t=0;for(let i=0;i<h.length;i++){s+=h[i]*(i-off);t+=h[i];}return t?s/t:0;}

if(typeof module!=="undefined") module.exports={balancePoint,makeRng,hashStr,LG,POSDEF,rosterV3,simGameV3,calibrateV3,impliedTotals,histOver,histQuantile,histMean,histAtLeast,HIST,S};
