import json, re, os
H = os.path.dirname(os.path.abspath(__file__))
rd = lambda f: open(os.path.join(H, f)).read()
shell = rd('shell.html')
strip = lambda s: re.sub(r"\nif\(typeof module[^\n]*", "", s)
nfl = json.load(open(os.path.join(H, 'slate_nfl.json')))
tdn = json.load(open(os.path.join(H, 'td_cal_nfl.json')))
tdf = json.load(open(os.path.join(H, 'td_dk_fit.json')))
tdfit = {k: round(tdf[k], 4) for k in ('a', 'bk', 'bm', 'dva', 'dvb')}
data = ("/* Built-in slates. The live copies in the shared database replace these when present. */\n"
        f"const BASE_NFL={json.dumps(nfl, separators=(',', ':'))};\n"
        f"const TDCAL={{NFL:{json.dumps(tdn)}}};\n"
        f"/* DraftKings anytime-TD fit: 8,422 prices about 5 minutes before kickoff, 2023-24. */\n"
        f"const TDFIT={json.dumps(tdfit)};\n"
        f"/* game model: lean toward the game model vs DraftKings' spread, and the margin's spread in points */\n"
        f"const GMFIT={json.dumps(dict(k=nfl.get('gmfit', {}).get('k', .15), b=nfl.get('gmfit', {}).get('b', .1439), slope=nfl.get('gmfit', {}).get('slope', .044)))};\n")
page = (shell.replace('/*__DATA__*/', data).replace('/*__SCHEME__*/', strip(rd('scheme.js')))
        .replace('/*__ENGINE__*/', strip(rd('engine.js'))).replace('/*__MODEL__*/', rd('model.js')).replace('/*__APP__*/', rd('app.js')))
out = os.path.join(H, 'endzone.html'); open(out, 'w').write(page)
print(out, len(page))
