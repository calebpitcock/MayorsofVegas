import sys, json, numpy as np, pandas as pd
sys.path.insert(0,'.')
import nfl_build as nb
HL, PW, PS = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
nb.HL, nb.PRIOR_W, nb.PSEUDO = HL, PW, PS
b = nb.Builder(2025)
G = pd.read_csv(f'{nb.D}/games.csv'); G = G[(G.season == 2025) & (G.game_type == 'REG')]
T = b.T.set_index(['game_id','posteam'])
rows = []
import os
WEEKS = [int(x) for x in os.environ.get("EZW", "5,7,9,11,13,15,17").split(",")]
for w in WEEKS:
    for r in G[G.week == w].itertuples():
        for team in (r.away_team, r.home_team):
            sn = b.SN[(b.SN.game_id == r.game_id) & (b.SN.team == team)]
            q = b.Q[(b.Q.game_id == r.game_id) & (b.Q.posteam == team)]
            qb = q.sort_values('db').pid.iloc[-1] if len(q) else None
            pl = b.team_players(team, w, active_pids=set(sn.pid), qb_pid=qb)
            u = b.U[(b.U.game_id == r.game_id) & (b.U.posteam == team)].set_index('pid')
            if (r.game_id, team) not in T.index: continue
            tc, tt = T.loc[(r.game_id, team), 'tcar'], T.loc[(r.game_id, team), 'ttgt']
            sr = sum(x['rush'] for x in pl); st = sum(x['rec'] for x in pl)
            for x in pl:
                a = u.loc[x['id']] if x['id'] in u.index else None
                rows.append(dict(pos=x['pos'], rush=x['rush'], rec=x['rec'], sr=sr, st=st,
                                 ar=(a.car / tc) if a is not None else 0, at=(a.tgt / tt) if a is not None else 0))
R = pd.DataFrame(rows)
def err(col, act, sel):
    s = R[sel]; return float(np.mean((s[col] - s[act]) ** 2)), float(np.polyfit(s[col], s[act], 1)[0])
e1 = err('rush', 'ar', R.pos.isin(['RB'])); e2 = err('rec', 'at', R.pos.isin(['WR','TE','RB']))
print(f'HL={HL} PW={PW} PS={PS}  RB carry MSE {e1[0]:.5f} slope {e1[1]:.2f} | target MSE {e2[0]:.5f} slope {e2[1]:.2f} | mean team rush-share sum {R.sr.mean():.2f}')
