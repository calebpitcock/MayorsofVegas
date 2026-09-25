#!/bin/bash
# One-time data setup for a fresh session: nflverse history into ../data, and the three GitHub repos that carry
# DraftKings prices into /home/user/ext. Safe to re-run; existing history files are kept.
set -e
cd "$(dirname "$0")"; D=../data; mkdir -p $D $D/snap26 /home/user/ext
B=https://github.com/nflverse/nflverse-data/releases/download
get() { [ -s "$2" ] || curl -sSfL -o "$2" "$1"; }
curl -sSfL -o $D/games.csv https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv
for s in $(seq 2012 2026); do get $B/pbp/play_by_play_$s.csv.gz $D/play_by_play_$s.csv.gz & done; wait
for s in 2022 2023 2024 2025 2026; do get $B/snap_counts/snap_counts_$s.csv $D/snap_counts_$s.csv & get $B/rosters/roster_$s.csv $D/roster_$s.csv &
  get $B/injuries/injuries_$s.csv $D/injuries_$s.csv & done; wait
clone() { # repo dir paths...
  [ -d /home/user/ext/$2 ] || { git clone -q --depth 1 --filter=blob:none --sparse https://github.com/$1 /home/user/ext/$2; git -C /home/user/ext/$2 sparse-checkout set --no-cone "${@:3}"; }
}
clone jaredpatchett/NFL-Model jaredpatchett_NFL-Model /data
clone davidcantugtr/nfl-player-prop-opportunity nfl-player-prop-opportunity /data/latest /data/snapshots
clone mogden16/NFL-Wizard-Analysis mogden16_NFL-Wizard-Analysis /reports/phase7/stage_a/all_quotes.csv /reports/phase45_stage_a_all_quotes.csv '/reports/atd_price_quotes_*'
J=/home/user/ext/jaredpatchett_NFL-Model/data
ln -sf $J/historical_player_props_2024_2025.jsonl $D/; ln -sf $J/historical_odds_2021_2023.jsonl $D/hist_odds_2021_2023.jsonl; ln -sf $J/historical_odds_2024_2025.jsonl $D/hist_odds_2024_2025.jsonl
echo "data ready in $D"
