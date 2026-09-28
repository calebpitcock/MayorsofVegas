"""Team strength as the betting market saw it: a rating per team fitted to past closing spreads (nflverse games.csv),
recency-weighted, carried across seasons with shrinkage. Uses only games before the one being rated, so it is a
legitimate pre-game input. It registers what the play-by-play ratings miss (defense, roster, coaching, injuries
already known to the market) and is the game model's main team-strength signal."""
import numpy as np, pandas as pd
REP = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
def load_games(path='../../data/games.csv'):
    G = pd.read_csv(path); G = G[G.game_type == 'REG'].copy()
    for c in ('home_team', 'away_team'): G[c] = G[c].replace(REP)
    return G.sort_values(['gameday', 'game_id'])
def ratings(G, HLW=8.0, CARRY=0.5, LAM=2.0, S0=2006):
    """Returns {(game_id, team): rating before that game} and the final state (for the live week).
    HLW: half-life in weeks of a past line; CARRY: weight kept at a new season; LAM: ridge pull toward 0."""
    T = sorted(set(G.home_team) | set(G.away_team)); ix = {t: i for i, t in enumerate(T)}; n = len(T) + 1
    A = np.zeros((n, n)); b = np.zeros(n); d = 0.5 ** (1 / HLW); pre = {}; season = None; lastwk = None
    reg = LAM * np.diag([1.0] * (n - 1) + [0.0]) + 1e-6 * np.eye(n)
    def solve(): return np.linalg.solve(A + reg, b)
    G = G[G.season >= S0]
    for (s, wk), grp in G.groupby(['season', 'week'], sort=False):
        if season is not None and s != season: A *= CARRY; b *= CARRY
        season = s
        A *= d; b *= d
        r = solve()
        for g in grp.itertuples():
            pre[(g.game_id, g.home_team)] = r[ix[g.home_team]]; pre[(g.game_id, g.away_team)] = r[ix[g.away_team]]
        for g in grp.itertuples():
            if pd.isna(g.spread_line) or pd.isna(g.result): continue     # only lines of games already played count
            x = np.zeros(n); x[ix[g.home_team]] = 1; x[ix[g.away_team]] = -1; x[-1] = 0 if g.location == 'Neutral' else 1
            A += np.outer(x, x); b += x * g.spread_line
    return pre, dict(A=A, b=b, T=T, ix=ix, reg=reg, season=season, CARRY=CARRY)
def live(state, season):
    """Ratings for the coming week (carry applied if a new season starts)."""
    A, b = state['A'].copy(), state['b'].copy()
    if state['season'] != season: A *= state['CARRY']; b *= state['CARRY']
    r = np.linalg.solve(A + state['reg'], b)
    return {t: r[i] for t, i in state['ix'].items()}, r[-1]
