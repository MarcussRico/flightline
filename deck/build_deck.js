// FLIGHTLINE · SIH26249 idea deck in the SIH idea-submission template format.
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
function img(slide, file, x, y, w, pxw, pxh, o = {}) {
  const h = w * pxh / pxw;
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
    ["Problem Statement ID: ", "SIH26249"],
    ["Problem Statement Title: ", "Air Power — Predictive Maintenance & Fleet Availability"],
    ["Organisation: ", "Ministry of Defence"],
    ["Idea: ", "FLIGHTLINE — Fleet Availability Twin"],
    ["Team Name: ", "Code Byte"],
  ];
  s.addText(rows.map(([k, v], i) => [
    { text: k, options: { bold: true, bullet: { indent: 18 } } },
    { text: v, options: { bold: false, breakLine: i < rows.length - 1 } },
  ]).flat(), { isTextBox: true, x: 0.55, y: 2.3, w: 6.4, h: 4.3, fontFace: "Arial", fontSize: 20, color: "000000", paraSpaceAfter: 14, valign: "top", margin: 0, objectName: nm("details") });
  s.addNotes("Keep it plain. One sentence: every other team predicts when a part fails; FLIGHTLINE predicts how many sortie-days the fleet is about to lose, and names the single action that saves the most of them.");
}

// ================================================================ 2 · IDEA TITLE
pres.addSection({ title: "Problem and idea" });
{
  const s = content("Problem and idea");
  s.addText("IDEA TITLE", { placeholder: "title" });
  text(s, "FLIGHTLINE — Fleet Availability Twin", { x: 0.45, y: 1.2, w: 12.4, h: 0.38, fontSize: 20, bold: true });
  text(s, "A decision layer that joins the four maintenance silos, predicts how many sortie-days the fleet is about to lose, and names the action that saves the most of them — scored in aircraft-days, not RMSE.", { x: 0.45, y: 1.58, w: 12.4, h: 0.55, fontSize: 14, color: "222222" });
  const X = [0.45, 4.68, 8.91], BW = 4.0, Y = 2.3, BH = 4.5;
  X.forEach((x) => boxed(s, x, Y, BW, BH));
  const head = (x, t) => text(s, t, { x: x + 0.2, y: Y + 0.15, w: BW - 0.4, h: 0.5, fontSize: 21, bold: true, color: C.accent1 });
  head(X[0], "THE PROBLEM :");
  text(s, [
    { text: "The statement names fragmentation, not accuracy: ", options: { bold: true, breakLine: false } },
    { text: "“fragmented and largely reactive … not adequately integrated”.", options: { italic: true, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    ...bullets([
      "Health monitoring, technical records, spares and MRO agencies never meet",
      "A fault predicted on Tuesday collides with a six-week spares lead time — the aircraft sits on the ground anyway",
      "RUL models report RMSE; nobody reports aircraft-days",
    ], { gap: 6 }),
  ], { x: X[0] + 0.2, y: Y + 0.72, w: BW - 0.4, h: BH - 0.9, fontSize: 14 });
  head(X[1], "FLIGHTLINE :");
  text(s, [
    { text: "ONE GRAPH OF THE FOUR SILOS", options: { bold: true, breakLine: true } },
    { text: "tail → LRU → part → stock → depot bay → sorties", options: { breakLine: true } },
    { text: "PROGNOSIS WITH HONEST INTERVALS", options: { bold: true, breakLine: true } },
    { text: "Remaining life as a 90% conformal interval; abstains when unsure", options: { breakLine: true } },
    { text: "FLEET SIMULATOR + OPTIMISER", options: { bold: true, breakLine: true } },
    { text: "90 days, day by day; CP-SAT re-sequences depot inductions and expedites", options: { breakLine: true } },
    { text: "CANNIBALISATION, PRICED", options: { bold: true, breakLine: true } },
    { text: "Every swap returns a net in aircraft-days over 30 days", options: {} },
  ], { x: X[1] + 0.2, y: Y + 0.72, w: BW - 0.4, h: BH - 0.9, fontSize: 13.5, paraSpaceAfter: 3 });
  head(X[2], "WHAT THE OFFICER GETS :");
  text(s, [
    ...bullets([
      "Ranked actions, each scored in aircraft-days gained",
      "“Why this number?” — the trace of which silo said what",
      "Availability attribution: why Ao is what it is",
      "Live what-if: ground aircraft, delay spares, surge sorties",
      "Printable draft maintenance order",
    ], { gap: 6, more: true }),
    { text: " ", options: { breakLine: true, fontSize: 6 } },
    { text: "It ranks and prices. It never authorises — the signature stays with the officer.", options: { bold: true } },
  ], { x: X[2] + 0.2, y: Y + 1.12, w: BW - 0.4, h: BH - 1.25, fontSize: 14 });
  s.addNotes("The statement does not say the models are inaccurate. It says the data never meets. So we do not compete on accuracy: we join the four silos and optimise the number the Air Force already runs on — operational availability.");
}

// ================================================================ 3 · THE REFRAME (APH)
{
  const s = content("Problem and idea");
  s.addText("THE REFRAME: APH", { placeholder: "title" });
  card(s, 0.45, 1.25, 12.43, 1.0, { fill: HEX.tint, line: HEX.tint });
  text(s, [
    { text: "APH  =  P( t", options: {} }, { text: "warning", options: { subscript: true } },
    { text: "  ≤  t", options: {} }, { text: "failure", options: { subscript: true } },
    { text: "  −  ( spares lead + depot queue + bay time ) )", options: {} },
  ], { x: 0.6, y: 1.3, w: 8.6, h: 0.9, fontFace: "Cambria", fontSize: 20, color: C.text2, valign: "middle" });
  text(s, "A prediction is worth nothing if it arrives after the last day you could have acted on it.", { x: 9.25, y: 1.3, w: 3.5, h: 0.9, fontSize: 13, italic: true, color: C.text2, valign: "middle" });

  text(s, "Two real models · same training data · same " + N.n_test_units + " held-out run-to-failure units", { x: 0.45, y: 2.45, w: 7.3, h: 0.32, fontSize: 13, bold: true });
  const hdr = (t) => ({ text: t, options: { bold: true, color: "FFFFFF", fill: { color: HEX.navy }, align: "center" } });
  const row = (k, a, b, strong) => [
    { text: k, options: { color: "222222" } },
    { text: a, options: { align: "center", color: "444444" } },
    { text: b, options: { align: "center", bold: true, color: strong ? C.accent1 : "000000" } },
  ];
  s.addTable([
    [hdr("Measure"), hdr(`Short-horizon model\n(RUL capped at ${M.cap_cycles}, literature convention)`), hdr("FLIGHTLINE\n(uncapped + conformal)")],
    row("RMSE on the model's own target", SH.rmse_cycles.toFixed(1) + " cycles", FL.rmse_cycles.toFixed(1) + " cycles"),
    row(`RMSE in the last ${M.cap_cycles} cycles before failure`, SH.rmse_last_cycles.toFixed(1) + " cycles", FL.rmse_last_cycles.toFixed(1) + " cycles"),
    row("APH — failures warned in time", pct(SH.aph, 0), pct(FL.aph, 0), true),
    row("Aircraft-days lost to late warnings / 100 failures", SH.aircraft_days_lost_per_100_failures.toFixed(0), FL.aircraft_days_lost_per_100_failures.toFixed(0), true),
    row(`Fleet backtest: sorties lost in 90 days (no prognosis: ${BT.none.sortie_days_lost})`, String(BT.short_horizon.sortie_days_lost), String(BT.flightline.sortie_days_lost), true),
  ], { x: 0.45, y: 2.82, w: 7.3, colW: [3.3, 2.1, 1.9], fontFace: "Arial", fontSize: 12, rowH: [0.55, 0.42, 0.42, 0.42, 0.42, 0.5], valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.line }, margin: [2, 6, 2, 6], objectName: nm("aph-table") });
  card(s, 0.45, 5.75, 7.3, 1.05, { fill: "FFFFFF", line: HEX.blue, lw: 1.5 });
  text(s, [
    { text: "More accurate near failure — and still loses. ", options: { bold: true, color: C.accent1 } },
    { text: `The capped model cannot see past ${M.cap_cycles} cycles (≈${SH.warns_up_to_days.toFixed(0)} days); most spares take longer than that to arrive. FLIGHTLINE warns at a median ${FL.median_lead_over_window.toFixed(1)}× the decision window.`, options: {} },
  ], { x: 0.62, y: 5.82, w: 7.0, h: 0.92, fontSize: 13, valign: "middle" });

  const parts = Object.keys(M.per_part).sort((a, b) => M.per_part[a].window_days - M.per_part[b].window_days);
  const SHORT = { "PN-5520-ADC": "Air data", "PN-3108-GEN": "Generator", "PN-4410-HP": "Hyd. pump", "PN-1904-MLA": "MLG actuator", "PN-2275-FCU": "Fuel control", "PN-6731-RTX": "Radar TX" };
  const labels = parts.map((p) => `${SHORT[p]} (${M.per_part[p].window_days} d)`);
  s.addChart(pres.charts.BAR, [
    { name: "Short-horizon", labels, values: parts.map((p) => Math.round(100 * M.per_part[p].short_horizon)) },
    { name: "FLIGHTLINE", labels, values: parts.map((p) => Math.round(100 * M.per_part[p].flightline)) },
  ], {
    x: 8.0, y: 2.45, w: 4.88, h: 4.35, barDir: "bar", barGapWidthPct: 45,
    chartColors: [HEX.soft, HEX.blue], showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt",
    showTitle: true, title: "APH by part (decision window in days)", titleFontSize: 13, titleFontFace: "+mn-lt", titleColor: "000000",
    showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt", dataLabelColor: "444444", dataLabelFormatCode: '0"%"',
    valAxisMinVal: 0, valAxisMaxVal: 115, valAxisHidden: true, valGridLine: { style: "none" },
    catAxisLabelFontSize: 11, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "333333", catAxisOrientation: "maxMin",
    objectName: nm("aph-chart"),
  });
  s.addNotes(`A model with RMSE 0.9 sounds better than 48.6. But that 0.9 is measured against RUL capped at ${M.cap_cycles} cycles — the convention most C-MAPSS papers use — and a capped model cannot warn earlier than the cap. APH is the share of failures warned early enough to get the spare, the bay and the crew in place. Ours: ${pct(FL.aph, 0)}. Then in a 90-day backtest on true failures, both models drive pre-emptive spares orders: ${BT.short_horizon.sortie_days_lost} sorties lost vs ${BT.flightline.sortie_days_lost}.`);
}

// ================================================================ 4 · TECHNICAL APPROACH
pres.addSection({ title: "How it works" });
{
  const s = content("How it works");
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
    ["5  DELIVERY", ["FastAPI + offline dashboard", "Live what-if, re-solves in ≈1 s", "Printable draft maintenance order"]],
  ];
  const pw = 2.3, pg = 0.2, py = 3.42, ph = 2.2;
  steps.forEach(([h, lines], i) => {
    const x = 0.45 + i * (pw + pg) + (i > 0 ? 0 : 0);
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
    ["SERVING", "Python · FastAPI · uvicorn · Chart.js (vendored)"],
    ["ASSURANCE", "77 pytest tests · same seed → same numbers"],
  ];
  const cw = 12.43 / stack.length;
  card(s, 0.45, 6.07, 12.43, 0.82, { fill: "FFFFFF", line: HEX.line });
  stack.forEach(([h, b], i) => {
    const x = 0.45 + i * cw;
    text(s, [{ text: h, options: { bold: true, breakLine: true, color: C.text2 } }, { text: b, options: { color: "333333" } }], { x: x + 0.1, y: 6.12, w: cw - 0.2, h: 0.74, fontSize: 10.5 });
  });
  s.addNotes("The twin that matters is of the maintenance system, not the engine. Air-gapped by construction: no cloud call, no LLM, no GPU, one SQLite file. Units: the model predicts RUL in cycles (sorties); it becomes days only when divided by planned utilisation. The headline delta is always simulator vs simulator — never the optimiser's own objective.");
}

// ================================================================ 5 · CANNIBALISATION
{
  const s = content("How it works");
  s.addText("CANNIBALISATION, PRICED", { placeholder: "title" });
  text(s, "What GAO-02-86 found (US Navy + Air Force, FY1996–2000)", { x: 0.45, y: 1.22, w: 4.2, h: 0.5, fontSize: 13, bold: true });
  const f = (k, v) => [{ text: k, options: { bold: true, color: C.accent1, align: "left" } }, { text: v, options: { color: "222222" } }];
  s.addTable([
    f("≈850,000", "cannibalisations reported"),
    f("≈5.3 million", "additional maintenance hours"),
    f("≥ 2×", "“at least twice as long as normal repairs”"),
    f("111 parts", "missing from one aircraft"),
    f("903–1,756 days", "four cannibalised FA-18s not flown"),
    f("> 25%", "readiness fell when the Army stopped (1987 test)"),
  ], { x: 0.45, y: 1.75, w: 4.2, colW: [1.4, 2.8], fontFace: "Arial", fontSize: 11, rowH: 0.44, valign: "middle", border: { type: "solid", pt: 0.75, color: HEX.line }, margin: [2, 5, 2, 5], objectName: nm("gao-table") });
  text(s, [
    { text: "Services' own policy: ", options: { bold: true } },
    { text: "cannibalisations “aggravate the very same supply problems that they are meant to overcome.”", options: { italic: true } },
    { text: "  Load-bearing and corrosive at once.", options: { bold: true, color: C.accent1 } },
  ], { x: 0.45, y: 4.95, w: 4.2, h: 1.1, fontSize: 12 });
  text(s, "Source: GAO-02-86, Military Aircraft: Services Need Strategies to Reduce Cannibalizations, Nov 2001.", { x: 0.45, y: 6.32, w: 4.2, h: 0.5, fontSize: 10, color: HEX.grey });

  const mx = 4.95, mw = 3.8;
  text(s, "So FLIGHTLINE prices it", { x: mx, y: 1.22, w: mw, h: 0.4, fontSize: 15, bold: true, color: C.accent1 });
  card(s, mx, 1.68, mw, 1.62, { fill: HEX.tint, line: HEX.tint });
  text(s, [
    { text: "net = recipient gain − donor loss − re-failure", options: { bold: true, breakLine: true } },
    { text: " ", options: { breakLine: true, fontSize: 5 } },
    { text: "The donor takes the recipient's place in the spares queue: the swap moves the hole, it does not fill it. Swap labour 2× normal (GAO). Moved part loses 20% of remaining life — a modelled assumption, labelled on screen.", options: {} },
  ], { x: mx + 0.15, y: 1.76, w: mw - 0.3, h: 1.5, fontSize: 11.5 });
  text(s, "Same radar transmitter for grounded TAIL-02:", { x: mx, y: 3.48, w: mw, h: 0.32, fontSize: 12.5, bold: true });
  const tail02 = D.cann.filter((c) => c[1] === "TAIL-02");
  const fromDown = tail02.find((c) => c[4] > 0 && c[4] < 1000);
  const fromFlying = tail02.find((c) => c[4] === 0);
  const fromGrounded = G.cann.find((c) => c[1] === "TAIL-02");
  const rowsC = [
    [`${fromGrounded[0]} grounded for the horizon`, fromGrounded[3]],
    [`${fromDown[0]} down ${fromDown[4]} more days anyway`, fromDown[3]],
    [`${fromFlying[0]} flying today`, fromFlying[3]],
  ];
  rowsC.forEach(([k, v], i) => {
    const y = 3.88 + i * 0.78;
    card(s, mx, y, mw, 0.66, { fill: "FFFFFF", line: HEX.line });
    text(s, "Donor " + k, { x: mx + 0.15, y, w: 2.3, h: 0.66, fontSize: 12, valign: "middle" });
    text(s, (v > 0 ? "+" : v < 0 ? "−" : "") + Math.abs(v).toFixed(1), { x: mx + 2.4, y, w: 1.25, h: 0.66, fontSize: 24, bold: true, align: "right", valign: "middle", color: v > 0 ? C.accent1 : C.accent3 });
  });
  text(s, "aircraft-days over 30 days", { x: mx, y: 6.24, w: mw, h: 0.3, fontSize: 10.5, color: HEX.grey, align: "right" });
  const ih = img(s, "cann_grounded.png", 9.0, 1.22, 3.88, 1004, 1244, { alt: "FLIGHTLINE cannibalisation card: +1 aircraft in 2 days, +28.0 aircraft-days over 30" });
  text(s, "Live card in the prototype (TAIL-01 and TAIL-03 grounded)", { x: 9.0, y: 1.22 + ih + 0.06, w: 3.88, h: 0.3, fontSize: 10, color: HEX.grey });
  s.addNotes("It is both necessary and corrosive, so we do not ban it — we price it. The officer on this panel has signed cannibalisation authorisations; nobody has shown them this number. Robbing a flying aircraft is always net negative: it only moves the hole. Robbing an aircraft that is down anyway can pay handsomely.");
}

// ================================================================ 6 · ABSTENTION GATE
{
  const s = content("How it works");
  s.addText("THE ABSTENTION GATE", { placeholder: "title" });
  text(s, "We can tell you when we don't know.", { x: 0.45, y: 1.22, w: 3.75, h: 0.75, fontSize: 19, bold: true, color: C.accent1 });
  card(s, 0.45, 2.05, 3.75, 1.2, { fill: HEX.tint, line: HEX.tint });
  text(s, [
    { text: "Rule", options: { bold: true, breakLine: true } },
    { text: "Abstain when the 90% interval is wider than the decision window ", options: {} },
    { text: "and", options: { bold: true } },
    { text: " its lower edge falls inside it.", options: { breakLine: true } },
    { text: "→ recommend inspection, not a prediction", options: { italic: true, color: C.accent1 } },
  ], { x: 0.6, y: 2.13, w: 3.5, h: 1.25, fontSize: 11.5 });
  const stat = (y, big, small) => {
    text(s, big, { x: 0.45, y, w: 1.55, h: 0.62, fontSize: 28, bold: true, color: C.accent1, valign: "middle" });
    text(s, small, { x: 2.05, y, w: 2.15, h: 0.62, fontSize: 11, color: "222222", valign: "middle" });
  };
  stat(3.62, pct(N.evaluation.coverage), `coverage on ${N.evaluation.n_test_points.toLocaleString("en-IN")} held-out points (target 90%)`);
  stat(4.34, pct(N.cov_last20, 0), `coverage in the last 20 cycles before failure (${N.n_last20} points)`);
  stat(5.06, String(D.counts.inspect), `parts flagged for inspection today; ${D.counts.order_now} confident enough to order; ${D.counts.monitor} monitored`);
  text(s, "Mondrian conformalised quantile regression: calibrated separately in three bands of predicted RUL, so the guarantee holds near failure, not just on average.", { x: 0.45, y: 5.85, w: 3.75, h: 0.95, fontSize: 11, color: HEX.grey });
  const ih = img(s, "gate.png", 4.5, 1.22, 8.38, 2544, 1014, { alt: "Abstention gate: remaining-life intervals against decision windows" });
  text(s, [
    { text: "Grey bar ", options: { bold: true } }, { text: "= 90% interval narrow enough to act on: order now.   ", options: {} },
    { text: "Amber bar ", options: { bold: true, color: C.accent2 } }, { text: "= wider than its decision window (shaded): the model abstains.", options: {} },
  ], { x: 4.5, y: 1.22 + ih + 0.12, w: 8.38, h: 0.5, fontSize: 11.5 });
  card(s, 4.5, 5.35, 8.38, 1.45, { fill: "FFFFFF", line: HEX.blue, lw: 1.5 });
  text(s, "Where a false negative can cost aircrew and a false positive wastes a sortie, a system that knows the limits of its own confidence is worth more than one that is slightly more accurate on average.", { x: 4.68, y: 5.42, w: 8.0, h: 1.3, fontSize: 15, italic: true, valign: "middle", color: C.text2 });
  s.addNotes("Say this slowly. Conformal prediction gives a distribution-free coverage guarantee: no assumption about the error distribution. A single global correction gave 92% overall but about 80% near failure — exactly the wrong place to be overconfident — so we calibrate per band.");
}

// ================================================================ 7 · LIVE DEMO
pres.addSection({ title: "Demo" });
{
  const s = content("Demo");
  s.addText("LIVE DEMO", { placeholder: "title" });
  const ih = img(s, "dashboard.png", 0.45, 1.22, 7.6, 3200, 2000, { alt: "FLIGHTLINE dashboard: headline Ao and line board" });
  text(s, `Running prototype · 127.0.0.1:8000 · offline · seed 26249 · re-solves in ≈${(D.ms / 1000).toFixed(1)} s`, { x: 0.45, y: 1.22 + ih + 0.06, w: 7.95, h: 0.28, fontSize: 10.5, color: HEX.grey });
  text(s, `Ao ${pct(D.ao_b)} → ${pct(D.ao_p)}  ·  +${D.d_ac} aircraft-days  ·  +${D.d_sd} sorties flown  ·  sorties lost ${D.lost_b} → ${D.lost_p}`, { x: 0.45, y: 6.4, w: 8.0, h: 0.45, fontSize: 12.5, bold: true, color: C.text2, valign: "middle" });
  const x = 8.65, w = 4.23;
  text(s, "Let the panel break it", { x, y: 1.22, w, h: 0.4, fontSize: 17, bold: true, color: C.accent1 });
  const moves = [
    ["“Ground two aircraft at Base A.”", "Click 01 and 03",
      `Ao falls to ${pct(G.ao_b)}. Top action becomes: cannibalise the radar from grounded TAIL-03 to TAIL-02, +${G.top[0][1].toFixed(1)} aircraft-days.`],
    ["“Spares convoy is 10 days late.”", "Drag convoy delay to 10",
      `Spares share of the gap ${pts(D.attr_b.spares_lead_time)} → ${pts(DL.attr_b.spares_lead_time)} pts; order-now parts ${D.counts.order_now} → ${DL.counts.order_now}; priced cannibalisation +${DL.top[0][1].toFixed(0)}.`],
    ["“Surge: 40% more sorties.”", "Drag sortie surge to +40%",
      `Sorties lost: ${SU.lost_b} under current practice vs ${SU.lost_p} under the plan (+${SU.d_ac} aircraft-days).`],
  ];
  moves.forEach(([say, act, see], i) => {
    const y = 1.72 + i * 1.62;
    card(s, x, y, w, 1.48, { fill: HEX.tint, line: HEX.tint });
    text(s, [{ text: say, options: { bold: true, breakLine: true } }, { text: act, options: { color: C.accent1, bold: true } }], { x: x + 0.15, y: y + 0.08, w: w - 0.3, h: 0.55, fontSize: 12.5 });
    text(s, see, { x: x + 0.15, y: y + 0.66, w: w - 0.3, h: 0.78, fontSize: 11.5, color: "222222" });
  });
  text(s, "Every action carries “Why this number?” — the trace of which silo said what.", { x, y: 6.62, w, h: 0.3, fontSize: 10.5, italic: true, color: HEX.grey });
  s.addNotes("Do not play a recording. Hand them the controls. Change anything you like — both plans are re-simulated and CP-SAT re-solves in about a second, with the reason printed next to every recommendation. Press Reset before you start.");
}

// ================================================================ 8 · FEASIBILITY AND VIABILITY
pres.addSection({ title: "Feasibility and impact" });
{
  const s = content("Feasibility and impact");
  s.addText("FEASIBILITY AND VIABILITY", { placeholder: "title" });
  const col = [0.45, 4.7, 8.95], cw = 3.93;
  const head = (x, t) => text(s, t, { x, y: 1.22, w: cw, h: 0.36, fontSize: 15, bold: true, color: C.accent1 });
  head(col[0], "HONEST ABOUT DATA");
  text(s, [
    ...bullets([
      "We have no IAF data and do not pretend to. The badge says SYNTHETIC SCENARIO on every screen",
      "Degradation: 432 run-to-failure units with the shape of NASA N-CMAPSS",
      "Drop real N-CMAPSS / C-MAPSS files in data/raw and the model retrains on real engines; logistics stay synthetic and the badge says so",
      "Decisions never see ground truth; it is used only to backtest",
    ], { gap: 7 }),
  ], { x: col[0], y: 1.65, w: cw, h: 3.0, fontSize: 12 });
  head(col[1], "PLATFORM-AGNOSTIC");
  text(s, "Swap the degradation model; everything above it is unchanged. Fewer labelled failures do not make it unsafe — the interval widens and it warns earlier:", { x: col[1], y: 1.65, w: cw, h: 0.95, fontSize: 12 });
  const ft = M.fine_tuning;
  s.addChart(pres.charts.LINE, [{ name: "Warning lead ÷ decision window", labels: ft.map((r) => String(r.labelled_failures)), values: ft.map((r) => +r.median_lead_over_window.toFixed(2)) }], {
    x: col[1], y: 2.62, w: cw, h: 2.15, chartColors: [HEX.blue], lineSize: 2.5, lineDataSymbol: "circle", lineDataSymbolSize: 7,
    showLegend: false, showTitle: true, title: "Warning lead ÷ window vs labelled failures", titleFontSize: 11, titleFontFace: "+mn-lt", titleColor: "000000",
    showValue: true, dataLabelPosition: "t", dataLabelFontSize: 9, dataLabelFontFace: "+mn-lt", dataLabelColor: "444444", dataLabelFormatCode: '0.0"×"',
    valAxisMinVal: 1, valAxisMaxVal: 3.6, valAxisHidden: true, valGridLine: { style: "none" }, catAxisLabelFontSize: 10, catAxisLabelFontFace: "+mn-lt", catAxisLabelColor: "333333",
    objectName: nm("finetune-chart"),
  });
  text(s, `APH stays ${pct(Math.min(...ft.map((r) => r.aph)), 0)}–${pct(Math.max(...ft.map((r) => r.aph)), 0)} from ${ft[0].labelled_failures} to ${ft[ft.length - 1].labelled_failures} labelled failures. More data buys efficiency, not safety.`, { x: col[1], y: 4.8, w: cw, h: 0.62, fontSize: 11, color: "222222" });
  head(col[2], "RISKS → MITIGATIONS");
  const r = (a, b) => [{ text: a, options: { bold: true, color: "222222" } }, { text: b, options: { color: "333333" } }];
  s.addTable([
    r("Model ≠ real fleet", "Decision layer is model-agnostic; conformal recalibrates on a small held-out set"),
    r("Classified data", "Air-gapped on one base server; no cloud, no external API"),
    r("Trust", "Ranks and prices, never authorises; every number traceable"),
    r("Optimiser approximations", "Every plan re-scored by the full simulator"),
  ], { x: col[2], y: 1.65, w: cw, colW: [1.45, 2.48], fontFace: "Arial", fontSize: 10.5, valign: "middle", rowH: 0.78, border: { type: "solid", pt: 0.75, color: HEX.line }, margin: [2, 5, 2, 5], objectName: nm("risk-table") });
  card(s, 0.45, 5.5, 12.43, 1.38, { fill: HEX.tint, line: HEX.tint });
  text(s, "RESEARCH AND REFERENCES", { x: 0.6, y: 5.56, w: 6, h: 0.28, fontSize: 11.5, bold: true, color: C.accent1 });
  text(s, bullets([
    "Arias Chao M. et al., Aircraft engine run-to-failure dataset under real flight conditions (N-CMAPSS), Data 6(1):5, 2021 · Saxena A. et al., C-MAPSS, PHM 2008",
    "Romano Y., Patterson E., Candès E., Conformalized Quantile Regression, NeurIPS 2019",
    "US GAO, GAO-02-86, Military Aircraft: Services Need Strategies to Reduce Cannibalizations, 2001 · Sherbrooke C., METRIC, Operations Research 16(1), 1968",
    "Google OR-Tools CP-SAT solver · scikit-learn HistGradientBoostingRegressor · NetworkX",
  ], { gap: 1 }), { x: 0.6, y: 5.84, w: 12.15, h: 1.0, fontSize: 10, color: "222222" });
  s.addNotes("Volunteer the weakness before the panel finds it. Our claim is not that this model transfers to a Su-30. Our claim is that the decision layer is platform-agnostic: the twin, the simulator, the attribution, the optimiser, the cannibalisation price and the abstention gate are unchanged when the degradation model is swapped.");
}

// ================================================================ 9 · AVAILABILITY ATTRIBUTION
{
  const s = content("Feasibility and impact");
  s.addText("AVAILABILITY ATTRIBUTION", { placeholder: "title" });
  text(s, `Why is availability ${pct(D.ao_b)} and not ${pct(D.ceil_b)}?`, { x: 0.45, y: 1.2, w: 12.43, h: 0.45, fontSize: 19, bold: true, color: C.accent1 });
  const wh = img(s, "waterfall_baseline.png", 0.45, 1.75, 5.1, 1254, 820, { alt: "Attribution waterfall, current practice" });
  const bh = img(s, "board_baseline.png", 5.8, 1.75, 7.08, 2544, 1298, { alt: "Line board: every aircraft, every day, coloured by reason" });
  text(s, "Line board: 24 aircraft × 90 days, each day on the ground coloured by its reason (current practice)", { x: 5.8, y: 1.75 + bh + 0.06, w: 7.08, h: 0.3, fontSize: 10, color: HEX.grey });
  const a = D.attr_b, ad = D.attr_days_b;
  const items = [
    ["Waiting for spares", a.spares_lead_time, ad.spares_lead_time],
    ["Waiting for a depot bay", a.depot_contention, ad.depot_contention],
    ["Unscheduled removal", a.unscheduled_removal, ad.unscheduled_removal],
    ["Cannibalisation cascade", a.cannibalisation_cascade, ad.cannibalisation_cascade],
  ];
  const tY = 1.75 + wh + 0.18;
  s.addTable([
    ...items.map(([k, v, d]) => [{ text: k }, { text: pts(v) + " pts", options: { align: "right", bold: true } }, { text: d + " aircraft-days", options: { align: "right", color: "444444" } }]),
    [{ text: "Total availability gap", options: { bold: true } }, { text: pts(D.gap_b) + " pts", options: { align: "right", bold: true, color: C.accent1 } }, { text: items.reduce((t, x) => t + x[2], 0) + " aircraft-days", options: { align: "right", bold: true } }],
  ], { x: 0.45, y: tY, w: 5.1, colW: [2.3, 1.1, 1.7], fontFace: "Arial", fontSize: 11.5, rowH: 0.3, valign: "middle", border: { type: "solid", pt: 0.5, color: HEX.line }, margin: [1, 5, 1, 5], objectName: nm("attr-table") });
  card(s, 5.8, 5.6, 7.08, 1.28, { fill: HEX.tint, line: HEX.tint });
  text(s, [
    { text: "Every grounded aircraft-day is counted once, under its highest-priority reason, so the causes add up to the gap exactly — a unit-tested invariant, not a chart. ", options: {} },
    { text: "This is the screen a Base Maintenance Officer opens at 0700.", options: { bold: true, color: C.text2 } },
  ], { x: 5.98, y: 5.66, w: 6.75, h: 1.16, fontSize: 12.5, valign: "middle" });
  s.addNotes(`Under current practice the fleet loses ${pts(D.gap_b)} points of availability below its inspection-only ceiling of ${pct(D.ceil_b)}: ${pts(a.spares_lead_time)} to spares lead time, ${pts(a.depot_contention)} to depot contention, ${pts(a.unscheduled_removal)} to unscheduled removals, ${pts(a.cannibalisation_cascade)} to cannibalisation cascades. Nobody else is doing lost-availability attribution.`);
}

// ================================================================ 10 · IMPACT AND BENEFITS
{
  const s = content("Feasibility and impact");
  s.addText("IMPACT AND BENEFITS", { placeholder: "title" });
  const stats = [
    ["+" + D.d_ac, "aircraft-days in 90 days on a 24-aircraft fleet (+" + D.d_ao.toFixed(1) + " pts Ao), same aircraft, parts and bays"],
    [D.lost_b + " → " + D.lost_p, "tasked sorties lost to unavailability, current practice → plan"],
    [D.queue_b.toFixed(1) + " → " + D.queue_p.toFixed(1), "mean days an inspection waits for a depot bay"],
    [pct(FL.aph, 0), "of failures warned in time to act (capped-RMSE model: " + pct(SH.aph, 0) + ")"],
  ];
  const sw = 2.93, sg = 0.237;
  stats.forEach(([big, small], i) => {
    const x = 0.45 + i * (sw + sg);
    card(s, x, 1.25, sw, 1.75, { fill: HEX.tint, line: HEX.tint });
    text(s, big, { x: x + 0.15, y: 1.32, w: sw - 0.3, h: 0.78, fontSize: 34, bold: true, color: C.accent1, valign: "middle" });
    text(s, small, { x: x + 0.15, y: 2.1, w: sw - 0.3, h: 0.85, fontSize: 11.5, color: "222222" });
  });
  const who = [
    ["BASE MAINTENANCE OFFICER", ["Why availability is what it is, by cause", "Which depot induction to move, and when"]],
    ["LOGISTICS OFFICER", ["Which spare, stocked where, unlocks the most", "Which order to expedite, with its aircraft-days"]],
    ["ENGINEERING OFFICER", ["Cannibalisation priced before it is signed", "Inspect-or-order, with the model's own uncertainty"]],
  ];
  const ww = 4.0, wg = 0.215;
  who.forEach(([h, lines], i) => {
    const x = 0.45 + i * (ww + wg);
    boxed(s, x, 3.25, ww, 1.5);
    text(s, h, { x: x + 0.15, y: 3.33, w: ww - 0.3, h: 0.32, fontSize: 12.5, bold: true, color: C.accent1 });
    text(s, bullets(lines, { gap: 4 }), { x: x + 0.15, y: 3.7, w: ww - 0.3, h: 1.1, fontSize: 12.5 });
  });
  card(s, 0.45, 5.0, 6.1, 1.88, { fill: HEX.navy, line: HEX.navy });
  text(s, [
    { text: "DEPLOYMENT", options: { bold: true, breakLine: true } },
    { text: "Air-gapped by construction: one base server, one SQLite file, open-source stack. No cloud call, no LLM, no GPU, no foreign dependency. Nothing leaves the base network.", options: {} },
  ], { x: 0.62, y: 5.16, w: 5.8, h: 1.65, fontSize: 13, color: "FFFFFF", valign: "middle" });
  card(s, 6.78, 5.0, 6.1, 1.88, { fill: "FFFFFF", line: HEX.blue, lw: 1.5 });
  text(s, [
    { text: "WHAT WE NEED NEXT", options: { bold: true, color: C.accent1, breakLine: true } },
    ...bullets([
      "Labelled removals for one LRU family",
      "Lead-time history and stock levels by base",
      "Bay counts and phase intervals for one type; cannibalisation logs",
    ], { gap: 2 }),
  ], { x: 6.95, y: 5.16, w: 5.8, h: 1.65, fontSize: 12.5, valign: "middle" });
  s.addNotes("Aircraft-days recovered from the same aircraft, parts and bays — by joining the data, not by buying anything. Air-gapped by construction: nothing leaves the base network. The numbers are from the synthetic scenario; the first step with real data is one LRU family at one base.");
}

(async () => {
  await pres.writeFile({ fileName: OUT });
  await applyTheme(OUT, THEME);
  console.log("wrote", OUT);
})();
