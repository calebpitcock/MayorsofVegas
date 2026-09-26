"""Walk-forward margin model on ratings2; returns out-of-sample predictions per season."""
import numpy as np, pandas as pd, ratings2 as rt
G = pd.read_csv('../../data/games.csv'); G = G[(G.game_type == 'REG') & (G.season >= 2013) & G.result.notna()].copy()
for c in ('home_team', 'away_team'): G[c] = G[c].replace({'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'})
F = ['epa', 'pepa', 'repa', 'sr', 'qb', 'qbd', 'rest', 'div', 'neutral']
def build(tp, qp):
    pre, _ = rt.team_ratings(**tp); qpre, upre, _, _ = rt.qb_ratings(**qp)
    rows = []
    for g in G.itertuples():
        h, a = pre.get((g.game_id, g.home_team)), pre.get((g.game_id, g.away_team))
        if h is None or a is None: continue
        qh = qpre.get((g.game_id, g.home_qb_id), qp.get('QPRIOR', -0.02) - 0.08); qa = qpre.get((g.game_id, g.away_qb_id), qp.get('QPRIOR', -0.02) - 0.08)
        uh, ua = upre.get((g.game_id, g.home_team), -0.02), upre.get((g.game_id, g.away_team), -0.02)
        dh = (h[0] + a[1]) - (a[0] + h[1])      # offense EPA gained + opponent defense EPA allowed (defense ratings are EPA ALLOWED)
        rows.append(dict(game_id=g.game_id, season=g.season, week=g.week, result=g.result, spread_line=g.spread_line, home_team=g.home_team, away_team=g.away_team,
                         home_moneyline=g.home_moneyline, away_moneyline=g.away_moneyline,
                         epa=dh[0], pepa=dh[1], repa=dh[2], sr=dh[3], qb=qh - qa, qbd=(qh - uh) - (qa - ua),
                         rest=np.clip(g.home_rest - g.away_rest, -7, 7), div=g.div_game, neutral=int(g.location == 'Neutral')))
    return pd.DataFrame(rows)
def walk(D, S0, S1, RHL=4.0, l2=1.0, cols=F):
    out = []
    for S in range(S0, S1 + 1):
        tr = D[(D.season < S) & (D.week >= 3)]; te = D[D.season == S].copy()
        sw = 0.5 ** ((S - 1 - tr.season) / RHL)
        A = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols]); W = sw.values[:, None]
        w = np.linalg.solve((A * W).T @ A + l2 * np.diag([0] + [1] * len(cols)), (A * W).T @ tr.result.values)
        te['m'] = np.column_stack([np.ones(len(te))] + [te[c] for c in cols]) @ w
        out.append(te.assign(hfa=w[0], **{f'w_{c}': w[i + 1] for i, c in enumerate(cols)}))
    return pd.concat(out)
