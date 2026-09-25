"""This week's game-model margins and DraftKings game lines, attached to the slate as g.gm and g.dk.
The game model never touches the player simulation."""
import json, sys, os, numpy as np, pandas as pd
sys.path.insert(0, '..'); sys.path.insert(0, '.')
import ratings2 as rt, model2, model3, model4, market
P = dict(HG=14.0, CARRY=0.85, M0=3.0); QP = dict(QHL=1500.0, QCARRY=0.8, QM0=100.0, QPRIOR=-0.02)
K_LEAN = 0.10          # lean toward the model vs DraftKings' line. Fitted vs closing lines 2016-25: 0.17 ± 0.08; set conservatively (close_eval3.py)
ANCHOR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'anchor.json')))   # win/cover rates per point, ml_anchor.py
FULL = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'}
def main(slate_path):
    slate = json.load(open(slate_path)); ov = json.load(open('../overrides.json')); WEEK = ov['week']; SEASON = 2026
    # 1) fitted margin model on every completed season
    D = model4.add(model2.build(P, QP))
    tr = D[(D.season < SEASON + 1) & (D.week >= 3)]; sw = 0.5 ** ((SEASON - tr.season) / 8.0)
    cols = model4.F4; A = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols]); Wt = sw.values[:, None]
    w = np.linalg.solve((A * Wt).T @ A + np.diag([0] + [1] * len(cols)), (A * Wt).T @ tr.result.values)
    # stats-only view (no books rating): how good each team is on the field, for the Stats rank and the off/def/ST columns
    cols2 = [c for c in cols if c != 'mkt']; A2 = np.column_stack([np.ones(len(tr))] + [tr[c] for c in cols2])
    w2 = np.linalg.solve((A2 * Wt).T @ A2 + np.diag([0] + [1] * len(cols2)), (A2 * Wt).T @ tr.result.values); c2 = {c: w2[1 + i] for i, c in enumerate(cols2)}
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
    # ---- team values: every team's worth in points against an average team on a neutral field. The game model is
    # linear in home-minus-away features, so each team has its own value and a game's fair margin is exactly
    # home field + value(home) - value(away) + rest/division terms. Parts: the books' rating, this week's QB, offense,
    # defense and special teams (opponent-adjusted play-by-play), plus a small public-opinion share when available.
    ci = {c: w[1 + i] for i, c in enumerate(cols)}
    _, stst = model4.st_ratings()
    def st_of(t):
        x = stst.get(t)
        if not x: return 0.0
        c = model4.ST['CARRY'] if x['season'] != SEASON else 1.0
        return x['x'] * c / (x['w'] * c + model4.ST['M0'])
    TEAMS = sorted(mr)
    def starter(t): return name2pid.get(ov['STARTER'].get(t)) or b.starter(t, WEEK)
    parts = {}
    for t in TEAMS:
        o, dd = team(t); q = starter(t); rq = qbr(q); u = used[t]['x'] / used[t]['w'] if t in used and used[t]['w'] > 0 else -0.02
        parts[t] = dict(books=ci['mkt'] * mr[t], off=ci['off_epa'] * o[0] + ci['off_sr'] * o[3], dfn=-(ci['def_epa'] * dd[0] + ci['def_sr'] * dd[3]),
                        st=ci['st'] * st_of(t), qb=ci['qb'] * rq + ci['qbd'] * (rq - u) + ci['qb2'] * y2(q),
                        qbName=R.loc[q, 'full_name'] if q in R.index else None, qbid=q,
                        off2=c2['off_epa'] * o[0] + c2['off_sr'] * o[3], dfn2=-(c2['def_epa'] * dd[0] + c2['def_sr'] * dd[3]), st2=c2['st'] * st_of(t),
                        qbS=c2['qb'] * rq + c2['qbd'] * (rq - u) + c2['qb2'] * y2(q))
    K = ('books', 'qb', 'off', 'dfn', 'st')
    mean = {k: float(np.mean([parts[t][k] for t in TEAMS])) for k in K + ('off2', 'dfn2', 'st2', 'qbS')}
    for t in TEAMS:
        for k in K + ('off2', 'dfn2', 'st2', 'qbS'): parts[t][k] -= mean[k]
        parts[t]['model'] = sum(parts[t][k] for k in K); parts[t]['stats'] = parts[t]['off2'] + parts[t]['dfn2'] + parts[t]['st2']
    # public opinion (power rankings fetched at refresh time into public_rank.json); fixed small weight, untestable
    PUBW = 0.10
    pf = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'public_rank.json')
    pub = json.load(open(pf)) if os.path.exists(pf) else None
    if pub and (pub.get('season'), pub.get('week')) != (SEASON, WEEK): pub = None          # stale: last week's rankings don't count
    ladder = sorted((parts[t]['model'] for t in TEAMS), reverse=True)                    # public rank r -> the r-th best model value
    for t in TEAMS:
        r = (pub or {}).get('ranks', {}).get(t)
        parts[t]['public'] = ladder[r - 1] if r else None
        parts[t]['value'] = (1 - PUBW) * parts[t]['model'] + PUBW * parts[t]['public'] if r else parts[t]['model']
    rk = lambda key: {t: i + 1 for i, t in enumerate(sorted(TEAMS, key=lambda t: -parts[t][key]))}
    rv, rb, rs = rk('value'), rk('books'), rk('stats')
    rows = [dict(t=t, rank=rv[t], value=round(parts[t]['value'], 1), books=round(parts[t]['books'], 1), qb=round(parts[t]['qb'], 1),
                 off=round(parts[t]['off2'], 1), dfn=round(parts[t]['dfn2'], 1), st=round(parts[t]['st2'], 1), stats=round(parts[t]['stats'], 1),
                 booksRank=rb[t], statsRank=rs[t], publicRank=(pub or {}).get('ranks', {}).get(t), qbName=parts[t]['qbName']) for t in TEAMS]
    rows.sort(key=lambda x: x['rank'])
    slate['teams'] = rows; slate['hfa'] = round(float(w[0]), 2)
    slate['public'] = dict(source=pub['source'], asOf=pub.get('asOf'), weight=PUBW) if pub else None
    FR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'flag_record.json')
    flags = json.load(open(FR)) if os.path.exists(FR) else None
    for g in slate['games']:
        h, a = g['home'], g['away']; r = G[(G.home_team == h) & (G.away_team == a)]
        if r.empty: continue
        r = r.iloc[0]
        qh, qa = parts[h]['qbid'], parts[a]['qbid']
        rest = float(np.clip(r.home_rest - r.away_rest, -7, 7)); neu = int(r.location == 'Neutral')
        m = float(w[0] + ci['neutral'] * neu + ci['rest'] * rest + ci['div'] * int(r.div_game) + parts[h]['value'] - parts[a]['value'])
        sv = lambda t: parts[t]['stats'] + parts[t]['qbS']          # stats view: on-field numbers and QB only, no books
        ms = float(w2[0] + c2['neutral'] * neu + c2['rest'] * rest + c2['div'] * int(r.div_game) + sv(h) - sv(a))
        why = []
        for k, lab in (('books', 'books rate'), ('qb', 'quarterback'), ('off', 'offense'), ('dfn', 'defense'), ('st', 'special teams')):
            x = parts[h][k] - parts[a][k]
            if abs(x) >= 1.5: why.append(f"{lab} {abs(x):.1f} pts to {h if x > 0 else a}")
        if rest: why.append(f"rest {'+' if rest > 0 else ''}{int(rest)} days for {h}")
        g['gm'] = dict(m=round(m, 2), ms=round(ms, 2), qbH=R.loc[qh, 'full_name'] if qh in R.index else None, qbA=R.loc[qa, 'full_name'] if qa in R.index else None, why='; '.join(why))
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
        print(f"{a}@{h}: ratings {h} {m:+.1f} stats {h} {ms:+.1f} | line {h} {-g['dk']['spread']:+.1f} ({g['dk']['src']}) | {g['gm']['why']}")
    slate['gmfit'] = dict(k=K_LEAN, b=ANCHOR['b'], slope=ANCHOR['slope'], coef=dict(zip(['hfa'] + cols, map(float, w))), flagAt=3.0, flagAtStats=5.0, flags=flags)
    for x in rows: print(f"{x['rank']:2d} {x['t']:3s} {x['value']:+5.1f} | books {x['books']:+5.1f} (#{x['booksRank']}) qb {x['qb']:+5.1f} | stats {x['stats']:+5.1f} #{x['statsRank']} (off {x['off']:+4.1f} def {x['dfn']:+4.1f} st {x['st']:+4.1f}) public #{x['publicRank']}  {x['qbName']}")
    json.dump(slate, open(slate_path, 'w'))
if __name__ == '__main__': main(sys.argv[1])
