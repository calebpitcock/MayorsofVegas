#!/bin/bash
# usage: BT_OUT=... BT_DATA=... BT_PRICES=... BT_GRADE=... run.sh on|off
# Rebuilds weeks 2-5 as of each first kickoff (RZ_ASOF) in a scratch copy of desk/, then grades them. "off" zeroes the matchup weights.
set -e
V=$1; SP=${BT_OUT:?set BT_OUT to a scratch dir}; W=$SP/bt_$V; DATA=${BT_DATA:?set BT_DATA (nflverse parquet dir)}; PRICES=${BT_PRICES:?set BT_PRICES (prep_prices.py output)}; GRADE=${BT_GRADE:?set BT_GRADE (grade.py data dir)}
rm -rf $W; mkdir -p $W; cp -r $(cd $(dirname $0)/.. && pwd) $W/
cd $W/desk; rm -f site/locked_w*.json site/picks_w*.json && echo '[]' > site/archive.json
if [ "$V" = off ]; then
  python3 - <<'PY'
s=open('build.py').read()
s=s.replace("'matchup': {'w': 1.0, 'cap': 0.10,","'matchup': {'w': 0.0, 'cap': 0.10,",1).replace("'matchup': {'w': 0.6, 'cap': 0.08,","'matchup': {'w': 0.0, 'cap': 0.08,",1)
assert s.count("'matchup': {'w': 0.0")==2; open('build.py','w').write(s)
PY
fi
for wk in 2 3 4 5; do
  echo '{"asOf":"backtest","about":"","bar":"","outs":[],"players":{},"games":{},"sources":[]}' > news_w$wk.json
  echo '{}' > reported_w$wk.json
  first=$(python3 -c "
import pandas as pd;G=pd.read_csv('$DATA/games.csv');g=G[(G.season==2026)&(G.week==$wk)]
k=pd.to_datetime(g.gameday+' '+g.gametime.astype(str)).min().tz_localize('America/New_York').tz_convert('UTC');print((k-pd.Timedelta(minutes=5)).isoformat())")
  RZ_ASOF=1 RZ_NOW=$first python3 build.py $DATA $PRICES/w$wk $wk
  python3 grade.py $GRADE $wk > /dev/null
done
