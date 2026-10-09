"""Results calibration for the Redzone Desk's yardage and catch distributions (no sportsbook input).
The simulation was built to be calibrated against DraftKings props; with books out of the Redzone model, its
position-level biases show (2026 weeks 2-4: WR receiving yards ~20% low, RB receiving yards ~35% high, rushing spread
too narrow). This fits, per stat and position, a scale s and a spread w on what actually happened:
    X' = s * (median + w * (X - median))
by minimizing the ranked probability score over every player who played, and checks it leaving one week out
(log loss and side hit rate at the books' lines, which are only used to score, never to fit).
Usage: python3 redzone/calibrate.py BTDIR VARIANT  -> redzone/calibration.json (read by predict.js)"""
import json, os, sys, math, numpy as np, pandas as pd
H = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, H)
import backtest as bt
STATS = ('recYds', 'rushYds', 'rec'); POS = ('WR', 'TE', 'RB', 'QB')
SG = np.round(np.arange(0.70, 1.41, 0.02), 2); WG = np.round(np.arange(0.70, 1.61, 0.05), 2)

def median(a): return next((k for k in range(len(a)) if a[k] < .5), len(a)) - 1 + .5

def at_least(a, x):
    """P(X >= x) for real x from the integer table a[k] = P(X >= k) (linear between integers)."""
    x = np.clip(x, 0, len(a) - 1); i = np.floor(x).astype(int); f = x - i; j = np.minimum(i + 1, len(a) - 1)
    return a[i] * (1 - f) + a[j] * f

def cal_at_least(a, k, s, w):
    m = median(a); return at_least(a, m + (np.asarray(k, float) / s - m) / w)

def load(btdir, var, weeks):
    rows = []
    for W in weeks:
        (o, tds, played), L = bt.outcomes(W), bt.lines(W)
        for p in json.load(open(f'{btdir}/{var}/w{W}/dump.json')):
            if p['id'] not in played: continue
            for st in STATS:
                if p['pos'] == 'QB' and st != 'rushYds': continue
                a = np.array(p[st]);
                if sum(a[1:]) < (1 if st == 'rec' else 8): continue        # not part of the offense in this stat
                ln = L.get((p['gid'], p['n'], st))
                rows.append(dict(W=W, st=st, pos=p['pos'], a=a, v=o[st].get(p['id'], 0), line=ln[0] if ln else None, book=ln[1] if ln else None))
    return pd.DataFrame(rows)

def rps(x, s, w):
    K = np.arange(1, 16) if x.st.iloc[0] == 'rec' else np.arange(5, 201, 5)
    return float(np.mean([np.mean((cal_at_least(a, K, s, w) - (v >= K)) ** 2) for a, v in zip(x.a, x.v)]))

def fit(x):
    best = min(((rps(x, s, w), s, w) for s in SG for w in WG)); return best[1], best[2]

def ll(q, y): q = min(max(q, 1e-3), 1 - 1e-3); return -(y * math.log(q) + (1 - y) * math.log(1 - q))

lgt = lambda q: math.log(min(max(q, 1e-3), 1 - 1e-3) / (1 - min(max(q, 1e-3), 1 - 1e-3)))
sig = lambda z: 1 / (1 + math.exp(-z))

def line_probs(x, par):
    """model P(over the line) after scale/spread, with the outcome; lines only define the event."""
    x = x[x.line.notna() & (x.v != x.line)]
    return [(float(cal_at_least(r.a, math.ceil(r.line), *par.get((r.st, r.pos), (1.0, 1.0)))), int(r.v > r.line), r.book, r.st) for r in x.itertuples()]

def fit_trust(pr):
    """how far to trust the model's distance from 50% at a line: P' = sig(k * logit(P)), k fitted on outcomes."""
    return min(np.round(np.arange(0, 1.01, .05), 2), key=lambda k: sum(ll(sig(k * lgt(q)), y) for q, y, _, _ in pr))

def line_score(x, par, k=1.0):
    return np.array([(ll(sig(k * lgt(q)), y), int((q > .5) == y), ll(b, y)) for q, y, b, _ in line_probs(x, par)])

def load_td(btdir, var, weeks):
    rows = []
    for W in weeks:
        o, tds, played = bt.outcomes(W)
        rows += [dict(W=W, pos=p['pos'], z=lgt(p['td']), y=int(p['id'] in tds)) for p in json.load(open(f'{btdir}/{var}/w{W}/dump.json')) if p['id'] in played]
    return pd.DataFrame(rows)

def fit_td(x):
    """P' = sig(a*logit(P) + b + pos[position]), a few Newton-free coordinate steps on log loss (ridge on the offsets)."""
    best = None
    for a in np.arange(.5, 1.21, .05):
        for b in np.arange(-.4, .41, .05):
            pos = {}
            for q in ('QB', 'RB', 'WR', 'TE'):
                y = x[x.pos == q]
                pos[q] = min(np.arange(-.5, .51, .05), key=lambda c: sum(ll(sig(a * z + b + c), t) for z, t in zip(y.z, y.y)) + 8 * c * c) if len(y) else 0.0
            L = sum(ll(sig(a * z + b + pos[q]), t) for z, t, q in zip(x.z, x.y, x.pos))
            if best is None or L < best[0]: best = (L, round(float(a), 2), round(float(b), 2), {k: round(float(v), 2) for k, v in pos.items()})
    return dict(a=best[1], b=best[2], pos=best[3])

def td_score(x, c): return np.array([ll(sig(c['a'] * z + c['b'] + c['pos'].get(q, 0)), t) for z, t, q in zip(x.z, x.y, x.pos)]) if c else np.array([ll(sig(z), t) for z, t in zip(x.z, x.y)])

def main(btdir, var, weeks=(2, 3, 4)):
    T = load_td(btdir, var, weeks); print('anytime TD, leave one week out:')
    allr = [[], []]
    for W in weeks:
        c = fit_td(T[T.W != W]); r0, r1 = td_score(T[T.W == W], None), td_score(T[T.W == W], c); allr[0].append(r0); allr[1].append(r1)
        print(f'  week {W}: n={len(r0)} log loss {r0.mean():.4f} -> {r1.mean():.4f}  ({c})')
    print(f'  all: {np.concatenate(allr[0]).mean():.4f} -> {np.concatenate(allr[1]).mean():.4f}')
    # TD recalibration is a check only: on 2026 weeks 2-4 it helped one week of three (log loss 0.4733 -> 0.4716), so it isn't applied
    df = load(btdir, var, weeks); groups = [(st, pos) for st in STATS for pos in POS if ((df.st == st) & (df.pos == pos)).sum() >= 30]
    print('leave one week out (scored at the books\' lines):')
    tot = {'raw': [], 'cal': [], 'trust': []}
    for W in weeks:
        tr, te = df[df.W != W], df[df.W == W]
        par = {g: fit(tr[(tr.st == g[0]) & (tr.pos == g[1])]) for g in groups}; k = fit_trust(line_probs(tr, par))
        r0, r1, r2 = line_score(te, {}), line_score(te, par), line_score(te, par, k)
        for n_, r_ in (('raw', r0), ('cal', r1), ('trust', r2)): tot[n_].append(r_)
        print(f'  week {W}: n={len(r0)}  log loss raw {r0[:,0].mean():.4f}, scaled {r1[:,0].mean():.4f}, + trust {k:.2f} {r2[:,0].mean():.4f} (book {r0[:,2].mean():.4f})  side hit {r0[:,1].mean():.3f} -> {r1[:,1].mean():.3f}')
    a, b, c = (np.vstack(tot[n_]) for n_ in ('raw', 'cal', 'trust'))
    print(f'  all:    n={len(a)}  log loss raw {a[:,0].mean():.4f}, scaled {b[:,0].mean():.4f}, + trust {c[:,0].mean():.4f} (book {a[:,2].mean():.4f}; 50/50 0.6931)  side hit {a[:,1].mean():.3f} -> {b[:,1].mean():.3f}')
    par = {g: fit(df[(df.st == g[0]) & (df.pos == g[1])]) for g in groups}; trust = fit_trust(line_probs(df, par))
    print(f'  trust at a line (all weeks): {trust:.2f}')
    out = {'_about': __doc__.split('\n')[0] + f' Fitted on 2026 weeks {list(weeks)} ({var}).', 'weeks': list(weeks),
           'trust': trust, 'fit': {f'{st}|{pos}': dict(s=s, w=w) for (st, pos), (s, w) in par.items()}}
    for k, v in out['fit'].items(): print(f'  {k:12} scale {v["s"]:.2f} spread {v["w"]:.2f}')
    if '--write' in sys.argv: json.dump(out, open(os.path.join(H, 'calibration.json'), 'w'), indent=1); print('wrote redzone/calibration.json')

if __name__ == '__main__': main(sys.argv[1], sys.argv[2])
