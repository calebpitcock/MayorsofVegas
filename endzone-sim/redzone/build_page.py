"""Embed every week's picks (redzone/site/picks_w*.json) and the latest week's news check (redzone/site/news_w*.json, if
any) into the page -> redzone/site/index.html, the file to publish.
Usage: python3 redzone/build_page.py"""
import json, os, re, glob
H = os.path.dirname(os.path.abspath(__file__))
wk = lambda f: int(re.search(r'w(\d+)', os.path.basename(f)).group(1))
files = sorted(glob.glob(os.path.join(H, 'site', 'picks_w*.json')), key=wk)
emb = lambda x: json.dumps(x, separators=(',', ':')).replace('</', '<\\/')
data = emb([json.load(open(f)) for f in files])
# the news check belongs to the newest week only; an older week's notes would mislabel this week's picks
nf = os.path.join(H, 'site', f'news_w{wk(files[-1])}.json') if files else None
news = emb(json.load(open(nf))) if nf and os.path.exists(nf) else '{}'
page = open(os.path.join(H, 'redzone.html')).read()
tag, ntag = '<script type="application/json" id="rzdata">[]</script>', '<script type="application/json" id="rznews">{}</script>'
assert tag in page and ntag in page
page = page.replace(tag, f'<script type="application/json" id="rzdata">{data}</script>').replace(ntag, f'<script type="application/json" id="rznews">{news}</script>')
open(os.path.join(H, 'site', 'index.html'), 'w').write(page)
print('page built with weeks', [wk(f) for f in files], '+ news' if news != '{}' else '(no news file)')
