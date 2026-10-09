"""Assemble the Redzone Desk page -> site/index.html (the file to publish).

    python3 build_page.py <week> [old page data json]

Embeds site/picks_w<week>.json (this week), site/news_w<week>.json, and site/archive.json: older weeks from the
retired simulation model, slimmed to what My picks and Record need (id, type, text, game, chance, price, first
reasons), so picks you tracked before still resolve. Pass the old page's rzdata JSON once to (re)write the archive.
"""
import json
import os
import sys

H = os.path.dirname(os.path.abspath(__file__))
WEEK = int(sys.argv[1])
SITE = os.path.join(H, 'site')
arch_path = os.path.join(SITE, 'archive.json')

if len(sys.argv) > 2:
    old = json.load(open(sys.argv[2]))
    keep = ('id', 'type', 'text', 'game', 'gameId', 'prob', 'price', 'team', 'pos', 'player')
    arch = []
    for w in old:
        lab = w.get('label', f"Week {w['week']}")
        if w['week'] == WEEK:
            lab = f"Week {w['week']}: Thursday (old model)"
        arch.append(dict(week=w['week'], label=lab, board=w['board'],
                         picks=[{**{k: p[k] for k in keep if k in p}, 'why': p.get('why', [])[:4]} for p in w['picks']]))
    json.dump(arch, open(arch_path, 'w'), separators=(',', ':'))

emb = lambda x: json.dumps(x, separators=(',', ':')).replace('</', '<\\/')
data = json.load(open(os.path.join(SITE, f'picks_w{WEEK}.json')))
news = json.load(open(os.path.join(SITE, f'news_w{WEEK}.json')))
arch = json.load(open(arch_path)) if os.path.exists(arch_path) else []
page = open(os.path.join(H, 'page_head.html')).read() + '\n' + open(os.path.join(H, 'desk_body.html')).read()
for tag, val in (('rzdata', data), ('rzarchive', arch), ('rznews', news)):
    empty = '{}' if tag != 'rzarchive' else '[]'
    old_tag = f'<script type="application/json" id="{tag}">{empty}</script>'
    assert page.count(old_tag) == 1, tag
    page = page.replace(old_tag, f'<script type="application/json" id="{tag}">{emb(val)}</script>')
open(os.path.join(SITE, 'index.html'), 'w').write(page)
print(f"page: week {WEEK}, {len(data['games'])} games, {len(data['picks'])} picks, archive weeks {[a['week'] for a in arch]}, {len(page.encode()) // 1024} KB")
