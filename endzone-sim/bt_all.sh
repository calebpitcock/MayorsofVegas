#!/bin/bash
# Full backtest set for one code tree: TD 2023-24 (who-played actives), DraftKings props + TD 2024-26 (pregame actives).
# Usage: bt_all.sh <src dir>
cd "$1" || exit 1
export EZV='{"opp":1,"scheme":"off"}'
EZSEASON=2023 EZMODE=actual EZROLE=ex2023 python3 backtest_build.py 3 18 > lb23.txt 2>&1 &
EZSEASON=2024 EZMODE=actual EZROLE=ex2024 python3 backtest_build.py 3 18 > lb24.txt 2>&1 &
EZSEASON=2024 EZMODE=pregame EZBOOK=draftkings EZROLE=ex2024 python3 backtest_build.py 1 18 > lp24.txt 2>&1 &
EZSEASON=2025 EZMODE=pregame EZBOOK=draftkings EZROLE=ex2025 python3 backtest_build.py 1 18 > lp25.txt 2>&1 &
EZSEASON=2026 EZMODE=pregame EZBOOK=draftkings EZROLE=all python3 backtest_build.py 1 2 > lp26.txt 2>&1 &
wait
F="bt_2023_3_18_rex2023 bt_2024_3_18_rex2024 bt_2024_1_18_pre_draftkings_rex2024 bt_2025_1_18_pre_draftkings_rex2025 bt_2026_1_2_pre_draftkings_rall"
for f in $F; do EZTAG=_dk node bt_run.js $f.json > run_$f.log 2>&1 & done
wait
for f in $F; do python3 fix_td.py ${f}_dk_rows.json $f.json; python3 fix_ry.py ${f}_dk_rows.json; done
echo ALLDONE
