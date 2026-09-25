/* ============================ MODEL TAB COPY ============================ */
function MODEL_HTML(){
  const card=(t,g,cls,p)=>`<div class="rcard"><h4>${t}<span class="grade ${cls}">${g}</span></h4><p>${p}</p></div>`;
  return `<div class="prose">
  <div class="callout"><b>Short version.</b> Five bet types, three separate models. Touchdowns and yardage/catch props come from the player simulation, each priced its own way. Moneyline and spread come from a game model that never touches the player numbers. Everything is graded against real DraftKings prices. The touchdown and prop models know things DraftKings' price doesn't, but only the props have shown a profit in testing, and not yet in 2026. The game model now registers team strength, but it still hasn't beaten DraftKings' closing lines. Built to be refreshed and used right before kickoff.</div>

  <h3>Report card</h3></div>
  <div class="rgrid">
    ${card("Anytime TD","real but small","m",`Graded against 8,697 DraftKings anytime-TD prices from about 5 minutes before kickoff (2023–24), fitting on one season and testing on the other. Combined with DraftKings' price, the model beat DraftKings alone in both: 2024 log loss 0.4702 vs 0.4715, 2023 0.4304 vs 0.4314; 2026 Weeks 1–2 (166 prices) 0.5038 vs 0.5061. DraftKings' touchdown hold is still bigger than that edge: betting the players that cleared it lost 9% (2024) and 2% (2023).`)}
    ${card("Yards and catches","promising, unproven","m",`937 graded DraftKings props (receiving yards, rushing yards, catches), 2024–26. The chance shown is 80% DraftKings' no-vig price and 20% simulation. That beat DraftKings in 2024 (0.689 vs 0.700) and 2025 (0.681 vs 0.689) and was about even in 2026 (0.694 vs 0.693). Bets it picked returned +13% ± 6% over 288 bets: +46% in 2024, +17% in 2025, −0.5% in 2026 so far.`)}
    ${card("Moneyline and spread","better model, still no edge","b",`Rebuilt to register team strength: a rating from every team's past closing lines (it carries defense, roster and coaching, which the play-by-play numbers missed), plus opponent-adjusted efficiency, each starting quarterback's record, a second-year-quarterback term, rest and home field. Tuned on 2016–20, tested on 2021–25: average miss 10.03 points, down from 10.30 (the closing line's is 9.75). At closing prices, when it disagreed by 3+ points its side covered 52.5% (+1.9% ± 3.5% after DraftKings' price, −2.3% in 2021–25). Moneylines lost at DraftKings' prices. Priced from DraftKings' own odds, moved 10% toward the model.`)}
    ${card("Role signals","helped","g",`New this version: snap-share trend, practice participation, players returning from a missed game, and one-game samples. Held out one season at a time, they cut running-back carry-share error 4–5% in every season and target-share error about 1%. They improved touchdown accuracy against DraftKings in every test and prop bets from +7.5% to +13%.`)}
    ${card("TD calibration","calibrated","g",`Refit on 2025 weeks 4–18 with players known before kickoff (4,199 player-games): Brier 0.1414 against 0.1576 for a constant. Quarterback scramble touchdowns are counted.`)}
    ${card("Team ratings and line flags","a lean, not an edge","m",`Every team gets a value in points (Teams tab): market strength, this week's quarterback and opponent-adjusted efficiency. A game's fair line is home field plus the difference. When DraftKings' spread sits 3+ points from it, the game is flagged. Since 2016 (each season rated only from earlier seasons), flagged sides covered 52.7% against closing lines: +2.4% ± 3.5%, profitable in 7 of 10 seasons, about 4 a week. Moneylines on the same games lost 4%. The ratings also fixed a long-standing bug: defense had been counted backwards.`)}
    ${card("Coaching","one piece helped","m",`Each head coach's fourth-down aggressiveness (last three seasons, any team, league trend removed) shifts how often his team goes for it, which changes how many drives end in touchdowns instead of field goals. Fourth-down rates were updated to 2024–26 behaviour (4th-and-1 in plus territory: 90%, was 80%). Tested and rejected: discounting last season's usage and pass rate for teams with a new head coach made shares slightly worse.`)}
    ${card("Matchup history","no signal","b",`Tested on every game since 1999 and every player-game since 2012: team vs team, head coach vs head coach, player vs a defense, player vs a coach, and an offense vs a defense against its implied total. Every correlation was zero within noise once the line and recent form were known, so none of it is used.`)}
    ${card("Kept separate","by design","g",`The game model uses no player numbers, and the player simulation uses DraftKings' spread and total only to set how many points each team scores. Scratching a player changes touchdowns, yards and catches, never the moneyline or spread. Bets are singles only: parlays were never validated, and they multiply DraftKings' hold.`)}
  </div>
  <div class="prose">
  <h3>How to use this against DraftKings</h3>
  <ul>
    <li><b>Yards and catches: small stakes on the Best value list.</b> This is the only market with a positive test record. It hasn't shown it in 2026 yet, and early-season usage is the weakest part of the model.</li>
    <li><b>Touchdowns: bet news, not the board.</b> At kickoff prices DraftKings' hold is bigger than the model's edge. The window is between news (a starter ruled out, a new goal-line back) and DraftKings repricing. Scratch the player under Games and his teammates' numbers update at once.</li>
    <li><b>Moneyline and spread: use the flags as a lean, not a bet.</b> Flags are for spreads only. The game model now sees team strength and predicts where lines move (sides it liked on Tuesday closed its way 46% of the time and against it 27%), but at the closing price it hasn't shown a profit.</li>
    <li><b>Right before kickoff:</b> ask for a refresh (it pulls the official injury report, the newest DraftKings lines and props, and reruns everything), then scratch anyone announced inactive.</li>
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
  <p><b>Player simulation</b> (touchdowns, yards, catches): every snap is played out, and every yard goes to a named player based on his recent share of carries and targets, corrected for role signals. Each offense's efficiency is solved so DraftKings' spread and total land on the simulation's 50/50 point. Fourth-down decisions follow each head coach's own aggressiveness. Weather reaches the simulation only through DraftKings' total. <b>Game model</b> (moneyline, spread): a regression on team strength from past closing lines, each team's opponent-adjusted expected points per play and success rate, the starting quarterback's own expected points per dropback (and whether he is in his second season), rest and home field. Everything is weighted toward recent games and carried across seasons.</p>

  <h3>Tested and rejected</h3>
  <ul>
    <li>Route participation: helpful in principle, but not published for 2026, so the live page couldn't use it.</li>
    <li>Betting the game model's moneylines: lost money in three of four test seasons.</li>
    <li>A per-market "overs are overpriced" prop correction: failed out of sample once a grading bug was fixed.</li>
    <li>A 50/50 model/book average on touchdowns, position-specific TD adjustments, coverage-scheme adjustments, goal-line (inside the 5) weighting: no improvement.</li>
    <li>Where a defense gives up its touchdowns (to backs, receivers or tight ends; run vs pass): pure noise (split-half correlation about zero over 2016–25), now removed from touchdown odds. The target-share and yardage parts of the defense profile stay.</li>
    <li>Head-to-head and coach-vs-coach history, player-vs-team history: no signal.</li>
    <li>Discounting last season for teams with a new head coach: slightly worse usage and pass-rate estimates.</li>
    <li>Recalibrating the simulation's prop chances per market: made the 80/20 blend worse (its lean toward unders is useful).</li>
    <li>For spreads and moneylines, against closing lines (walk-forward, 2012–25): rest, short weeks, byes, travel and time zones, west-coast teams in early games, primetime, late season, wind, recent covers, last game's margin, QB changes, and Tuesday-to-close line movement, alone or in boosted-tree models. All did no better than a coin flip. Betting DraftKings when its price was off the rest of the market: its spreads almost never are, and its off-market moneylines lost. Training the game model directly on the closing line instead of the score: same results.</li>
  </ul>

  <h3>Known limits</h3>
  <ul>
    <li>2026 is two weeks of data, and it's the season where every model did worst. Early-season usage leans on last year.</li>
    <li>TD grading used kickoff prices; earlier-week DraftKings prices weren't available to test.</li>
    <li>Official game statuses post Friday afternoon and are read automatically by the refresh (Out and Doubtful removed, Questionable flagged). Inactives announced 90 minutes before kickoff aren't in any feed: scratch them on the game card.</li>
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
