"""Early injury exits flagged by each rule (pbp text / injury report / manual), 2022-26, with a sample to eyeball.
Every season's games are scored with the full season visible (week 19), so this counts flags, not what a given
build week could see. Usage: python3 audit/early_exit/flags.py > audit/early_exit/flags.txt"""
import os, sys, numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
os.environ['EZEXIT'] = '1'
import nfl_build as nb
none = pd.DataFrame(columns=['game_id', 'team', 'abbr'])
rows = []
for S in (2023, 2024, 2025, 2026):
    b = nb.Builder(S); names = b.R['full_name'].to_dict(); pos = b.R['position'].to_dict() if 'position' in b.R else {}
    seasons = (S - 1, S) if S == 2023 else (S,)
    for team in sorted(b.SN_ALL.team.unique()):
        sn = b.SN_ALL[(b.SN_ALL.team == team) & b.hist_mask(b.SN_ALL, 19)]
        e_all = nb.injury_exits(sn, b.PINJ, b.INJ_ALL, names, S, 19, b.EXIT_MANUAL)
        e_pbp = nb.injury_exits(sn, b.PINJ, b.INJ_ALL.iloc[0:0], names, S, 19)
        e_rep = nb.injury_exits(sn, none, b.INJ_ALL, names, S, 19)
        e_man = nb.injury_exits(sn, none, b.INJ_ALL.iloc[0:0], names, S, 19, b.EXIT_MANUAL)
        # candidates: under half of baseline with no evidence (benchings etc.), for context
        for g, pid in e_all:
            r = sn[(sn.game_id == g) & (sn.pid == pid)].iloc[0]
            if int(r.season) not in seasons: continue
            base = float(sn[(sn.pid == pid) & (sn.game_id != g)].offense_pct.median())
            rows.append(dict(season=int(r.season), week=int(r.week), team=team, n=names.get(pid, pid), pos=pos.get(pid, ''), pct=float(r.offense_pct),
                             base=base, pbp=(g, pid) in e_pbp, rep=(g, pid) in e_rep, man=(g, pid) in e_man))
    print('season', S, 'done', file=sys.stderr, flush=True)
F = pd.DataFrame(rows).drop_duplicates(['season', 'week', 'team', 'n']).sort_values(['season', 'week', 'team'])
F['rule'] = np.select([F.pbp & F.rep, F.pbp, F.rep], ['pbp+report', 'pbp only', 'report only'], 'manual only')
print('Early injury exits flagged, by season and rule (a flag can have more than one kind of evidence)')
print(F.groupby(['season', 'rule']).size().unstack(fill_value=0).to_string())
print('\nby position:', F.groupby('pos').size().to_dict(), '| per team-season:', round(len(F[F.season < 2026]) / (32 * 4), 2))
print(f"\nsnap share in the flagged game: median {F.pct.median():.2f}; his baseline median {F.base.median():.2f}")
print('\nRandom sample of 20 (seed 7) to eyeball:')
print(F.sample(20, random_state=7).sort_values(['season', 'week']).to_string(index=False, formatters={'pct': '{:.2f}'.format, 'base': '{:.2f}'.format}))
print('\nAll 2026 flags:'); print(F[F.season == 2026].to_string(index=False, formatters={'pct': '{:.2f}'.format, 'base': '{:.2f}'.format}))
F.to_csv(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flags.csv'), index=False)
