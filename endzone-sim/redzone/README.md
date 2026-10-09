# Redzone Desk

The user's all-factors model. Page: https://claude.ai/artifact/LxdpMGQt4nDJCg1RDhP2gc (private).

**What it is.** The Endzone Sim player simulation with every factor the Endzone Sim tested and rejected switched on
at heavy weight, and no sportsbook number used as a model input. The user asked for this knowing those factors
tested worse; the DraftKings-anchored Endzone Sim is unchanged and still available. Weights are in `config.json`
(0 = off).

| Factor | Where |
|---|---|
| End-zone targets, inside-5 carries, red-zone snaps (2025 participation + 2026 red-zone touches) | `features.py` → `p.gl` |
| Yards after catch over expected (nflfastR xYAC) | `features.py` → `p.ypr` |
| Pass rate over expected (nflfastR xpass) | `features.py` → `g.passRate` |
| Player vs this defense (last 5 meetings vs his 8-game baseline) | `features.py` → `p.ypc`, `p.ypr`, `p.gl` |
| Formation run term + TE/RB shifts, undamped | `features.py` → `formation.attach` → `g.form`, engine `ctx.fw=1` |
| Slot receivers | estimated from short middle-of-field targets (no free alignment data) |
| Where defenses give up TDs | engine `ctx.tdloc=1`, `ctx.tdlocW=2` |
| Team vs team, coach vs coach, offense vs defense history | `points.py` (margin and total) |
| New head coach: usage discount + 40% rating reset | `EZNEWHC=1` in `gen_nfl.py`, `points.py` |
| Books' team rating | weight 0 (`EZBOOKSW=0` in `gm/game_live.py`) |

The stricter injury-exit rule is not used: it and the current rule are the same switch, and the current one catches
more injuries.

**Coverage and football stats.** `coverage_2026.py` estimates this season's man and single-high rates (real
charting is published after the season); `football.py` adds pass rush vs protection, separation, run blocking, RYOE,
QB accuracy, drops, big plays, play style, air yards and turnovers; `db_matchups.py` pairs each receiver with his likely
corners/safeties (coverage stats allowed, size, 40 speed, style) and writes `g.mu` for the Matchups tab.
`get_stats.sh` downloads Next Gen Stats, PFR advanced stats and FTN charting.

**Scoring.** `points.py` sets each game's margin (the stats-only game model plus the history and new-coach terms) and
total (a points regression on opponent-adjusted offense/defense, fitted 2016–25, plus QB and history). The simulation
is calibrated to those, not to a sportsbook line. The consensus line is kept in `g.line` only as the number a spread or
total pick is measured against.

**Weekly.** `./setup_data.sh` once in a fresh session (or rerun it to refresh 2026 data), update the hand OUT /
QUESTIONABLE lists in `gen_nfl.py` and `STARTER` in `overrides.json`, then `redzone/run.sh <week>`. Publish
`redzone/site/index.html` (the page with every week's picks built in by `build_page.py`) to the page URL.

**Tracking.** The page's database: `mine/<pick id>` = the user's tracked picks (the page writes them; `result` is
W/L/P when the user marks it), `grades/w<week>` = `{results: {<pick id>: "W"|"L"|"P"}}`, written by Claude after the
games (grade every pick in `picks_w<week>.json` that can be graded; the page's Model record counts the Top plays
board). Rules: everyone who can open the page reads; only the owner/editors write.

## Grading, backtest and calibration (added 2026-10-08)

**After each week's games:** `python3 redzone/grade.py <week>` grades every pick from nflverse play-by-play
(players with no offensive snaps are voids) and writes `redzone/grades_w<week>.json`; put it in the page's database as
`grades/w<week>`.

**Backtest:** `redzone/bt.sh <week> <outdir> [config]` rebuilds a past 2026 week as of that week (`EZBTWEEK`: game
ratings, history and stats use only earlier games; the official injury report; that week's active roster and actual
starting QB; no hand lists) and dumps every player's simulated distributions. `python3 redzone/backtest.py <btdir> base
<variant>...` scores them against what happened (TD log loss; yardage at the books' lines, which are only used to score)
with a paired 90% interval by game. Weights for a variant come from its config file (`EZRZCFG`).

**Results calibration** (`calibration.json`, read by `predict.js`): the simulation was built to be calibrated against
DraftKings props, and with books out its position biases show (weeks 2-4: WR receiving yards about 20% low, RB
receiving yards high, rushing spread too narrow). `python3 redzone/calibrate.py <btdir> <variant> --write` fits a scale
and spread per stat and position on actual outcomes, plus `trust`: how much of the model's distance from 50% at a posted
line held up (0.15). Refit it each week with the new week added.

**What the 2026-10-08 backtest found (weeks 2-4, 877 player-games for TDs, 782 priced yardage lines):**

| Change vs the old config | Rec yds log loss | TD log loss |
|---|---|---|
| History factors off (all four) | -0.012 (better, clear of 0) | -0.010 (better, clear of 0) |
| Player-vs-this-defense history off | -0.010 (better) | -0.006 (better) |
| Coverage/scheme off | -0.004 (noise) | -0.002 (noise) |
| Coverage/scheme x2 | +0.007 (worse) | +0.001 |
| Coverage/scheme x3 | +0.018 (worse) | +0.004 (worse) |
| Man/zone, shells, CB matchups off one at a time | within +/-0.003 | within +/-0.001 |

So the history factors are off and coverage/scheme stays at 1x. Coverage can't be pushed harder with free data: 2026
man/zone is estimated (charting is published after the season) and defender coverage stats are a few games deep.
Yardage picks at the books' lines are still coin flips after calibration (log loss 0.6931 vs 0.6931 for 50/50), so the
page's over/under numbers sit close to 50%; TD chances are calibrated overall (19.9% predicted, 19.7% scored).
