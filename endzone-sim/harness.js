// concatenate into one module so globals are plain (vm contexts slow global access)
const fs=require('fs'),path=require('path'),os=require('os');
const src=fs.readFileSync(__dirname+'/scheme.js','utf8').replace(/if\(typeof module[^\n]*/,'')+"\n"+
  fs.readFileSync(__dirname+'/engine.js','utf8').replace(/if\(typeof module[^\n]*$/m,'')+
  "\nmodule.exports={TUNE,LEAGUE,SCHEME,makeRng,hashStr,LG,POSDEF,rosterV3,simGameV3,calibrateV3,impliedTotals,histOver,histQuantile,histMean,histAtLeast,balancePoint,HIST,S};";
const f=path.join(__dirname,'_bundle.js'); fs.writeFileSync(f,src); module.exports=require(f);
