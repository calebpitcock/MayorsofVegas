"""Does a receiver's own man/zone (and blitz) target split, times the opponent's man (blitz) rate, predict his target share
beyond the model's share? Everything from data before the game. Rows: role_{S}.csv (model share 'rec' before role
correction, actual share 'at'), 2023-25, held out one season at a time."""
import pandas as pd, numpy as np
P = pd.read_parquet('plays.parquet'); POS = pd.read_csv('/tmp/claude-0/-home-user-MayorsofVegas/90b2c212-0a48-567c-b98b-0f99669387f7/scratchpad/data/players.csv', usecols=['gsis_id','position']).set_index('gsis_id').position.replace({'FB':'RB'}); T = P[(P.play_type == 'pass') & (P.pass_attempt == 1) & (P.sack.fillna(0) == 0) & P.receiver_player_id.notna()].copy()
R = pd.concat([pd.read_csv(f'/home/user/MayorsofVegas/endzone-sim/role_{s}.csv') for s in (2023, 2024, 2025)])
K_P, K_D = 40.0, 150.0
def window(S, w):
    return T[((T.season == S) & (T.week < w)) | (T.season == S - 1)]
def feats(S, w, key):
    X = window(S, w); X = X[X[key].notna()]; lg = X[key].mean()
    team = X.groupby(['game_id', 'posteam', key]).size().rename('tt').reset_index()
    pl = X.groupby(['game_id', 'posteam', 'receiver_player_id', key]).size().rename('pt').reset_index()
    games = pl[['game_id', 'receiver_player_id']].drop_duplicates()
    tp = games.merge(team, on='game_id')                                    # team targets in the games the player was targeted
    a = tp.groupby(['receiver_player_id', key]).tt.sum().unstack(fill_value=0); b = pl.groupby(['receiver_player_id', key]).pt.sum().unstack(fill_value=0)
    a, b = a.reindex(columns=[0.0, 1.0], fill_value=0), b.reindex(index=a.index, columns=[0.0, 1.0], fill_value=0)
    s_all = ((b[0.0] + b[1.0]) / (a[0.0] + a[1.0]).clip(lower=1)).clip(lower=1e-3)
    # position-level split: share of targets in key=1 vs key=0 plays, relative to overall, by position
    X2 = X.assign(rp=X.receiver_player_id.map(POS)); pz = X2.groupby(key).rp.value_counts(normalize=True).unstack(); ov = X2.rp.value_counts(normalize=True)
    q1 = (pz.loc[1.0] / ov).to_dict(); q0 = (pz.loc[0.0] / ov).to_dict()
    pp = pd.Series(a.index.map(lambda i: POS.get(i)), index=a.index)
    p1 = pp.map(q1).fillna(1.0); p0 = pp.map(q0).fillna(1.0)
    r1 = ((b[1.0] + K_P * s_all * p1) / (a[1.0] + K_P)) / s_all; r0 = ((b[0.0] + K_P * s_all * p0) / (a[0.0] + K_P)) / s_all
    d = X.groupby('defteam')[key].agg(['sum', 'count']); drate = (d['sum'] + K_D * lg) / (d['count'] + K_D)
    return r1, r0, drate, lg
rows = []
for S in (2023, 2024, 2025):
    for w in sorted(R[R.season == S].week.unique()):
        sub = R[(R.season == S) & (R.week == w) & R.pos.isin(['WR', 'TE', 'RB'])].copy()
        if not len(sub): continue
        opp = {}
        g = P[(P.season == S) & (P.week == w)][['game_id', 'posteam', 'defteam']].drop_duplicates()
        for r in g.itertuples(): opp[(r.game_id, r.posteam)] = r.defteam
        sub['opp'] = [opp.get((a, t)) for a, t in zip(sub.game_id, sub.team)]
        for key in ('man', 'blitz'):
            r1, r0, drate, lg = feats(S, w, key)
            m1 = sub.pid.map(r1); m0 = sub.pid.map(r0)
            m1 = m1.fillna(sub.pid.map(lambda i: 1.0)); m0 = m0.fillna(1.0); dd = sub.opp.map(drate).fillna(lg)
            sub[f'mult_{key}'] = (dd * m1 + (1 - dd) * m0) / (lg * m1 + (1 - lg) * m0)
        rows.append(sub)
    print(S, flush=True)
X = pd.concat(rows); X['y'] = X['at'] - X['rec']
for key in ('man', 'blitz'): X[f'f_{key}'] = X.rec * (X[f'mult_{key}'] - 1)
X.to_parquet('matchup_rows_pos.parquet')
print('multiplier spread: man sd', X.mult_man.std().round(3), 'blitz sd', X.mult_blitz.std().round(3))
for pos in (['WR', 'TE', 'RB'], ['WR'], ['TE'], ['RB']):
    D = X[X.pos.isin(pos)]
    for cols in (['f_man'], ['f_blitz'], ['f_man', 'f_blitz']):
        base, new, coefs = [], [], []
        for S in (2023, 2024, 2025):
            tr, te = D[D.season != S], D[D.season == S]
            A = np.c_[np.ones(len(tr)), tr[cols].values]; w_ = np.linalg.lstsq(A, tr.y.values, rcond=None)[0]
            pb = np.full(len(te), np.c_[np.ones(len(tr))].T @ tr.y.values / len(tr))            # intercept-only baseline (same bias fix)
            pn = np.c_[np.ones(len(te)), te[cols].values] @ w_
            base.append(np.mean((te.y - pb) ** 2)); new.append(np.mean((te.y - pn) ** 2)); coefs.append(w_[1:].round(2))
        print(f"{'/'.join(pos):8s} {'+'.join(cols):14s} held-out MSE change: " + ', '.join(f"{s} {100*(n-b)/b:+.2f}%" for s, b, n in zip((2023, 2024, 2025), base, new)) + f"  coef {coefs}")
