# Research desk backtest, 2026 Weeks 2–5 (run Oct 14, 2026)

Current rules (no caps; TD +2, total +3, yardage +4 pts; beats the posted price's break-even), each week rebuilt as of
its first kickoff (`RZ_ASOF=1`): this week's and later play-by-play, charting, rosters and results hidden.

Prices: totals = nflverse closing lines; yardage = last nfl-player-prop-opportunity snapshot before each game's kickoff
(DraftKings first); anytime TD = last NFL-Model `player_td.json` commit before kickoff (12/16, 15/16, 16/16, 14/15 games
priced). Week 1 can't be built (no 2026 games yet for the season facts).

## Top plays (what the record would have counted)

| | Picks | W-L | Units | ROI |
|---|---|---|---|---|
| **All, matchups on (live config)** | 401 | 178-223 | **-4.7u** | -1.2% |
| Totals | 44 | 25-19 | +3.6u | +8.1% |
| Yardage | 199 | 100-99 | -10.1u | -5.1% |
| Anytime TD | 158 | 53-105 | +1.8u | +1.2% |
| Week 2 / 3 / 4 / 5 | 77 / 113 / 108 / 103 | | -9.8 / -7.1 / -4.7 / +16.9u | |
| **All, matchups off** | 296 | 128-168 | **+10.6u** | +3.6% |
| Old caps (top 10 TD / 6 totals / 10 yards per week) | 104 | 53-51 | +9.9u | +9.5% |

Board units have a standard deviation of about ±25u over 401 picks, so none of these differ from zero.

## Does the desk beat the book's own percentages?

Paired log loss, desk minus book (positive = desk worse), 90% bootstrap interval:

| | n | Desk − book |
|---|---|---|
| Board, matchups on | 401 | +0.0036 [-0.0055, +0.0130] |
| All picks, matchups on | 2180 | +0.0006 [-0.0017, +0.0028] |
| All yardage | 965 | +0.0018 [-0.0015, +0.0051] |
| All anytime TD | 1152 | -0.0001 [-0.0028, +0.0027] |
| All totals | 63 | -0.0037 [-0.0326, +0.0260] |

No measurable improvement over the book anywhere. Edge size doesn't sort winners from losers either: board picks with
8+ point edges went 14-18 (-5.4u).

## Caveats

- Sharp Football coverage tables are only available as of Week 5, so "matchups on" saw some future data. It still did
  worse than "matchups off".
- No hand-gathered news; only the official injury report's Outs. QB names come from the schedule (actual starters).
- Totals are graded at closing lines, the hardest number to beat.

Rerun: `backtest/prep_prices.py` (prices), `backtest/run.sh on|off`, `backtest/evaluate.py`.
