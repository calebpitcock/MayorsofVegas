"""This week's game-model margins and DraftKings game lines, attached to the slate as g.gm and g.dk.
The game model never touches the player simulation."""
import json, sys, os, numpy as np, pandas as pd
sys.path.insert(0, '..'); sys.path.insert(0, '.')
import ratings2 as rt, model2, model3, market
P = dict(HG=14.0, CARRY=0.85, M0=3.0); QP = dict(QHL=1500.0, QCARRY=0.8, QM0=100.0, QPRIOR=-0.02)
K_LEAN = 0.10          # lean toward the model vs DraftKings' line. Fitted vs closing lines 2016-25: 0.17 ± 0.08; set conservatively (close_eval3.py)
ANCHOR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'anchor.json')))   # win/cover rates per point, ml_anchor.py
FULL = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'}
def main(slate_path):
    slate = json.load(open(slate_path)); ov = json.load(open('../overrides.json')); WEEK = ov['week']; SEASON = 2026
    # 1) fitted margin model on every completed season
    D = model3.add(model2.build(P, QP), model3.MP)
    tr = D[(D.season < SEASON + 1) & (D.week >= 3)]; sw = 0.5 ** ((SEASON - tr.season) / 8.0)
    cols = model3.F3; A = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols]); Wt = sw.values[:, None]
    w = np.linalg.solve((A * Wt).T @ A + np.diag([0] + [1] * len(cols)), (A * Wt).T @ tr.result.values)
    # 2) ratings as of now
    _, st = rt.team_ratings(**P); _, _, qs, used = rt.qb_ratings(**QP)
    T0 = rt.T0; mu = T0[T0.season == SEASON][rt.STATS].mean().values
    def team(t):
        s = st[t]; carry = P['CARRY'] if s['season'] != SEASON else 1.0
        o = (s['so'] * carry + P['M0'] * mu) / (s['wo'] * carry + P['M0']) - mu; d = (s['sd'] * carry + P['M0'] * mu) / (s['wd'] * carry + P['M0']) - mu
        return o, d
    import nfl_build as nb
    b = nb.Builder(SEASON); R = b.R
    name2pid = {v: k for k, v in R.full_name.dropna().items()}
    def qbr(pid):
        s = qs.get(pid)
        if s is None: return QP['QPRIOR'] - 0.08
        c = QP['QCARRY'] if s['season'] != SEASON else 1.0
        return (s['x'] * c + QP['QM0'] * QP['QPRIOR']) / (s['w'] * c + QP['QM0'])
    G = pd.read_csv('../../data/games.csv'); G = G[(G.season == SEASON) & (G.week == WEEK)]
    Gm = market.load_games(); Gm = Gm[(Gm.season < SEASON) | (Gm.week < WEEK)]          # lines of games already played
    _, mstate = market.ratings(Gm, **model3.MP); mr, _ = market.live(mstate, SEASON)
    y2 = lambda pid: 1.0 if model3.career_year(pid, SEASON) == 1 else 0.0
    dk = pd.read_csv('../../data/dk_game_lines_latest.csv'); dk = dk[dk.Bookmaker == 'DraftKings']
    for g in slate['games']:
        h, a = g['home'], g['away']; r = G[(G.home_team == h) & (G.away_team == a)]
        if r.empty: continue
        r = r.iloc[0]
        qh = name2pid.get(ov['STARTER'].get(h)) or b.starter(h, WEEK); qa = name2pid.get(ov['STARTER'].get(a)) or b.starter(a, WEEK)
        (oh, dh), (oa, da) = team(h), team(a)
        diff = (oh - da) - (oa - dh)
        rh, ra = qbr(qh), qbr(qa)
        uh = used[h]['x'] / used[h]['w'] if h in used and used[h]['w'] > 0 else -0.02
        ua = used[a]['x'] / used[a]['w'] if a in used and used[a]['w'] > 0 else -0.02
        f = dict(epa=diff[0], pepa=diff[1], repa=diff[2], sr=diff[3], qb=rh - ra, qbd=(rh - uh) - (ra - ua),
                 rest=float(np.clip(r.home_rest - r.away_rest, -7, 7)), div=int(r.div_game), neutral=int(r.location == 'Neutral'),
                 mkt=mr[h] - mr[a], qb2=y2(qh) - y2(qa))
        m = float(w[0] + sum(w[i + 1] * f[c] for i, c in enumerate(cols)))
        why = []
        qbpts = w[1 + cols.index('qb')] * f['qb'] + w[1 + cols.index('qbd')] * f['qbd']
        if abs(qbpts) >= 1.5: why.append(f"quarterbacks worth {abs(qbpts):.1f} pts to {h if qbpts > 0 else a}")
        effpts = sum(w[1 + cols.index(c)] * f[c] for c in ('epa', 'pepa', 'repa', 'sr'))
        mpts = w[1 + cols.index('mkt')] * f['mkt']
        if abs(mpts) >= 1.5: why.append(f"team strength {abs(mpts):.1f} pts to {h if mpts > 0 else a}")
        if abs(effpts) >= 1.5: why.append(f"recent efficiency {abs(effpts):.1f} pts to {h if effpts > 0 else a}")
        if f['qb2']: why.append(f"second-year QB for {h if f['qb2'] > 0 else a}")
        if f['rest']: why.append(f"rest {'+' if f['rest'] > 0 else ''}{int(f['rest'])} days for {h}")
        g['gm'] = dict(m=round(m, 2), qbH=R.loc[qh, 'full_name'] if qh in R.index else None, qbA=R.loc[qa, 'full_name'] if qa in R.index else None, why='; '.join(why))
        # DraftKings lines if posted, else the nflverse consensus line
        d = dk[(dk.Home.map(FULL) == h) & (dk.Away.map(FULL) == a)]
        if len(d):
            sp = d[d.Market == 'spreads']; ml = d[d.Market == 'h2h']
            hs = sp[sp['Team / Side'].map(FULL) == h].iloc[0]; as_ = sp[sp['Team / Side'].map(FULL) == a].iloc[0]
            g['dk'] = dict(src='dk', spread=float(hs.Line), spo=dict(home=int(hs['American Odds']), away=int(as_['American Odds'])),
                           ml=dict(home=int(ml[ml['Team / Side'].map(FULL) == h]['American Odds'].iloc[0]), away=int(ml[ml['Team / Side'].map(FULL) == a]['American Odds'].iloc[0])),
                           asOf=str(d['Last Update'].max()))
        else:
            g['dk'] = dict(src='consensus', spread=-float(r.spread_line), spo=dict(home=int(r.home_spread_odds), away=int(r.away_spread_odds)),
                           ml=dict(home=int(r.home_moneyline), away=int(r.away_moneyline)))
        print(f"{a}@{h}: model {h} {m:+.1f} | line {h} {-g['dk']['spread']:+.1f} ({g['dk']['src']}) | {g['gm']['why']}")
    slate['gmfit'] = dict(k=K_LEAN, b=ANCHOR['b'], slope=ANCHOR['slope'], coef=dict(zip(['hfa'] + cols, map(float, w))))
    json.dump(slate, open(slate_path, 'w'))
if __name__ == '__main__': main(sys.argv[1])
