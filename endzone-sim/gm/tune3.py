import itertools, numpy as np, pandas as pd, model2, model3, os
import os
D0 = pd.read_parquet('D.parquet') if os.path.exists('D.parquet') else model2.build(dict(HG=14.0, CARRY=0.85, M0=3.0), dict(QHL=1500.0, QCARRY=0.8, QM0=100.0))
res = []
for HLW, CARRY, LAM in itertools.product((4.0, 8.0, 16.0), (0.3, 0.5, 0.8), (1.0, 4.0)):
    D = model3.add(D0, dict(HLW=HLW, CARRY=CARRY, LAM=LAM))
    O = model2.walk(D, 2016, 2020, RHL=8.0, cols=model3.F3); mae = float(np.mean(np.abs(O.result - O.m)))
    res.append((mae, HLW, CARRY, LAM)); print(round(mae, 4), HLW, CARRY, LAM, flush=True)
res.sort(); print('best', res[:3])
