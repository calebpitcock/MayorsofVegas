"""For each team-game (weeks 3-18): the model's predicted carry/target shares next to role signals knowable before
kickoff (snap share trend, practice report), and what actually happened. Actives = who played (as in the TD backtests)."""
import sys, os, numpy as np, pandas as pd, nfl_build as nb
S = int(sys.argv[1]); b = nb.Builder(S)
G = pd.read_csv(f'{nb.D}/games.csv'); G = G[(G.season == S) & (G.game_type == 'REG')]
T = b.T.set_index(['game_id', 'posteam'])
SNf = pd.read_csv(f'{nb.D}/snap_counts_{S}.csv'); SNf = SNf[SNf.game_type == 'REG']
pfr2g = {v: k for k, v in b.R['pfr_id'].dropna().items()}
SNf['pid'] = SNf.pfr_player_id.map(pfr2g)
INJ = pd.read_csv(f'{nb.D}/injuries_{S}.csv'); INJ = INJ[INJ.game_type == 'REG']
INJ = INJ.drop_duplicates(['gsis_id', 'week'], keep='last').set_index(['gsis_id', 'week'])
rows = []
for w in range(3, 19):
    for r in G[G.week == w].itertuples():
        for team in (r.away_team, r.home_team):
            if (r.game_id, team) not in T.index: continue
            sn = b.SN[(b.SN.game_id == r.game_id) & (b.SN.team == team)]
            q = b.Q[(b.Q.game_id == r.game_id) & (b.Q.posteam == team)]
            qb = q.sort_values('db').pid.iloc[-1] if len(q) else None
            pl = b.team_players(team, w, active_pids=set(sn.pid), qb_pid=qb)
            u = b.U[(b.U.game_id == r.game_id) & (b.U.posteam == team)].set_index('pid')
            tc, tt = T.loc[(r.game_id, team), 'tcar'], T.loc[(r.game_id, team), 'ttgt']
            hist = SNf[(SNf.team == team) & (SNf.week < w)]
            for x in pl:
                if x['pos'] == 'QB': continue
                h = hist[hist.pid == x['id']].sort_values('week')
                lastw = hist.week.max()
                s_last = float(h[h.week == lastw].offense_pct.sum()) if len(h) else 0.0
                s_prev = float(h[h.week < lastw].offense_pct.tail(3).mean()) if (h.week < lastw).any() else np.nan
                s_all = float(h.offense_pct.mean()) if len(h) else 0.0
                inj = INJ.loc[(x['id'], w)] if (x['id'], w) in INJ.index else None
                a = u.loc[x['id']] if x['id'] in u.index else None
                rows.append(dict(season=S, week=w, game_id=r.game_id, team=team, pid=x['id'], n=x['n'], pos=x['pos'], conf=x['conf'], g=x['g'],
                                 rush=x['rush'], rec=x['rec'], s_last=s_last, s_prev=s_prev, s_all=s_all, played_last=int(len(h[h.week == lastw]) > 0),
                                 status=(inj.report_status if inj is not None and isinstance(inj.report_status, str) else ''),
                                 practice=(inj.practice_status if inj is not None and isinstance(inj.practice_status, str) else ''),
                                 ar=(a.car / tc) if a is not None else 0.0, at=(a.tgt / tt) if a is not None else 0.0,
                                 td=int(a.rtd + a.ctd) if a is not None else 0, tc=tc, tt=tt))
    print('week', w, len(rows), file=sys.stderr, flush=True)
pd.DataFrame(rows).to_csv(f'role_{S}.csv', index=False)
