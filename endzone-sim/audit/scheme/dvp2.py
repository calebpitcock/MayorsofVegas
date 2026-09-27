"""Defense vs position, the parts not yet measured: yards per target, catch rate and yards per catch allowed to RB/WR/TE,
and whether a defense's zone rate shifts where targets go (TE/RB underneath vs WR). Split-half (odd/even weeks)
reliability within a season, and season-to-season, 2016-25."""
import pandas as pd, numpy as np
D = '/home/user/MayorsofVegas/data'
pos = pd.read_csv(f'{D}/players.csv' if False else '/tmp/claude-0/-home-user-MayorsofVegas/90b2c212-0a48-567c-b98b-0f99669387f7/scratchpad/data/players.csv', usecols=['gsis_id', 'position']).set_index('gsis_id').position.replace({'FB': 'RB'})
fr = []
for s in range(2016, 2026):
    p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['season', 'season_type', 'week', 'defteam', 'play_type', 'pass_attempt', 'sack', 'two_point_attempt', 'receiver_player_id', 'complete_pass', 'receiving_yards'], low_memory=False)
    p = p[(p.season_type == 'REG') & (p.play_type == 'pass') & (p.pass_attempt == 1) & (p.sack.fillna(0) == 0) & (p.two_point_attempt.fillna(0) == 0) & p.receiver_player_id.notna()]
    fr.append(p)
T = pd.concat(fr); T['rp'] = T.receiver_player_id.map(pos); T = T[T.rp.isin(['RB', 'WR', 'TE'])]; T['y'] = T.receiving_yards.fillna(0)
lg = T.groupby(['season', 'rp']).agg(ypt=('y', 'mean'), cr=('complete_pass', 'mean'))
def rel(d):
    g = d.groupby(['defteam', 'season', 'rp']).agg(ypt=('y', 'mean'), cr=('complete_pass', 'mean'), n=('y', 'size'))
    g = g.join(lg, on=['season', 'rp'], rsuffix='_lg'); g['ypt'] -= g.ypt_lg; g['cr'] -= g.cr_lg; return g
o, e = rel(T[T.week % 2 == 1]), rel(T[T.week % 2 == 0]); J = o.join(e, lsuffix='_o', rsuffix='_e', how='inner')
F = rel(T).reset_index().sort_values(['defteam', 'rp', 'season'])
print('defense vs position                 split-half r   season->season r')
for k, lab in (('ypt', 'yards per target allowed'), ('cr', 'catch rate allowed')):
    for pp in ('RB', 'WR', 'TE'):
        j = J.xs(pp, level='rp'); r = np.corrcoef(j[k + '_o'], j[k + '_e'])[0, 1]
        f = F[F.rp == pp].copy(); f['prev'] = f.groupby('defteam')[k].shift(1); f = f.dropna(subset=['prev'])
        print(f"  {lab:28s} {pp}:  {r:+.2f}            {np.corrcoef(f[k], f.prev)[0, 1]:+.2f}")
# zone rate -> where targets go (charting 2022-25)
P = pd.read_parquet('plays.parquet'); X = P[(P.play_type == 'pass') & (P.pass_attempt == 1) & (P.sack.fillna(0) == 0) & P.receiver_player_id.notna() & P.man.notna()].copy()
X['rp'] = X.receiver_player_id.map(pos)
lgs = X.groupby('man').rp.value_counts(normalize=True).unstack(); print('\nleague target share by position vs coverage (2022-25):'); print(lgs.round(3).to_string())
