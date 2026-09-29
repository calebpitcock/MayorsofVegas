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

**Scoring.** `points.py` sets each game's margin (the stats-only game model plus the history and new-coach terms) and
total (a points regression on opponent-adjusted offense/defense, fitted 2016–25, plus QB and history). The simulation
is calibrated to those, not to a sportsbook line. The consensus line is kept in `g.line` only as the number a spread or
total pick is measured against.

**Weekly.** `./setup_data.sh` once in a fresh session (or rerun it to refresh 2026 data), update the hand OUT /
QUESTIONABLE lists in `gen_nfl.py` and `STARTER` in `overrides.json`, then `redzone/run.sh <week>`. Publish
`redzone/redzone.html` to the page URL with `files` = every `redzone/site/*` (weeks.json + picks_w*.json).

**Tracking.** The page's database: `mine/<pick id>` = the user's tracked picks (the page writes them; `result` is
W/L/P when the user marks it), `grades/w<week>` = `{results: {<pick id>: "W"|"L"|"P"}}`, written by Claude after the
games (grade every pick in `picks_w<week>.json` that can be graded; the page's Model record counts the Top plays
board). Rules: everyone who can open the page reads; only the owner/editors write.
