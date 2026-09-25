# Endzone Sim v3.3 (DraftKings: TD, yards, catches, moneyline, spread)

Source for the published artifact https://claude.ai/artifact/GdsYysQkGu9mq7NycSyCSr.
The page reads live state from the artifact's database (`slate/current` = NFL,
`ledger/current`, `tuning/current`, `grades/current`, `slip/suggested`, `lines/current`).

## Layout
- `engine.js` — play-level simulator, market calibration, histograms.
- `scheme.js` — coverage/pressure layer and legacy per-player tuning.
- `app.js`, `model.js`, `shell.html` — the page; `build.py` assembles `endzone.html`.
- `nfl_build.py` / `gen_nfl.py` — NFL usage priors and the weekly slate from nflverse data.

- `backtest_build.py`, `bt_run.js`, `bt_eval.py`, `td_cal.py` — 2025 backtests and TD recalibration.
- `precompute.js` — attaches calibrated offense multipliers (`k`) to a slate before publishing.
- `attach_td.py` — this week's anytime-TD prices (best price across books) converted to estimated DraftKings prices.
- `live_props.py` — this week's DraftKings prop lines and prices.

## Role signals (v3.3)
- `role_data.py` — per player-game: the model's share next to snap-share trend, practice report and availability, and the actual share (2023–25).
- `role_fit.py` — fits the correction; `role_coef_all.json` is live, `role_coef_ex{S}.json` excludes season S for honest backtests (`EZROLE=ex2024`).
- `role_eval.py`, `role_td_cmp.py`, `props_cmp.py` — held-out share error, TD vs DraftKings and props vs DraftKings with and without it.
- `nfl_build.Builder.role_adjust` applies it; `gen_nfl.py` feeds the flagged-questionable list in until official statuses post.

## Game model: moneyline and spread (gm/, separate from the player simulation)
- `team_games.py` — per team-game EPA/success from play-by-play 2012–2026; `ratings2.py` — opponent-adjusted, recency-weighted team ratings and QB ratings.
- `model2.py` — walk-forward margin regression; `tune.py`/`tune2.py` tuned on 2016–20 only; `final_eval.py` tests 2021–25 vs closing lines and DraftKings' Tuesday lines (`tue_lines.py`).
- `ml_anchor.py` — prices moneyline/spread from DraftKings' own odds moved by the model's disagreement (`anchor.json`).
- `game_live.py` — this week's margins and DraftKings game lines onto the slate (`g.gm`, `g.dk`, `gmfit`). QB overrides live in `overrides.json`, shared with `gen_nfl.py`.

## Grading against DraftKings
- `td_vs_book.py`, `td_fit2.py` — model vs 8,422 DraftKings anytime-TD prices (2023–24, ~5 min before kickoff); writes `td_dk_fit.json`, the weighting the page uses.
- `td_2026.py` — the same check on 2026 Weeks 1–2.
- `props_hist.py` with `EZBOOK=draftkings` — DraftKings-only prop history (2024–25 jsonl + 2026 snapshots in `../data/snap26/`).
- `props_eval.py`, `unders.py`, `props_fit.py` — props vs DraftKings; 80% DraftKings / 20% simulation is the page default.
- `fix_ry.py`, `fix_td.py` — grading fix: official rushing yards and rushing TDs include QB scrambles (the usage frames count designed runs only).

## Data (not committed; all reachable from a cloud session through GitHub)
Put these in `../data/` relative to the scripts:
- `https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv` (lines, results)
- `https://github.com/nflverse/nflverse-data/releases/download/pbp/play_by_play_{2012..2026}.csv.gz`
- `.../releases/download/injuries/injuries_{2022..2026}.csv` (practice reports, role signals)
- `.../releases/download/snap_counts/snap_counts_{2024,2025,2026}.csv`
- `.../releases/download/rosters/roster_{2024,2025,2026}.csv`, `.../injuries/injuries_2026.csv`
- `https://raw.githubusercontent.com/jaredpatchett/NFL-Model/main/data/historical_player_props_2024_2025.jsonl` (2024–25 prop odds for the props-vs-book test)
- `https://github.com/davidcantugtr/nfl-player-prop-opportunity` `data/latest/player_props.csv` (this week's prop prices; `live_props.py` attaches DraftKings rows) and `data/snapshots/2026-W0*/` (2026 grading)
- `https://github.com/jaredpatchett/NFL-Model` `data/player_td.json` (this week's anytime-TD prices; `attach_td.py`) and `data/historical_odds_{2021_2023,2024_2025}.jsonl` (Tuesday DraftKings game lines)
- davidcantugtr `data/latest/game_lines.csv` (this week's DraftKings moneylines and spreads; `gm/game_live.py`)
- `https://github.com/mogden16/NFL-Wizard-Analysis` `reports/phase7/stage_a/all_quotes.csv` (2023–24 anytime-TD quotes, 10 books), `reports/phase45_stage_a_all_quotes.csv` and `reports/atd_price_quotes_2026-09-17.csv` (2026)

## Weekly refresh
1. Re-download pbp, snap counts, injuries, games.csv.
2. Edit OUT / QUESTIONABLE / STARTER in `gen_nfl.py`; update the week; run it.
3. Edit `overrides.json` (week, starting QBs). `python3 live_props.py` (DraftKings props), `python3 attach_td.py slate_nfl.json ../data/player_td.json` (TD prices).
4. `node precompute.js slate_nfl.json`; rebuild `gm/team_games.py` after new games, then `cd gm && python3 game_live.py ../slate_nfl.json`; write the slate to the artifact DB (`slate/current`) and run `build.py`.
