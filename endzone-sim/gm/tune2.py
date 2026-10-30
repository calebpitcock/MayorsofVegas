import itertools, numpy as np, model2
res = []
for (HG, CARRY), (QHL, QCARRY, QM0) in itertools.product(((10.0, 0.7), (10.0, 0.85), (14.0, 0.85)), ((800.0, 0.8, 150.0), (1500.0, 0.8, 100.0), (1500.0, 0.95, 100.0), (3000.0, 0.9, 60.0))):
    D = model2.build(dict(HG=HG, CARRY=CARRY, M0=3.0), dict(QHL=QHL, QCARRY=QCARRY, QM0=QM0))
    O = model2.walk(D, 2016, 2020, RHL=8.0); mae = float(np.mean(np.abs(O.result - O.m))); res.append((mae, HG, CARRY, QHL, QCARRY, QM0)); print(round(mae, 4), HG, CARRY, QHL, QCARRY, QM0, flush=True)
res.sort(); print('best', res[0])
