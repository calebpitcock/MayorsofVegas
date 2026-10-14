# Redzone Desk: research edition

Replaces the simulation model behind https://claude.ai/artifact/LxdpMGQt4nDJCg1RDhP2gc (from Week 5, Oct 2026).
No simulation, ratings or fitted model: **book price → facts → small written-down nudges.**
**Coverage matchups are current season only** (2026 play-by-play, FTN blitz flag, Sharp Football 2026 tables). Trends, records and player history use every season available.

| File | What it does |
|---|---|
| `trends.py` | Team, QB, coach and head-to-head records from nflverse `games.csv` (every game since 1999 with closing lines): ATS / O-U / SU this season, streaks, last 10/20, fav/dog, home/road, after W/L, prime time, division, neutral site, rest. Keeps only lopsided ones (`notable`). |
| `players.py` | Player game logs (pbp 2019-26), every 2026 pass with FTN's blitz flag (`season_passes`, `split`), and 2026 defense-vs-style EPA ranks (play-action, motion, deep, screens, inside/outside, shotgun/under-center runs, middle throws). |
| `build.py` | Pulls book prices, attaches facts, applies `RULES` (every weight and cap is in that dict and printed on the page), writes `site/picks_w<week>.json`. |
| `sharp_*_2026.csv` | Sharp Football Analysis 2026 team tables, refreshed weekly from www.sharpfootballanalysis.com/stats-nfl/: `nfl-coverage-schemes` (man/zone, middle closed/open), `nfl-coverage-stats-by-position` (YPT allowed WR/TE/RB, outside/slot), `nfl-defensive-tendencies` (blitz, box, sub package). |
| `news_w<week>.json`, `reported_w<week>.json` | Hand-gathered injury news and outlet-reported trends, with sources. Shown, not added (books already moved on it). |
| `lock.py` | Locks each game's Top plays at kickoff. `build.py` calls it first: any game that has kicked off is copied from the previous build into `site/locked_w<week>.json` and never re-picked. `build_page.py` shows each week's locked games as a Record entry, and the Desk record counts only locked boards. `RZ_NOW` overrides the clock for testing. |
| `grade.py` | Grades every desk pick for a week (current build, locked boards, archive) from nflverse play-by-play; writes `../grades_w<week>.json` and prints each board's record and units. Any snap is action (a return TD counts); no snaps = push. |
| `build_page.py` | `page_head.html` (styles) + `desk_body.html` (page) + data → `site/index.html`, the file to publish. Keeps older weeks in `site/archive.json` so tracked picks and the record still resolve. |

## Top plays and the record

A pick makes Top plays when the facts move it off the book by at least: TDs 2 pts (max 10), totals 3 pts (max 6),
yardage 4 pts (max 10), **and** the Desk chance beats the break-even of the posted price with the margin in. The rule
is `RULES['board']` in `build.py` and is printed on the page. The record is W-L plus units: 1 unit per pick at the
posted price (tracked picks: the price when tracked).

## Weekly run

```bash
S=<scratch dir>
# nflverse (GitHub releases): play_by_play_2019..2026, ftn_charting_2026,
# roster_weekly_2026, injuries_2026 (.parquet) and nfldata games.csv  -> $S/nfldata
# prices: git clone davidcantugtr/nfl-player-prop-opportunity -> $S/ext/pp  (yardage lines)
#         git clone jaredpatchett/NFL-Model -> $S/ext/jp              (data/player_td.json: best anytime-TD prices only)
# write news_w<week>.json and reported_w<week>.json from the week's reporting
# refresh sharp_*_2026.csv from the three Sharp pages (server-rendered tables; pandas.read_html works)
# news_w<week>.json may carry "qb": {team: name} when the nflverse schedule lists the wrong starter
python3 build.py $S/nfldata $S/ext <week>     # locks kicked-off games first (lock.py), then re-picks the rest
python3 build_page.py <week>
# publish site/index.html to the artifact URL (keeps the db capability for My picks / grades)
# rebuild before each window (Thu, Sun morning, Mon): every rebuild re-picks games not yet started; started ones stay locked

# after the games (needs games.csv, play_by_play_2026, snap_counts_2026.csv, roster_2026.csv):
python3 grade.py $S/nfldata <week>             # then write ../grades_w<week>.json to the page db as grades/w<week>
```

Book sources: anytime TD = best US price from NFL-Model's live Odds API pull; yardage = DraftKings (then FanDuel,
BetMGM, BetRivers, Bovada, BetOnline); spreads/totals/moneylines = nflverse schedule consensus. Not backtested.
Fetch only the two data files (`raw.githubusercontent.com/.../main/data/player_td.json` and
`.../data/latest/player_props.csv`) into `$S/ext/jp` and `$S/ext/pp`; a week with no rows there builds with game totals
only and the page says player prices are pending.
