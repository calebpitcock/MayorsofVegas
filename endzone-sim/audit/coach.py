import pandas as pd, numpy as np
G = pd.read_csv('games.csv'); G = G[G.result.notna() & (G.game_type == 'REG')].copy()
rep = {'OAK':'LV','SD':'LAC','STL':'LA'}
for c in ('home_team','away_team'): G[c] = G[c].replace(rep)
h = G.assign(team=G.home_team, opp=G.away_team, m=G.result, line=-G.spread_line, coach=G.home_coach)
a = G.assign(team=G.away_team, opp=G.home_team, m=-G.result, line=G.spread_line, coach=G.away_coach)
T = pd.concat([h, a])[['season','week','gameday','team','opp','m','line','coach']].sort_values(['team','gameday'])
T['ats'] = T.m + T.line     # line is the team's spread (neg = favoured); m + line > 0 = covered
S = T.groupby(['team','season']).agg(pd_=('m','mean'), first_coach=('coach','first'), last_coach=('coach','last')).reset_index()
S['prev_pd'] = S.groupby('team').pd_.shift(1); S['prev_last'] = S.groupby('team').last_coach.shift(1)
S['newhc'] = (S.first_coach != S.prev_last).astype(int)
E = T[T.week <= 8].merge(S[['team','season','prev_pd','newhc']], on=['team','season']).dropna(subset=['prev_pd'])
E = E[E.season >= 2002]
print("teams with a new head coach in week 1:", int(S[S.season >= 2002].newhc.sum()), "of", int((S.season >= 2002).sum()), "team-seasons")
print("\nweeks 1-8 margin ~ last season's point differential per game")
for f, lab in ((0, 'same head coach'), (1, 'new head coach')):
    x = E[E.newhc == f]; b = np.polyfit(x.prev_pd, x.m, 1); r = np.corrcoef(x.prev_pd, x.m)[0, 1]
    # bootstrap the slope by team-season
    ks = x.groupby(['team','season']).ngroup().values; u = np.unique(ks); rng = np.random.default_rng(0); bs = []
    idx = {k: np.where(ks == k)[0] for k in u}
    for _ in range(400):
        s = np.concatenate([idx[k] for k in rng.choice(u, len(u))]); bs.append(np.polyfit(x.prev_pd.values[s], x.m.values[s], 1)[0])
    print(f"  {lab:16s} games={len(x):5d}  carryover slope {b[0]:.3f} (95% {np.percentile(bs,2.5):.3f}-{np.percentile(bs,97.5):.3f})  corr {r:.3f}")
print("\nDoes the market already know? weeks 1-8 cover margin ~ last season's point differential")
for f, lab in ((0, 'same head coach'), (1, 'new head coach')):
    x = E[(E.newhc == f) & E.line.notna()]; b = np.polyfit(x.prev_pd, x.ats, 1)
    good = x[x.prev_pd > 3]; bad = x[x.prev_pd < -3]
    print(f"  {lab:16s} slope {b[0]:+.3f}  | last year good (>+3/g) cover {np.mean(good.ats>0):.3f} n={len(good)} | last year bad (<-3/g) cover {np.mean(bad.ats>0):.3f} n={len(bad)}")
# mid-season head coach changes: how fast does the old rating stop describing the team?
T['chg'] = T.groupby(['team','season']).coach.transform(lambda c: (c != c.iloc[0]).cumsum().clip(upper=1))
mid = T.groupby(['team','season']).filter(lambda d: d.chg.max() == 1 and d.chg.sum() >= 3)
rows = []
for (t, s), d in mid.groupby(['team','season']):
    pre, post = d[d.chg == 0], d[d.chg == 1]
    if len(pre) < 4: continue
    rows.append(dict(team=t, season=s, pre=pre.m.mean(), post=post.m.mean(), post_ats=post.ats.mean(), n=len(post), coach=post.coach.iloc[0]))
M = pd.DataFrame(rows)
print(f"\nmid-season head-coach changes since 1999: {len(M)}")
print(f"  margin before {M.pre.mean():+.1f}/g, after {M.post.mean():+.1f}/g;  cover margin after the change {M.post_ats.mean():+.2f} pts/g, covered {np.mean(M.post_ats>0):.2f} of teams")
print(f"  slope of post-change margin on pre-change margin {np.polyfit(M.pre, M.post, 1)[0]:.2f}")
