"""Were the flagged games real early exits? nflverse participation (2022-25) lists every offensive player on every
snap. For each flagged player-game: his share of the team's snaps in the first quarter vs after his last snap.
A real exit = he was on the field early and then never again (last snap before the 4th quarter and at least 40% of the
team's snaps after it). Reads flags.csv from flags.py. Usage: python3 audit/early_exit/verify.py"""
import os, numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); D = os.path.join(H, '..', '..', '..', 'data')
F = pd.read_csv(f'{H}/flags.csv'); F = F[F.season <= 2025]
R = pd.concat([pd.read_csv(f'{D}/roster_{s}.csv', usecols=['season', 'full_name', 'gsis_id', 'team']) for s in range(2022, 2026)])
out = []
for s in range(2022, 2026):
    pa = pd.read_parquet(f'{D}/pbp_participation_{s}.parquet', columns=['nflverse_game_id', 'play_id', 'possession_team', 'offense_players'])
    pb = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'play_id', 'week', 'qtr', 'play_type', 'season_type'], low_memory=False)
    pb = pb[(pb.season_type == 'REG') & pb.play_type.isin(['run', 'pass'])]
    pa = pa.rename(columns={'nflverse_game_id': 'game_id'}).merge(pb, on=['game_id', 'play_id'])
    for r in F[F.season == s].itertuples():
        ids = R[(R.season == s) & (R.full_name == r.n)].gsis_id.unique()
        g = pa[(pa.week == r.week) & (pa.possession_team.replace({'LA': 'LA'}) == r.team)].sort_values('play_id')
        if not len(g) or not len(ids): out.append(dict(**r._asdict(), found=False)); continue
        on = g.offense_players.fillna('').apply(lambda x: any(i in x for i in ids)).values
        if not on.any(): out.append(dict(**r._asdict(), found=True, snaps=0, last_frac=0.0, q1=0.0, exit=False)); continue
        last = np.where(on)[0].max(); frac_after = 1 - (last + 1) / len(g)
        q1 = on[g.qtr.values == 1].mean() if (g.qtr.values == 1).any() else np.nan
        out.append(dict(**r._asdict(), found=True, snaps=int(on.sum()), last_qtr=int(g.qtr.values[last]), after=round(frac_after, 2), q1=round(float(q1), 2),
                        exit=bool(frac_after >= .4 and g.qtr.values[last] <= 3)))
V = pd.DataFrame(out); V = V[V.found.astype(bool)].copy(); V['exit'] = V.exit.astype(bool)
print(f'flags 2022-25 matched to participation: {len(V)} of {len(F)}')
print('Share that were real exits (on the field early, then gone for 40%+ of the game):')
print(V.groupby('rule').agg(n=('exit', 'size'), real_exit=('exit', 'mean'), q1_on=('q1', 'mean')).round(2).to_string())
print('\nall rules:', round(V.exit.mean(), 2))
print('\nreport-only flags that were NOT exits (sample of 12):')
print(V[(V.rule == 'report only') & ~V.exit].sample(12, random_state=3)[['season', 'week', 'team', 'n', 'pos', 'pct', 'base', 'q1', 'last_qtr', 'after']].to_string(index=False))
V.to_csv(f'{H}/verify.csv', index=False)
