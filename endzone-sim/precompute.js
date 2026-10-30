// attach calibrated offense multipliers to each game so the page doesn't have to solve them on load
const E=require('./harness.js');const fs=require('fs');
for(const f of process.argv.slice(2)){
  const sl=JSON.parse(fs.readFileSync(f));
  for(const g of sl.games){ const k=E.calibrateV3(g,{tuning:{},out:new Set(),tune:E.TUNE,opp:1,scheme:'off'},{N:5000,trust:1});
    g.k=k.map(x=>+x.toFixed(4)); g.kFor=[g.spread,g.total]; g.kTrust=1; }
  sl.engine=3;
  fs.writeFileSync(f,JSON.stringify(sl));
  console.log(f,sl.games.map(g=>g.id+':'+g.k.join('/')).join(' '));
}
