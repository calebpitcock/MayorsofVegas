# Endzone Sim — handoff (v3.3, Friday 2026-09-25, NFL Week 3)

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
- **Source:** `endzone-sim/` in `calebpitcock/MayorsofVegas`, branch `claude/beautiful-franklin-9i7vh8`. 5 commits are **unpushed**: every push returns 403 because Claude lacks GitHub access. The user was told to reconnect at https://claude.ai/connect-github and install the Claude GitHub App. Push first thing if access works.
- **Data is not committed.** `README.md` lists every download URL. All of it is reachable from a cloud session only through GitHub (nflverse releases, raw.githubusercontent, git clone). Sports sites are blocked.

## Rules the user set (keep them)
1. **Only DraftKings prices.** Don't line-shop or show other books. TD prices from best-across-books sources are converted to an estimated DK price and marked ≈.
2. **Only the five bet types, and they stay separate.** The game model (moneyline/spread) never feeds the player simulation. The player simulation uses DK's spread and total only to set each team's scoring level. Scratching a player never changes a moneyline or spread. No parlays.
3. **Be honest and harsh** about what works. Report numbers with uncertainty, and say when something doesn't beat DK.
4. **No scheduled jobs.** The user refreshes by asking.
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
  - Prices start from DK's own no-vig odds and move by k=0.15 × (model margin − DK spread). Win rate per point b=0.1439, cover rate per point 0.044 (`anchor.json`).
  - `game_live.py` writes `g.gm` and `g.dk` onto the slate.

## Honest grades (all against real DraftKings prices)
| Bet type | Grade | Evidence |
|---|---|---|
| **Anytime TD** | real but small edge; not profitable at kickoff | 8,697 DK prices 2023–24 (~5 min pre-kick, mogden16/NFL-Wizard-Analysis). DK + model beat DK alone in every test: 2024 log loss 0.4701 vs 0.4715 (95% interval clear of zero), 2023 0.4304 vs 0.4314, 2026 Weeks 1–2 0.4310 vs 0.4330. DK hold is ~15%; betting positive-EV spots at kickoff lost 2% (2023) and 11% (2024). |
| **Yards and catches** | promising, unproven | 937 graded DK props 2024–26. 80/20 blend log loss 0.6877 vs DK 0.6929. Model-picked bets +13% ± 6% (288 bets): 2024 +46%, 2025 +17%, 2026 −0.5%. |
| **Moneyline / spread** | no edge | Can't beat the close (MAE 10.49 vs 9.995). Vs DK Tuesday lines 2021–25 (1,339 games): predicts line movement (closes its way 42% vs 31% against), but spread bets broke even and moneyline bets lost ~9%. |
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

## Weekly refresh (when the user asks)
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
