#!/bin/bash
# Pre-game refresh, meant to run right before kickoff (Sunday late morning, or before any window).
# Pulls this season's newest data (play-by-play, snap counts, the official injury report, weekly rosters, closing
# lines of games already played) and the newest DraftKings snapshots, then rebuilds everything:
#   player usage + official statuses -> DraftKings props -> anytime-TD prices -> offense calibration ->
#   game model (team strength, QBs) -> page.
# Afterwards the slate goes to the page's database (slate/current) and the page is republished; Claude does those
# two steps with the Artifact tools. Set the week in overrides.json (plus any starting-QB changes) before running.
set -e
cd "$(dirname "$0")"; D=../data; S=2026
B=https://github.com/nflverse/nflverse-data/releases/download
[ -s $D/play_by_play_2025.csv.gz ] || ./setup_data.sh
echo "== data"
curl -sSfL -o $D/.games.tmp https://raw.githubusercontent.com/nflverse/nfldata/master/data/games.csv && mv $D/.games.tmp $D/games.csv || echo 'WARN: games.csv not refreshed'
# download to a temp file and swap in only on success (3 tries), so a failed download keeps the previous copy
fetch() { local out=$D/$(basename $1) t=$D/.$(basename $1).tmp
  for i in 1 2 3; do curl -sSfL -o $t $B/$1 && [ -s $t ] && { rm -f $out; mv $t $out; return 0; }; sleep $((i*3)); done
  echo "WARN: could not refresh $(basename $1); using the previous copy"; rm -f $t; [ -s $out ]; }
for f in pbp/play_by_play_$S.csv.gz snap_counts/snap_counts_$S.csv injuries/injuries_$S.csv rosters/roster_$S.csv weekly_rosters/roster_weekly_$S.csv; do
  fetch $f || { echo "missing $(basename $f) and no previous copy; stopping"; exit 1; }; done
for r in jaredpatchett_NFL-Model nfl-player-prop-opportunity mogden16_NFL-Wizard-Analysis; do git -C /home/user/ext/$r pull -q --depth 1 || echo "warn: $r not updated"; done
ln -sf /home/user/ext/nfl-player-prop-opportunity/data/snapshots/$S-W*/*.csv $D/snap26/ 2>/dev/null || true
ln -sf /home/user/ext/nfl-player-prop-opportunity/data/latest/game_lines.csv $D/dk_game_lines_latest.csv
echo "== slate";         python3 gen_nfl.py | grep -E "official|games;"
python3 -c "import json,sys; s=json.load(open('slate_nfl.json')); n=sum(len(g['players']) for g in s['games']); sys.exit(0 if n>=12*len(s['games']) else 'slate has only %d players for %d games: data problem, stopping' % (n, len(s['games'])))"
echo "== DK props";      python3 live_props.py
echo "== DK TD prices";  python3 attach_td.py slate_nfl.json /home/user/ext/jaredpatchett_NFL-Model/data/player_td.json
echo "== calibrate";     node precompute.js slate_nfl.json > /dev/null
echo "== public";        python3 fetch_public.py || true
echo "== game model";    (cd gm && python3 team_games.py > /dev/null && python3 st_games.py > /dev/null && python3 game_live.py ../slate_nfl.json | grep -E "^[A-Z]+@")
echo "== page";          python3 build.py
python3 - <<'PY'
import json; s = json.load(open('slate_nfl.json'))
print(f"slate {s['label']} v{s['version']}: {len(s['games'])} games; props as of {max((g.get('propsAsOf') or '') for g in s['games'])}; TD prices as of {max((g.get('tdAsOf') or '') for g in s['games'])}")
PY
