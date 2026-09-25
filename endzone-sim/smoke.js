// Smoke test: load the built page in Chromium, let the simulations finish, check the game cards, the wind box and
// the props tab, and fail on any page error. Usage: NODE_PATH=$(npm root -g) node smoke.js [endzone.html]
const { chromium } = require('playwright');
(async () => {
  const f = 'file://' + require('path').resolve(process.argv[2] || 'endzone.html');
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 390, height: 844 } }); const errs = [];
  p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/ERR_CERT|fonts/.test(m.text())) errs.push(m.text()); });
  await p.goto(f); await p.waitForFunction(() => document.querySelectorAll('.prow').length > 20, null, { timeout: 240000 });
  await p.waitForFunction(() => document.querySelector('#prog i').style.width === '0%', null, { timeout: 240000 });
  const cards = await p.$$eval('.gcard', x => x.length), winds = await p.$$eval('input[data-wind]', x => x.length);
  const why = await p.$$eval('.gmwhy', x => x.slice(0, 3).map(e => e.textContent.trim()));
  const td0 = await p.$eval('.gcard .prow', e => e.textContent.replace(/\s+/g, ' ').trim());
  const w = await p.$('input[data-wind]'); const gid = await w.getAttribute('data-wind');
  await w.fill('22'); await w.dispatchEvent('change'); await p.waitForTimeout(4000);
  const note = await p.$eval(`#g-${gid} .flagrow .tiny:last-child`, e => e.textContent);
  await p.screenshot({ path: 'smoke_games.png', fullPage: false });
  await p.click('nav.bot [data-tab="props"]'); await p.waitForTimeout(1500);
  const props = await p.$$eval('#tab-props li, #tab-props .prop', x => x.length);
  console.log(JSON.stringify({ cards, winds, why, td0, windNote: note, props, errors: errs }, null, 1));
  await b.close(); if (errs.length || !cards || !props) process.exit(1);
})();
