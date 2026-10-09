"""Game-level facts from nflverse games.csv (every game since 1999 with its closing line, QBs and coaches).

Nothing here predicts anything. Each function counts what already happened (against the spread, over/under,
straight up) in a slice of games and turns the notable counts into sentences. A slice is notable when it is lopsided
over enough games (see `notable`), so the page shows things like "TB 0-12-1 ATS in its last 13" and skips coin flips.
"""
import math
import pandas as pd

FRANCHISE = {'OAK': 'LV', 'SD': 'LAC', 'STL': 'LA'}
NAMES = {'ARI': 'Cardinals', 'ATL': 'Falcons', 'BAL': 'Ravens', 'BUF': 'Bills', 'CAR': 'Panthers', 'CHI': 'Bears',
         'CIN': 'Bengals', 'CLE': 'Browns', 'DAL': 'Cowboys', 'DEN': 'Broncos', 'DET': 'Lions', 'GB': 'Packers',
         'HOU': 'Texans', 'IND': 'Colts', 'JAX': 'Jaguars', 'KC': 'Chiefs', 'LA': 'Rams', 'LAC': 'Chargers',
         'LV': 'Raiders', 'MIA': 'Dolphins', 'MIN': 'Vikings', 'NE': 'Patriots', 'NO': 'Saints', 'NYG': 'Giants',
         'NYJ': 'Jets', 'PHI': 'Eagles', 'PIT': 'Steelers', 'SEA': 'Seahawks', 'SF': '49ers', 'TB': 'Buccaneers',
         'TEN': 'Titans', 'WAS': 'Commanders'}


def primetime(gametime):
    return isinstance(gametime, str) and gametime >= '19:00'


def team_games(games):
    """One row per team per played game, from that team's side: margin, its own spread, cover margin, total vs line."""
    g = games[games.result.notna()].copy()
    rows = []
    for r in g.itertuples(index=False):
        for side, opp in (('home', 'away'), ('away', 'home')):
            s = 1 if side == 'home' else -1
            line = -s * r.spread_line if pd.notna(r.spread_line) else None  # the team's own spread: -3 = favored by 3
            rows.append(dict(
                game_id=r.game_id, season=r.season, week=r.week, game_type=r.game_type, date=r.gameday,
                weekday=r.weekday, gametime=r.gametime, prime=primetime(r.gametime),
                team=FRANCHISE.get(getattr(r, side + '_team'), getattr(r, side + '_team')),
                opp=FRANCHISE.get(getattr(r, opp + '_team'), getattr(r, opp + '_team')),
                home=side == 'home', neutral=r.location == 'Neutral', divg=bool(r.div_game),
                pf=getattr(r, side + '_score'), pa=getattr(r, opp + '_score'), margin=s * r.result,
                line=line, cover=(s * (r.result - r.spread_line)) if pd.notna(r.spread_line) else None,
                total=r.total, total_line=r.total_line,
                ou=(r.total - r.total_line) if pd.notna(r.total_line) else None,
                qb=getattr(r, side + '_qb_name'), opp_qb=getattr(r, opp + '_qb_name'),
                coach=getattr(r, side + '_coach'), opp_coach=getattr(r, opp + '_coach'),
                rest=getattr(r, side + '_rest'), opp_rest=getattr(r, opp + '_rest')))
    return pd.DataFrame(rows).sort_values(['date', 'game_id']).reset_index(drop=True)


def rec(series, kind):
    """W-L-P from cover margins (kind='ats'), over/under margins ('ou') or straight-up margins ('su')."""
    s = series.dropna()
    w, l, p = int((s > 0).sum()), int((s < 0).sum()), int((s == 0).sum())
    return w, l, p


def fmt(w, l, p, kind):
    lab = {'ats': 'ATS', 'su': '', 'ou': ''}[kind]
    if kind == 'ou':
        return f"over {w}-{l}" + (f"-{p}" if p else '')
    return f"{w}-{l}" + (f"-{p}" if p else '') + (f" {lab}" if lab else '')


def streak(series):
    """Current run from the most recent game backwards: (+n wins/covers/overs, -n losses, 0 if last was a push).
    Pushes inside a losing run are counted as part of it and returned separately (books call it 0-12-1)."""
    s = [x for x in series.dropna().tolist()]
    if not s:
        return 0, 0
    last = next((x for x in reversed(s) if x != 0), 0)
    if last == 0:
        return 0, 0
    sign = 1 if last > 0 else -1
    n = pushes = 0
    for x in reversed(s):
        if x == 0:
            pushes += 1
        elif (x > 0) == (sign > 0):
            n += 1
        else:
            break
    return sign * n, pushes


def notable(w, l, n_min=8):
    n = w + l
    if n < 5:
        return 0
    rate = w / n
    if n < n_min and 0 < rate < 1:
        return 0
    if abs(rate - .5) < (.2 if n >= 12 else .25):
        return 0
    return abs(rate - .5) * math.sqrt(n)


def team_facts(T, team, opp, g):
    """Candidate facts for one side of an upcoming game g (a games.csv row). Returns [(score, text, tag)]."""
    me = T[T.team == team]
    out = []
    this = me[me.season == g.season]
    # this season, always shown
    w, l, p = rec(this.cover, 'ats')
    ow, ol, op = rec(this.ou, 'ou')
    out.append((99, f"{team} is {fmt(w, l, p, 'ats')} this season; its games are {fmt(ow, ol, op, 'ou')}.", 'season'))
    # streaks (ATS, straight up, over/under) across seasons, regular + playoffs
    for col, what in (('cover', 'ATS'), ('margin', 'SU'), ('ou', 'OU')):
        s, pushes = streak(me[col])
        n = abs(s)
        if n >= 4 or (col == 'cover' and n >= 3 and pushes):
            if col == 'cover':
                txt = (f"{team} has covered {n} straight" if s > 0 else
                       f"{team} hasn't covered in {n + pushes} straight (0-{n}" + (f"-{pushes}" if pushes else '') + ' ATS)')
            elif col == 'margin':
                txt = f"{team} has won {n} straight" if s > 0 else f"{team} has lost {n} straight"
            else:
                txt = f"{team} games have gone over {n} straight" if s > 0 else f"{team} games have stayed under {n} straight"
            out.append((1.5 + n / 2, txt + '.', 'streak'))
    # last 10 / last 20 ATS
    for k in (10, 20):
        last = me.tail(k)
        w, l, p = rec(last.cover, 'ats')
        sc = notable(w, l)
        if sc:
            out.append((sc, f"{team} is {fmt(w, l, p, 'ats')} in its last {k} games.", 'form'))
    since = me[me.season >= g.season - 3]
    is_home = g.home_team == team or FRANCHISE.get(g.home_team) == team
    my_line = -g.spread_line if is_home else g.spread_line
    # as favorite / underdog and home / road, last 3+ seasons
    role = 'favorite' if my_line < 0 else 'underdog'
    sl = since[(since.line < 0) if my_line < 0 else (since.line > 0)]
    w, l, p = rec(sl.cover, 'ats')
    sc = notable(w, l)
    if sc:
        out.append((sc, f"{team} is {fmt(w, l, p, 'ats')} as a{'n' if role[0] == 'u' else ''} {role} since {g.season - 3}.", 'role'))
    where = since[since.home == is_home]
    w, l, p = rec(where.cover, 'ats')
    sc = notable(w, l)
    if sc:
        out.append((sc, f"{team} is {fmt(w, l, p, 'ats')} {'at home' if is_home else 'on the road'} since {g.season - 3}.", 'venue'))
    ow, ol, op = rec(where.ou, 'ou')
    sc = notable(ow, ol)
    if sc:
        out.append((sc * .9, f"{team} {'home' if is_home else 'road'} games since {g.season - 3}: {fmt(ow, ol, op, 'ou')}.", 'venue'))
    # off a win / off a loss
    me2 = me.copy()
    me2['prev'] = me2.margin.shift(1)
    prev = me.margin.iloc[-1] if len(me) else 0
    sub = me2[(me2.season >= g.season - 3) & ((me2.prev > 0) if prev > 0 else (me2.prev < 0))]
    w, l, p = rec(sub.cover, 'ats')
    sc = notable(w, l)
    if sc:
        out.append((sc, f"{team} is {fmt(w, l, p, 'ats')} after a {'win' if prev > 0 else 'loss'} since {g.season - 3}.", 'spot'))
    # primetime
    if primetime(g.gametime):
        pt = me[(me.prime) & (me.season >= g.season - 5)]
        w, l, p = rec(pt.margin, 'su')
        aw, al, ap = rec(pt.cover, 'ats')
        if w + l >= 5:
            out.append((max(notable(w, l, 6), notable(aw, al, 6), .8), f"{team} in prime time since {g.season - 5}: {w}-{l}" + (f"-{p}" if p else '') + f" straight up, {fmt(aw, al, ap, 'ats')}.", 'prime'))
    # division
    if g.div_game:
        dv = since[since.divg]
        w, l, p = rec(dv.cover, 'ats')
        sc = notable(w, l)
        if sc:
            out.append((sc, f"{team} is {fmt(w, l, p, 'ats')} in division games since {g.season - 3}.", 'div'))
    # neutral / international
    if g.location == 'Neutral':
        nt = me[me.neutral & (me.game_type == 'REG')]
        w, l, p = rec(nt.margin, 'su')
        aw, al, ap = rec(nt.cover, 'ats')
        if w + l >= 3:
            out.append((2.5, f"{team} at neutral/international sites: {w}-{l} straight up, {fmt(aw, al, ap, 'ats')}.", 'neutral'))
    # rest edge
    if pd.notna(g.away_rest) and pd.notna(g.home_rest):
        mine, theirs = (g.home_rest, g.away_rest) if is_home else (g.away_rest, g.home_rest)
        if mine - theirs >= 3:
            out.append((2.2, f"{team} has {int(mine)} days of rest to the opponent's {int(theirs)}.", 'rest'))
    return out


def h2h_facts(T, away, home, g):
    m = T[(T.team == home) & (T.opp == away)]
    out = []
    if not len(m):
        return out
    last = m.tail(10)
    w, l, p = rec(last.margin, 'su')
    aw, al, ap = rec(last.cover, 'ats')
    ow, ol, op = rec(last.ou, 'ou')
    yrs = f"{int(last.season.min())}-{str(int(last.season.max()))[2:]}"
    out.append((99, f"Last {len(last)} meetings ({yrs}): {home} {w}-{l}" + (f"-{p}" if p else '') +
                f" straight up, {fmt(aw, al, ap, 'ats')}; {fmt(ow, ol, op, 'ou')}.", 'h2h'))
    s, pushes = streak(m.margin)
    if abs(s) >= 3:
        t = home if s > 0 else away
        out.append((2 + abs(s) / 2, f"{t} has won the last {abs(s)} meetings.", 'h2h'))
    s, pushes = streak(m.cover)
    if abs(s) >= 3:
        t = home if s > 0 else away
        out.append((2 + abs(s) / 2, f"{t} has covered the last {abs(s)} meetings.", 'h2h'))
    six = m.tail(6)
    if len(six) >= 4 and six.ou.notna().all():
        d = six.ou.mean()
        if abs(d) >= 4:
            out.append((abs(d) / 2, f"Last {len(six)} meetings averaged {six.total.mean():.1f} points, {abs(d):.1f} {'over' if d > 0 else 'under'} the closing total.", 'h2h'))
    return out


def qb_facts(T, qb, team, opp, g):
    """Starting-QB records from every start since 1999 (by name; nflverse lists the projected starter)."""
    if not isinstance(qb, str):
        return []
    q = T[T.qb == qb]
    out = []
    n = len(q)
    if n == 0:
        return [(50, f"{qb} would be making his first NFL start.", 'qb')]
    w, l, p = rec(q.margin, 'su')
    aw, al, ap = rec(q.cover, 'ats')
    out.append((60, f"{qb} as a starter: {w}-{l}" + (f"-{p}" if p else '') + f", {fmt(aw, al, ap, 'ats')} ({n} starts since 1999 in this data).", 'qb'))
    is_home = g.home_team == team
    my_line = -g.spread_line if is_home else g.spread_line
    if primetime(g.gametime):
        pt = q[q.prime]
        w, l, p = rec(pt.margin, 'su')
        aw, al, ap = rec(pt.cover, 'ats')
        if w + l >= 3:
            out.append((max(notable(w, l, 6), notable(aw, al, 6), 1.5), f"{qb} in prime time: {w}-{l}" + (f"-{p}" if p else '') + f" straight up, {fmt(aw, al, ap, 'ats')}.", 'qb'))
    role = q[(q.line > 0) if my_line > 0 else (q.line < 0)]
    w, l, p = rec(role.margin, 'su')
    aw, al, ap = rec(role.cover, 'ats')
    sc = max(notable(w, l), notable(aw, al))
    if sc:
        out.append((sc, f"{qb} as a{'n underdog' if my_line > 0 else ' favorite'}: {w}-{l} straight up, {fmt(aw, al, ap, 'ats')}.", 'qb'))
    vs = q[q.opp == opp]
    if len(vs) >= 2:
        w, l, p = rec(vs.margin, 'su')
        aw, al, ap = rec(vs.cover, 'ats')
        out.append((max(notable(w, l, 3), notable(aw, al, 3), 1.2 if len(vs) >= 3 else .8), f"{qb} vs {opp}: {w}-{l}" + (f"-{p}" if p else '') + f" straight up, {fmt(aw, al, ap, 'ats')}.", 'qb'))
    if n >= 10:
        last = q.tail(10)
        aw, al, ap = rec(last.cover, 'ats')
        sc = notable(aw, al)
        if sc:
            out.append((sc, f"{qb} is {fmt(aw, al, ap, 'ats')} in his last 10 starts.", 'qb'))
    if is_home is False:
        rd = q[~q.home & ~q.neutral]
        w, l, p = rec(rd.margin, 'su')
        sc = notable(w, l, 10)
        if sc:
            out.append((sc, f"{qb} on the road: {w}-{l} straight up.", 'qb'))
    return out


def coach_facts(T, coach, team, g):
    if not isinstance(coach, str):
        return []
    c = T[T.coach == coach]
    out = []
    if len(c) < 6:
        if len(c) < 17:
            out.append((1.0, f"{coach} is in his first season as a head coach ({len(c)} games).", 'coach'))
        return out
    is_home = g.home_team == team
    my_line = -g.spread_line if is_home else g.spread_line
    role = c[(c.line > 0) if my_line > 0 else (c.line < 0)]
    aw, al, ap = rec(role.cover, 'ats')
    sc = notable(aw, al, 10)
    if sc:
        out.append((sc, f"{coach} as a{'n underdog' if my_line > 0 else ' favorite'}: {fmt(aw, al, ap, 'ats')} as a head coach.", 'coach'))
    c2 = c.copy()
    c2['prev'] = c2.margin.shift(1)
    prev = c.margin.iloc[-1]
    sub = c2[(c2.prev < 0) if prev < 0 else (c2.prev > 0)]
    aw, al, ap = rec(sub.cover, 'ats')
    sc = notable(aw, al, 10)
    if sc:
        out.append((sc, f"{coach} after a {'loss' if prev < 0 else 'win'}: {fmt(aw, al, ap, 'ats')} as a head coach.", 'coach'))
    return out


def pick(facts, k):
    """Always keep the score-99/60/50 'context' lines, then the k strongest notable facts."""
    facts = sorted(facts, key=lambda x: -x[0])
    seen, out = set(), []
    for sc, txt, tag in facts:
        if txt in seen:
            continue
        seen.add(txt)
        out.append(dict(text=txt, tag=tag, score=round(sc, 2)))
    ctx = [f for f in out if f['score'] >= 50]
    rest = [f for f in out if f['score'] < 50][:k]
    return ctx + rest

