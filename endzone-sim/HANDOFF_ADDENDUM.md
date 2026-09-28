## v3.6 — early injury exits (2026-09-28, claude.ai session, NOT yet committed or backtested)
- **Problem:** a player hurt early in a game counted as a full game with a tiny share, and as his most recent game it
  carried the most weight (half-life 2). Backups' inflated shares in that game also counted in full because the starter
  was "present". Week 3 example: Barkley (stinger on the first play of Week 2) came out at 39% of PHI carries vs Bigsby
  30%, creating fake edges (Bigsby TD +600 at +7.7% EV, Barkley under 70.5 rush at +8.4%).
- **Fix (`nfl_build.py`, `EZEXIT=1` default, `EZEXIT=0` = old behaviour):** a game is an early injury exit when the
  player's snap share is under 50% of his own baseline (median of his other games for that team, baseline >= 30%) AND
  there is injury evidence: play-by-play "was injured during the play" (adds `desc` to PBP_COLS), or he is on the injury
  report in the next two weeks (only as far as the build week can see), or `overrides.json` `EARLY_EXIT`
  lists [name, season, week]. Flagged games are dropped from his snap rows, so they behave exactly like missed games:
  his shares skip the game, teammates get the 0.25 absent-starter down-weight for it, and role_adjust reads a return.
  Benchings without injury evidence (Stevenson, Week 2) still count.
- **Tested:** unit tests (`test_early_exit.py`) and a synthetic two-game PHI replica through `Builder.team_players`
  (Barkley 0.24 -> 0.47, Bigsby 0.38 -> 0.21). **Not yet backtested on real data.** Next session: run the TD/props/
  share backtests with EZEXIT=0 vs 1 (and `fix_ry.py`/`fix_td.py` as usual) before trusting it.
- **Live slate v37:** board cut to MNF PHI@CHI only; Barkley/Bigsby rush shares hand-set to 0.55/0.138 as an estimate of
  the fix (real pbp wasn't reachable). Prices are general current market prices (the user said exact DK prices aren't
  required); prop odds assumed -110 where only the line was found.

## v3.7 — formation matchups (2026-09-28, claude.ai session, NOT backtested; user asked to use it now)
- **What:** offense personnel (share of plays with 3+ WR vs heavy 2+ TE / 2+ RB) meets the defense's light-box (<=6),
  stacked-box (8+) and nickel/dime rates. Heavy personnel vs a defense that stays in nickel/dime -> lighter boxes; vs
  one that matches with base -> heavier boxes (shift C=0.5). Box mix -> yards per carry with league values by box
  (light 5.2 / 7-man 4.5 / 8+ 3.8), relative to a league-average matchup, damped to 40% (box counts partly follow the
  situation, and `dp.ypc` already carries some of it), capped ±6%. 2026 rates shrunk toward league by sample.
- **Where:** `formation.py` writes `g.form[side] = {run, light, heavy, heavyPers, text}`; `engine.js` multiplies run
  efficiency by `g.form[side].run ^ ctx.fw` (`ctx.fw`: 1 default, 0 off; neutral sims use 0); `matchups.js` compares
  against fw:0 and adds a "Formations:" line to each team's matchup text. `pregame.sh` runs formation.py before precompute.
- **Data:** `formation_2026.json`, hand-copied from Sharp Football Analysis (offensive personnel 2026, pulled Sep 28;
  defensive tendencies page dated Sep 22 — confirm that table is 2026, its description still says 2025). Refresh weekly.
  Team level only; player-by-personnel splits need nflverse participation (2022–25) or a paid source (PFF/FTN).
- **Size:** effects are small by construction (tonight CHI run efficiency +0.5%, PHI −0.1%). Team box/personnel
  tendencies only vary enough to move a team a few percent even undamped (max ~+6% raw, e.g. CIN's 69% light boxes).
- **To do (data session):** backtest with EZ fw=0 vs 1 on 2022–25 using nflverse participation for the same measures
  (offense_personnel, defense_personnel, defenders_in_box) — TD log loss vs DK, props, RB ypc error — tune C and DAMP,
  then add player-level personnel splits (TE2/WR3/FB on-field share by grouping) if the team-level version holds up.
- **v3.7b position shifts (same session):** `g.form[side].pos = {TE:{tgt,ypt}, RB:{tgt,ypt}}`. bv = (offense 3-WR rate
  x defense base rate) − league (linebackers covering a spread set); nh = (offense heavy rate x defense nickel/dime
  rate) − league (a DB on the tight end). TE targets 1 + 0.6·bv − 0.4·nh, yards/target 1 + 0.3·bv − 0.2·nh; RB targets
  1 + 0.5·bv, yards/target 1 + 0.3·bv; capped ±8%. Engine: `fT` multiplies wTgt and wRZTgt (so red-zone targets and TDs
  move too), `fY` multiplies yards per catch; WRs absorb the change through shared target weights. Slot WRs (who also
  gain vs base) aren't separated: the model has no slot/outside split. Coefficients are guesses from the mechanism,
  not fits — backtest with fw=0 vs 1 and fit them on 2022–25 participation data (targets by offense_personnel x
  defense_personnel x position) before trusting the sizes.
- **v3.7c slot receivers (same session):** `slot_2026.json` = each player's share of snaps in the slot (fill weekly from
  StatRankings "Slot Rate", free full-season view; PFF or RotoWire alignment also work). formation.py writes per-player
  `g.form[side].players[name] = {tgt, ypt}`: WR = 1 + 0.6·bv·slot (targets), 1 + 0.3·bv·slot (yards/target); TE's
  position shift re-weighted by (0.5 + slot) so move/slot TEs get the linebacker mismatch and inline TEs less. Engine
  uses the per-player value before the position value. Empty file = no slot effect (live board as of v40: empty —
  couldn't read the table from claude.ai; the page's long menu truncates the fetch). Sets `p.slot` on slate players.

## TEST PLAN for the next session with GitHub/nflverse access (user asked: test ALL changes before trusting them)
Rules: held out by season, report numbers with uncertainty, compare against DraftKings, ship only what helps.
1. **Early injury exits (EZEXIT=0 vs 1):** carry/target share error on 2022–25 (all player-weeks after an exit and their
   teammates), TD log loss vs DK kickoff prices (2023, 2024; 2026 wk1–3), props 80/20 bets. Check how many game-exits
   each rule flags (pbp text / injury report / manual) and eyeball 20 of them.
2. **Formation run term (ctx.fw=0 vs 1):** rebuild historical team inputs walk-forward from nflverse participation
   2022–25: offense 3-WR rate (offense_personnel), defense light/stacked box (defenders_in_box), nickel/dime rate
   (defense_personnel). Test RB ypc error, rush share of team TDs, TD log loss vs DK, rushing-yard props. Fit C and DAMP.
3. **Position shifts (TE/RB):** fit the bv/nh coefficients from targets by position x offense_personnel x
   defense_personnel (2022–25), held out by season; then the full DK backtest with the fitted values vs fw=0.
4. **Slot:** nflverse has NO alignment (participation has personnel/box/coverage/route, not where receivers line up).
   Options: (a) StatRankings+ archive or PFF for 2022–25 slot rates, then fit + backtest like 3; (b) without history,
   collect 2026 weekly slot rates and evaluate after ~6 weeks (small sample; say so). Until then slot stays a guess.
5. Also re-run the existing suite (`bt_all.sh`) so nothing else moved, and `fix_ry.py`/`fix_td.py` on graded rows.
Network needed: github.com, raw.githubusercontent.com, release assets (nflverse), plus www.sharpfootballanalysis.com
and statrankings.com for the weekly formation/slot inputs.
