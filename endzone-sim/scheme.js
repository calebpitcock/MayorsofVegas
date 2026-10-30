/* ==========================================================================
   SCHEME + COVERAGE LAYER
   Defenses are no longer two softness scalars. Each carries a coverage and
   pressure profile, and each pass-catcher carries an alignment/skill profile.
   The interaction between them moves WHO scores — never HOW MUCH the team
   scores, which stays anchored to the market's implied team total. Letting
   scheme inflate scoring would double-count what the total already prices.

   src: w1 = measured in Week 1 2026 · 25 = 2025 team baseline
        dc = estimated from the 2026 coordinator's history · lg = league average
   ======================================================================== */
const LEAGUE={man:.33,blitz:.25,mofc:.48,press:.32,disg:.38,src:"lg"};
const SCHEME={
  DAL:{man:.032,blitz:.182,mofc:.42,press:.28,src:"w1",
       note:"86.4% zone, 3.2% man — last in the NFL in man rate — and an 18.2% blitz rate. Nobody travels."},
  MIN:{man:.45,blitz:.783,mofc:.55,press:.50,src:"w1",
       note:"Blitzed 78.3% of snaps with a 50% pressure rate. The most aggressive defense in the league by a mile."},
  TB: {man:.30,blitz:.46,mofc:.70,press:.42,src:"w1",
       note:"65% zone, 46% blitz, middle of the field closed on ~70% of snaps."},
  ARI:{man:.28,blitz:.20,mofc:.35,press:.30,disg:.48,src:"w1",
       note:"Second-lowest blitz rate in Week 1 (20%) and a heavy diet of disguised Cover 6."},
  WAS:{man:.38,blitz:.40,mofc:.52,press:.36,src:"w1",
       note:"Daronte Jones brings pressure — the blitz is the identity, and it leaves one-on-ones outside."},
  ATL:{man:.164,blitz:.334,mofc:.62,press:.30,src:"25",
       note:"Ulbrich's defense lives in Cover 3 — 46.9% of snaps, fifth in the league — with man on only 16.4% and Cover 1 at 11.3%, 30th. Single-high, three-deep: the deep outside is covered and the seams are not. Blitzed 33.4%, second-most in the league."},
  GB: {man:.186,blitz:.24,mofc:.40,press:.26,src:"25",
       note:"Fourth-lowest man rate (18.6%) with the third-highest cloud-coverage rate. Corners sit."},
  KC: {man:.34,blitz:.30,mofc:.48,press:.34,disg:.515,src:"25",
       note:"Spagnuolo disguises coverage more than anyone — 51.5% of snaps."},
  SF: {man:.30,blitz:.24,mofc:.45,press:.32,disg:.514,src:"25"},
  PIT:{man:.36,blitz:.32,mofc:.50,press:.38,src:"dc",
       note:"Patrick Graham's first year: pressure from structure, No. 1 pass-rush grade in Week 1."},
  SEA:{man:.33,blitz:.26,mofc:.42,press:.36,src:"25",
       note:"Allowed a league-low 17.2 points per game last season; picked off Maye three times in Week 1."},
  HOU:{man:.35,blitz:.30,mofc:.46,press:.36,src:"25"},
  BAL:{man:.31,blitz:.34,mofc:.47,press:.33,src:"25"},
  NYJ:{man:.28,blitz:.22,mofc:.40,press:.30,src:"dc",
       note:"Brian Duker's first year, out of the Miami pass-game room — two-high looks, low blitz."},
  DEN:{man:.40,blitz:.32,mofc:.50,press:.40,src:"25"},
  LAC:{man:.32,blitz:.26,mofc:.46,press:.32,src:"25"},
  CHI:{man:.30,blitz:.24,mofc:.46,press:.30,src:"25"},
  NE: {man:.34,blitz:.28,mofc:.48,press:.34,src:"25"}
};
const schemeFor=t=>Object.assign({},LEAGUE,SCHEME[t]||{});

/* Alignment and skill profile. slot/wide/inline/back sum to 1 (where the
   routes come from); sep = separation vs man, cont = contested/press winner,
   vert = vertical threat. Archetypes, not tracking data — stated as such. */
const POSALIGN={
  WR:{slot:.40,wide:.60,inline:0,back:0,sep:.50,cont:.50,vert:.50},
  TE:{slot:.30,wide:.05,inline:.65,back:0,sep:.45,cont:.65,vert:.35},
  RB:{slot:.10,wide:.02,inline:0,back:.88,sep:.50,cont:.35,vert:.45},
  QB:{slot:0,wide:0,inline:0,back:1,sep:.5,cont:.5,vert:.5},
  FLD:{slot:.33,wide:.42,inline:.17,back:.08,sep:.50,cont:.50,vert:.50}
};
const ALIGN={
 "Ja'Marr Chase":{slot:.32,wide:.68,sep:.88,cont:.68,vert:.80},
 "Justin Jefferson":{slot:.36,wide:.64,sep:.86,cont:.75,vert:.78},
 "CeeDee Lamb":{slot:.52,wide:.48,sep:.82,cont:.65,vert:.68},
 "George Pickens":{slot:.18,wide:.82,sep:.58,cont:.82,vert:.86},
 "Terry McLaurin":{slot:.24,wide:.76,sep:.78,cont:.60,vert:.80},
 "Mike Evans":{slot:.20,wide:.80,sep:.52,cont:.92,vert:.70},
 "DeVonta Smith":{slot:.42,wide:.58,sep:.76,cont:.52,vert:.62},
 "Emeka Egbuka":{slot:.58,wide:.42,sep:.72,cont:.52,vert:.60},
 "Chris Olave":{slot:.28,wide:.72,sep:.78,cont:.48,vert:.72},
 "Rashee Rice":{slot:.62,wide:.38,sep:.74,cont:.58,vert:.45},
 "Xavier Worthy":{slot:.44,wide:.56,sep:.70,cont:.32,vert:.94},
 "Jaylen Waddle":{slot:.40,wide:.60,sep:.80,cont:.35,vert:.88},
 "Marvin Harrison Jr.":{slot:.16,wide:.84,sep:.62,cont:.84,vert:.74},
 "Jaxon Smith-Njigba":{slot:.55,wide:.45,sep:.84,cont:.55,vert:.66},
 "Rashod Bateman":{slot:.22,wide:.78,sep:.60,cont:.55,vert:.80},
 "LaJohntay Wester":{slot:.72,wide:.28,sep:.68,cont:.28,vert:.70},
 "Parker Washington":{slot:.60,wide:.40,sep:.62,cont:.45,vert:.60},
 "Ladd McConkey":{slot:.62,wide:.38,sep:.82,cont:.42,vert:.58},
 "Caleb Douglas":{slot:.35,wide:.65,sep:.55,cont:.50,vert:.72},
 "Deebo Samuel":{slot:.55,wide:.30,inline:0,back:.15,sep:.60,cont:.72,vert:.50},
 "Mark Andrews":{slot:.38,wide:.04,inline:.58,sep:.52,cont:.80,vert:.40},
 "Travis Kelce":{slot:.45,wide:.05,inline:.50,sep:.56,cont:.76,vert:.32},
 "Trey McBride":{slot:.40,wide:.04,inline:.56,sep:.62,cont:.78,vert:.38},
 "Tyler Warren":{slot:.36,wide:.06,inline:.58,sep:.54,cont:.72,vert:.45},
 "Christian McCaffrey":{slot:.22,wide:.04,back:.74,sep:.78,cont:.40,vert:.55},
 "De'Von Achane":{slot:.20,wide:.04,back:.76,sep:.74,cont:.25,vert:.80},
 "Ashton Jeanty":{slot:.16,wide:.02,back:.82,sep:.66,cont:.55,vert:.62},
 "Saquon Barkley":{slot:.12,wide:.02,back:.86,sep:.60,cont:.45,vert:.78},
 "Jonathan Taylor":{slot:.10,wide:.02,back:.88,sep:.52,cont:.45,vert:.72},
 "Derrick Henry":{slot:.04,wide:0,back:.96,sep:.35,cont:.70,vert:.60},
 "Bijan Robinson":{slot:.24,wide:.05,back:.71,sep:.80,cont:.55,vert:.68},
 "Bucky Irving":{slot:.16,wide:.02,back:.82,sep:.68,cont:.42,vert:.62},
 "Kenneth Walker III":{slot:.12,wide:.02,back:.86,sep:.58,cont:.45,vert:.78},
 "David Montgomery":{slot:.10,wide:.02,back:.88,sep:.45,cont:.62,vert:.35},
 "Aaron Jones":{slot:.18,wide:.03,back:.79,sep:.66,cont:.40,vert:.58},
 "D'Andre Swift":{slot:.18,wide:.03,back:.79,sep:.68,cont:.35,vert:.55},
 "TreVeyon Henderson":{slot:.20,wide:.03,back:.77,sep:.70,cont:.35,vert:.82},
 "Rhamondre Stevenson":{slot:.12,wide:.02,back:.86,sep:.48,cont:.60,vert:.40},
 "Omarion Hampton":{slot:.14,wide:.02,back:.84,sep:.58,cont:.58,vert:.60},
 "J.K. Dobbins":{slot:.12,wide:.02,back:.86,sep:.55,cont:.48,vert:.58},
 "RJ Harvey":{slot:.22,wide:.04,back:.74,sep:.70,cont:.30,vert:.74},
 "Bhayshul Tuten":{slot:.14,wide:.02,back:.84,sep:.60,cont:.38,vert:.80},
 "Travis Etienne":{slot:.18,wide:.03,back:.79,sep:.64,cont:.38,vert:.70},
 /* Week 3 additions */
 "Jahmyr Gibbs":{slot:.24,wide:.04,back:.72,sep:.82,cont:.40,vert:.85},
 "James Cook":{slot:.13,wide:.02,back:.85,sep:.70,cont:.35,vert:.85},
 "Breece Hall":{slot:.17,wide:.03,back:.80,sep:.72,cont:.35,vert:.80},
 "Javonte Williams":{slot:.10,wide:.02,back:.88,sep:.50,cont:.65,vert:.50},
 "Alvin Kamara":{slot:.24,wide:.04,back:.72,sep:.78,cont:.50,vert:.50},
 "Amon-Ra St. Brown":{slot:.58,wide:.42,sep:.85,cont:.60,vert:.50},
 "Garrett Wilson":{slot:.35,wide:.65,sep:.82,cont:.70,vert:.75},
 "Christian Watson":{slot:.20,wide:.80,sep:.60,cont:.60,vert:.92},
 "Tee Higgins":{slot:.25,wide:.75,sep:.62,cont:.85,vert:.78},
 "Jake Ferguson":{slot:.35,wide:.05,inline:.55,sep:.50,cont:.72,vert:.35},
 "Dalton Kincaid":{slot:.45,wide:.05,inline:.45,sep:.60,cont:.65,vert:.50},
 "Tucker Kraft":{slot:.32,wide:.04,inline:.64,sep:.58,cont:.82,vert:.45},
 "Drake London":{slot:.30,wide:.70,sep:.66,cont:.90,vert:.68},
 "Matthew Golden":{slot:.38,wide:.62,sep:.74,cont:.42,vert:.88}
};
const alignOf=p=>Object.assign({slot:0,wide:0,inline:0,back:0},POSALIGN[p.pos]||POSALIGN.WR,ALIGN[p.n]||{});

/* Player-level scheme multipliers. Centered on the league profile so a
   league-average defense returns 1.00 and nothing drifts. */
function schemeMult(p,d){
  const a=alignOf(p), zone=1-d.man;
  const dZone=zone-(1-LEAGUE.man), dMan=d.man-LEAGUE.man,
        dBlitz=d.blitz-LEAGUE.blitz, dHigh=d.mofc-LEAGUE.mofc;
  /* zone concedes the middle: slot, in-line seams, backs in the flat.
     man rewards separators and puts backs on linebackers.
     blitz means one-on-one and hot routes.  single-high opens the deep thirds. */
  let rec=1
    + dZone*( a.slot*.62 + a.inline*.50 + a.back*.45 - a.wide*.34 )
    + dMan *( (a.sep-.5)*1.25 + a.back*.40 + (a.cont-.5)*.35 )
    + dBlitz*( (a.vert-.5)*.75 + a.slot*.34 - a.inline*.10 )
    + dHigh*( (a.vert-.5)*.65 + a.inline*.22 - a.slot*.18 );
  /* the red zone is a different coverage world: the field shrinks, man rate
     climbs, and boxing out beats separating. */
  const rzMan=Math.max(.2,Math.min(.8,.35+.6*d.man));
  const rzRec=rec*(1+(rzMan-.45)*((a.cont-.5)*1.9-(a.sep-.5)*.55)+(d.press-LEAGUE.press)*(a.cont-.5)*1.1);
  const exRec=rec*(1+dBlitz*.55+dHigh*.45+(a.vert-.5)*(dBlitz*.6+dHigh*.5));
  const cl=x=>Math.max(.55,Math.min(1.75,x));
  return {base:cl(rec), rz:cl(rzRec), ex:cl(exRec),
    exRun:cl(1+(LEAGUE.mofc-d.mofc)*.35*(a.vert-.5)*2+(LEAGUE.blitz-d.blitz)*.2)};
}
/* Team-level mix: two-high and light boxes open run lanes; blitz and
   single-high move touchdowns from the red zone out to explosive plays.
   These shift the MIX of scores, not the NUMBER of them. */
function mixMult(d){
  return { rush: Math.max(.7,Math.min(1.35, 1+(LEAGUE.mofc-d.mofc)*.80+(LEAGUE.blitz-d.blitz)*.30)),
           explosive: Math.max(.6,Math.min(1.6, 1+(d.blitz-LEAGUE.blitz)*.85+(d.mofc-LEAGUE.mofc)*.70+(d.man-LEAGUE.man)*.40)) };
}
function schemeRead(d,team){
  const out=[]; const zone=1-d.man;
  if(zone>=.72) out.push("zone-heavy — the holes are over the middle");
  if(d.man>=.42) out.push("man-heavy — separators and backs on linebackers");
  if(d.blitz>=.40) out.push("blitzes constantly — explosive shots up");
  if(d.blitz<=.21) out.push("rarely blitzes — plays it out in front");
  if(d.mofc>=.56) out.push("single-high — loaded box, deep shots live");
  if(d.mofc<=.42) out.push("two-high — light box, run lanes open");
  if((d.disg||0)>=.48) out.push("disguises post-snap more than anyone");
  return out.length?out.join(" · "):"league-average coverage profile";
}

const TUNE={
 "Jalen Hurts":{gl:2.30,deep:.25}, "Lamar Jackson":{gl:1.35,deep:.55},
 "Jayden Daniels":{gl:1.30,deep:.60}, "Patrick Mahomes":{gl:1.15,deep:.40},
 "Daniel Jones":{gl:1.20,deep:.40}, "Drake Maye":{gl:1.20,deep:.45},
 "Baker Mayfield":{gl:1.25,deep:.35}, "Bryce Young":{gl:1.15,deep:.45},
 "Carson Wentz":{gl:1.20,deep:.30},
 "Derrick Henry":{gl:1.30,deep:1.05}, "Bijan Robinson":{gl:1.10,deep:1.20},
 "Ashton Jeanty":{gl:1.15,deep:1.10}, "Kenneth Walker III":{gl:1.05,deep:1.35},
 "Saquon Barkley":{gl:.80,deep:1.45}, "Jonathan Taylor":{gl:1.10,deep:1.25},
 "Christian McCaffrey":{gl:1.10,deep:1.05}, "De'Von Achane":{gl:.80,deep:1.60},
 "Bucky Irving":{gl:1.05,deep:1.15}, "David Montgomery":{gl:1.35,deep:.70},
 "Aaron Jones":{gl:1.00,deep:1.10}, "D'Andre Swift":{gl:1.20,deep:1.00},
 "J.K. Dobbins":{gl:1.15,deep:.95}, "RJ Harvey":{gl:.85,deep:1.30},
 "Bhayshul Tuten":{gl:.95,deep:1.30}, "Travis Etienne":{gl:.90,deep:1.25},
 "Omarion Hampton":{gl:1.15,deep:1.05}, "Rhamondre Stevenson":{gl:1.20,deep:.80},
 "TreVeyon Henderson":{gl:.85,deep:1.45}, "Zach Charbonnet":{gl:1.30,deep:.85},
 "Tyler Allgeier":{gl:1.30,deep:.75}, "Jeremiyah Love":{gl:.90,deep:1.35},
 "Chris Brooks":{gl:1.20,deep:.80}, "MarShawn Lloyd":{gl:.85,deep:1.30},
 "Kaleb Johnson":{gl:1.10,deep:.85}, "Jacory Croskey-Merritt":{gl:1.00,deep:1.15},
 "Mike Evans":{gl:1.55,deep:1.15}, "Ja'Marr Chase":{gl:1.15,deep:1.45},
 "Justin Jefferson":{gl:1.10,deep:1.40}, "CeeDee Lamb":{gl:1.15,deep:1.25},
 "George Pickens":{gl:1.05,deep:1.60}, "Terry McLaurin":{gl:1.20,deep:1.35},
 "DeVonta Smith":{gl:1.10,deep:1.20}, "Emeka Egbuka":{gl:1.05,deep:1.20},
 "Chris Olave":{gl:.95,deep:1.25}, "Rashee Rice":{gl:1.20,deep:.90},
 "Xavier Worthy":{gl:.85,deep:1.75}, "Jaylen Waddle":{gl:.80,deep:1.60},
 "Marvin Harrison Jr.":{gl:1.30,deep:1.25}, "Jaxon Smith-Njigba":{gl:1.05,deep:1.30},
 "Rashod Bateman":{gl:1.00,deep:1.35}, "LaJohntay Wester":{gl:.75,deep:1.35},
 "Parker Washington":{gl:.90,deep:1.25}, "Ladd McConkey":{gl:1.00,deep:1.15},
 "Caleb Douglas":{gl:.85,deep:1.40}, "Deebo Samuel":{gl:1.15,deep:1.05},
 "Mark Andrews":{gl:1.45,deep:.70}, "Travis Kelce":{gl:1.30,deep:.60},
 "Trey McBride":{gl:1.30,deep:.70}, "Tyler Warren":{gl:1.25,deep:.85}
};
if(typeof module!=='undefined') module.exports={LEAGUE,SCHEME,schemeFor,alignOf,schemeMult,mixMult,schemeRead,TUNE,ALIGN,POSALIGN};
