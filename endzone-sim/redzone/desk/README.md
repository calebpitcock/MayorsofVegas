# Redzone Desk: research edition

Replaces the simulation model behind https://claude.ai/artifact/LxdpMGQt4nDJCg1RDhP2gc (from Week 5, Oct 2026).
No simulation, ratings or fitted model: **book price → facts → small written-down nudges.**
**Current season only:** every stat, matchup and nudge uses 2026 games; nothing from prior seasons.

| File | What it does |
|---|---|
| `trends.py` | `season_facts` / `qb_season_facts`: this season's records from nflverse `games.csv` (SU/ATS/O-U, streaks, fav/dog, home/road, prime time, average margin vs spread and total, rest, starting QB). The older multi-season functions are kept but not called. |
| `players.py` | 2026 player game logs, every 2026 pass with FTN's blitz flag (`season_passes`, `split`), and 2026 defense-vs-style EPA ranks (play-action, motion, deep, screens, inside/outside, shotgun/under-center runs, middle throws). |
| `build.py` | Pulls book prices, attaches facts, applies `RULES` (every weight and cap is in that dict and printed on the page), writes `site/picks_w<week>.json`. |
| `sharp_*_2026.csv` | Sharp Football Analysis 2026 team tables, refreshed weekly from www.sharpfootballanalysis.com/stats-nfl/: `nfl-coverage-schemes` (man/zone, middle closed/open), `nfl-coverage-stats-by-position` (YPT allowed WR/TE/RB, outside/slot), `nfl-defensive-tendencies` (blitz, box, sub package). |
| `news_w<week>.json`, `reported_w<week>.json` | Hand-gathered injury news and outlet-reported trends, with sources. Shown, not added (books already moved on it). |
| `build_page.py` | `page_head.html` (styles) + `desk_body.html` (page) + data → `site/index.html`, the file to publish. Keeps older weeks in `site/archive.json` so tracked picks and the record still resolve. |

## Weekly run

```bash
S=<scratch dir>
# nflverse (GitHub releases): play_by_play_2026, ftn_charting_2026,
# roster_weekly_2026, injuries_2026 (.parquet) and nfldata games.csv  -> $S/nfldata
# prices: git clone davidcantugtr/nfl-player-prop-opportunity -> $S/ext/pp  (yardage lines)
#         git clone jaredpatchett/NFL-Model -> $S/ext/jp              (data/player_td.json: best anytime-TD prices only)
# write news_w<week>.json and reported_w<week>.json from the week's reporting
python3 build.py $S/nfldata $S/ext <week>
python3 build_page.py <week>
# publish site/index.html to the artifact URL (keeps the db capability for My picks / grades)
```

Book sources: anytime TD = best US price from NFL-Model's live Odds API pull; yardage = DraftKings (then FanDuel,
BetMGM, BetRivers, Bovada, BetOnline); spreads/totals/moneylines = nflverse schedule consensus. Not backtested.
