# Endzone Sim — handoff (v3.4, Friday 2026-09-25, NFL Week 3)

## What this is
An NFL betting model for one user who bets **only on DraftKings** and **only on five bet types: anytime TD, receiving yards, rushing yards, catches, moneyline, spread.** Singles only.

- **Page:** https://claude.ai/artifact/GdsYysQkGu9mq7NycSyCSr (private). Read and publish it with the Artifact tool. The artifact also stores the source under `src/`.
- **Database** (ArtifactData on that URL; always pass `if_version`):
  - `slate/current` — this week's slate (v24). It replaces the page's built-in copy.
  - `tuning/current` — notes, weights, fits (v12).
  - `ledger/current` — the user's logged bets, with closing prices for CLV.
  - `lines/current` — lines the user typed.
  - `grades/current` — graded results.
  - `slip/suggested` — legacy; the slip no longer shows it.
- **Source:** `endzone-sim/` in `calebpitcock/MayorsofVegas`, branch `claude/sports-model-accuracy-9mhl6y` (pushed).
- **Data is not committed.** `README.md` lists every download URL. All of it is reachable from a cloud session only through GitHub (nflverse releases, raw.githubusercontent, git clone). Sports sites are blocked.

## v3.4 in one paragraph (2026-09-25)
Built for use **right before kickoff**. `./pregame.sh` refreshes everything in about 2 minutes: this season's data,
the official injury report (Out/Doubtful removed, Questionable flagged), the newest DraftKings props and TD prices, the
calibration, the game model and the page. Then write `slate_nfl.json` to `slate/current` and republish. Changes, each
backtested against DraftKings (`audit/AUDIT-2026-09-25.md`, "v3.4 results"):
- Game model registers team strength: market rating from past closing lines (`gm/market.py`, `gm/model3.py`) plus a
  second-year-QB term. 2021–25 MAE 10.30 → 10.03; lean k 0.15 → 0.10 (fit vs closing lines 0.17 ± 0.08). Still no
  proven edge at closing prices.
- Removed the touchdown-location defense inputs (pure noise); modern 4th-down rates; head-coach 4th-down
  aggressiveness (`nfl_build.coach_agg`, `g.agg`). Wind: the user won't type it, so the page box was removed; the
  engine still applies `g.wind` if a slate carries it (only historical games do).
- TD calibration and DK blend refit on the new engine (`td_cal_nfl.json`, `td_dk_fit.json`, via `audit/cmp_td.py`).
- Tested and rejected: new-head-coach usage/pass-rate discount (`EZNEWHC=1`), per-market prop recalibration,
  matchup history of any kind.
- Spread/moneyline: every attempt to make picks significantly better at closing prices failed (off-market DK prices,
  situational factors, line movement, fitting to the close); see the audit's last section. Don't repeat them.
- Team ratings + line flags (the user's ask): `game_live.py` writes `slate.teams` (value/rank, parts: strength, QB,
  efficiency; sums exactly to the game model's margin) and `gmfit.flags` from `gm/flag_record.py`. The page flags DK
  spreads 3+ pts from the fair line (record since 2016: 52.7% cover, +2.4% ± 3.5%; moneylines −4%, so spreads only).
  Found and fixed while building it: `model2.build` and `game_live.py` counted defense backwards (defense ratings are EPA
  allowed); pure-efficiency MAE 10.30 → 10.18, combined model unchanged (10.04).
- Team values v2 (user's spec): `gm/model4.py` splits opponent-adjusted offense and defense, adds special teams
  (`gm/st_games.py`, split-half r 0.16, shrunk) and keeps the books' rating and QB terms. `game_live.py` writes
  `slate.teams` (value, books, stats with off/def/st, QB, public rank) and two fair lines per game: `g.gm.m` (ratings) and
  `g.gm.ms` (stats only, no books). Flags: stats 5+ pts off (2016–25: 57.0%, 9/10 seasons), ratings 3+ (53.0%, 8/10);
  records in `gm/flag_record.json` (`gm/flag_record.py`). Flags are shown as mismatches, not picks (user's ask).
- Team-specific home field: tested and rejected (season-to-season r −0.04 vs the line, 2002–25; fitted weight −0.3).
- Public opinion: `public_rank.json` = {season, week, source, asOf, ranks: {TEAM: rank}}, 10% of value, only used when
  its week matches. The rankings sites (nfl.com, espn.com, walterfootball.com, sharpfootballanalysis.com) are blocked by
  this environment's network policy; once the user allows one, fetch this week's ranking with WebFetch during the
  refresh, write the file, rerun `gm/game_live.py`. Not backtestable (no history), so its weight is fixed, not fitted.
- ONE combined value + ONE flag (user's latest spec, replaces the two-flag version): value = 0.25 × ratings view (books +
  stats + QB) + 0.75 × stats view (off/def/ST + QB, no books), then 10% public power ranking when available; each home
  team's home field = league + 0.5 × its own edge (cap ±1). Flag at 4+ pts. Blend and threshold chosen on 2016–20
  (`gm/blend_select.py`); record in `gm/flag_record.json`: 2016–25 55.1% (532), 2021–25 53.1% (241).
- Sources: public = NFL.com weekly power rankings (`public_rank.json`: {season, week, source, asOf, ranks: {TEAM: rank}});
  home field = nfelo HFA tracker, https://www.nfeloapp.com/tools/nfl-home-field-advantage-hfa-tracker/ (`hfa_source.json`:
  {season, source, asOf, hfa: {TEAM: points}}). Both sites are BLOCKED by this environment's network policy (only GitHub and
  package registries pass). Until the user allows www.nfl.com and www.nfeloapp.com, public is left out and home field comes
  from nflverse results (`model4.home_edges`). Once allowed: WebFetch both during the refresh, write the two files,
  rerun `cd gm && python3 game_live.py ../slate_nfl.json`, then build and publish.
- A fresh session runs `./setup_data.sh` once (all data, about 5 minutes). `bt_all.sh <tree>` reruns every backtest.

## Rules the user set (keep them)
1. **Only DraftKings prices.** Don't line-shop or show other books. TD prices from best-across-books sources are converted to an estimated DK price and marked ≈.
2. **Only the five bet types, and they stay separate.** The game model (moneyline/spread) never feeds the player simulation. The player simulation uses DK's spread and total only to set each team's scoring level. Scratching a player never changes a moneyline or spread. No parlays.
3. **Be honest and harsh** about what works. Report numbers with uncertainty, and say when something doesn't beat DK.
4. **No scheduled jobs.** The user refreshes by asking, usually right before kickoff (`./pregame.sh`).
5. **Carried from the original handoff:** mark a player as scored only when a primary source or two independent sources agree. QB and scheme changes redistribute team scoring, never inflate it. Player weights are shares, and the Field takes the remainder.

## How it works
- **Player simulation** (`engine.js`, play-by-play with seeded RNG) produces anytime TD, yards and catches.
  - Usage shares come from nflverse play-by-play (`nfl_build.py`, empirical-Bayes, recency half-life 2 games).
  - A **role correction** then adjusts shares (`role_fit.py` → `role_coef_all.json`, applied in `Builder.role_adjust`). Signals: snap-share trend, practice status (limited/DNP), official Questionable, returning from a missed game, one-game samples.
  - Each offense's efficiency is solved so DK's spread and total are the simulation's 50/50 point (`precompute.js`).
- **TD pricing:** `logit p = a + bk·logit(DK implied) + bm·logit(calibrated model)`, from `td_dk_fit.json` (a≈0.015, bk≈0.82, bm≈0.32). The calibration is in `td_cal_nfl.json` (QB offset +0.48 now that scramble TDs count).
- **Yards/catches pricing:** chance = 80% DK no-vig + 20% simulation (the `LAMP` slider on the page).
- **Game model** (`gm/`): opponent-adjusted EPA/success team ratings plus starting-QB EPA/dropback vs the team's recent QBs, rest, home field, division and neutral site.
  - Walk-forward regression, trained on 2013+ and tuned on 2016–20 only. Tuned values: team half-life 14 games, carryover 0.85, QB half-life 1500 dropbacks, QB carryover 0.8, QB prior 100 dropbacks.
  - v3.4: adds market team strength (`market.py`: ridge ratings on past closing spreads, half-life 4 weeks, season carry 0.5) and a second-year-QB term (`model3.py`); tuned on 2016–20 only.
  - Prices start from DK's own no-vig odds and move by k=0.10 × (model margin − DK spread). Win rate per point b=0.1439, cover rate per point 0.044 (`anchor.json`).
  - `game_live.py` writes `g.gm` and `g.dk` onto the slate.

## Honest grades (all against real DraftKings prices)
| Bet type | Grade | Evidence |
|---|---|---|
| **Anytime TD** | real but small edge; not profitable at kickoff | 8,697 DK prices 2023–24 (~5 min pre-kick, mogden16/NFL-Wizard-Analysis). DK + model beat DK alone in every test: 2024 log loss 0.4701 vs 0.4715 (95% interval clear of zero), 2023 0.4304 vs 0.4314, 2026 Weeks 1–2 0.4310 vs 0.4330. DK hold is ~15%; betting positive-EV spots at kickoff lost 2% (2023) and 11% (2024). |
| **Yards and catches** | promising, unproven | 937 graded DK props 2024–26. 80/20 blend log loss 0.6877 vs DK 0.6929. Model-picked bets +13% ± 6% (288 bets): 2024 +46%, 2025 +17%, 2026 −0.5%. |
| **Moneyline / spread** | better model, no edge | v3.4 MAE 2021–25 10.03 (was 10.30; close 9.75). Predicts Tuesday→close movement 46% vs 27% against (was 40/33). At closing prices, 3+ pt disagreements covered 52.5%, ROI +1.9% ± 3.5% (2021–25 −2.3%). Moneylines lose. |
| **TD calibration** | calibrated | 2025 held-out weeks 12–18: Brier 0.1430 vs constant 0.1585. |

Other findings:
- DK prop overs hit 44.5% at a 50% price, but that edge is fading: +13% (2024), +7% (2025), −1% (2026).
- QB rushing unders lost 24% (DK underprices scrambling).
- Blind TD bets longer than +600 lost 21–29%.

## Bugs found this session (don't repeat them)
- **Grading bug:** the usage frames count designed runs only, so QB scrambles were missing from actual rushing yards and TDs. `fix_ry.py` and `fix_td.py` correct graded rows. Any new backtest must run them.
- **Moneyline pricing:** a normal bell curve from margin to win% overrated underdogs. Always anchor to DK's own odds.
- **Team codes:** OAK/SD/STL in games.csv → LV/LAC/LA in play-by-play.
- **Storage:** blocked browser storage broke the slip; `store` now has an in-memory fallback.
- **Shell:** `pkill -f` / `pgrep -f` kill your own shell (exit 144). `git ls-tree -l` on blobless clones hangs.
- **2026 data gaps:** nflverse has no 2026 route participation. Week-of `report_status` (Questionable/Out) posts Friday afternoon; until then `gen_nfl.py` feeds its hand QUESTIONABLE list into the role correction.

## Weekly refresh (when the user asks) — v3.4: `./pregame.sh` does steps 1–2 and 4–6; set `overrides.json` week/QBs first
1. Re-download from nflverse: `play_by_play_2026.csv.gz`, `snap_counts_2026.csv`, `injuries_2026.csv`, `roster_weekly_2026.csv`, and `games.csv` (nfldata).
2. `git fetch` the data repos:
   - davidcantugtr/nfl-player-prop-opportunity: `data/latest/player_props.csv` and `game_lines.csv`
   - jaredpatchett/NFL-Model: `data/player_td.json`
3. Edit `overrides.json` (week, starting-QB overrides) and the OUT/QUESTIONABLE dicts in `gen_nfl.py`, from news. Use the two-source rule for injuries.
4. Build and attach, in order:
   - `python3 gen_nfl.py`
   - `python3 live_props.py`
   - `python3 attach_td.py slate_nfl.json ../data/nflmodel_player_td_w3.json`
   - `node precompute.js slate_nfl.json`
   - `cd gm && python3 team_games.py && python3 game_live.py ../slate_nfl.json`
5. Write the slate to the DB: `ArtifactData set slate/current file_path=slate_nfl.json` with `if_version`.
6. `python3 build.py`, then smoke-test in Chromium (Playwright; see `shot2.js`/`shot3.js` patterns). Read the artifact, then publish.
7. Add a note to `tuning/current.notes`. Grade last week's bets and TDs with the two-source rule.

## Open work / best next steps
- **Track CLV** from the user's ledger. It's the fastest real signal. Ask them to log DK closing prices.
- **Collect early-week DK TD prices.** Every TD test used kickoff prices; the edge may live earlier in the week, around news.
- **Unused data:** DK line history 2022–24 is in [Risky-Scout/nfl-predictions-pricing](https://github.com/Risky-Scout/nfl-predictions-pricing) (`data/purchased/odds_closing_dev_2022_2024.parquet`, ~10 snapshots per game). Use it to test the game model against opening lines.
- **Spread pricing on 3 and 7:** use an empirical margin distribution around key numbers instead of a linear per-point slope.
- **Early season:** 2026 Weeks 1–2 were the weakest for every model because early usage leans on last season. Consider weighting preseason depth charts (nflverse `depth_charts_2026.csv`, ESPN format, untested).
- **Late games:** the prop snapshot covers ~72h, so Sunday-late and Monday props fill in later.
