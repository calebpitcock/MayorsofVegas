/* ============================ MODEL TAB COPY ============================ */
function MODEL_HTML(){
  const card=(t,g,cls,p)=>`<div class="rcard"><h4>${t}<span class="grade ${cls}">${g}</span></h4><p>${p}</p></div>`;
  return `<div class="prose">
  <div class="callout"><b>Short version.</b> Five bet types, three separate models. Touchdowns and yardage/catch props come from the player simulation, each priced its own way. Moneyline and spread come from a game model that never touches the player numbers. Everything is graded against real DraftKings prices. The touchdown and prop models know things DraftKings' price doesn't, but only the props have shown a profit in testing, and not yet in 2026. The game model doesn't beat DraftKings.</div>

  <h3>Report card</h3></div>
  <div class="rgrid">
    ${card("Anytime TD","real but small","m",`Graded against 8,697 DraftKings anytime-TD prices from about 5 minutes before kickoff (2023–24), plus 432 from 2026 Weeks 1–2. Combined with DraftKings' price, the model beat DraftKings alone in every test: 2024 (log loss 0.4701 vs 0.4715; 95% interval clear of zero), 2023 (0.4304 vs 0.4314) and 2026 (0.4310 vs 0.4330). DraftKings' touchdown hold is still bigger than that edge: at kickoff, betting the players that cleared it lost 2% (2023) and 11% (2024).`)}
    ${card("Yards and catches","promising, unproven","m",`937 graded DraftKings props (receiving yards, rushing yards, catches), 2024–26. The chance shown is 80% DraftKings' no-vig price and 20% simulation. That beat DraftKings in 2024 (0.689 vs 0.700) and 2025 (0.681 vs 0.689) and was about even in 2026 (0.694 vs 0.693). Bets it picked returned +13% ± 6% over 288 bets: +46% in 2024, +17% in 2025, −0.5% in 2026 so far.`)}
    ${card("Moneyline and spread","no edge","b",`A separate game model: opponent-adjusted efficiency, each starting quarterback's own record, rest and home field. It was trained only on earlier seasons, tuned on 2016–20 and tested on 2021–25. Against DraftKings' Tuesday lines (1,339 games), it predicts which way the line moves: sides it liked closed its way 42% of the time and against it 31%. Priced from DraftKings' own odds and moved 15% toward the model, spread bets broke even (0% ± 5%) and moneyline bets lost about 9%.`)}
    ${card("Role signals","helped","g",`New this version: snap-share trend, practice participation, players returning from a missed game, and one-game samples. Held out one season at a time, they cut running-back carry-share error 4–5% in every season and target-share error about 1%. They improved touchdown accuracy against DraftKings in every test and prop bets from +7.5% to +13%.`)}
    ${card("TD calibration","calibrated","g",`2025 held-out weeks 12–18: Brier 0.1430 against 0.1585 for a constant. Quarterback scramble touchdowns are counted, which moved the quarterback correction up (+0.48).`)}
    ${card("Kept separate","by design","g",`The game model uses no player numbers, and the player simulation uses DraftKings' spread and total only to set how many points each team scores. Scratching a player changes touchdowns, yards and catches, never the moneyline or spread. Bets are singles only: parlays were never validated, and they multiply DraftKings' hold.`)}
  </div>
  <div class="prose">
  <h3>How to use this against DraftKings</h3>
  <ul>
    <li><b>Yards and catches: small stakes on the Best value list.</b> This is the only market with a positive test record. It hasn't shown it in 2026 yet, and early-season usage is the weakest part of the model.</li>
    <li><b>Touchdowns: bet news, not the board.</b> At kickoff prices DraftKings' hold is bigger than the model's edge. The window is between news (a starter ruled out, a new goal-line back) and DraftKings repricing. Scratch the player under Games and his teammates' numbers update at once.</li>
    <li><b>Moneyline and spread: early in the week, if at all.</b> The model's one real skill is anticipating where the line goes. A side it likes on Tuesday tends to get a better number than it closes at, but that hasn't been enough to win.</li>
    <li><b>Avoid long-shot TDs and QB rushing unders.</b> Blind TD bets longer than +600 lost 21–29%. Quarterback rushing unders lost 24% over three seasons.</li>
    <li><b>Type the real price.</b> Prices marked ≈ are estimates. In the slip, the chance and EV recalculate at whatever DraftKings price you type.</li>
    <li><b>Log every bet with its closing price.</b> Beating the close is the fastest honest signal of an edge.</li>
  </ul>

  <h3>Where the numbers come from</h3>
  <ul>
    <li><b>Usage and roles</b>: nflverse play-by-play (2012–2026) and snap counts, plus nflverse practice reports (2022–2026).</li>
    <li><b>DraftKings props and game lines this week</b>: davidcantugtr/nfl-player-prop-opportunity (Odds API snapshots on GitHub).</li>
    <li><b>Anytime-TD prices this week</b>: jaredpatchett/NFL-Model (best price across books), converted to an estimated DraftKings price.</li>
    <li><b>Grading</b>: mogden16/NFL-Wizard-Analysis (anytime-TD quotes 2023–24 and 2026), jaredpatchett/NFL-Model (2024–25 props, and Tuesday DraftKings game lines 2021–25), davidcantugtr snapshots (2026 props), nflverse schedules (closing lines and results since 1999).</li>
  </ul>

  <h3>How the models work</h3>
  <p><b>Player simulation</b> (touchdowns, yards, catches): every snap is played out, and every yard goes to a named player based on his recent share of carries and targets, corrected for role signals. Each offense's efficiency is solved so DraftKings' spread and total land on the simulation's 50/50 point. <b>Game model</b> (moneyline, spread): a regression on each team's opponent-adjusted expected points per play, pass and run, and success rate. Ratings are weighted toward recent games and carried across seasons. It adds the starting quarterback's own expected points per dropback compared with the quarterbacks behind the team's recent numbers, plus rest and home field.</p>

  <h3>Tested and rejected</h3>
  <ul>
    <li>Route participation: helpful in principle, but not published for 2026, so the live page couldn't use it.</li>
    <li>Betting the game model's moneylines: lost money in three of four test seasons.</li>
    <li>A per-market "overs are overpriced" prop correction: failed out of sample once a grading bug was fixed.</li>
    <li>A 50/50 model/book average on touchdowns, position-specific TD adjustments, defense-versus-position and coverage-scheme adjustments, goal-line (inside the 5) weighting: no improvement.</li>
  </ul>

  <h3>Known limits</h3>
  <ul>
    <li>2026 is two weeks of data, and it's the season where every model did worst. Early-season usage leans on last year.</li>
    <li>TD grading used kickoff prices; earlier-week DraftKings prices weren't available to test.</li>
    <li>Official game statuses post Friday afternoon. Until then, the flagged questionable list stands in.</li>
    <li>The game model's margin is turned into chances with a smooth curve, so it slightly misprices spreads on key numbers (3 and 7).</li>
  </ul>

  <h3>Tuning</h3>
  <div class="knobs">
    <div class="knob"><label for="kProp">Prop DraftKings weight <b id="vProp">${Math.round(100*LAMP)}%</b></label><input type="range" id="kProp" min="0" max="100" value="${Math.round(100*LAMP)}"></div>
    <div class="knob"><label for="kTrust">Usage trust <b id="vTrust">${Math.round(100*TRUST)}%</b></label><input type="range" id="kTrust" min="50" max="100" value="${Math.round(100*TRUST)}"></div>
  </div>
  <p class="empty">DraftKings weight is how much of a prop's chance comes from DraftKings' own no-vig price; the rest is the simulation. 80% held up best tested one season at a time. Touchdowns and game lines use fitted weights and have no slider. Usage trust shrinks each player's share toward a positional baseline.</p>
  </div>`;
}
