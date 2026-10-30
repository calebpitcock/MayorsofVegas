"""Walk-forward: train on every earlier season, predict the next. Does anything beat a coin flip against the close?"""
import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import lightgbm as lgb
X = pd.read_parquet('ats.parquet'); X = X[~X.push].copy()
dec = lambda o: np.where(o > 0, 1 + o / 100, 1 + 100 / -o)
SIT = ['spread', 'homedog', 'bigfav', 'rest', 'hshort', 'ashort', 'hbye', 'abye', 'div', 'neutral', 'tz', 'westearly', 'prime', 'late', 'wind', 'ats3', 'mg1', 'qbchg']
ALL = SIT + ['dis', 'mkt', 'qb', 'qbd', 'qb2']
ll = lambda p, y: float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def walk(feats, S0, S1, kind, start):
    out = []
    for S in range(S0, S1 + 1):
        tr = X[(X.season < S) & (X.season >= start)].dropna(subset=feats); te = X[X.season == S].dropna(subset=feats).copy()
        if kind == 'lr':
            sc = StandardScaler().fit(tr[feats]); m = LogisticRegression(C=0.05).fit(sc.transform(tr[feats]), tr.y); te['p'] = m.predict_proba(sc.transform(te[feats]))[:, 1]
        else:
            m = lgb.LGBMClassifier(n_estimators=150, learning_rate=0.03, num_leaves=7, min_child_samples=80, subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5, verbose=-1)
            m.fit(tr[feats], tr.y); te['p'] = m.predict_proba(te[feats])[:, 1]
        out.append(te)
    return pd.concat(out)
def report(E, lab):
    E = E.dropna(subset=['hodds', 'aodds']); side = E.p > .5; conf = (E.p - .5).abs()
    won = np.where(side, E.y == 1, E.y == 0); pay = np.where(side, dec(E.hodds.values), dec(E.aodds.values)); pl = np.where(won, pay - 1, -1)
    s = f"{lab:34s} n={len(E):4d} LL {ll(E.p.clip(.01,.99), E.y):.4f} (coin .6931) | all picks {won.mean():.3f} ROI {pl.mean():+.3f}"
    for q in (.5, .8, .9):
        m = (conf >= conf.quantile(q)).values; s += f" | top {int(round(100*(1-q)))}%: {won[m].mean():.3f} ROI {pl[m].mean():+.3f}±{pl[m].std()/np.sqrt(m.sum()):.3f}"
    print(s)
report(walk(SIT, 2012, 2025, 'lr', 2006), 'situational, logistic 2012-25')
report(walk(SIT, 2012, 2025, 'gbm', 2006), 'situational, boosted trees 2012-25')
report(walk(ALL, 2018, 2025, 'lr', 2014), 'situational+model, logistic 2018-25')
report(walk(ALL, 2018, 2025, 'gbm', 2014), 'situational+model, trees 2018-25')
report(walk(['dis'], 2018, 2025, 'lr', 2014), 'model disagreement only 2018-25')
# line movement (2021+): does the Tuesday->close move tell you anything AT the close?
M = X.dropna(subset=['move']); M = M[M.move != 0]
fol = np.where(M.move > 0, M.y == 1, M.y == 0)
print(f"\nline moved toward a side Tue->close (n={len(M)}): that side covers the close {fol.mean():.3f}")
for lo in (1, 2, 3):
    m = (M.move.abs() >= lo).values; print(f"  moved {lo}+ pts: n={m.sum()} steam side covers {fol[m].mean():.3f}")
