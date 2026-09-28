"""Formation matchup (v3.7, UNTESTED against DraftKings — see HANDOFF addendum). Writes g.form onto each game.

Offense personnel (share of plays with 3+ WR; the rest is heavy: 2+ TE or 2+ RB) meets the defense's box and package
tendencies (light box <= 6, heavy box 8+, sub-package = nickel/dime rate).
  1. Box mix the offense should see: the defense's own light/heavy rates, shifted by this offense's heaviness.
     Heavy personnel vs a defense that stays in nickel/dime -> more light boxes; vs a defense that matches with base
     -> more heavy boxes. Shift = C x (offense heavy rate - league) split by the defense's sub rate.
  2. Run efficiency from that box mix with league yards per carry by box (light 5.2, 7-man 4.5, 8+ 3.8), relative to a
     league-average matchup, then DAMPED: box counts partly follow the situation (short yardage), and the model's
     defense yards-per-carry term already carries some of it.
2026 rates are shrunk toward the league mean by sample size (few games so far). Team scoring is still anchored to
DraftKings, so this moves WHO gets the yards and touchdowns (backs vs pass catchers), not how many points a team scores.
Usage: python3 formation.py slate_nfl.json [formation_2026.json]"""
import json, sys
YPC = dict(light=5.2, base=4.5, heavy=3.8)
C, DAMP, CAP = 0.5, 0.4, 0.06
# Position shifts (targets and yards per target), UNTESTED sizes; direction from the personnel mechanism:
#   base defense vs 3-WR sets -> linebackers cover TEs/RBs (mismatch for them);
#   nickel/dime vs heavy sets -> a defensive back covers the TE (mismatch removed; the run game gets the light box).
# WRs are not shifted directly: target weights are shared within a team, so TE/RB gains come out of the WRs.
POS = dict(TE=dict(tgt=(0.6, -0.4), ypt=(0.3, -0.2)), RB=dict(tgt=(0.5, 0.0), ypt=(0.3, 0.0)))
PCAP = 0.08
# Slot (v3.7c): the linebacker-in-coverage mismatch hits whoever lines up in the slot. WRs get targets/yards shifts
# scaled by their slot rate s (share of snaps in the slot); a TE's shift is re-weighted toward his slot/move share.
SLOT = dict(tgt=0.6, ypt=0.3)
K_OFF, N_DEF, K_DEF = 150, 120, 150        # shrinkage pseudo-plays; defensive sample size not published, assumed ~2 games

def attach(games, F, SL):
    """Write g['form'] onto each game. F = {'off': {team: [p3wr, plays]}, 'def': {team: [blitz, light, heavy, sub(, plays)]}}
    (a defense's play count is optional; without it N_DEF is assumed). SL = {player name: slot rate}."""
    off = {k: v for k, v in F['off'].items() if not k.startswith('_')}
    dfn = {k: v for k, v in F['def'].items() if not k.startswith('_')}
    mean = lambda xs: sum(xs) / len(xs)
    lg = dict(heavy=mean([1 - v[0] for v in off.values()]), light=mean([v[1] for v in dfn.values()]),
              hbox=mean([v[2] for v in dfn.values()]), sub=mean([v[3] for v in dfn.values()]))
    ypc = lambda L, H: L * YPC['light'] + H * YPC['heavy'] + (1 - L - H) * YPC['base']
    base = ypc(lg['light'], lg['hbox'])
    for g in games:
        g['form'] = {}
        for side, team, opp in (('away', g['away'], g['home']), ('home', g['home'], g['away'])):
            if team not in off or opp not in dfn: continue
            p3, n = off[team]; w = n / (n + K_OFF)
            heavy = w * (1 - p3) + (1 - w) * lg['heavy']
            nd = dfn[opp][4] if len(dfn[opp]) > 4 else N_DEF; wd = nd / (nd + K_DEF)
            _, L0, H0, sub = dfn[opp][:4]
            L0, H0, sub = (wd * L0 + (1 - wd) * lg['light'], wd * H0 + (1 - wd) * lg['hbox'], wd * sub + (1 - wd) * lg['sub'])
            d = C * (heavy - lg['heavy'])
            L = min(.9, max(0, L0 + d * sub)); H = min(.9, max(0, H0 + d * (1 - sub)))
            raw = ypc(L, H) / base
            m = max(1 - CAP, min(1 + CAP, 1 + DAMP * (raw - 1)))
            pct = lambda x: f"{round(100 * x)}%"
            txt = (f"{team} is in heavy personnel (2+ TE or 2+ RB) on {pct(1 - p3)} of plays (league {pct(lg['heavy'])}); "
                   f"{opp} plays a light box on {pct(dfn[opp][1])} of snaps (league {pct(lg['light'])}), a stacked box on {pct(dfn[opp][2])} "
                   f"(league {pct(lg['hbox'])}), and nickel/dime on {pct(dfn[opp][3])} (league {pct(lg['sub'])}). ")
            txt += f"Against {team}'s personnel, expect {pct(L)} light and {pct(H)} stacked boxes -> {team} run efficiency {'+' if m >= 1 else '−'}{abs(100 * (m - 1)):.1f}%."
            # personnel mismatches (shrunk rates): LBs covering a 3-WR set, and nickel/dime covering a heavy set
            baseR = 1 - sub; bv = (1 - heavy) * baseR - (1 - lg['heavy']) * (1 - lg['sub'])
            nh = heavy * sub - lg['heavy'] * lg['sub']
            pos = {}
            for P, c in POS.items():
                mk = lambda k: round(max(1 - PCAP, min(1 + PCAP, 1 + c[k][0] * bv + c[k][1] * nh)), 4)
                pos[P] = dict(tgt=mk('tgt'), ypt=mk('ypt'))
            te, rb = pos['TE'], pos['RB']
            if abs(te['tgt'] - 1) >= .01 or abs(rb['tgt'] - 1) >= .01:
                why = []
                if abs(bv) >= .01: why.append(f"{opp} is in base personnel {'more' if bv > 0 else 'less'} than usual against {team}'s 3-WR looks, so linebackers cover backs and tight ends {'more' if bv > 0 else 'less'} often")
                if abs(nh) >= .01: why.append(f"{opp} often answers {team}'s heavy sets with nickel/dime, putting a defensive back on the tight end" if nh > 0 else f"heavy personnel against nickel/dime, which puts a defensive back on the tight end, should come up less than usual in this game")
                txt += (f" Targets: tight ends {'+' if te['tgt'] >= 1 else '−'}{abs(100 * (te['tgt'] - 1)):.1f}%, backs {'+' if rb['tgt'] >= 1 else '−'}{abs(100 * (rb['tgt'] - 1)):.1f}% "
                        f"(receivers give up the difference), because " + "; and ".join(why) + ".")
            players, slots = {}, []
            for pl in g.get('players', []):
                if pl.get('t') != team or pl['n'] not in SL: continue
                sr = float(SL[pl['n']]); pl['slot'] = round(sr, 3)
                if pl['pos'] == 'WR':
                    mk2 = lambda k: round(max(1 - PCAP, min(1 + PCAP, 1 + SLOT[k] * bv * sr)), 4)
                    players[pl['n']] = dict(tgt=mk2('tgt'), ypt=mk2('ypt')); slots.append((pl['n'], sr, players[pl['n']]['tgt']))
                elif pl['pos'] == 'TE':   # inline TEs rarely draw the linebacker mismatch; slot/move TEs do
                    w = 0.5 + sr
                    players[pl['n']] = {k: round(max(1 - PCAP, min(1 + PCAP, 1 + w * (v - 1))), 4) for k, v in pos['TE'].items()}
            if slots and abs(bv) >= .01:
                slots.sort(key=lambda x: -x[1])
                txt += " Slot: " + ", ".join(f"{n} ({round(100*sr)}% slot) targets {'+' if t >= 1 else '−'}{abs(100*(t-1)):.1f}%" for n, sr, t in slots[:3]) + "."
            g['form'][side] = dict(run=round(m, 4), light=round(L, 3), heavy=round(H, 3), heavyPers=round(heavy, 3), pos=pos, players=players, text=txt)

def run():
    import os
    f = sys.argv[1] if len(sys.argv) > 1 else 'slate_nfl.json'
    sp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'slot_2026.json')
    SL = json.load(open(sp)).get('players', {}) if os.path.exists(sp) else {}
    F = json.load(open(sys.argv[2] if len(sys.argv) > 2 else 'formation_2026.json'))
    S = json.load(open(f)); attach(S['games'], F, SL)
    json.dump(S, open(f, 'w'))
    for g in S['games']:
        for s in ('away', 'home'):
            if s in g['form']: print(g['id'], s, g['form'][s]['run'], '|', g['form'][s]['text'])
if __name__ == '__main__': run()
