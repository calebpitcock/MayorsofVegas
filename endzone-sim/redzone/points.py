"""Redzone Desk scoreboard: each game's margin and total from the model alone (no sportsbook number goes in).
  margin = game model with the books' rating weighted 0 (gm/game_live.py, EZBOOKSW=0: offense, defense, special teams,
           QB, rest, division, home field)
         + team-vs-team history (last 3 meetings), coach-vs-coach history (last 3), offense-vs-defense history
         - a new-head-coach reset of that team's offense/defense rating
  total  = a points regression on opponent-adjusted offense and defense ratings (fitted 2016-25), plus QB and
           offense-vs-defense history.
The consensus line is kept only as the number a pick is measured against (g.line); it never feeds the model.
Run from gm/ after game_live.py.  Usage: python3 ../redzone/points.py ../slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..')); sys.path.insert(0, '.')
import ratings2 as rt
CFG = json.load(open(os.environ.get('EZRZCFG') or os.path.join(HERE, 'config.json')))
SEASON = 2026; P = dict(HG=14.0, CARRY=0.85, M0=3.0); HFA = 1.8
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}

def games():
    G = pd.read_csv('../../data/games.csv')
    for c in ('home_team', 'away_team'): G[c] = G[c].replace(REP)
    return G

def fit_points(pre, G):
    rows = []
    g = G[(G.season.between(2016, 2025)) & (G.game_type == 'REG') & G.home_score.notna()]
    for r in g.itertuples():
        H, A = pre.get((r.game_id, r.home_team)), pre.get((r.game_id, r.away_team))
        if H is None or A is None: continue
        home = 0.0 if r.location == 'Neutral' else 1.0
        rows.append((r.season, r.home_score, H[0][0], H[0][3], A[1][0], A[1][3], home))
        rows.append((r.season, r.away_score, A[0][0], A[0][3], H[1][0], H[1][3], 0.0))
    X = pd.DataFrame(rows, columns=['season', 'pts', 'oe', 'os', 'de', 'ds', 'home'])
    X['lg'] = X.groupby('season').pts.transform('mean')
    A = np.column_stack([np.ones(len(X)), X.oe, X.os, X.de, X.ds, X.home]); w = 0.5 ** ((2025 - X.season.values) / 6.0)
    coef = np.linalg.solve((A * w[:, None]).T @ A + np.diag([0, 1, 1, 1, 1, 0]), (A * w[:, None]).T @ (X.pts - X.lg).values)
    return coef

def history(G, h, a, ch, ca, week=99):
    past = G[G.home_score.notna() & ((G.season < SEASON) | (G.week < week))].sort_values(['season', 'week'])
    tv = past[((past.home_team == h) & (past.away_team == a)) | ((past.home_team == a) & (past.away_team == h))].tail(3)
    # margin for h, venue removed
    tm = [(r.result - (0 if r.location == 'Neutral' else HFA)) * (1 if r.home_team == h else -1) for r in tv.itertuples()]
    cv = past[((past.home_coach == ch) & (past.away_coach == ca)) | ((past.home_coach == ca) & (past.away_coach == ch))].tail(3)
    cm = [(r.result - (0 if r.location == 'Neutral' else HFA)) * (1 if r.home_coach == ch else -1) for r in cv.itertuples()]
    # offense vs this defense: points in the last 3 meetings minus that team's average that season
    avg = {}
    for s in tv.season.unique():
        x = past[past.season == s]
        for t in (h, a):
            pts = pd.concat([x[x.home_team == t].home_score, x[x.away_team == t].away_score])
            avg[(s, t)] = pts.mean()
    od = {h: [], a: []}
    for r in tv.itertuples():
        od[r.home_team].append(r.home_score - avg[(r.season, r.home_team)]); od[r.away_team].append(r.away_score - avg[(r.season, r.away_team)])
    return dict(team=tm, teamGames=[f"{int(r.season)}: {r.away_team} {int(r.away_score)} @ {r.home_team} {int(r.home_score)}" for r in tv.itertuples()],
                coach=cm, coachN=len(cm), od={k: (float(np.mean(v)) if v else 0.0) for k, v in od.items()})

def main(path, week):
    S = json.load(open(path)); G = games()
    pre, st = rt.team_ratings(**P)
    coef = fit_points(pre, G)
    T0 = rt.T0; mu = T0[T0.season == SEASON][rt.STATS].mean().values
    def team(t):
        s = st[t]; carry = P['CARRY'] if s['season'] != SEASON else 1.0
        o = (s['so'] * carry + P['M0'] * mu) / (s['wo'] * carry + P['M0']) - mu; d = (s['sd'] * carry + P['M0'] * mu) / (s['wd'] * carry + P['M0']) - mu
        return o, d
    done = G[(G.season == SEASON) & G.home_score.notna()]
    lg_now = pd.concat([done.home_score, done.away_score]).mean()
    last = G[(G.season == SEASON - 1) & G.home_score.notna()]; lg_last = pd.concat([last.home_score, last.away_score]).mean()
    n_now = len(done); lg = (n_now * lg_now + 64 * lg_last) / (n_now + 64)
    TV = {r['t']: r for r in S.get('teams', [])}
    coaches = G[G.season == SEASON]; prev = G[G.season == SEASON - 1]
    def coach(t, gg): x = gg[(gg.home_team == t) | (gg.away_team == t)].sort_values('week'); r = x.iloc[-1]; return r.home_coach if r.home_team == t else r.away_coach
    for g in S['games']:
        h, a = g['home'], g['away']
        r = G[(G.season == SEASON) & (G.week == week) & (G.home_team == h) & (G.away_team == a)].iloc[0]
        neu = r.location == 'Neutral'
        oh, dh = team(h); oa, da = team(a)
        pts_h = lg + coef[0] + coef[1] * oh[0] + coef[2] * oh[3] + coef[3] * da[0] + coef[4] * da[3] + (0 if neu else coef[5])
        pts_a = lg + coef[0] + coef[1] * oa[0] + coef[2] * oa[3] + coef[3] * dh[0] + coef[4] * dh[3]
        qh, qa = TV.get(h, {}).get('qb', 0.0), TV.get(a, {}).get('qb', 0.0)
        total = pts_h + pts_a + CFG['qb_total_weight'] * (qh + qa)
        m = g['gm']['m']
        why = [x for x in (g['gm'].get('why') or '').split('; ') if x]
        hs = history(G, h, a, r.home_coach, r.away_coach, week)
        adj = []
        if hs['team'] and CFG['team_history']:          # a factor set to 0 is left out of the reasons too
            v = CFG['team_history'] * float(np.mean(hs['team'])); m += v
            adj.append(dict(k='team', pts=round(v, 2), text=f"Last {len(hs['team'])} meetings: {h if np.mean(hs['team']) > 0 else a} by {abs(np.mean(hs['team'])):.1f} a game on average ({'; '.join(hs['teamGames'])})"))
        if hs['coach'] and r.home_coach != r.away_coach and CFG['coach_history']:
            v = CFG['coach_history'] * float(np.mean(hs['coach'])); m += v
            adj.append(dict(k='coach', pts=round(v, 2), text=f"{r.home_coach} vs {r.away_coach}: {r.home_coach if np.mean(hs['coach']) > 0 else r.away_coach}'s teams by {abs(np.mean(hs['coach'])):.1f} a game in their last {hs['coachN']} meetings"))
        oh_, oa_ = CFG['offense_vs_defense_history'] * hs['od'][h], CFG['offense_vs_defense_history'] * hs['od'][a]
        if (hs['od'][h] or hs['od'][a]) and CFG['offense_vs_defense_history']:
            m += oh_ - oa_; total += oh_ + oa_
            adj.append(dict(k='od', pts=round(oh_ - oa_, 2), text=f"Scoring in recent meetings vs season average: {h} {hs['od'][h]:+.1f}, {a} {hs['od'][a]:+.1f} points"))
        for t, sign in ((h, 1), (a, -1)):
            if coach(t, coaches) != coach(t, prev) and t in TV:
                v = -sign * CFG['new_coach_rating_reset'] * (TV[t]['off'] + TV[t]['dfn'])
                if abs(v) >= .05:
                    m += v; adj.append(dict(k='newhc', pts=round(v, 2), text=f"New head coach for {t} ({coach(t, coaches)}): {int(100 * CFG['new_coach_rating_reset'])}% of its offense/defense rating reset toward average ({'-' if v * sign < 0 else '+'}{abs(v):.1f} pts)"))
        # football matchups (football.py g.rzx): pass rush vs protection, run blocking, big plays, play style, turnovers
        rzx = g.get('rzx') or {}
        if rzx:
            wm = CFG.get('stats', {}).get('matchup_points', 1.0); d = {}
            for side, sgn in (('home', 1), ('away', -1)):
                x = rzx[side]; mult = x['pass'] ** 0.55 * x['run'] ** 0.45 * x['exp'] ** 0.2 / (x['int'] ** 0.08 * x['fum'] ** 0.05)
                d[side] = wm * (mult - 1) * (total + sgn * m) / 2
            m += d['home'] - d['away']; total += d['home'] + d['away']
            adj.append(dict(k='stats', pts=round(d['home'] - d['away'], 2), text=f"Matchup stats (pressure, blocking, big plays, play style, turnovers): {h} {d['home']:+.1f} pts, {a} {d['away']:+.1f} pts"))
        total = float(max(24.0, total))
        line = g.get('dk') or {}
        g['line'] = dict(spread=line.get('spread', g['spread']), total=g['total'], ml=line.get('ml', g.get('ml')), src=line.get('src', 'consensus'))
        g['spread'], g['total'], g['spreadSrc'], g['totalSrc'] = round(-m, 2), round(total, 1), 'model', 'model'
        g['rzg'] = dict(margin=round(m, 2), total=round(total, 1), base=round(g['gm']['m'], 2), why=why, adj=adj,
                        pts=dict(home=round((total + m) / 2, 1), away=round((total - m) / 2, 1)),
                        coaches=dict(home=r.home_coach, away=r.away_coach))
        print(f"{a}@{h}: model {h} {m:+.1f}, total {total:.1f} | line {h} {-g['line']['spread']:+.1f}, {g['line']['total']} | " + ' / '.join(x['text'][:60] for x in adj))
    json.dump(S, open(path, 'w'))

if __name__ == '__main__': main(sys.argv[1], int(sys.argv[2]))
