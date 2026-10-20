// FLIGHTLINE · SIH26249 idea deck: the six-slide SIH idea-submission template.
// Every number is read from numbers.json, which is dumped from the running engine.
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const { applyTheme } = require("/Users/sai/.claude/skills/synced/e7b415de-4930-4821-9baa-f8a21873b516_8b86747d-8b9d-473d-a3a7-4370c200c254/pptx/scripts/apply_theme.js");

const DIR = __dirname;
const SHOT = (f) => path.join(DIR, "shots", f);
const N = JSON.parse(fs.readFileSync(path.join(DIR, "numbers.json"), "utf8"));
const OUT = process.argv[2] || path.join(DIR, "FLIGHTLINE_SIH26249.pptx");

const THEME = {
  name: "FLIGHTLINE SIH",
  headFontFace: "Times New Roman",
  bodyFontFace: "Arial",
  colors: {
    dk1: "000000", lt1: "FFFFFF", dk2: "1F3A5F", lt2: "EEF3F8",
    accent1: "0070C0", accent2: "B07D1A", accent3: "C0392B", accent4: "4A72C4",
    accent5: "6B7780", accent6: "2E7D32", hlink: "0070C0", folHlink: "5B2C83",
  },
};
const HEX = { blue: "0070C0", navy: "1F3A5F", line: "C9D3DD", tint: "EEF3F8", grey: "6B7780", soft: "A6AFB6", amber: "B07D1A" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.title = "FLIGHTLINE — Fleet Availability Twin (SIH26249)";
pres.author = "Code Byte";
pres.subject = "Smart India Hackathon 2026 · SIH26249";
const C = pres.SchemeColor;
const W = 13.333;

const pct = (x, d = 1) => (100 * x).toFixed(d) + "%";
const pts = (x) => (100 * x).toFixed(1);

// ---------------------------------------------------------------- layouts
const logo = [
  { image: { x: 10.98, y: 0.17, w: 0.72, h: 0.82, path: SHOT("sih_bulb.png") } },
  { text: { text: "SMART INDIA\nHACKATHON\n2026", options: { x: 11.68, y: 0.2, w: 1.6, h: 0.78, fontFace: "Arial", fontSize: 12.5, bold: true, color: "4D5A61", margin: 0, valign: "middle", lineSpacingMultiple: 0.9 } } },
];
pres.defineSlideMaster({
  title: "SIH content",
  background: { color: "FFFFFF" },
  margin: [0.5, 0.45, 0.7, 0.45],
  objects: [
    ...logo,
    { rect: { x: 0, y: 7.02, w: W, h: 0.48, fill: { color: HEX.blue } } },
    { text: { text: "@SIH Idea submission- Template", options: { x: 3.5, y: 7.02, w: 6.33, h: 0.48, fontFace: "Arial", fontSize: 13, color: "FFFFFF", align: "center", valign: "middle", margin: 0 } } },
    { placeholder: { options: { name: "title", type: "title", x: 2.3, y: 0.26, w: 8.55, h: 0.86, fontFace: "Times New Roman", fontSize: 34, bold: true, color: "000000", align: "center", valign: "middle", margin: 0 }, text: "" } },
  ],
  slideNumber: { x: 12.35, y: 7.08, w: 0.6, h: 0.36, color: "FFFFFF", fontFace: "Arial", fontSize: 14, bold: true, align: "right" },
});
pres.defineSlideMaster({
  title: "SIH title page",
  background: { color: "FFFFFF" },
  objects: [...logo],
});

// ---------------------------------------------------------------- helpers
let nameSeq = 0;
const nm = (s) => `${s}-${++nameSeq}`;
function text(slide, t, o) {
  slide.addText(t, { isTextBox: true, fontFace: "Arial", color: C.text1, valign: "top", margin: 0, objectName: nm("text"), ...o });
}
function card(slide, x, y, w, h, o = {}) {
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: o.fill || "FFFFFF" }, line: { color: o.line || HEX.line, width: o.lw || 1 }, objectName: nm("card") });
}
function boxed(slide, x, y, w, h) { // the template's heavy black frame
  slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { color: "FFFFFF" }, line: { color: "000000", width: 2.25 }, objectName: nm("frame") });
}
function pngSize(file) {
  const b = fs.readFileSync(SHOT(file));
  return [b.readUInt32BE(16), b.readUInt32BE(20)];
}
function img(slide, file, x, y, w, _pxw, _pxh, o = {}) {
  const [pxw, pxh] = pngSize(file);  // always the file's own size, so a re-shot screenshot keeps its aspect
  let h = w * pxh / pxw;
  if (o.maxH && h > o.maxH) {  // too tall for its slot: fit to height, keep the right edge where it was
    const w2 = o.maxH * pxw / pxh;
    x += w - w2; w = w2; h = o.maxH;
  }
  slide.addImage({ path: SHOT(file), x, y, w, h, objectName: nm("shot"), altText: o.alt || file });
  if (o.frame !== false) slide.addShape(pres.shapes.RECTANGLE, { x, y, w, h, fill: { type: "none" }, line: { color: "9AA6B1", width: 0.75 }, objectName: nm("shot-frame") });
  return h;
}
function bullets(items, o = {}) {
  return items.map((t, i) => ({ text: t, options: { bullet: { indent: 14 }, breakLine: o.more || i < items.length - 1, paraSpaceAfter: o.gap ?? 4 } }));
}
function arrowDown(slide, x, y, h = 0.28) {
  slide.addShape(pres.shapes.DOWN_ARROW, { x, y, w: 0.34, h, fill: { color: HEX.blue }, line: { color: HEX.blue, width: 0 }, objectName: nm("arrow") });
}
function arrowRight(slide, x, y, w = 0.26) {
  slide.addShape(pres.shapes.RIGHT_ARROW, { x, y, w, h: 0.3, fill: { color: HEX.blue }, line: { color: HEX.blue, width: 0 }, objectName: nm("arrow") });
}
function content(section) {
  const s = pres.addSlide({ masterName: "SIH content", sectionTitle: section });
  // the template's team-name oval, top left
  s.addText("Code Byte", { shape: pres.shapes.OVAL, x: 0.3, y: 0.22, w: 1.75, h: 0.82, fill: { color: "FFFFFF" }, line: { color: "8064A2", width: 2 }, fontFace: "Calibri", fontSize: 17, color: "000000", align: "center", valign: "middle", margin: 0, objectName: nm("team") });
  return s;
}

const D = N.default, G = N.ground, DL = N.delay, SU = N.surge, M = N.metrics;
const FL = M.models.flightline, SH = M.models.short_horizon, BT = M.backtest;
// The official SIH idea template is six slides with fixed pointers; this deck keeps them verbatim.
const MAG = "A3196F";
const wordmark = (rest, o = {}) => [
  { text: "FLIGHT", options: { bold: true, charSpacing: 2, ...o } },
  { text: "LINE", options: { bold: true, charSpacing: 2, color: MAG, ...o } },
  { text: rest, options: { bold: false, ...o } },
];
const signed = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(d);
const tail02 = D.cann.filter((c) => c[1] === "TAIL-02");
const fromDown = tail02.find((c) => c[4] > 0 && c[4] < 1000);
const fromFlying = tail02.find((c) => c[4] === 0);

// ================================================================ 1 · TITLE PAGE
pres.addSection({ title: "Title" });
{
  const s = pres.addSlide({ masterName: "SIH title page", sectionTitle: "Title" });
  text(s, "SMART INDIA HACKATHON 2026", { x: 0.5, y: 0.28, w: 10.3, h: 0.85, fontFace: "Times New Roman", fontSize: 42, bold: true, color: "1F4E79", align: "center", valign: "middle" });
  s.addText("TITLE PAGE", { isTextBox: true, x: 0.5, y: 1.3, w: 7.2, h: 0.75, fontFace: "Times New Roman", fontSize: 34, bold: true, color: "000000", align: "center", valign: "middle", margin: 0, objectName: nm("title") });
  // template hexagons behind the emblem
  s.addShape(pres.shapes.HEXAGON, { x: 7.75, y: 1.55, w: 4.6, h: 5.3, rotate: 90, fill: { color: "ECECEC" }, line: { color: "ECECEC", width: 0 }, objectName: nm("hex") });
  s.addShape(pres.shapes.HEXAGON, { x: 7.0, y: 1.05, w: 1.9, h: 2.1, rotate: 90, fill: { type: "none" }, line: { color: "E1E1E1", width: 6 }, objectName: nm("hex") });
  s.addShape(pres.shapes.HEXAGON, { x: 6.55, y: 4.45, w: 1.0, h: 1.15, rotate: 90, fill: { color: "ECECEC" }, line: { color: "ECECEC", width: 0 }, objectName: nm("hex") });
  s.addImage({ path: SHOT("sih_bulb.png"), x: 8.75, y: 2.3, w: 2.6, h: 2.6 * 703 / 615, objectName: nm("emblem"), altText: "Smart India Hackathon emblem" });
  const rows = [
    ["Problem Statement ID: ", [{ text: "SIH26249" }]],
    ["Problem Statement Title: ", [{ text: "Air Power — Predictive Maintenance & Fleet Availability (Ministry of Defence)" }]],
    ["Theme: ", [{ text: "[fill in as listed on the SIH portal]", options: { italic: true, color: "C0392B" } }]],
    ["PS Category: ", [{ text: "Software" }]],
    ["Team Name: ", [{ text: "Code Byte" }]],
    ["Idea: ", wordmark(" — Fleet Availability Twin").map((r) => ({ text: r.text, options: { ...r.options } }))],
  ];
  s.addText(rows.map(([k, runs], i) => [
    { text: k, options: { bold: true, bullet: { indent: 18 } } },
    ...runs.map((r, j) => ({ text: r.text, options: { bold: false, ...(r.options || {}), breakLine: j === runs.length - 1 && i < rows.length - 1 } })),
  ]).flat(), { isTextBox: true, x: 0.55, y: 2.3, w: 6.3, h: 4.5, fontFace: "Arial", fontSize: 18, color: "000000", paraSpaceAfter: 12, valign: "top", margin: 0, objectName: nm("details") });
  s.addNotes("Keep it plain. One sentence: every other team predicts when a part fails; FLIGHTLINE predicts how many sortie-days the fleet is about to lose, and names the single action that saves the most of them.");
}

// ================================================================ 2 · IDEA TITLE
pres.addSection({ title: "Idea" });
{
  const s = content("Idea");
  s.addText("IDEA TITLE", { placeholder: "title" });
  text(s, wordmark(" — Fleet Availability Twin"), { x: 0.45, y: 1.2, w: 12.4, h: 0.38, fontSize: 20, bold: true });
  text(s, "A decision layer that joins the four maintenance silos, predicts how many sortie-days the fleet is about to lose, and names the action that saves the most of them — scored in aircraft-days, not RMSE.", { x: 0.45, y: 1.58, w: 12.4, h: 0.55, fontSize: 14, color: "222222" });
  const Y = 2.25, BH = 4.62;
  const cols = [[0.45, 3.75], [4.4, 4.3], [8.9, 3.98]];
  cols.forEach(([x, w]) => boxed(s, x, Y, w, BH));
  const head = ([x, w], t) => text(s, t, { x: x + 0.18, y: Y + 0.14, w: w - 0.36, h: 0.45, fontSize: 20, bold: true, color: C.accent1 });

  head(cols[0], "THE PROBLEM :");
  text(s, [
    { text: "The statement names fragmentation, not accuracy: ", options: { bold: true } },
    { text: "“fragmented and largely reactive … not adequately integrated”.", options: { italic: true, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    ...bullets([
      "Health monitoring, technical records, spares and MRO agencies never meet",
      "A fault predicted on Tuesday collides with a six-week spares lead time — the aircraft sits on the ground anyway",
      "Cannibalisation is signed without a price",
      "RUL models report RMSE; nobody reports aircraft-days",
    ], { gap: 6 }),
  ], { x: cols[0][0] + 0.18, y: Y + 0.68, w: cols[0][1] - 0.34, h: BH - 0.8, fontSize: 13.5 });

  head(cols[1], "THE SOLUTION :");
  const sol = [
    ["One graph of the four silos", "tail → LRU → part → stock → depot bay → sorties"],
    ["Prognosis with honest intervals", "Remaining life as a 90% conformal interval; abstains when unsure"],
    ["Fleet simulator + CP-SAT optimiser", "90 days, day by day; re-sequences depot inductions and expedites"],
    ["Ranked actions in aircraft-days", "Each with “Why this number?”; live what-if re-solves in ≈" + (D.ms / 1000).toFixed(1) + "\u00a0s"],
  ];
  text(s, [
    ...sol.flatMap(([h, b]) => [
      { text: h.toUpperCase(), options: { bold: true, breakLine: true } },
      { text: b, options: { breakLine: true, paraSpaceAfter: 7 } },
    ]),
    { text: "It ranks and prices. It never authorises — the signature stays with the officer.", options: { bold: true, color: C.text2 } },
  ], { x: cols[1][0] + 0.18, y: Y + 0.68, w: cols[1][1] - 0.34, h: BH - 0.8, fontSize: 13, paraSpaceAfter: 2 });

  head(cols[2], "WHAT IS NEW :");
  const news = [
    [`${pct(FL.aph, 0)} vs ${pct(SH.aph, 0)}`, "of failures warned in time to act (APH), against a capped-RUL model with the better RMSE"],
    [`${signed(fromDown[3])} vs ${signed(fromFlying[3])}`, "cannibalisation priced in aircraft-days: donor already down vs a flying donor"],
    [pct(N.evaluation.coverage), "interval coverage; when the interval is too wide it says “inspect”, not a guess"],
    [`${pts(D.gap_b)} pts`, `of lost availability attributed by cause — ${pts(D.attr_b.spares_lead_time)} of them to spares lead time`],
  ];
  news.forEach(([big, small], i) => {
    const y = Y + 0.7 + i * 0.97;
    text(s, big, { x: cols[2][0] + 0.18, y, w: cols[2][1] - 0.36, h: 0.4, fontSize: 21, bold: true, color: MAG });
    text(s, small, { x: cols[2][0] + 0.18, y: y + 0.4, w: cols[2][1] - 0.36, h: 0.52, fontSize: 11.5, color: "222222" });
  });
  s.addNotes(`The statement does not say the models are inaccurate. It says the data never meets. So we do not compete on accuracy: we join the four silos and optimise the number the Air Force already runs on — operational availability. The capped model has RMSE ${SH.rmse_cycles.toFixed(1)} against ours ${FL.rmse_cycles.toFixed(1)}, and still warns in time for only ${pct(SH.aph, 0)} of failures, because it cannot see past ${M.cap_cycles} cycles and most spares take longer than that to arrive.`);
}

// ================================================================ 3 · TECHNICAL APPROACH
pres.addSection({ title: "Technical approach" });
{
  const s = content("Technical approach");
  s.addText("TECHNICAL APPROACH", { placeholder: "title" });
  const T = N.twin;
  const silos = [
    ["HEALTH MONITORING", `${T.nodes.lru} installed LRUs · multivariate sensor histories, 6 operating regimes (N-CMAPSS shape)`],
    ["TECHNICAL RECORDS", `${T.edges.inspection_due} phase inspections due · durations · cannibalisation history`],
    ["SPARES", `${T.nodes.stock_location} stock locations · lead times 7–60 days · orders in transit`],
    ["MRO AGENCIES", `${T.nodes.depot} depots · ${T.nodes.bay} bays · one induction crew per depot per day`],
  ];
  const sw = 2.95, sg = 0.21;
  silos.forEach(([h, b], i) => {
    const x = 0.45 + i * (sw + sg);
    card(s, x, 1.22, sw, 0.98, { fill: HEX.tint, line: HEX.tint });
    text(s, h, { x: x + 0.12, y: 1.27, w: sw - 0.24, h: 0.3, fontSize: 12, bold: true, color: C.accent1 });
    text(s, b, { x: x + 0.12, y: 1.56, w: sw - 0.24, h: 0.6, fontSize: 11, color: "222222" });
    arrowDown(s, x + sw / 2 - 0.17, 2.24, 0.26);
  });
  card(s, 0.45, 2.55, 12.43, 0.62, { fill: HEX.navy, line: HEX.navy });
  text(s, [
    { text: "FLEET TWIN  ", options: { bold: true } },
    { text: `one NetworkX graph · ${T.n_nodes} nodes · ${T.n_edges} edges   ·   tail → installed LRU → part number → stock location → depot bay → sortie plan`, options: {} },
  ], { x: 0.65, y: 2.55, w: 12.0, h: 0.62, fontSize: 13, color: "FFFFFF", valign: "middle" });

  const steps = [
    ["1  PROGNOSIS", ["HistGradientBoosting on rolling mean / std / slope per sensor + age", "Mondrian conformalised quantile regression → 90% RUL interval", "Abstains when interval > decision window"]],
    ["2  SIMULATOR", ["90 days, day by day; wear ∝ sorties flown", "Base-stock (S−1, S) spares, FIFO", "Every down-day = one labelled “hold” → exact attribution"]],
    ["3  OPTIMISER", ["OR-Tools CP-SAT: induction day + depot, expedites", "Max sortie-days, then aircraft-days", "2 passes + simulator check; deterministic budget"]],
    ["4  DECISION LAYER", ["Cannibalisation priced over 30 days", "Spare unlock ranking (monotone replay)", "Actions in aircraft-days + causal trace"]],
    ["5  DELIVERY", ["FastAPI + offline dashboard", `Live what-if, re-solves in ≈${(D.ms / 1000).toFixed(1)}\u00a0s`, "Printable draft maintenance order"]],
  ];
  const pw = 2.3, pg = 0.2, py = 3.42, ph = 2.2;
  steps.forEach(([h, lines], i) => {
    const x = 0.45 + i * (pw + pg);
    boxed(s, x, py, pw, ph);
    text(s, h, { x: x + 0.12, y: py + 0.1, w: pw - 0.24, h: 0.32, fontSize: 12.5, bold: true, color: C.accent1 });
    text(s, bullets(lines, { gap: 4 }), { x: x + 0.12, y: py + 0.47, w: pw - 0.22, h: ph - 0.55, fontSize: 10.5, color: "222222" });
    if (i < steps.length - 1) arrowRight(s, x + pw + 0.015, py + ph / 2 - 0.15, 0.17);
  });
  text(s, "TECHNOLOGY STACK", { x: 0.45, y: 5.78, w: 12.43, h: 0.26, fontSize: 12, bold: true, color: C.accent1, align: "center" });
  const stack = [
    ["DATA", "SQLite · seeded generator · N-CMAPSS / C-MAPSS loader"],
    ["ML", "scikit-learn HistGradientBoosting · split-conformal"],
    ["OPTIMISATION", "Google OR-Tools CP-SAT"],
    ["GRAPH", "NetworkX"],
    ["SERVING", "Python · FastAPI · Tailwind CSS · Chart.js, all bundled"],
    ["ASSURANCE", `${N.n_tests} pytest tests · same seed → same numbers`],
  ];
  const cw = 12.43 / stack.length;
  card(s, 0.45, 6.07, 12.43, 0.82, { fill: "FFFFFF", line: HEX.line });
  stack.forEach(([h, b], i) => {
    const x = 0.45 + i * cw;
    text(s, [{ text: h, options: { bold: true, breakLine: true, color: C.text2 } }, { text: b, options: { color: "333333" } }], { x: x + 0.1, y: 6.12, w: cw - 0.2, h: 0.74, fontSize: 10.5 });
  });
  s.addNotes("The twin that matters is of the maintenance system, not the engine. Air-gapped by construction: no cloud call, no LLM, no GPU, one SQLite file. Units: the model predicts RUL in cycles (sorties); it becomes days only when divided by planned utilisation. The headline delta is always simulator vs simulator — never the optimiser's own objective.");
}

// ================================================================ 4 · FEASIBILITY AND VIABILITY
pres.addSection({ title: "Feasibility and viability" });
{
  const s = content("Feasibility and viability");
  s.addText("FEASIBILITY AND VIABILITY", { placeholder: "title" });
  // left: the working prototype
  const lx = 0.45, lw = 4.15, top = 1.22, bot = 6.87;
  boxed(s, lx, top, lw, bot - top);
  text(s, "TECHNICALLY FEASIBLE", { x: lx + 0.15, y: top + 0.1, w: lw - 0.3, h: 0.38, fontSize: 17, bold: true, color: C.accent1 });
  text(s, "Built, running and tested — offline", { x: lx + 0.15, y: top + 0.47, w: lw - 0.3, h: 0.28, fontSize: 11.5, bold: true, color: C.text2 });
  const ih = img(s, "dashboard.png", lx + 0.15, top + 0.82, lw - 0.3, 0, 0, { alt: "FLIGHTLINE prototype: overview and line board" });
  text(s, bullets([
    "Runs on one laptop: Python + SQLite; no GPU, no internet",
    `Both 90-day plans re-simulated and re-solved in ≈${(D.ms / 1000).toFixed(1)}\u00a0s`,
    `${N.n_tests} automated tests; same seed → same numbers`,
    "Real N-CMAPSS / C-MAPSS files in data/raw → retrains on real engines",
    "2-minute demo film recorded from the running prototype",
  ], { gap: 3 }), { x: lx + 0.15, y: top + 0.92 + ih, w: lw - 0.25, h: bot - top - 1.0 - ih, fontSize: 11, color: "222222" });

  // right: challenges → mitigations, in the template's two pointers
  const rx = 4.8, rw = 12.88 - 4.8;
  const th = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.blue }, fontSize: 13 } });
  const rr = (a, b) => [{ text: a, options: { bold: true, color: "000000" } }, { text: b, options: { color: "222222" } }];
  s.addTable([
    [th("KEY CHALLENGES"), th("MITIGATION")],
    rr("No IAF data", "“SYNTHETIC SCENARIO” badge on every screen; decisions never see ground truth — it is used only to backtest"),
    rr("Model trained on another platform", "The decision layer is platform-agnostic: swap the degradation model and the twin, simulator and optimiser are unchanged"),
    rr("Overconfidence near failure", `Conformal intervals calibrated per RUL band: ${pct(N.cov_last20, 0)} coverage in the last 20 cycles; abstains → inspect`),
    rr("Classified data", "Air-gapped: one base server, one SQLite file; no cloud, no LLM, no external API"),
    rr("Trust in automated advice", "Ranks and prices, never authorises; every number has a trace; every plan re-scored by the full simulator"),
  ], { x: rx, y: top, w: rw, colW: [2.45, rw - 2.45], fontFace: "Arial", fontSize: 11, rowH: [0.4, 0.55, 0.55, 0.55, 0.55, 0.55], valign: "middle", border: { type: "solid", pt: 1, color: "000000" }, margin: [3, 7, 3, 7], objectName: nm("risk-table") });

  // bottom right: viability with few labelled failures
  const by = 4.72, bh = bot - by;
  const ft = M.fine_tuning;
  card(s, rx, by, rw, bh, { fill: HEX.tint, line: HEX.tint });
  s.addChart(pres.charts.LINE, [{ name: "Warning lead ÷ decision window", labels: ft.map((r) => String(r.labelled_failures)), values: ft.map((r) => +r.median_lead_over_window.toFixed(2)) }], {
    x: rx + 0.1, y: by + 0.05, w: 4.1, h: bh - 0.1, chartColors: [HEX.blue], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    showLegend: false, showTitle: true, title: "Warning lead ÷ window vs labelled failures", titleFontSize: 10.5, titleFontFace: "+mn-lt", titleColor: "000000",
    showValue: true, dataLabelPosition: "t", dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt", dataLabelColor: "444444", dataLabelFormatCode: '0.0"×"',
    valAxisMinVal: 1, valAxisMaxVal: 3.8, valAxisHidden: true, valGridLine: { style: "none" }, catAxisLabelFontSize: 9.5, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "333333",
    plotArea: { fill: { color: HEX.tint } }, objectName: nm("finetune-chart"),
  });
  text(s, [
    { text: "VIABLE WITH LITTLE DATA", options: { bold: true, color: C.accent1, breakLine: true } },
    { text: `APH stays ${pct(Math.min(...ft.map((r) => r.aph)), 0)}–${pct(Math.max(...ft.map((r) => r.aph)), 0)} from ${ft[0].labelled_failures} to ${ft[ft.length - 1].labelled_failures} labelled failures. With fewer failures the interval widens and it warns earlier, not later.`, options: { breakLine: true } },
    { text: "More data buys efficiency, not safety.", options: { bold: true } },
  ], { x: rx + 4.35, y: by + 0.12, w: rw - 4.5, h: bh - 0.24, fontSize: 12, valign: "middle", color: "222222" });
  s.addNotes("Volunteer the weakness before the panel finds it. We have no IAF data and do not pretend to. Our claim is not that this model transfers to a Su-30. Our claim is that the decision layer is platform-agnostic: the twin, the simulator, the attribution, the optimiser, the cannibalisation price and the abstention gate are unchanged when the degradation model is swapped.");
}

// ================================================================ 5 · IMPACT AND BENEFITS
pres.addSection({ title: "Impact and benefits" });
{
  const s = content("Impact and benefits");
  s.addText("IMPACT AND BENEFITS", { placeholder: "title" });
  const stats = [
    ["+" + D.d_ac, `aircraft-days in 90 days on a 24-aircraft fleet (Ao ${pct(D.ao_b)} → ${pct(D.ao_p)}), same aircraft, parts and bays`],
    [D.lost_b + " → " + D.lost_p, "tasked sorties lost to unavailability, current practice → plan"],
    [D.queue_b.toFixed(1) + " → " + D.queue_p.toFixed(1), "mean days an inspection waits for a depot bay"],
    [`${BT.short_horizon.sortie_days_lost} → ${BT.flightline.sortie_days_lost}`, `sorties lost in a 90-day backtest on true failures, capped model → FLIGHTLINE (no prognosis: ${BT.none.sortie_days_lost})`],
  ];
  const sw = 2.93, sg = 0.237;
  stats.forEach(([big, small], i) => {
    const x = 0.45 + i * (sw + sg);
    card(s, x, 1.22, sw, 1.45, { fill: HEX.tint, line: HEX.tint });
    text(s, big, { x: x + 0.15, y: 1.27, w: sw - 0.3, h: 0.62, fontSize: 30, bold: true, color: C.accent1, valign: "middle" });
    text(s, small, { x: x + 0.15, y: 1.9, w: sw - 0.3, h: 0.74, fontSize: 10.5, color: "222222" });
  });

  // attribution: why Ao is what it is
  const ay = 2.85, ah = 2.3;
  boxed(s, 0.45, ay, 6.1, ah);
  text(s, `Why is availability ${pct(D.ao_b)} and not ${pct(D.ceil_b)}?`, { x: 0.6, y: ay + 0.08, w: 5.8, h: 0.34, fontSize: 14, bold: true, color: C.accent1 });
  const a = D.attr_b, ad = D.attr_days_b;
  const items = [
    ["Waiting for spares", a.spares_lead_time, ad.spares_lead_time],
    ["Waiting for a depot bay", a.depot_contention, ad.depot_contention],
    ["Unscheduled removal", a.unscheduled_removal, ad.unscheduled_removal],
    ["Cannibalisation cascade", a.cannibalisation_cascade, ad.cannibalisation_cascade],
  ];
  const hc = (t, al) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.navy }, align: al } });
  s.addTable([
    [hc("Cause", "left"), hc("Ao points", "right"), hc("Aircraft-days", "right")],
    ...items.map(([k, v, d]) => [{ text: k }, { text: pts(v), options: { align: "right", bold: true } }, { text: String(d), options: { align: "right", color: "444444" } }]),
    [{ text: "Gap below the ceiling", options: { bold: true } }, { text: pts(D.gap_b), options: { align: "right", bold: true, color: C.accent1 } }, { text: String(items.reduce((t, x) => t + x[2], 0)), options: { align: "right", bold: true } }],
  ], { x: 0.6, y: ay + 0.48, w: 5.8, colW: [3.0, 1.3, 1.5], fontFace: "Arial", fontSize: 11.5, rowH: 0.29, valign: "middle", border: { type: "solid", pt: 0.5, color: HEX.line }, margin: [1, 7, 1, 7], objectName: nm("attr-table") });

  // stress tests the panel can run live
  const sx = 6.78, swd = 6.1;
  boxed(s, sx, ay, swd, ah);
  text(s, "Stress-tested live — each re-solves in about a second", { x: sx + 0.15, y: ay + 0.08, w: swd - 0.3, h: 0.34, fontSize: 14, bold: true, color: C.accent1 });
  const moves = [
    ["Ground TAIL-01 and TAIL-03", `Ao ${pct(G.ao_b)}; new top action: cannibalise the radar from grounded TAIL-03 to TAIL-02, +${G.top[0][1].toFixed(0)} aircraft-days`],
    ["Spares convoy 10 days late", `Spares share of the gap ${pts(D.attr_b.spares_lead_time)} → ${pts(DL.attr_b.spares_lead_time)} pts; order-now parts ${D.counts.order_now} → ${DL.counts.order_now}`],
    ["Surge: 40% more sorties", `Sorties lost ${SU.lost_b} under current practice vs ${SU.lost_p} under the plan (+${SU.d_ac} aircraft-days)`],
  ];
  moves.forEach(([say, see], i) => {
    const y = ay + 0.5 + i * 0.6;
    text(s, [{ text: say, options: { bold: true, breakLine: true } }, { text: see, options: { color: "333333" } }], { x: sx + 0.15, y, w: swd - 0.3, h: 0.58, fontSize: 10.5 });
  });

  // who benefits, and how it is deployed
  const who = [
    ["BASE MAINTENANCE OFFICER", ["Why availability is what it is, by cause", "Which depot induction to move, and when"]],
    ["LOGISTICS OFFICER", ["Which spare, stocked where, unlocks the most", "Which order to expedite"]],
    ["ENGINEERING OFFICER", ["Cannibalisation priced before it is signed", "Inspect or order, with the model's own doubt"]],
  ];
  const wy = 5.33, wh = 6.87 - 5.33, ww = 2.93, wg = 0.237;
  who.forEach(([h, lines], i) => {
    const x = 0.45 + i * (ww + wg);
    boxed(s, x, wy, ww, wh);
    text(s, h, { x: x + 0.13, y: wy + 0.08, w: ww - 0.26, h: 0.3, fontSize: 11, bold: true, color: C.accent1 });
    text(s, bullets(lines, { gap: 3 }), { x: x + 0.13, y: wy + 0.44, w: ww - 0.2, h: wh - 0.5, fontSize: 11.5 });
  });
  const dx = 0.45 + 3 * (ww + wg);
  card(s, dx, wy, ww, wh, { fill: HEX.navy, line: HEX.navy });
  text(s, [
    { text: "AIR-GAPPED DEPLOYMENT", options: { bold: true, fontSize: 11, breakLine: true } },
    { text: "One base server, one SQLite file, open-source stack. Nothing leaves the base network.", options: {} },
  ], { x: dx + 0.13, y: wy + 0.08, w: ww - 0.26, h: wh - 0.16, fontSize: 11.5, color: "FFFFFF", valign: "top", paraSpaceAfter: 4 });
  s.addNotes(`Aircraft-days recovered from the same aircraft, parts and bays — by joining the data, not by buying anything. Every grounded aircraft-day is counted once under its highest-priority reason, so the causes add up to the gap exactly; that is a unit-tested invariant. The numbers are from the synthetic scenario; the first step with real data is one LRU family at one base.`);
}

// ================================================================ 6 · RESEARCH AND REFERENCES
pres.addSection({ title: "Research and references" });
{
  const s = content("Research and references");
  s.addText("RESEARCH AND REFERENCES", { placeholder: "title" });
  const refs = [
    ["Degradation data", [
      "Arias Chao M. et al. Aircraft engine run-to-failure dataset under real flight conditions (N-CMAPSS). Data 6(1):5, 2021",
      "Saxena A. et al. Damage propagation modeling for aircraft engine run-to-failure simulation (C-MAPSS). PHM 2008",
    ], "Shape of our synthetic degradation; the loader retrains on the real files"],
    ["Conformal prediction", [
      "Romano Y., Patterson E., Candès E. Conformalized quantile regression. NeurIPS 2019",
      "Vovk V., Gammerman A., Shafer G. Algorithmic Learning in a Random World. Springer, 2005",
    ], "90% remaining-life interval, calibrated per band (Mondrian); the abstention gate"],
    ["Cannibalisation evidence", [
      "US GAO. GAO-02-86, Military Aircraft: Services Need Strategies to Reduce Cannibalizations. Nov 2001",
      "≈850,000 cannibalisations and ≈5.3 million extra hours, FY1996–2000; at least twice the labour of a normal repair",
    ], "Swap labour priced at 2×; every swap scored before it is signed"],
    ["Spares and optimisation", [
      "Sherbrooke C. METRIC: a multi-echelon technique for recoverable item control. Operations Research 16(1), 1968",
      "Google OR-Tools CP-SAT · scikit-learn HistGradientBoosting · NetworkX",
    ], "Base-stock (S−1, S) spares; induction scheduling and expedites"],
  ];
  const cw = 2.95, cg = 0.21, cy = 1.22, ch = 3.7;
  refs.forEach(([h, cites, use], i) => {
    const x = 0.45 + i * (cw + cg);
    boxed(s, x, cy, cw, ch);
    s.addText(String(i + 1), { shape: pres.shapes.RECTANGLE, x, y: cy, w: 0.42, h: 0.42, fill: { color: HEX.blue }, line: { color: HEX.blue, width: 0 }, fontFace: "Arial", fontSize: 15, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, objectName: nm("ref-num") });
    text(s, h, { x: x + 0.52, y: cy + 0.06, w: cw - 0.62, h: 0.32, fontSize: 13, bold: true, color: C.accent1, valign: "middle" });
    text(s, bullets(cites, { gap: 6 }), { x: x + 0.14, y: cy + 0.55, w: cw - 0.24, h: 2.15, fontSize: 11.5, color: "222222" });
    card(s, x + 0.12, cy + ch - 0.92, cw - 0.24, 0.8, { fill: HEX.tint, line: HEX.tint });
    text(s, [{ text: "Used for: ", options: { bold: true } }, { text: use }], { x: x + 0.22, y: cy + ch - 0.9, w: cw - 0.44, h: 0.76, fontSize: 10.5, color: C.text2, valign: "middle" });
  });

  // pilot and validation plan
  const py = 5.12, ph = 6.87 - 5.12;
  boxed(s, 0.45, py, 12.43, ph);
  s.addText("OUR PILOT AND VALIDATION PLAN", { shape: pres.shapes.RECTANGLE, x: 4.67, y: py - 0.17, w: 4.0, h: 0.34, fill: { color: HEX.blue }, line: { color: HEX.blue, width: 0 }, fontFace: "Arial", fontSize: 12, bold: true, color: "FFFFFF", align: "center", valign: "middle", margin: 0, objectName: nm("plan-tag") });
  const plan = [
    ["Data", "One LRU family: removals, lead times, stock by base, bay counts, cannibalisation logs"],
    ["Retrain", "Degradation model on real removals; recalibrate the conformal intervals"],
    ["Shadow mode", "90 days at one base; officers keep deciding, FLIGHTLINE only advises"],
    ["Measure", "APH and aircraft-days against what actually happened"],
    ["Expand", "More LRU families, then more bases and types"],
  ];
  const pw = 2.2, pgap = (12.43 - 0.3 - plan.length * pw) / (plan.length - 1);
  plan.forEach(([h, b], i) => {
    const x = 0.6 + i * (pw + pgap);
    text(s, [{ text: h, options: { bold: true, color: C.accent1, breakLine: true } }, { text: b, options: { color: "222222" } }], { x, y: py + 0.3, w: pw, h: ph - 0.4, fontSize: 11.5, valign: "middle" });
    if (i < plan.length - 1) arrowRight(s, x + pw + (pgap - 0.2) / 2, py + ph / 2 - 0.05, 0.2);
  });
  s.addNotes("Every reference here is used in the build, not decoration. The GAO report is the evidence the panel will recognise: cannibalisation is necessary and corrosive, so we price it. The pilot needs one LRU family at one base for 90 days in shadow mode — officers keep deciding, FLIGHTLINE only advises, and we measure APH and aircraft-days against what actually happened.");
}

// pptxgenjs 3.12 writes an <a:pPr> before every run of a multi-run paragraph; only the first is
// legal (it must precede the runs). The extras make PowerPoint offer a repair and LibreOffice drop bullets.
async function dropStrayParagraphProps(file) {
  const JSZip = require("jszip");
  const zip = await JSZip.loadAsync(fs.readFileSync(file));
  const stray = /(<\/a:r>|<a:br\/>)<a:pPr\b[^>]*?(?:\/>|>[\s\S]*?<\/a:pPr>)/g;
  let n = 0;
  for (const name of Object.keys(zip.files).filter((f) => /^ppt\/slides\/slide\d+\.xml$/.test(f))) {
    const xml = await zip.file(name).async("string");
    let fixed = xml, prev;
    do { prev = fixed; fixed = fixed.replace(stray, (m, end) => (n++, end)); } while (fixed !== prev);
    if (fixed !== xml) zip.file(name, fixed);
  }
  fs.writeFileSync(file, await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" }));
  return n;
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  console.log("dropped", await dropStrayParagraphProps(OUT), "stray paragraph properties");
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
