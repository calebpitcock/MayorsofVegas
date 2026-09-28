import numpy as np, pandas as pd, model2, model3, sys
import os
D0 = pd.read_parquet('D.parquet') if os.path.exists('D.parquet') else model2.build(dict(HG=14.0, CARRY=0.85, M0=3.0), dict(QHL=1500.0, QCARRY=0.8, QM0=100.0))
B = model2.walk(D0, 2016, 2025, RHL=8.0)
m = lambda O, a, b: float(np.mean(np.abs((O.result - O.m)[(O.season >= a) & (O.season <= b)])))
c = lambda O, a, b: float(np.mean(np.abs((O.result - O.spread_line)[(O.season >= a) & (O.season <= b)])))
print(f"close MAE 2016-20 {c(B,2016,2020):.3f} 2021-25 {c(B,2021,2025):.3f} | old model {m(B,2016,2020):.3f} / {m(B,2021,2025):.3f}")
for HLW in (2.0, 3.0, 4.0, 6.0):
    D = model3.add(D0, dict(HLW=HLW, CARRY=0.5, LAM=1.0))
    for cols, lab in ((model3.F3, 'all'), (model2.F + ['mkt'], 'no qb2')):
        O = model2.walk(D, 2016, 2025, RHL=8.0, cols=cols)
        print(f"HLW {HLW} {lab:7s}: 2016-20 {m(O,2016,2020):.3f}  2021-25 {m(O,2021,2025):.3f}  w_mkt {O.w_mkt.iloc[-1]:.2f} w_qb {O.w_qb.iloc[-1]:.1f}" + (f" w_qb2 {O.w_qb2.iloc[-1]:.2f}" if 'qb2' in cols else ''))
