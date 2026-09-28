"""Unit tests for the early-injury-exit detector (nfl_build.injury_exits). Run: python3 test_early_exit.py"""
import os, sys, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfl_build as nb   # loads role_coef at import; it's in the folder

assert nb.pbp_abbrev('Amon-Ra St. Brown') == 'A.St. Brown'
assert nb.pbp_abbrev('Kenneth Walker III') == 'K.Walker'
assert nb.pbp_abbrev('Saquon Barkley') == 'S.Barkley'

sn = pd.DataFrame([
  # Barkley: 71% wk1, 8% wk2 (hurt first play)
  ('g1','PHI','SB',2026,1,.71),('g2','PHI','SB',2026,2,.08),
  # Bigsby: backup, 15% then 60%
  ('g1','PHI','TB',2026,1,.15),('g2','PHI','TB',2026,2,.60),
  # Stevenson: 85% then 36% after a fumble benching, NOT hurt
  ('n1','NE','RS',2026,1,.85),('n2','NE','RS',2026,2,.36),
  # Starter who just had a normal quieter game (60% vs 70%) and is on the report: not flagged (not under half)
  ('d1','DET','AG',2026,1,.70),('d2','DET','AG',2026,2,.60),
], columns=['game_id','team','pid','season','week','offense_pct'])
names = {'SB':'Saquon Barkley','TB':'Tank Bigsby','RS':'Rhamondre Stevenson','AG':'Jahmyr Gibbs'}
p = pd.DataFrame({'game_id':['g2','n2'],'posteam':['PHI','NE'],'defteam':['TEN','PIT'],
  'desc':['(14:52) 26-S.Barkley up the middle to PHI 27 for 2 yards (54-X.Y). 26-S.Barkley was injured during the play. His return is Questionable.',
          '(3:10) 38-R.Stevenson left end to NE 30 for 1 yard. FUMBLES, RECOVERED by PIT.']})
pinj = nb.injured_in_pbp(p)
assert set(zip(pinj.game_id, pinj.team, pinj.abbr)) == {('g2','PHI','S.Barkley'), ('g2','TEN','S.Barkley')}
none = pinj.iloc[0:0]
inj = pd.DataFrame({'gsis_id':['AG'],'season':[2026],'week':[3]})

# play-by-play evidence flags Barkley only (Stevenson benched, Gibbs not under half, Bigsby a backup)
assert nb.injury_exits(sn, pinj, inj, names, 2026, 3) == {('g2','SB')}
# no pbp text, but on next week's injury report
inj2 = pd.DataFrame({'gsis_id':['SB','AG'],'season':[2026,2026],'week':[3,3]})
assert nb.injury_exits(sn, none, inj2, names, 2026, 3) == {('g2','SB')}
# look-ahead guard: hurt in week 2, first on the report in week 4. A week-3 build can't see it; a week-5 build can.
inj4 = pd.DataFrame({'gsis_id':['SB'],'season':[2026],'week':[4]})
assert nb.injury_exits(sn, none, inj4, names, 2026, 3) == set()
assert nb.injury_exits(sn, none, inj4, names, 2026, 5) == {('g2','SB')}
# a report three weeks later is too late to count
inj5 = pd.DataFrame({'gsis_id':['SB'],'season':[2026],'week':[5]})
assert nb.injury_exits(sn, none, inj5, names, 2026, 6) == set()
# manual override
assert nb.injury_exits(sn, none, inj.iloc[0:0], names, 2026, 3, manual=[('SB',2026,2)]) == {('g2','SB')}
# low-baseline players are never flagged, even with evidence
low = pd.DataFrame([('x1','PHI','FB',2026,1,.20),('x2','PHI','FB',2026,2,.02)], columns=sn.columns)
pl = pd.DataFrame({'gsis_id':['FB'],'season':[2026],'week':[3]})
assert nb.injury_exits(low, none, pl, {'FB':'Ben VanSumeren'}, 2026, 3) == set()
print('test_early_exit: all passed')
