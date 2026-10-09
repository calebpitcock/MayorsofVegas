#!/bin/bash
# Redzone Desk backtest: rebuild a past 2026 week as of that week (EZBTWEEK: only earlier games in every rating, the
# official injury report, that week's active roster and actual starting QB) and dump every player's simulated
# distributions for redzone/backtest.py to score against what happened.
# Usage: redzone/bt.sh WEEK OUTDIR [CONFIG]   (CONFIG defaults to redzone/config.json)
#   stage 1 (slow, once per week): OUTDIR/../base_wWEEK.json; stage 2 (per config): the factor scripts + simulation.
set -e
cd "$(dirname "$0")/.."; W=${1:?week}; O=${2:?outdir}; C=$(realpath ${3:-redzone/config.json}); mkdir -p $O
R=$(realpath -m $(dirname $(dirname $O))); B=$R/base_w$W.json; export EZBTWEEK=$W EZWEEK=$W EZRZCFG=$C EZCOVJSON=$R/coverage_w$W.json
if [ ! -s $B ]; then
  EZOUT=$B.tmp EZNEWHC=1 python3 gen_nfl.py > /dev/null
  (cd gm && EZBOOKSW=0 python3 game_live.py $(realpath $B.tmp) > /dev/null); mv $B.tmp $B
fi
[ -s $EZCOVJSON ] || python3 redzone/coverage_2026.py $W > /dev/null
SL=$O/slate.json; cp $B $SL
python3 redzone/features.py $SL $W > /dev/null
python3 redzone/football.py $SL $W > /dev/null
python3 redzone/db_matchups.py $SL $W > /dev/null
python3 redzone/rb_matchups.py $SL $W > /dev/null
python3 redzone/finishing.py $SL $W > /dev/null
(cd gm && python3 ../redzone/points.py $(realpath $SL) $W > /dev/null)
EZDUMP=$O/dump.json node redzone/predict.js $SL $O/picks.json 2> /dev/null | head -1
