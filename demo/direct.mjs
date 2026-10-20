// FLIGHTLINE demo film: drives the real app, overlays captions/arrows/cursor, captures frames via CDP screencast.
import { chromium } from '/Users/sai/kneescope/node_modules/playwright/index.mjs';
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.dirname(new URL(import.meta.url).pathname);
const FRAMES = path.join(DIR, 'frames');
fs.mkdirSync(FRAMES, { recursive: true });
for (const f of fs.readdirSync(FRAMES)) fs.unlinkSync(path.join(FRAMES, f));
const APP = 'http://127.0.0.1:8000/';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const OVERLAY_CSS = `
#demo { position: fixed; inset: 0; pointer-events: none; z-index: 99999; font-family: Geist, system-ui, sans-serif; }
#demo svg.arrows { position: absolute; inset: 0; width: 100%; height: 100%; overflow: visible; }
#demo .callout { position: absolute; max-width: 340px; background: #111827; color: #fff; border-radius: 12px; padding: 12px 16px;
  font-size: 18px; line-height: 1.35; font-weight: 500; box-shadow: 0 18px 40px -12px rgba(17,24,39,.5); opacity: 0; transform: translateY(6px) scale(.98);
  transition: opacity .35s ease, transform .35s ease; border-left: 4px solid #d1338f; }
#demo .callout b { color: #f9a8d4; font-weight: 600; }
#demo .callout.on { opacity: 1; transform: none; }
#demo .ring { position: absolute; border-radius: 10px; box-shadow: 0 0 0 3px #d1338f, 0 0 0 9px rgba(209,51,143,.18); opacity: 0; transition: opacity .3s ease; }
#demo .ring.on { opacity: 1; animation: pulse 1.6s ease-in-out infinite; }
@keyframes pulse { 50% { box-shadow: 0 0 0 3px #d1338f, 0 0 0 14px rgba(209,51,143,.08); } }
#demo path.arrow { fill: none; stroke: #d1338f; stroke-width: 4; stroke-linecap: round; filter: drop-shadow(0 2px 3px rgba(17,24,39,.25)); }
#demo path.draw { stroke-dasharray: 1600; stroke-dashoffset: 1600; animation: draw .7s ease forwards; }
@keyframes draw { to { stroke-dashoffset: 0; } }
#demo .cap { position: absolute; left: 50%; bottom: 34px; transform: translate(-50%, 16px); width: min(1240px, 88vw); background: rgba(17,24,39,.94);
  color: #fff; border-radius: 16px; padding: 18px 26px 20px; display: flex; gap: 20px; align-items: flex-start; opacity: 0;
  transition: opacity .45s ease, transform .45s ease; box-shadow: 0 24px 60px -20px rgba(0,0,0,.55); }
#demo .cap.on { opacity: 1; transform: translate(-50%, 0); }
#demo .cap .step { flex: none; font-size: 14px; font-weight: 600; color: #fff; background: #a3196f; border-radius: 8px; padding: 6px 10px; margin-top: 3px; letter-spacing: .02em; }
#demo .cap .t { font-size: 26px; font-weight: 600; letter-spacing: -.01em; }
#demo .cap .b { font-size: 19px; color: #d1d5db; margin-top: 4px; line-height: 1.4; }
#demo .cap .b b { color: #fff; font-weight: 600; }
#demo .progress { position: absolute; left: 0; top: 0; height: 4px; background: #d1338f; width: 0; transition: width .6s ease; }
#demo .cursor { position: absolute; left: 0; top: 0; width: 26px; height: 26px; transition: left .7s cubic-bezier(.4,0,.2,1), top .7s cubic-bezier(.4,0,.2,1); opacity: 0; }
#demo .cursor.on { opacity: 1; }
#demo .ripple { position: absolute; width: 18px; height: 18px; margin: -9px 0 0 -9px; border-radius: 50%; border: 3px solid #d1338f; animation: rip .6s ease-out forwards; }
@keyframes rip { to { transform: scale(3.2); opacity: 0; } }
#demo .card { position: absolute; inset: 0; background: radial-gradient(1200px 600px at 50% 40%, rgba(255,255,255,.98), rgba(246,247,249,.97));
  display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; opacity: 0; transition: opacity .6s ease; color: #111827; }
#demo .card.on { opacity: 1; }
#demo .card .wm { font-size: 76px; font-weight: 700; letter-spacing: .14em; }
#demo .card .wm span { color: #a3196f; }
#demo .card .k { margin-top: 10px; font-size: 22px; color: #6b7280; }
#demo .card .line { margin: 34px auto 0; max-width: 1050px; font-size: 32px; line-height: 1.35; font-weight: 500; letter-spacing: -.01em; }
#demo .card .line em { font-style: normal; color: #a3196f; }
#demo .card .chips { margin-top: 36px; display: flex; gap: 12px; flex-wrap: wrap; justify-content: center; }
#demo .card .chips span { font-size: 17px; color: #374151; background: #fff; border: 1px solid #e5e7eb; border-radius: 999px; padding: 8px 16px; }
#demo .card .foot { margin-top: 28px; font-size: 15px; color: #9ca3af; }
`;

const OVERLAY_JS = `
(() => {
  const L = document.createElement('div'); L.id = 'demo';
  L.innerHTML = '<div class="progress"></div><svg class="arrows"><defs><marker id="ah" viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" fill="#d1338f"/></marker></defs></svg>' +
    '<div class="cap"><div class="step"></div><div><div class="t"></div><div class="b"></div></div></div>' +
    '<svg class="cursor" viewBox="0 0 26 26"><path d="M4 2 L4 21 L9 16.5 L12.5 24 L16 22.4 L12.6 15 L19 15 Z" fill="#fff" stroke="#111827" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  document.body.appendChild(L);
  const svg = L.querySelector('svg.arrows'), cap = L.querySelector('.cap'), cur = L.querySelector('.cursor');
  const rectOf = (t) => { const e = typeof t === 'string' ? document.querySelector(t) : t; if (!e) return null; return e.getBoundingClientRect(); };
  window.demo = {
    progress(p) { L.querySelector('.progress').style.width = (p * 100) + '%'; },
    caption(step, title, body) {
      cap.classList.remove('on');
      setTimeout(() => { cap.querySelector('.step').textContent = step; cap.querySelector('.t').innerHTML = title; cap.querySelector('.b').innerHTML = body; cap.classList.add('on'); }, title ? 250 : 0);
    },
    hideCaption() { cap.classList.remove('on'); },
    clear() { L.querySelectorAll('.callout,.ring').forEach((n) => n.remove()); svg.querySelectorAll('path.arrow').forEach((n) => n.remove()); },
    ring(sel, pad = 6) {
      const r = rectOf(sel); if (!r) return false;
      const d = document.createElement('div'); d.className = 'ring';
      Object.assign(d.style, { left: (r.left - pad) + 'px', top: (r.top - pad) + 'px', width: (r.width + 2 * pad) + 'px', height: (r.height + 2 * pad) + 'px' });
      L.appendChild(d); requestAnimationFrame(() => d.classList.add('on')); return true;
    },
    point(sel, html, side = 'left', dist = 150, ring = true) {
      const r = rectOf(sel); if (!r) return false;
      if (ring) this.ring(sel);
      const c = document.createElement('div'); c.className = 'callout'; c.innerHTML = html; L.appendChild(c);
      const cw = c.offsetWidth, ch = c.offsetHeight, W = innerWidth, H = innerHeight;
      let cx, cy, tx, ty;
      const midX = r.left + r.width / 2, midY = r.top + r.height / 2;
      if (side === 'left') { cx = r.left - dist - cw; cy = midY - ch / 2; tx = r.left - 12; ty = midY; }
      if (side === 'right') { cx = r.right + dist; cy = midY - ch / 2; tx = r.right + 12; ty = midY; }
      if (side === 'top') { cx = midX - cw / 2; cy = r.top - dist - ch; tx = midX; ty = r.top - 12; }
      if (side === 'bottom') { cx = midX - cw / 2; cy = r.bottom + dist; tx = midX; ty = r.bottom + 12; }
      cx = Math.max(20, Math.min(W - cw - 20, cx)); cy = Math.max(70, Math.min(H - ch - 170, cy));
      c.style.left = cx + 'px'; c.style.top = cy + 'px';
      // arrow from the callout edge nearest the target to the target edge
      let sx, sy;
      if (side === 'left') { sx = cx + cw + 6; sy = cy + ch / 2; }
      if (side === 'right') { sx = cx - 6; sy = cy + ch / 2; }
      if (side === 'top') { sx = cx + cw / 2; sy = cy + ch + 6; }
      if (side === 'bottom') { sx = cx + cw / 2; sy = cy - 6; }
      const mx = (sx + tx) / 2, my = (sy + ty) / 2, bend = (side === 'left' || side === 'right') ? -40 : 40;
      const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      p.setAttribute('class', 'arrow draw');
      p.setAttribute('d', 'M' + sx + ' ' + sy + ' Q' + ((side === 'top' || side === 'bottom') ? mx + bend : mx) + ' ' + ((side === 'left' || side === 'right') ? my + bend : my) + ' ' + tx + ' ' + ty);
      p.setAttribute('marker-end', 'url(#ah)');
      svg.appendChild(p);
      requestAnimationFrame(() => c.classList.add('on'));
      return true;
    },
    cursorTo(x, y, show = true) { cur.classList.toggle('on', show); cur.style.left = (x - 4) + 'px'; cur.style.top = (y - 2) + 'px'; },
    ripple(x, y) { const d = document.createElement('div'); d.className = 'ripple'; d.style.left = x + 'px'; d.style.top = y + 'px'; L.appendChild(d); setTimeout(() => d.remove(), 700); },
    card(html) { let c = L.querySelector('.card'); if (!c) { c = document.createElement('div'); c.className = 'card'; L.insertBefore(c, L.firstChild.nextSibling); } c.innerHTML = html; requestAnimationFrame(() => c.classList.add('on')); },
    hideCard() { const c = L.querySelector('.card'); if (c) c.classList.remove('on'); },
  };
})();
`;

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1536, height: 864 }, deviceScaleFactor: 1.25 });
const page = await context.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));

// start from today's scenario, light theme
await page.request.post(APP + 'api/scenario', { data: {} });
await page.goto(APP);
await page.evaluate(() => { try { localStorage.setItem('fl-theme', 'light'); } catch (e) {} });
await page.reload();
await page.waitForSelector('#app:not([hidden])');
await page.evaluate(() => document.fonts.ready);
await page.addStyleTag({ content: OVERLAY_CSS + ' html{scroll-behavior:smooth}' });
await page.addScriptTag({ content: OVERLAY_JS });

// live numbers for the captions
const S = await page.evaluate(async () => (await fetch('/api/state')).json());
const pct = (x, d = 1) => (100 * x).toFixed(d) + '%';
const b = S.baseline, p = S.plan, d = S.delta, M = S.metrics.models;

// ---------- helpers ----------
const D = (fn, ...a) => page.evaluate(([f, args]) => window.demo[f](...args), [fn, a]);
const box = async (sel) => (await page.locator(sel).first().boundingBox());
async function moveTo(sel, dx = 0.5, dy = 0.5) {
  const r = await box(sel); const x = r.x + r.width * dx, y = r.y + r.height * dy;
  await D('cursorTo', x, y, true); await page.mouse.move(x, y, { steps: 12 }); await sleep(750); return { x, y };
}
async function click(sel, dx, dy) { const { x, y } = await moveTo(sel, dx, dy); await D('ripple', x, y); await page.mouse.click(x, y); await sleep(250); }
async function scrollTo(sel, block = 'center') {
  await D('clear');
  await page.evaluate(([s, bl]) => document.querySelector(s).scrollIntoView({ behavior: 'smooth', block: bl }), [sel, block]);
  await sleep(1100);
}
async function solved() { await page.waitForFunction(() => document.querySelector('#solve').textContent.includes('Solved in'), null, { timeout: 15000 }); await sleep(400); }
const chapters = 9; let ch = 0;
const step = async (n, title, body) => { ch = n; await D('progress', n / chapters); await D('caption', `${n} / ${chapters}`, title, body); };

// ---------- capture ----------
const cdp = await context.newCDPSession(page);
const frames = [];
cdp.on('Page.screencastFrame', async (f) => {
  const name = `f${String(frames.length).padStart(6, '0')}.jpg`;
  fs.writeFileSync(path.join(FRAMES, name), Buffer.from(f.data, 'base64'));
  frames.push({ name, t: f.metadata.timestamp });
  try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch (e) {}
});
// a tiny always-moving pixel keeps frames flowing during static holds
await page.addStyleTag({ content: '#tick{position:fixed;right:0;bottom:0;width:1px;height:1px;z-index:100000;animation:tk 1s steps(30) infinite}@keyframes tk{to{opacity:.99}}' });
await page.evaluate(() => { const t = document.createElement('div'); t.id = 'tick'; document.body.appendChild(t); });
await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: 1920, maxHeight: 1080, everyNthFrame: 1 });
const t0 = Date.now(); const startWall = Date.now() / 1000;
const mark = (label) => console.log(((Date.now() - t0) / 1000).toFixed(1).padStart(6), label);

// ===== 0 · title =====
mark('title');
await D('card', `<div class="wm">FLIGHT<span>LINE</span></div><div class="k">Fleet availability twin · SIH26249 · Air Power: Predictive Maintenance &amp; Fleet Availability</div>
  <div class="line">Every other team predicts when a part fails.<br>FLIGHTLINE predicts how many <em>sortie-days</em> the fleet is about to lose, and names the action that saves the most of them.</div>
  <div class="chips"><span>Live prototype</span><span>Runs fully offline</span><span>Re-solves in ~1 s</span><span>Synthetic scenario · seed ${S.provenance.seed}</span></div>`);
await sleep(7600);
await D('hideCard'); await sleep(700);

// ===== 1 · overview =====
mark('overview');
await step(1, 'One screen joins four data silos', `Health monitoring, technical records, spares and depots, joined in one graph of the fleet. Same <b>24 aircraft</b>, same parts, same bays: the plan keeps <b>${pct(p.ao)}</b> of the fleet available against <b>${pct(b.ao)}</b> today.`);
await sleep(900);
await D('point', '#kpis .kpi:nth-child(1)', `Operational availability <b>${pct(b.ao)} → ${pct(p.ao)}</b>`, 'bottom', 70);
await sleep(1600);
await D('point', '#kpis .kpi:nth-child(2)', `<b>+${d.aircraft_days} aircraft-days</b> recovered in 90 days`, 'bottom', 210);
await sleep(1600);
await D('point', '#kpis .kpi:nth-child(3)', `Tasked sorties lost: <b>${b.sortie_days_lost} → ${p.sortie_days_lost}</b>`, 'bottom', 70);
await sleep(5200);

// ===== 2 · line board =====
mark('board');
await scrollTo('#lineboard', 'start');
await page.evaluate(() => window.scrollBy({ top: -90, behavior: 'smooth' })); await sleep(600);
await step(2, 'Line board: every aircraft, every day of the next 90', 'Each bar is time on the ground, coloured by why. <b>Amber</b> is waiting for spares: a fault predicted on time still collides with a long lead time.');
await sleep(700);
await D('point', '.bar-seg.k3[data-tail="TAIL-08"]', '<b>TAIL-08</b>: 49 days waiting for one spare', 'bottom', 60);
await sleep(4200);
await D('clear');
await click('.seg button[data-view="baseline"]');
await D('caption', '2 / 9', 'Current practice vs the FLIGHTLINE plan', 'Toggle the view: inspections at their due date, first come first served, against the plan the optimiser found.');
await sleep(2200);
await click('.seg button[data-view="plan"]');
await page.evaluate(() => { const w = [...document.querySelectorAll('#lineboard .won')].sort((a, b) => b.offsetWidth - a.offsetWidth)[0]; if (w) w.id = 'demo-won'; });
await D('point', '#demo-won', '<b>Magenta</b>: days the plan puts back on the line', 'bottom', 60);
await sleep(4200);

// ===== 3 · recommendations =====
mark('recommendations');
await scrollTo('#order-section', 'start');
await page.evaluate(() => window.scrollBy({ top: -80, behavior: 'smooth' })); await sleep(600);
const a1 = await page.evaluate(() => ({ t: document.querySelector('#actions .act .text-\\[14px\\]').textContent, g: document.querySelector('#actions .act .text-\\[20px\\]').textContent }));
await step(3, 'What to do, ranked in aircraft-days, not RMSE', 'Every recommendation is valued by simulating the whole fleet with it and without it.');
await sleep(600);
await D('point', '#actions .act:first-child', `<b>${a1.g} aircraft-days</b>: ${a1.t.toLowerCase().replace('pn-6731-rtx', 'the radar transmitter')}`, 'right', 40);
await sleep(2800);
await D('clear');
await click('#actions .act:first-child .why');
await sleep(500);
await D('point', '#actions .act:first-child .trace', 'The trace: <b>which silo said what</b>, and how the number was valued', 'right', 40);
await D('caption', '3 / 9', 'Why this number?', 'Spares order, AOG lead time, the optimiser\'s choice and the simulator\'s before/after. Nothing is a black box; FLIGHTLINE ranks and prices, it never authorises.');
await sleep(5600);
await page.locator('#actions .act:first-child .why').click(); await sleep(300);

// ===== 4 · cannibalisation =====
mark('cannibalisation');
await scrollTo('#cannibalisation', 'center');
const c1 = await page.evaluate(() => document.querySelector('#c-don').selectedOptions[0].textContent);
await step(4, 'Cannibalisation, priced, not banned', 'Robbing a part from one aircraft to fly another moves the hole; it does not fill it. US GAO found it takes at least twice the labour of a normal repair.');
await sleep(700);
await D('point', '#cann .rounded-lg', `Donor ${c1.split(' · ')[0]} is down for days anyway: <b>${c1.split(' · ')[1]} aircraft-days</b>`, 'left', 60);
await sleep(3400);
await D('clear');
const neg = await page.evaluate(() => { const o = [...document.querySelectorAll('#c-don option')].find((x) => x.textContent.includes('−')); return o ? { v: o.value, t: o.textContent } : null; });
if (neg) {
  await click('#c-don');
  await page.selectOption('#c-don', neg.v); await sleep(500);
  await D('point', '#cann .rounded-lg', `Rob a <b>flying</b> aircraft instead: <b>${neg.t.split(' · ')[1]}</b>. It only moves the hole.`, 'left', 60);
  await sleep(4800);
}

// ===== 5 · ground two aircraft =====
mark('ground');
await scrollTo('#overview', 'start');
await step(5, 'Let the panel break it: ground two aircraft', 'Click TAIL-01 and TAIL-03 at Base A. The simulator and the CP-SAT optimiser re-solve both plans live.');
await sleep(900);
await click('.chip[data-tail="TAIL-01"]'); await sleep(200);
await click('.chip[data-tail="TAIL-03"]');
await solved();
await D('point', '#solve', 'Both plans re-solved in <b>' + (await page.evaluate(() => document.querySelector('#solve b').textContent)) + '</b>', 'bottom', 70);
await sleep(2400);
await D('clear');
await scrollTo('#order-section', 'start');
await page.evaluate(() => window.scrollBy({ top: -80, behavior: 'smooth' })); await sleep(500);
const a2 = await page.evaluate(() => ({ t: document.querySelector('#actions .act .text-\\[14px\\]').textContent, g: document.querySelector('#actions .act .text-\\[20px\\]').textContent }));
await D('point', '#actions .act:first-child', `New #1: <b>${a2.t.replace('PN-6731-RTX', 'radar')}</b>, ${a2.g} aircraft-days. A grounded aircraft is the cheapest source of parts.`, 'right', 40);
await D('caption', '5 / 9', 'The answer changes with the situation', 'Grounding two aircraft turns one of them into a parts donor, and the priced swap jumps to the top of the list.');
await sleep(5600);

// ===== 6 · convoy delay + surge =====
mark('stress');
await D('clear');
await scrollTo('#overview', 'start');
await step(6, 'Spares convoy 10 days late, 40% sortie surge', 'Drag the sliders. Lead times stretch, more parts fall inside their decision window, and the plan re-sequences depot inductions to hold sorties.');
async function drag(sel, value, max) {
  const r = await box(sel); const y = r.y + r.height / 2;
  const x0 = r.x + 8 + (await page.$eval(sel, (e) => +e.value)) / max * (r.width - 16), x1 = r.x + 8 + value / max * (r.width - 16);
  await D('cursorTo', x0, y, true); await page.mouse.move(x0, y, { steps: 8 }); await sleep(700);
  await D('ripple', x0, y); await page.mouse.down();
  for (let i = 1; i <= 14; i++) { const x = x0 + (x1 - x0) * i / 14; await page.mouse.move(x, y); await D('cursorTo', x, y, true); await sleep(45); }
  await page.mouse.up();
  await page.$eval(sel, (e, v) => { if (+e.value !== v) { e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); e.dispatchEvent(new Event('change', { bubbles: true })); } }, value);
}
await drag('#delay', 10, 30); await solved();
await sleep(500);
await drag('#surge', 40, 100); await solved();
const k3 = await page.evaluate(() => document.querySelector('#kpis .kpi:nth-child(3)').innerText.replace(/\s+/g, ' '));
await D('point', '#kpis .kpi:nth-child(3)', `Under stress the plan still saves sorties: <b>${k3.match(/lost (\d+)/)?.[1] ?? ''}</b> lost vs <b>${k3.match(/Current practice (\d+)/)?.[1] ?? ''}</b> under current practice`, 'bottom', 70);
await sleep(5200);
await D('clear');
await click('#reset'); await solved(); await D('cursorTo', 760, 500, false);

// ===== 7 · attribution =====
mark('attribution');
await scrollTo('#attribution', 'center');
await step(7, 'Why is availability what it is?', 'Every grounded aircraft-day is counted once, under its highest-priority cause, so the causes add up to the gap <b>exactly</b>: a unit-tested invariant, not a chart.');
await sleep(800);
await D('point', '#wf > div:nth-child(2)', 'Spares lead time is the <b>biggest</b> cause: the silos not meeting', 'right', 60);
await sleep(5400);

// ===== 8 · prognosis =====
mark('prognosis');
await scrollTo('#prognosis', 'center');
await page.evaluate(() => {
  const rows = [...document.querySelectorAll('#gate > div')];
  const ins = rows.find((r) => r.textContent.trim().endsWith('Inspect')); if (ins) ins.id = 'demo-ins';
  const ord = rows.find((r) => r.textContent.trim().endsWith('Order now')); if (ord) ord.id = 'demo-ord';
});
await step(8, 'It says when it does not know', 'Remaining life is a 90% conformal interval. Wider than the window you need to act in, and the model abstains and asks for an inspection instead of guessing.');
await sleep(800);
await D('ring', '#demo-ord'); await D('point', '#demo-ord .rounded-full', '<b>Order now</b>: interval narrow enough to act on', 'right', 70, false);
await sleep(3000);
await D('clear'); await D('ring', '#demo-ins'); await D('point', '#demo-ins .rounded-full', '<b>Inspect</b>: interval wider than its decision window', 'right', 70, false);
await sleep(4800);

// ===== 9 · model accuracy =====
mark('model');
await scrollTo('#cmp', 'center');
await step(9, 'Accuracy is the wrong target', `A model capped the way most papers report scores RMSE <b>${M.short_horizon.rmse_cycles.toFixed(1)}</b> yet warns in time for only <b>${pct(M.short_horizon.aph, 0)}</b> of failures. FLIGHTLINE: <b>${pct(M.flightline.aph, 0)}</b>.`);
await sleep(800);
await page.addStyleTag({ content: '#cmp div.mt-2{display:inline-block}' }); await D('ring', '#cmp > div:nth-child(1)', 4); await D('point', '#cmp > div:nth-child(1) div.mt-2', `RMSE ${M.short_horizon.rmse_cycles.toFixed(1)}, but <b>can't see past ~${M.short_horizon.warns_up_to_days.toFixed(0)} days</b>`, 'right', 70, false);
await sleep(3200);
await D('clear'); await D('ring', '#cmp > div:nth-child(2)', 4); await D('point', '#cmp > div:nth-child(2) div.mt-2', `Backtest: <b>${S.metrics.backtest.flightline.sortie_days_lost}</b> sorties lost vs <b>${S.metrics.backtest.short_horizon.sortie_days_lost}</b>`, 'right', 70, false);
await sleep(5200);

// ===== close =====
mark('close');
await D('clear'); await D('hideCaption'); await D('progress', 1);
await D('card', `<div class="wm">FLIGHT<span>LINE</span></div>
  <div class="line">Joins the four silos. Predicts the <em>sortie-days</em> the fleet is about to lose.<br>Prices every action in aircraft-days, and says when it does not know.</div>
  <div class="chips"><span>${pct(b.ao)} → ${pct(p.ao)} availability</span><span>+${d.aircraft_days} aircraft-days / 90 days</span><span>${pct(M.flightline.aph, 0)} of failures warned in time</span><span>Air-gapped: one server, no cloud</span></div>
  <div class="foot">Numbers from a synthetic scenario (seed ${S.provenance.seed}). The decision layer is platform-agnostic: swap in real fleet data and everything above the model stays.</div>`);
await sleep(8200);
mark('end'); const endWall = Date.now() / 1000;

await cdp.send('Page.stopScreencast');
await sleep(300);
fs.writeFileSync(path.join(DIR, 'frames.json'), JSON.stringify({ frames, startWall, endWall }));
console.log('frames', frames.length, 'errors', errors);
await page.request.post(APP + 'api/scenario', { data: {} });
await browser.close();
