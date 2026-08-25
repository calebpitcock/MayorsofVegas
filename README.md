# Beer League Flappy Buck

A one-tap arcade game that sets the draft order for **Beer League**, the fantasy football
league of the **Mayors of Vegas** — eight Ohio State grads, class of 2025, now scattered
across the country.

Everyone plays the same game on their phone. Best score picks first. The combine closes
at **midnight ET as Saturday, August 29 begins**, and whatever is on the board at that
moment is final.

---

## The game

Tap to keep the football airborne and thread the uprights.

| Thing | Worth |
| --- | --- |
| Splitting the uprights | **+1** |
| Buckeye leaf in the gap | **+5** |
| Cold one in the gap | **+5** |

The gaps tighten and the field speeds up as your score climbs. Every 10 points the
screen throws up **O-H!**, then **I-O!** at 20, alternating the rest of the way.

The play area is locked to a fixed 400×640 ratio on every device, so a bigger phone
never means an easier game. Run it as many times as you want — only your **best** score
sticks to the board.

## How the draft order gets set

The league runs in two phases.

**1. The combine.** Everyone grinds scores. The board ranks all eight players live. Ties
break toward whoever got there first.

**2. The claims.** When the clock hits zero the combine closes itself and slot-claiming
opens. Players choose **in score order** — highest score first — and each one takes
**any open slot they want**. That is the whole point: winning the combine doesn't hand
you the first overall pick, it hands you the *choice*. Take pick 1, or take pick 8 for
the back-to-back turn. Your call.

The board shows who is on the clock. Only that player sees claim buttons.

### The deadline

The cutoff is one shared instant — `2026-08-29T00:00:00-04:00`, epoch
`1787976000000` — not each viewer's local midnight, so all eight of you race the same
clock regardless of timezone. The countdown card shows that moment translated into your
own local time, and turns scarlet inside the final 24 hours.

When it passes, the first open page to notice flips the league to the claim phase and
publishes once. Nobody has to be awake for it.

## Ohio State, throughout

- The **Horseshoe** rolls past in the background — bowl, scarlet rim, lit concourse, two
  light standards throwing glow into the night
- A **Block O** at midfield on the scrolling turf
- **Buckeye leaves** as the bonus pickup, sharing gaps with the beer cans
- **O-H! / I-O!** on every tenth point
- Scarlet-and-silver helmet stripe under the wordmark; scarlet stripes on the ball

---

## Repository layout

```
.
├── index.html          built — complete standalone page (GitHub Pages, file://)
├── dist/artifact.html  built — body-content only, for publishing as a Claude Artifact
├── src/
│   ├── head.html       <title>, fonts, the entire stylesheet
│   ├── body1.html      league state, shared-board publishing, countdown, UI
│   └── body2.html      audio, the canvas game engine, event wiring, boot
├── live_state.json     the league board — scores, claims, phase
└── build.py            assembles src/ into both built outputs
```

**Never hand-edit `index.html` or `dist/artifact.html`.** They are generated. Edit
`src/` and rebuild:

```bash
python3 build.py
```

No dependencies — standard-library Python 3 only. The build refuses to write anything if
its self-consistency checks fail.

## How the shared scoreboard works

There is no server and no database. The page **is** the database.

The league board lives in a `<script id="league-state" type="application/json">` block
inside the page. When you beat your personal best, the page rebuilds its own source with
the new state swapped in and republishes itself as a new version of the artifact. Every
open copy live-reloads to it.

It can do that because the page carries a base64 copy of its own source in
`<script id="tpl">`, with placeholders where the state and that copy belong. Rebuilding
means decoding it, substituting both, and publishing. `build.py` verifies this round-trip
is an exact **fixed point** — the page reproduces itself byte-for-byte — because a page
that drifts on each republish would corrupt itself after a few scores.

Two details worth knowing if you touch this:

- **Publishing is rare on purpose.** A run only publishes if it beat your previous best.
  Ordinary runs never touch the network, so a bad night doesn't spam versions.
- **Identity rides in the URL hash** (`#p=Tyler`). A publish reloads the page, and
  artifacts can run in sandboxes where `localStorage` throws — the hash survives both,
  so nobody gets bounced back to the name picker after setting a best.

### Running it

**As a Claude Artifact** (the real thing, shared board and all): publish
`dist/artifact.html` with the `artifact` capability declared. Share the link **with edit
access** — scores post using each viewer's own authority, so a read-only viewer can play
but cannot post. The page detects this and says so plainly rather than silently dropping
the score.

**As a static page** (GitHub Pages, or just opening `index.html`): fully playable, but
there is no shared board — it runs in practice mode and says so. Scores stay on that
device.

## Never wipe the board

The live artifact carries the league's **real scores** inside it, and the players' own
runs republish it. A rebuild from source ships whatever is in `live_state.json` — so
publishing a code change without syncing first will erase everyone's results.

Before shipping any change:

1. Fetch the live artifact and copy the JSON out of its `league-state` script tag.
2. Paste it into `live_state.json`.
3. `python3 build.py`
4. Publish `dist/artifact.html`.

`build.py` prints the board it baked in — check that line before you publish.

## Commissioner controls

At the bottom of the page, behind a disclosure. Every button needs a second tap to
confirm.

| Control | Effect |
| --- | --- |
| Close the combine now | Freezes scores and opens claims early |
| Reopen the combine | Clears all claims, resumes scoring, **and overrides the Aug 29 clock** |
| Wipe all scores and picks | Full reset |

Reopening sets `ignoreDeadline` in the league state, so a manual reopen after the cutoff
doesn't get instantly re-closed by the timer.

---

## The league

Tyler · Ryan · Gabe · Donald · Austin · Andrew · Caleb · John

Go Bucks.
