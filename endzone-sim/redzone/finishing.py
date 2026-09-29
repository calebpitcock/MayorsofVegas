"""Redzone Desk: finishing drives (TD vs field goal) and goal-line play-calling, measured and tested.
1. Red-zone TD rate: of an offense's drives that reach the 20, the share that end in a touchdown; and the same allowed
   by each defense. Without this, every team with the same projected points gets the same number of touchdowns.
2. Goal-line play-calling: each offense's pass rate inside the 10 (and each defense's faced), plus how the offense's
   QB takes carries near the goal line (sneaks and QB runs, FTN charting).
Test: weeks 1-3 plus last season (0.3) predict each team-game in weeks 4-18, 2022-2025, fitted on three seasons and
scored on the fourth, against the league average. Red-zone TD rate did not beat the league average game by game; at
the season level only the offense's LAST-season rate carries over (r 0.21), so only that is used, at its fitted slope.
Goal-line pass rate did beat it (3 of 4 seasons) and is used at its fitted weights.
Usage: python3 finishing.py test | python3 finishing.py slate.json WEEK"""
import json, os, sys, numpy as np, pandas as pd
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, '..'))
import nfl_build as nb
D = nb.D; REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA', 'LAR': 'LA'}
_P = {}

def pbp(s):
    if s not in _P:
        p = pd.read_csv(f'{D}/play_by_play_{s}.csv.gz', usecols=['game_id', 'play_id', 'season_type', 'week', 'posteam', 'defteam', 'drive', 'drive_inside20',
                        'fixed_drive_result', 'play_type', 'yardline_100', 'qb_dropback', 'two_point_attempt', 'rusher_player_id', 'qb_kneel'], low_memory=False)
        p = p[p.season_type == 'REG'].copy()
        for c in ('posteam', 'defteam'): p[c] = p[c].replace(REP)
        p['season'] = s; _P[s] = p
    return _P[s]

def team_games(s):
    """per (offense, defense, game): red-zone trips and TDs; goal-line (inside the 10) plays and passes."""
    p = pbp(s)
    dr = p[p.drive.notna()].groupby(['game_id', 'week', 'posteam', 'defteam', 'drive']).agg(rz=('drive_inside20', 'max'), res=('fixed_drive_result', 'first')).reset_index()
    dr = dr[dr.rz == 1]
    rz = dr.groupby(['game_id', 'week', 'posteam', 'defteam']).agg(trips=('rz', 'size'), td=('res', lambda r: (r == 'Touchdown').sum())).reset_index()
    gl = p[(p.yardline_100 <= 10) & p.play_type.isin(['run', 'pass']) & (p.two_point_attempt.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0)]
    gl = gl.groupby(['game_id', 'week', 'posteam', 'defteam']).agg(glp=('play_type', 'size'), glpass=('qb_dropback', 'sum')).reset_index()
    return rz.merge(gl, on=['game_id', 'week', 'posteam', 'defteam'], how='outer').fillna(0).assign(season=s)

def rates(s, w):
    """shrunk offense and defense rates from season s weeks < w (1.0) and s-1 (0.3), as deviations from the league."""
    a = pd.concat([team_games(s - 1).assign(wt=0.3), team_games(s)[lambda x: x.week < w].assign(wt=1.0)])
    for c in ('trips', 'td', 'glp', 'glpass'): a[c] = a[c] * a.wt
    lg_td = a.td.sum() / a.trips.sum(); lg_gl = a.glpass.sum() / a.glp.sum()
    out = {}
    for side, key in (('off', 'posteam'), ('def', 'defteam')):
        g = a.groupby(key)[['trips', 'td', 'glp', 'glpass']].sum()
        out[side] = dict(td=((g.td + 12 * lg_td) / (g.trips + 12) - lg_td).to_dict(), gl=((g.glpass + 25 * lg_gl) / (g.glp + 25) - lg_gl).to_dict(),
                         td_raw=(g.td / g.trips.replace(0, np.nan)).to_dict(), trips=g.trips.to_dict())
    return out, float(lg_td), float(lg_gl)

def dataset():
    rows = []
    for s in (2022, 2023, 2024, 2025):
        R, lt, lgl = rates(s, 4); t = team_games(s); t = t[t.week >= 4]
        for x in t.itertuples():
            rows.append(dict(season=s, trips=x.trips, glp=x.glp, y_td=(x.td / x.trips - lt) if x.trips else np.nan, y_gl=(x.glpass / x.glp - lgl) if x.glp else np.nan,
                             o_td=R['off']['td'].get(x.posteam, 0), d_td=R['def']['td'].get(x.defteam, 0),
                             o_gl=R['off']['gl'].get(x.posteam, 0), d_gl=R['def']['gl'].get(x.defteam, 0)))
    return pd.DataFrame(rows)

def fit(d, y, cols, wcol):
    d = d.dropna(subset=[y]); A = np.column_stack([d[c] for c in cols]); W = d[wcol].values
    return np.linalg.lstsq(A * np.sqrt(W)[:, None], d[y].values * np.sqrt(W), rcond=None)[0]

def season_slope():
    """Season level: does an offense's red-zone TD rate last season predict weeks 4-18 this season? (weeks 1-3 do not;
    defenses do not repeat at all: 2022-25 r = 0.21 offense last season, -0.11 weeks 1-3, 0.08 defense)"""
    xs, ys, ns = [], [], []
    for s in (2022, 2023, 2024, 2025):
        t = team_games(s); p = team_games(s - 1)
        r = t[t.week >= 4].groupby('posteam')[['trips', 'td']].sum(); q = p.groupby('posteam')[['trips', 'td']].sum()
        lr, lq = r.td.sum() / r.trips.sum(), q.td.sum() / q.trips.sum()
        for tm in r.index:
            if tm in q.index: xs.append(q.td[tm] / q.trips[tm] - lq); ys.append(r.td[tm] / r.trips[tm] - lr); ns.append(r.trips[tm])
    x, y, n = map(np.array, (xs, ys, ns))
    return float(np.sum(n * x * y) / np.sum(n * x * x)), float(np.corrcoef(x, y)[0, 1])

def test():
    d = dataset(); out = {}
    sl, r = season_slope(); out['redzone_td_season'] = dict(slope=round(sl, 3), r=round(r, 3)); print('red-zone TD rate, last season -> this season: slope %.3f r %.3f' % (sl, r))
    for name, y, cols, wc in (('redzone_td', 'y_td', ['o_td', 'd_td'], 'trips'), ('goal_line_pass', 'y_gl', ['o_gl', 'd_gl'], 'glp')):
        e0, e1 = [], []
        for hold in (2022, 2023, 2024, 2025):
            tr, te = d[d.season != hold], d[(d.season == hold)].dropna(subset=[y])
            b = fit(tr, y, cols, wc); pr = np.column_stack([te[c] for c in cols]) @ b
            e0.append(np.sqrt(np.average(te[y] ** 2, weights=te[wc]))); e1.append(np.sqrt(np.average((te[y] - pr) ** 2, weights=te[wc])))
        b = fit(d, y, cols, wc)
        # season-level check: does the team's prediction line up with its actual rate over weeks 4-18?
        out[name] = dict(coef=dict(zip(cols, map(float, b))), rmse_league=round(float(np.mean(e0)), 4), rmse_model=round(float(np.mean(e1)), 4),
                         by_season=[round(float(a), 4) for a in e1], league_by_season=[round(float(a), 4) for a in e0])
        print(name, json.dumps(out[name]))
    json.dump(out, open(os.path.join(HERE, 'finishing_fit.json'), 'w'), indent=1)

def live(path, week):
    S = json.load(open(path)); F = json.load(open(os.path.join(HERE, 'finishing_fit.json')))
    CFG = json.load(open(os.path.join(HERE, 'config.json'))); W = CFG.get('finishing', {}).get('weight', 1.0)
    R, lt, lgl = rates(2026, week)
    cg = F['goal_line_pass']['coef']
    q = team_games(2025).groupby('posteam')[['trips', 'td']].sum(); lq = q.td.sum() / q.trips.sum()
    last_dev = ((q.td / q.trips) - lq).to_dict(); last_rate = (q.td / q.trips).to_dict()
    # QBs near the goal line: share of the team's designed carries inside the 5 taken by its QBs (sneaks included)
    p = pd.concat([pbp(2025).assign(wt=0.3), pbp(2026)[lambda x: x.week < week].assign(wt=1.0)])
    R_ = nb.rosters(); qb = set(R_[R_.position == 'QB'].index)
    g5 = p[(p.play_type == 'run') & (p.yardline_100 <= 5) & p.rusher_player_id.notna() & (p.two_point_attempt.fillna(0) == 0) & (p.qb_kneel.fillna(0) == 0)]
    g5 = g5.assign(isqb=g5.rusher_player_id.isin(qb).astype(float))
    lqb = (g5.wt * g5.isqb).sum() / g5.wt.sum()
    qbshare = (((g5.wt * g5.isqb).groupby(g5.posteam).sum() + 10 * lqb) / (g5.wt.groupby(g5.posteam).sum() + 10)).to_dict()
    for g in S['games']:
        g.setdefault('rzx', {}); g['fin'] = {}
        for side, off, dfn in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            o_td, d_td = R['off']['td'].get(off, 0), R['def']['td'].get(dfn, 0); o_gl, d_gl = R['off']['gl'].get(off, 0), R['def']['gl'].get(dfn, 0)
            dev = W * F['redzone_td_season']['slope'] * last_dev.get(off, 0.0); glp = W * (cg['o_gl'] * o_gl + cg['d_gl'] * d_gl)
            g['rzx'].setdefault(side, {}); g['rzx'][side]['rzdev'] = round(float(dev), 4); g['rzx'][side]['glpass'] = round(float(glp), 4)
            g['fin'][side] = dict(offLast=round(float(last_rate.get(off, lq)), 3), lgLast=round(float(lq), 3), offRaw=R['off']['td_raw'].get(off), offTrips=round(R['off']['trips'].get(off, 0), 1),
                                  defTD=round(lt + d_td, 3), defRaw=R['def']['td_raw'].get(dfn), lgTD=round(lt, 3), dev=round(float(dev), 3),
                                  offGL=round(lgl + o_gl, 3), defGL=round(lgl + d_gl, 3), lgGL=round(lgl, 3), glpass=round(float(glp), 3),
                                  qbShare=round(float(qbshare.get(off, lqb)), 3), lgQB=round(float(lqb), 3))
            # QB goal-line role from data: scale his red-zone weight by his team's QB share of carries inside the 5 vs his carry share
            for pl in g['players']:
                if pl['t'] == off and pl['pos'] == 'QB' and pl.get('rush', 0) > 0:
                    target = qbshare.get(off, lqb) / max(.02, pl['rush'])
                    pl['gl'] = round(float(np.clip(0.5 * pl['gl'] + 0.5 * target, .3, 5.0)), 3)
    json.dump(S, open(path, 'w'))
    print(f'finishing: league red-zone TD rate {lt:.3f}, goal-line pass rate {lgl:.3f}, QB share of carries inside the 5 {lqb:.3f}')

if __name__ == '__main__':
    if sys.argv[1] == 'test': test()
    else: live(sys.argv[1], int(sys.argv[2]))
