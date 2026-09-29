"""Embed every week's picks (redzone/site/picks_w*.json) into the page -> redzone/site/index.html, the file to publish.
Usage: python3 redzone/build_page.py"""
import json, os, re, glob
H = os.path.dirname(os.path.abspath(__file__))
files = sorted(glob.glob(os.path.join(H, 'site', 'picks_w*.json')), key=lambda f: int(re.search(r'w(\d+)', f).group(1)))
data = json.dumps([json.load(open(f)) for f in files], separators=(',', ':')).replace('</', '<\\/')
page = open(os.path.join(H, 'redzone.html')).read()
tag = '<script type="application/json" id="rzdata">[]</script>'
assert tag in page
open(os.path.join(H, 'site', 'index.html'), 'w').write(page.replace(tag, f'<script type="application/json" id="rzdata">{data}</script>'))
print('page built with weeks', [int(re.search(r'w(\d+)', f).group(1)) for f in files])
