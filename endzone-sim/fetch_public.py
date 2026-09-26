"""Public opinion: this week's NFL.com power rankings (Nick Shook's weekly column) -> public_rank.json.
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
def main(season, week):
    url = f'https://www.nfl.com/news/nfl-power-rankings-week-{week}-{season}-nfl-season'
    r = subprocess.run(['curl', '-sSfL', '-m', '30', '-A', 'Mozilla/5.0', url], capture_output=True)
    if r.returncode != 0: print(f'public: could not read {url} (is www.nfl.com allowed?)'); return 1
    s = r.stdout.decode('utf-8', 'ignore'); ranks = parse(s)
    if not ranks: print('public: page read but the 32-team list did not parse; keeping the previous file'); return 1
    d = re.search(r'"datePublished"\s*:\s*"([^"]+)"', s); a = re.search(r'"author"\s*:\s*\[?\s*\{[^}]*"name"\s*:\s*"([^"]+)"', s)
    out = dict(season=season, week=week, source='NFL.com power rankings' + (f' ({a.group(1)})' if a else ''), url=url,
               asOf=d.group(1) if d else None, ranks=ranks)
    json.dump(out, open(os.path.join(H, 'public_rank.json'), 'w'), indent=1)
    print(f"public: {out['source']}, {out['asOf']}: " + ' '.join(f'{v}.{k}' for k, v in sorted(ranks.items(), key=lambda kv: kv[1])[:5]) + ' ...')
    return 0
if __name__ == '__main__':
    wk = json.load(open(os.path.join(H, 'overrides.json')))['week']
    sys.exit(main(2026, int(sys.argv[1]) if len(sys.argv) > 1 else wk))
