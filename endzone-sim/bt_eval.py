import json, sys, numpy as np, pandas as pd
f = sys.argv[1] if len(sys.argv) > 1 else 'bt_2025_4_18_rows.json'
d = json.load(open(f)); R = pd.DataFrame(d['rows']); G = pd.DataFrame(d['grows'])
out = {}
def brier(p, y): return float(np.mean((p - y) ** 2))
def ll(p, y): p = np.clip(p, 1e-4, 1 - 1e-4); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
print('player rows', len(R), 'games', len(G))
# ---------- anytime TD ----------
T = R.copy()
base = T.td.mean()
print(f"\nANYTIME TD  n={len(T)}  scored={T.td.sum()}  mean model p={T.pTD.mean():.3f}  actual rate={base:.3f}")
print(f"  Brier model {brier(T.pTD, T.td):.4f}  vs constant {brier(np.full(len(T), base), T.td):.4f}   logloss {ll(T.pTD, T.td):.4f} vs {ll(np.full(len(T), base), T.td):.4f}")
# naive usage baseline: logistic fit on share (in-sample, generous to the baseline)
from numpy.linalg import lstsq
X = np.c_[np.ones(len(T)), T.rush, T.rec, T.pos.eq('QB')]
# simple position-rate x share baseline
pb = T.groupby('pos').td.transform('mean')
print(f"  Brier position-average baseline {brier(pb, T.td):.4f}")
for pos, g in T.groupby('pos'):
    print(f"  {pos}: n={len(g)} model {g.pTD.mean():.3f} actual {g.td.mean():.3f}  ratio {g.td.mean()/g.pTD.mean():.2f}  Brier {brier(g.pTD, g.td):.4f}")
T['bin'] = pd.cut(T.pTD, [0, .05, .1, .15, .2, .3, .4, .5, .6, 1])
print(T.groupby('bin', observed=True).agg(n=('td','size'), model=('pTD','mean'), actual=('td','mean')).round(3).to_string())
# ---------- yardage / volume distributions ----------
def dist(name, sel, pit, m, a, med, q10=None, q90=None):
    s = R[sel].dropna(subset=[pit])
    if not len(s): return
    pit_ = s[pit].values
    dec = np.histogram(pit_, bins=10, range=(0, 1))[0] / len(s)
    cov = float(np.mean((s[a] >= s[q10]) & (s[a] <= s[q90]))) if q10 else None
    print(f"\n{name}: n={len(s)}  mean model {s[m].mean():.1f} actual {s[a].mean():.1f}  bias {s[a].mean()-s[m].mean():+.1f}"
          f"  P(actual>model median) {np.mean(s[a] > s[med]):.3f} (=.5 if calibrated, excl ties {np.mean(s[a]==s[med]):.3f})"
          + (f"  80% interval coverage {cov:.3f}" if cov is not None else ''))
    print('  PIT deciles (each should be ~.100):', ' '.join(f'{x:.3f}' for x in dec))
    mae_model = float(np.mean(np.abs(s[a] - s[med])))
    print(f"  MAE of model median {mae_model:.1f}")
dist('QB passing yards', R.pos.eq('QB') & R.aPY.notna(), 'pitPY', 'mPY', 'aPY', 'medPY', 'q10PY', 'q90PY')
dist('QB pass attempts', R.pos.eq('QB') & R.aPA.notna(), 'pitPA', 'mPA', 'aPA', 'mPA')
dist('RB rushing yards (carry share >= .25)', R.pos.eq('RB') & (R.rush >= .25), 'pitRY', 'mRY', 'aRY', 'medRY', 'q10RY', 'q90RY')
dist('WR/TE receiving yards (target share >= .12)', R.pos.isin(['WR','TE']) & (R.rec >= .12), 'pitRCY', 'mRCY', 'aRCY', 'medRCY', 'q10RCY', 'q90RCY')
dist('WR/TE receptions (target share >= .12)', R.pos.isin(['WR','TE']) & (R.rec >= .12), 'pitREC', 'mREC', 'aREC', 'medREC')
dist('RB receiving yards (target share >= .08)', R.pos.eq('RB') & (R.rec >= .08), 'pitRCY', 'mRCY', 'aRCY', 'medRCY', 'q10RCY', 'q90RCY')
for pos in ['RB','WR','TE']:
    s = R[R.pos == pos]
    print(f"  volume {pos}: carries model {s.mRA.mean():.2f} actual {s.aRA.mean():.2f} | targets model {s.mTGT.mean():.2f} actual {s.aTGT.mean():.2f}")
# ---------- game level ----------
G['hw'] = (G.hs > G['as']).astype(float) + .5 * (G.hs == G['as'])
def mlp(o): return np.where(o < 0, -o / (-o + 100), 100 / (o + 100))
m = G.dropna(subset=['mlH','mlA'])
ph = mlp(m.mlH.values); pa = mlp(m.mlA.values); pm = ph / (ph + pa)
print(f"\nGAMES n={len(G)}  Brier home win: model {brier(G.pH, G.hw):.4f}   de-vigged moneyline {brier(pm, m.hw):.4f} (n={len(m)})")
print(f"  mean |model - moneyline| {np.mean(np.abs(m.pH - pm)):.4f}")
cov = (G.hs - G['as'] + G.spread)  # home margin + home spread >0 = home covers
print(f"  home cover rate {np.mean(cov>0):.3f} push {np.mean(cov==0):.3f}; over rate {np.mean((G.hs+G['as'])>G.total):.3f}")
