#!/bin/bash
# Redzone Desk: build a week's picks with every Redzone factor on and no sportsbook input to the model.
# Usage: redzone/run.sh WEEK   -> redzone/slate_wWEEK.json, redzone/picks_wWEEK.json
# Before a real refresh: ./setup_data.sh once, then pregame.sh's data downloads (or rerun setup_data.sh), and edit the
# hand OUT/QUESTIONABLE lists in gen_nfl.py and STARTER in overrides.json from the week's news.
set -e
cd "$(dirname "$0")/.."; W=${1:?week}; SL=redzone/slate_w$W.json
[ -e ../data/dk_game_lines_latest.csv ] || ln -sf /home/user/ext/nfl-player-prop-opportunity/data/latest/game_lines.csv ../data/dk_game_lines_latest.csv
echo "== slate (week $W)"; EZWEEK=$W EZOUT=$SL EZNEWHC=1 python3 gen_nfl.py | grep -E "official|games;"
echo "== game model (no books)"; (cd gm && python3 team_games.py >/dev/null && python3 st_games.py >/dev/null && EZWEEK=$W EZBOOKSW=0 python3 game_live.py ../$SL >/dev/null)
echo "== factors";  python3 redzone/features.py $SL $W
echo "== scoreboard"; (cd gm && python3 ../redzone/points.py ../$SL $W)
echo "== simulate"; node redzone/predict.js $SL redzone/picks_w$W.json
# the page's data files: every week's picks plus an index (publish redzone/site/* next to redzone.html)
mkdir -p redzone/site && cp redzone/picks_w$W.json redzone/site/
python3 redzone/build_page.py
