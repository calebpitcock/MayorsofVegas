"""Public opinion: a CONSENSUS of this week's published power rankings -> public_rank.json (average rank across every
list that could be read; one writer's list is too idiosyncratic on its own). Sources: NFL.com's two weekly lists
(Nick Shook, Neil Reynolds). Add outlets to SOURCES as their domains are allowed.
Needs www.nfl.com in the environment's allowed domains. Leaves the previous file alone if the page can't be read or
doesn't parse into exactly 32 distinct ranks (a stale week is ignored by gm/game_live.py anyway)."""
import re, html, json, os, sys, subprocess
H = os.path.dirname(os.path.abspath(__file__))
FULL = {'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL','Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI','Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL','Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB','Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX','Kansas City Chiefs':'KC','Los Angeles Rams':'LA','Los Angeles Chargers':'LAC','Las Vegas Raiders':'LV','Miami Dolphins':'MIA','Minnesota Vikings':'MIN','New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG','New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT','Seattle Seahawks':'SEA','San Francisco 49ers':'SF','Tampa Bay Buccaneers':'TB','Tennessee Titans':'TEN','Washington Commanders':'WAS'}
def parse(s):
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    L = [l.strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', t)).split('\n') if l.strip()]
    # the ranked list: a line "1", then within a few lines the full team name; then "2", and so on to 32
    for start in [i for i, l in enumerate(L) if l == '1']:
        ranks, want, i = {}, 1, start
        while i < len(L) and want <= 32:
            if L[i] == str(want):
                for j in range(i + 1, min(i + 8, len(L))):
                    if L[j] in FULL and FULL[L[j]] not in ranks: ranks[FULL[L[j]]] = want; want += 1; i = j; break
            i += 1
        if len(ranks) == 32: return ranks
    return None
def parse_changes(s):
    """Lists written as 'Team Name  --' / 'Team Name  +6' lines in rank order (Neil Reynolds' format)."""
    t = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
    L = [re.sub(r'\s+', ' ', l.replace('\xa0', ' ')).strip() for l in html.unescape(re.sub(r'<[^>]+>', '\n', t)).split('\n')]
    pat = re.compile(r'^(%s) (--|[+-]\d+)$' % '|'.join(map(re.escape, FULL))); order = []
    for l in L:
        m = pat.match(l)
        if m and FULL[m.group(1)] not in order: order.append(FULL[m.group(1)])
    return {t: i + 1 for i, t in enumerate(order)} if len(order) == 32 else None
SOURCES = [  # (label, url pattern, parser)
    ('NFL.com (Nick Shook)', 'https://www.nfl.com/news/nfl-power-rankings-week-{week}-{season}-nfl-season', parse),
    ('NFL.com (Neil Reynolds)', 'https://www.nfl.com/news/reynolds-week-{week}-power-rankings-{season}', parse_changes),
]
def get(url):
    r = subprocess.run(['curl', '-sSfL', '-m', '30', '-A', 'Mozilla/5.0', url], capture_output=True)
    return r.stdout.decode('utf-8', 'ignore') if r.returncode == 0 else None
def main(season, week):
    lists = {}
    for label, pat, fn in SOURCES:
        url = pat.format(week=week, season=season); s = get(url)
        r = fn(s) if s else None
        if r and len(set(r.values())) == 32: lists[label] = dict(url=url, ranks=r); print(f'public: {label} read')
        else: print(f'public: {label} not available ({url})')
    if not lists: print('public: no ranking could be read; keeping the previous file'); return 1
    avg = {t: sum(l['ranks'][t] for l in lists.values()) / len(lists) for t in FULL.values()}
    order = sorted(avg, key=lambda t: (avg[t], min(l['ranks'][t] for l in lists.values())))
    out = dict(season=season, week=week, source='consensus of ' + ', '.join(lists), asOf=None,
               ranks={t: i + 1 for i, t in enumerate(order)}, avgRank={t: round(avg[t], 2) for t in order}, lists=lists)
    json.dump(out, open(os.path.join(H, 'public_rank.json'), 'w'), indent=1)
    print('public consensus: ' + ' '.join(f'{i + 1}.{t}' for i, t in enumerate(order)))
    return 0
if __name__ == '__main__':
    wk = json.load(open(os.path.join(H, 'overrides.json')))['week']
    sys.exit(main(2026, int(sys.argv[1]) if len(sys.argv) > 1 else wk))
