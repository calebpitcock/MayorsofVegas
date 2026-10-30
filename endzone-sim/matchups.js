// Matchup report: what this week's defenses and schemes do to each player, in plain words.
// Each game is simulated twice with the team's scoring anchored to DraftKings both times: against this week's actual
// defense (matchups at weight 1, the tested weight) and against a league-average defense (matchups off). The difference
// is the matchup's effect on each player's TD chance, targets and yards; the text says why and whether it is an edge.
// Usage: node matchups.js slate_nfl.json   (writes g.mx onto every game)
const E=require('./harness.js'), fs=require('fs');
const f=process.argv[2]||'slate_nfl.json', S=JSON.parse(fs.readFileSync(f));
const CAL=JSON.parse(fs.readFileSync(__dirname+'/td_cal_nfl.json'));
const lg=q=>{q=Math.min(.999,Math.max(.001,q));return Math.log(q/(1-q));}, sg=z=>1/(1+Math.exp(-z));
const cal=p=>sg(CAL.slope*lg(p.pModel)+(CAL[p.pos]||0));
const pct=(x,d=0)=>`${x>=0?'+':'−'}${Math.abs(100*x).toFixed(d)}%`, P=x=>Math.round(100*x)+'%';
const NAME={RB:'backs',WR:'receivers',TE:'tight ends'};
const N=20000;   // enough that simulation noise in the difference (~0.4 TD points) stays under the verdict thresholds
for(const g of S.games){
  const base={tuning:{},out:new Set(),tune:E.TUNE,opp:1,scheme:'off'};
  const on=E.simGameV3(g,{N,trust:1,k:g.k,seed:E.hashStr(g.id+'|mx')},{...base,mw:1});
  const k0=E.calibrateV3(g,{...base,mw:0,fw:0},{N:3000,trust:1});
  const off=E.simGameV3(g,{N,trust:1,k:k0,seed:E.hashStr(g.id+'|mx')},{...base,mw:0,fw:0});
  const mx={players:{},teams:{}};
  for(const side of ['away','home']){
    const team=g[side], dfn=side==='away'?g.home:g.away, dp=(g.defp||{})[side]||{}, ds=(g.defScheme||{})[side], L=(g.defScheme||{}).lg;
    // team-level: is this defense a run funnel or a pass funnel?
    const ypc=dp.ypc||1, ypt=dp.ypt||1, t=[];
    if(Math.abs(ypc-1)>=.04||Math.abs(ypt-1)>=.04) t.push(`${dfn} allows ${pct(ypc-1)} yards per carry and ${pct(ypt-1)} per target vs average`+(ypc-ypt>=.05?`: a run-friendly matchup for ${team}.`:ypt-ypc>=.05?`: a pass-friendly matchup for ${team}.`:'.'));
    if(ds&&L) t.push(`${dfn} plays man on ${P(ds.man)} of charted snaps (league ${P(L.man)}) and blitzes ${P(ds.blitz)} (league ${P(L.blitz)}).`);
    const fmx=(g.form||{})[side]; if(fmx&&fmx.text) t.push('Formations: '+fmx.text);
    mx.teams[team]=t.join(' ');
    for(const p of on.players){ if(p.side!==team||p.field||p.hidden||p.pos==='QB') continue;
      const q=off.players.find(x=>x.n===p.n); if(!q) continue; const src=g.players.find(x=>x.n===p.n)||{};
      const dTD=cal(p)-cal(q), rec=p.pos!=='RB'||p.mean.TGT>p.mean.RA/3;
      const yOn=p.mean.RCY+p.mean.RY, yOff=q.mean.RCY+q.mean.RY, dY=yOff>1?yOn/yOff-1:0, dT=q.mean.TGT>.3?p.mean.TGT/q.mean.TGT-1:0;
      const why=[], cp=src.covParts;
      const sp=x=>x>=1?`${Math.round(100*(x-1))}% more`:`${Math.round(100*(1-x))}% fewer`;
      if(cp&&cp.man&&Math.abs(cp.man.raw-1)>=.005){ const moreMan=cp.man.rate>cp.man.lg, ok=cp.man.raw>1;
        why.push({w:Math.abs(cp.man.raw-1),s:Math.sign(cp.man.raw-1),t:`${dfn} plays ${moreMan?'more man':'more zone'} than average (man ${P(cp.man.rate)} vs ${P(cp.man.lg)}), which ${ok?'suits':'works against'} him: he gets ${sp(cp.man.split)} of his team's targets against man than against zone`}); }
      if(cp&&cp.blitz&&Math.abs(cp.blitz.raw-1)>=.005){ const moreB=cp.blitz.rate>cp.blitz.lg, ok=cp.blitz.raw>1;
        why.push({w:Math.abs(cp.blitz.raw-1),s:Math.sign(cp.blitz.raw-1),t:`${dfn} blitzes ${moreB?'more':'less'} than average (${P(cp.blitz.rate)} vs ${P(cp.blitz.lg)}), which ${ok?'suits':'works against'} him: he gets ${sp(cp.blitz.split)} of his team's targets when teams blitz`}); }
      const tg=(dp.tgt||{})[p.pos]; if(tg&&Math.abs(tg-1)>=.04) why.push({w:Math.abs(tg-1)*.7,s:Math.sign(tg-1),t:`${dfn} lets ${NAME[p.pos]} get ${tg>1?'more':'fewer'} targets than usual (${pct(tg-1)})`});
      if(p.pos==='RB'&&Math.abs(ypc-1)>=.04) why.push({w:Math.abs(ypc-1)*.6,s:Math.sign(ypc-1),t:`${dfn} allows ${ypc>1?'more':'fewer'} yards per carry than average (${pct(ypc-1)})`});
      if(rec&&Math.abs(ypt-1)>=.04) why.push({w:Math.abs(ypt-1)*.6,s:Math.sign(ypt-1),t:`${dfn} allows ${ypt>1?'more':'fewer'} yards per target than average (${pct(ypt-1)})`});
      const tdl=(dp.tdpos||{})[p.pos]; const ignored=tdl&&Math.abs(tdl-1)>=.15?`(Not used: ${dfn} has allowed ${tdl.toFixed(2)}× the usual share of receiving TDs to ${NAME[p.pos]}, but that doesn't repeat week to week.)`:'';
      why.sort((a,b)=>b.w-a.w);
      const big=Math.abs(dTD)>=.02||Math.abs(dY)>=.06, some=Math.abs(dTD)>=.01||Math.abs(dY)>=.03, up=(dTD*4+dY)>=0;
      const verdict=big?(up?'Edge':'Disadvantage'):some?(up?'Slight edge':'Slight disadvantage'):'No edge';
      const size=`TD chance ${dTD>=0?'+':'−'}${Math.abs(100*dTD).toFixed(1)} pts, ${rec?'targets '+pct(dT)+', ':''}yards ${pct(dY)} vs a league-average defense`;
      const dir=up?1:-1, pro=why.filter(x=>x.s===dir).slice(0,2), con=why.filter(x=>x.s===-dir).slice(0,1);
      let because='';
      if(verdict==='No edge') because=why.length?` Pluses and minuses roughly cancel or are too small to matter: ${why.slice(0,2).map(x=>x.t+(x.s>0?' (helps)':' (hurts)')).join('; ')}.`:' This defense is close to average in every way that matters for him.';
      else because=(pro.length?` Why: ${pro.map(x=>x.t).join('; and ')}.`:` Why: the matchup ${up?'pushes targets away from his teammates, and some come to him':'favours his teammates, so some of his work goes to them'}.`)+(con.length?` Partly offset: ${con[0].t}.`:'');
      const text=`${verdict}: ${size}.`+because+(ignored?' '+ignored:'');
      mx.players[p.n]={verdict,dTD:+dTD.toFixed(4),dY:+dY.toFixed(4),dT:+dT.toFixed(4),text};
    }
  }
  g.mx=mx;
}
fs.writeFileSync(f,JSON.stringify(S));
const all=S.games.flatMap(g=>Object.entries(g.mx.players).map(([n,v])=>({g:g.id,n,...v})));
const cnt={}; all.forEach(x=>cnt[x.verdict]=(cnt[x.verdict]||0)+1); console.log('matchup verdicts', JSON.stringify(cnt));
all.filter(x=>x.verdict!=='No edge').sort((a,b)=>Math.abs(b.dTD)-Math.abs(a.dTD)).slice(0,12).forEach(x=>console.log(`${x.g} ${x.n}: ${x.text}`));
