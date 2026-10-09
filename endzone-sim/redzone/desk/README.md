# Redzone Desk: research edition

Replaces the simulation model behind https://claude.ai/artifact/LxdpMGQt4nDJCg1RDhP2gc (from Week 5, Oct 2026).
No simulation, ratings or fitted model: **book price → facts → small written-down nudges.**

| File | What it does |
|---|---|
| `trends.py` | Team, QB, coach and head-to-head records from nflverse `games.csv` (every game since 1999 with closing lines): ATS / O-U / SU this season, streaks, last 10/20, fav/dog, home/road, after W/L, prime time, division, neutral site, rest. Keeps only lopsided ones (`notable`). |
| `players.py` | Player game logs (pbp 2019-26), receiver man/zone and shell splits (participation 2024-25), defense coverage rates, and 2026 defense-vs-style EPA ranks (play-action, motion, deep, screens, inside/outside, shotgun/under-center runs, middle throws). |
| `build.py` | Pulls book prices, attaches facts, applies `RULES` (every weight and cap is in that dict and printed on the page), writes `site/picks_w<week>.json`. |
| `sharp_coverage_2026.csv` | 2026 man, zone, middle-closed and middle-open rates by defense from Sharp Football Analysis (refresh weekly from www.sharpfootballanalysis.com/stats-nfl/nfl-coverage-schemes/). |
| `news_w<week>.json`, `reported_w<week>.json` | Hand-gathered injury news and outlet-reported trends, with sources. Shown, not added (books already moved on it). |
| `build_page.py` | `page_head.html` (styles) + `desk_body.html` (page) + data → `site/index.html`, the file to publish. Keeps older weeks in `site/archive.json` so tracked picks and the record still resolve. |

## Weekly run

```bash
S=<scratch dir>
# nflverse (GitHub releases): play_by_play_2019..2026, pbp_participation_2024/2025, ftn_charting_2026,
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
