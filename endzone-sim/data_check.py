"""Data check, run by pregame.sh after the slate is built: is every input present and current for this week?
Writes slate['dataCheck'] = [{level: ok|warn|gap, area, text}] for the page, and prints the same list.
'gap' = something the model needs is missing and the numbers it feeds are weaker for it; 'warn' = partial or stale."""
import json, os, sys, datetime as dt, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import nfl_build as nb
D = nb.D; EXT = '/home/user/ext'
path = sys.argv[1] if len(sys.argv) > 1 else 'slate_nfl.json'
S = json.load(open(path)); SEASON = 2026
WEEK = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))['week']
now = pd.Timestamp.now('UTC'); out = []
def add(level, area, text): out.append(dict(level=level, area=area, text=text))
def age(ts):
    t = pd.Timestamp(ts); t = t.tz_convert('UTC') if t.tzinfo else t.tz_localize('UTC'); h = (now - t).total_seconds() / 3600
    return f'{h:.0f}h old' if h < 48 else f'{h / 24:.1f} days old'

# ---- this season's play data vs games played
G = nb.games(); G = G[(G.season == SEASON) & (G.game_type == 'REG') & (G.week <= WEEK) & G.home_score.notna()]
played = set(G.game_id)
p = pd.read_csv(f'{D}/play_by_play_{SEASON}.csv.gz', usecols=['game_id'], low_memory=False); miss_p = played - set(p.game_id)
sn = pd.read_csv(f'{D}/snap_counts_{SEASON}.csv', usecols=['game_id'], low_memory=False); miss_s = played - set(sn.game_id)
ft = pd.read_parquet(f'{D}/ftn_charting_{SEASON}.parquet', columns=['nflverse_game_id']); miss_f = played - set(ft.nflverse_game_id)
for name, m in (('Play-by-play', miss_p), ('Snap counts', miss_s), ('FTN charting (blitz, box, play action)', miss_f)):
    if m: add('gap', 'Season data', f"{name}: missing {len(m)} of {len(played)} games played ({', '.join(sorted(m))}).")
    else: add('ok', 'Season data', f"{name}: all {len(played)} games played this season.")
if not os.path.exists(f'{D}/pbp_participation_{SEASON}.parquet'):
    add('warn', 'Season data', f"Man/zone coverage charting isn't published for {SEASON} yet (nflverse releases it after the season), "
        f"so each defense's man-coverage rate is from {SEASON - 1}; blitz rates do use {SEASON}. Defenses with a new coordinator can be off.")

# ---- availability
inj = pd.read_csv(f'{D}/injuries_{SEASON}.csv'); iw = inj[(inj.week == WEEK) & (inj.game_type == 'REG')]
teams = sorted({t for g in S['games'] for t in (g['away'], g['home'])})
nost = [t for t in teams if not iw[(iw.team == t)].report_status.notna().any()]
add('ok' if not nost else 'warn', 'Injuries', f"Official injury report: {len(set(iw.team) & set(teams))} of {len(teams)} teams on the slate reported"
    + (f"; no game statuses yet for {', '.join(nost)} (Monday/late teams post them the day before)." if nost else ', all with game statuses.'))
rw = pd.read_csv(f'{D}/roster_weekly_{SEASON}.csv', low_memory=False, usecols=['week', 'team', 'gsis_id', 'status'])
add('ok' if rw.week.max() >= WEEK else 'gap', 'Rosters', f"Weekly rosters through week {rw.week.max()}" + ('' if rw.week.max() >= WEEK else f" — week {WEEK} missing, injured-reserve moves may be missed."))

# ---- starters and big roles vs depth charts
b = nb.Builder(SEASON); R = b.R
ov = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))
dc = pd.read_csv(f'{D}/depth_charts_{SEASON}.csv', low_memory=False); dts = dc.dt.max(); dc = dc[dc.dt == dts]
out_ids = set(iw[iw.report_status.isin(['Out', 'Doubtful'])].gsis_id)
slate_ids = {p['id'] for g in S['games'] for p in g['players']}
slate_qb = {p['t']: p for g in S['games'] for p in g['players'] if p['pos'] == 'QB'}
for t in teams:
    q = dc[(dc.team == t) & (dc.pos_abb == 'QB') & (dc.pos_rank == 1)]
    if not len(q): continue
    q1 = q.gsis_id.iloc[0]; s = slate_qb.get(t)
    if s and s['id'] != q1:
        why = 'hand override (news)' if t in ov['STARTER'] else ('depth-chart QB1 out/doubtful' if q1 in out_ids else 'check')
        add('ok' if why != 'check' else 'warn', 'Starters', f"{t}: slate QB {s['n']}, depth chart lists {q.player_name.iloc[0]} — {why}.")
lim = {'RB': 1, 'WR': 2, 'TE': 1}
big = dc[(dc.pos_grp == '3WR 1TE') & dc.pos_abb.isin(lim) & dc.team.isin(teams)]
big = big[big.apply(lambda r: r.pos_rank <= lim[r.pos_abb], axis=1)]
act = set(rw[(rw.week == rw.week.max()) & (rw.status == 'ACT')].gsis_id)
missing = [f"{r.team} {r.pos_abb}{r.pos_rank} {r.player_name}" for r in big.itertuples()
           if r.gsis_id not in slate_ids and r.gsis_id not in out_ids and r.gsis_id in act]
if missing: add('warn', 'Starters', f"Depth-chart starters not on the slate (no usage history with this team, or removed on news): {', '.join(missing)}.")
else: add('ok', 'Starters', f"Every active depth-chart starter (RB1, WR1-2, TE1) is on the slate (depth charts {age(dts)}).")

# ---- prices
def role(p): return p['rush'] >= .25 or p['rec'] >= .15
nop = {}
for g in S['games']:
    m = [p['n'] for p in g['players'] if p['pos'] != 'QB' and role(p) and p.get('mkt') is None]
    if m: nop[g['id']] = m
td = json.load(open(f'{EXT}/jaredpatchett_NFL-Model/data/player_td.json'))
src_teams = {x['team'] for x in td['players'] if (x.get('market') or {}).get('anytime_td_price') is not None}
absent = [t for t in teams if t not in src_teams]
add('gap' if absent else 'ok', 'TD prices', f"Anytime-TD prices ({age(td['generated_at'])}, best US price converted to a DraftKings estimate)"
    + (f": none at all for {', '.join(absent)}." if absent else ' cover every team.'))
if nop: add('gap', 'TD prices', 'Main-role players with no TD price (model probability shown, no edge possible): '
            + '; '.join(f"{k}: {', '.join(v)}" for k, v in nop.items()) + '.')
base = f'{EXT}/nfl-player-prop-opportunity/data/snapshots'; wk = sorted(os.listdir(base))[-1]
snaps = sorted(f for f in os.listdir(f'{base}/{wk}') if f.endswith('_player_props.csv'))
sts = pd.to_datetime(snaps[-1][:15], format='%Y%m%dT%H%M%S', utc=True) if snaps else None
nprops = {g['id']: sum(1 for p in g['players'] if p.get('book')) for g in S['games']}
none = [k for k, v in nprops.items() if v == 0]
add('gap' if none else 'ok', 'Props', (f"DraftKings yardage props: latest snapshot {age(sts)}; " if sts is not None else 'DraftKings yardage props: no snapshot this week; ')
    + f"{len(nprops) - len(none)} of {len(nprops)} games have props" + (f", none for {', '.join(none)}." if none else '.')
    + ' Receiving and rushing yards only; DraftKings receptions and anytime TD are not in this feed.')
gl = pd.read_csv(f'{D}/dk_game_lines_latest.csv'); glt = pd.to_datetime(gl['Last Update'], utc=True).max()
add('warn' if (now - glt).total_seconds() > 24 * 3600 else 'ok', 'Game lines',
    f"DraftKings spreads/totals snapshot {age(glt)}; line flags and chances use the current consensus line wherever it has moved since.")
S['dataCheck'] = dict(at=now.isoformat()[:19] + 'Z', items=out)
json.dump(S, open(path, 'w'))
for x in out: print(f"[{x['level']:4s}] {x['area']}: {x['text']}")
