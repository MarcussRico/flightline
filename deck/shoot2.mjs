import { chromium } from '/Users/sai/kneescope/node_modules/playwright/index.mjs';
const OUT = '/private/tmp/claude-501/-Users-sai/ae59e700-15de-4417-810f-41855f20d109/scratchpad/deckbuild/shots';
const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1600, height: 1000 }, deviceScaleFactor: 2 });
await p.goto('http://127.0.0.1:8000/'); await p.waitForSelector('#app:not([hidden])'); await p.evaluate(() => document.fonts.ready);
await p.addStyleTag({ content: '.topbar{position:static!important} section.card{align-self:start}' });
await p.click('.seg button[data-view="baseline"]'); await p.waitForTimeout(300);
await p.locator('section[aria-labelledby="wf-h"]').screenshot({ path: `${OUT}/waterfall_baseline.png` });
await p.locator('section[aria-labelledby="board-h"]').screenshot({ path: `${OUT}/board_baseline.png` });
await b.close();
