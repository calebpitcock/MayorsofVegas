import itertools, json, numpy as np, model2
grid = []
for HG, CARRY, M0 in itertools.product((6.0, 10.0, 16.0), (0.3, 0.5, 0.7), (3.0,)):
    D = model2.build(dict(HG=HG, CARRY=CARRY, M0=M0), dict())
    for RHL in (3.0, 8.0):
        O = model2.walk(D, 2016, 2020, RHL=RHL); mae = float(np.mean(np.abs(O.result - O.m)))
        grid.append((mae, HG, CARRY, M0, RHL)); print(round(mae, 4), HG, CARRY, M0, RHL, flush=True)
grid.sort(); print('best', grid[:3])
b = grid[0]
for QHL, QCARRY, QM0 in itertools.product((200.0, 400.0, 800.0), (0.5, 0.8), (150.0, 400.0)):
    D = model2.build(dict(HG=b[1], CARRY=b[2], M0=b[3]), dict(QHL=QHL, QCARRY=QCARRY, QM0=QM0))
    O = model2.walk(D, 2016, 2020, RHL=b[4]); mae = float(np.mean(np.abs(O.result - O.m))); print('qb', round(mae, 4), QHL, QCARRY, QM0, flush=True)
