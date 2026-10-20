# FLIGHTLINE — Fleet Availability Twin

**SIH26249 · Air Power: Predictive Maintenance & Fleet Availability**

> Every other team will predict when a part fails. FLIGHTLINE predicts how many
> sortie-days the fleet is about to lose, and names the action that saves the most of them.

The problem statement blames **fragmentation**: health monitoring, technical records,
spares and MRO agencies never meet. It does not say the models are inaccurate. So FLIGHTLINE
does not compete on RUL accuracy. It joins the four silos into one graph, simulates the fleet
day by day, and optimises the number the Air Force already runs on: **operational availability,
in aircraft-days and sortie-days**.

```
APH = P( t_warning ≤ t_failure − (spares lead + depot queue + bay time) )
```

A prediction is worth nothing if it arrives after the last day you could have acted on it.

---

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate     # Python 3.11 or newer
pip install -r requirements.txt
python -m flightline.seed                              # about a minute: scenario, model, metrics
uvicorn flightline.api:app --reload
```

Open **http://127.0.0.1:8000**. Then run `pytest` (77 tests, ~13 s).

- **Offline by construction.** Chart.js and the fonts are vendored in `flightline/static/`.
  Nothing calls the internet at run time. There is no cloud API, no LLM, no GPU and no login.
- **Deterministic.** Seed 26249 always gives the same numbers, including the optimiser
  (CP-SAT runs on a deterministic work budget, not a wall-clock limit).
- **Fast.** Server cold start ≈ 2 s. A scenario re-solves in ≈ 0.9–1.3 s on an M-series Mac.
- Tested on Python 3.14.6. Every pinned wheel was checked to exist for Python 3.11 as well.
- OR-Tools installed in 17 s here, so the CP-SAT optimiser is live. If it ever fails to
  import, `scheduler.py` falls back to the greedy schedule and the UI says
  "greedy (OR-Tools unavailable)".

---

## The demo: let the panel break it (numbers from seed 26249)

| They say | You do | They see |
|---|---|---|
| (start) | — | Current practice keeps **82.7%** available; the FLIGHTLINE plan **85.6%**: **+64 aircraft-days, +18 sorties**. Sorties lost 23 → 5. |
| "Ground two aircraft at Base A." | Click **01** and **03** | Ao falls to 79.0%. The top action becomes **Cannibalise the radar transmitter from TAIL-03 to TAIL-02: +28 aircraft-days**. A grounded aircraft is the cheapest source of parts. The worst candidate on the card, robbing a *flying* aircraft, prices at **−7.2**. |
| "Spares convoy is 10 days late." | Drag **Spares convoy delay** to 10 | Spares lead time grows from 8.0 to 9.9 points of the gap. Parts whose interval now reaches their window rise from 3 to 10 *order now*. **Price cannibalisation, don't react** becomes the top action at +60 aircraft-days. |
| "Surge: 40% more sorties next fortnight." | Drag **Sortie surge** to +40% | Sorties lost under current practice jump to 64; the plan holds it to 39 (+83 aircraft-days). The optimiser re-sequences 13 depot inductions. |

Every recommendation has a **Why this number** trace naming which silo said what and how the
number was valued. **Print maintenance order** produces a one-page draft order with every trace.

---

## What is on the screen

| Panel | What it answers |
|---|---|
| **Line board** | All 24 tails × 90 days. Each day on the ground is coloured by *why*. Toggle current practice / plan; outlined days are days lost under current practice that fly under the plan. The number beside each tail is its criticality: sortie-days lost if that aircraft is lost for the horizon. |
| **Where availability goes** | Attribution waterfall: ceiling (only scheduled inspections) minus each cause = achieved Ao. The causes sum to the gap **exactly**. |
| **What to do** | Ranked actions, each in aircraft-days, with method and trace. |
| **Cannibalisation, priced** | Pick any waiting aircraft and donor and see what the swap really nets over 30 days. |
| **The abstention gate** | Every part whose 90% interval reaches its decision window. Too wide → the model abstains and asks for inspection. |
| **Which spare, stocked where** | One more unit at each base, replayed through the projection. |
| **Depot inductions** | Current practice vs plan, with due dates and bay waits. |
| **Accuracy is the wrong target** | APH vs RMSE, a ground-truth backtest, and how the model behaves as labelled failures grow. |

---

## What is real and what is synthetic

**The method is real; the data is not.** The provenance badge says so on every screen.

- **Synthetic** (`datagen.py`, seed 26249): 24 tails (`TAIL-01…24`), 3 bases (`BASE-A/B/C`),
  6 LRU types with lead times 7–60 days, 2 depots (2 + 1 bays), a 90-day sortie plan, phase
  inspections, stock and in-transit orders. Also 432 historical run-to-failure units with the
  *shape* of N-CMAPSS: multivariate sensors, six operating regimes, monotonic degradation
  plus noise, and a true failure cycle per unit.
- **Placeholders, deliberately.** No real tail numbers, squadrons, insignia or ministry
  branding. This is our analysis, not an official system.
- **Real NASA data drops in.** Put `N-CMAPSS_DS*.h5` (needs `pip install h5py`) or
  C-MAPSS `train_FD00*.txt` into `data/raw/` and re-run the seed. The degradation model
  then trains, calibrates and tests on real engines. Each installed part takes a held-out real
  unit cut at the same fraction of life. The badge changes to
  `N-CMAPSS DEGRADATION · SYNTHETIC LOGISTICS`, because the logistics stay synthetic.
- **Ground truth is quarantined.** True failure times and future sensor traces exist only
  for the backtest in `metrics.py`. Every decision the dashboard shows is made on the
  model's predictions, never on the truth.

---

## How it works

```
datagen ─► SQLite ─► data.World / DegradationSet ─► prognosis (HGB + Mondrian CQR)
                                   │                          │ RUL intervals (cycles)
                                   ▼                          ▼
                     availability.simulate ◄── scheduler (greedy │ CP-SAT) ◄── cannibalise.price_core
                                   │
                    twin (NetworkX graph) · engine (actions, traces) · metrics (APH, backtest)
                                   │
                              api (FastAPI) ─► static/index.html
```

| File | Role |
|---|---|
| `datagen.py` | Seeded synthetic fleet and run-to-failure population. |
| `ncmapss.py` | Optional loader for real N-CMAPSS / C-MAPSS files. |
| `prognosis.py` | Rolling mean/std/slope features per sensor (regime-normalised) plus age, `HistGradientBoostingRegressor`, conformal intervals, abstention. |
| `availability.py` | Day-by-day simulator, attribution, first-order replay. |
| `scheduler.py` | `schedule_greedy` (current practice) and the CP-SAT optimiser. |
| `cannibalise.py` | `price_cannibalisation` and its cost model. |
| `twin.py` | The graph: tail → LRU → part → stock → depot bay → sorties. `criticality()`, `spare_unlock_ranking()`. |
| `metrics.py` | APH, RMSE, the capped-model comparison, fleet backtest, fine-tuning curve. |
| `engine.py` | Runs a scenario end to end; builds actions with traces. |
| `api.py` | `GET /api/state`, `GET /api/actions`, `POST /api/scenario`, `GET /api/why/{id}`, `POST /api/cannibalise`, `GET /api/predict/{tail}/{part}`. |

### Units

RUL is predicted in **cycles** (one cycle = one sortie). It becomes **days** only when divided
by the tail's planned utilisation (sorties per day at its base, ≈0.63 nominal). Windows and lead
times are in **days**. Outcomes are in **aircraft-days** (one aircraft available for one day) and
**sortie-days** (one tasked aircraft-day actually flown: `min(tasked, available)` per base per day).

### Prognosis: point RUL plus an honest interval

- Gradient boosting on trailing 10- and 30-cycle mean, std and slope of each sensor, after
  removing the operating-regime effect (k-means on the settings, z-score per regime), plus
  cycles since install and part type. Trains in about 4 s and is cached in `models/`.
- **Conformalised quantile regression** (Romano et al., 2019): two quantile models give a
  first band, and a held-out calibration set measures how wrong that band is. This is
  **Mondrian**: calibrated separately in three bands of predicted RUL, so the 90% holds near
  failure and not just on average. Held-out coverage is **91.6%** overall and **94%** within
  20 cycles of failure.
- **Abstention.** `abstain = (rul_hi − rul_lo) > decision_window AND rul_lo ≤ decision_window`.
  The second clause is our addition to the brief's rule. Without it, a brand-new part with a
  naturally wide interval would be sent for inspection. An interval sitting wholly beyond the
  window needs no decision today and is monitored.

### Simulator and attribution

Every reason an aircraft is down is a *hold*. Each tail-day takes the label of its
highest-priority hold (directed grounding > scheduled inspection > waiting for a bay > waiting
for spares > cannibalisation cascade > unscheduled removal). Every down day is therefore counted
exactly once:

```
ceiling = 1 − (inspection days / total)     gap = ceiling − Ao = Σ causes   (exact, tested)
```

Spares follow a base-stock (S−1, S) policy: each failure orders a replacement, and arrivals serve
waiting aircraft first-come first-served. Wear is proportional to sorties flown, so a surge wears
parts faster.

*Directed grounding* is a fifth cause that the brief does not list. It is non-zero only when you
ground aircraft in the scenario, and it keeps those days from being mislabelled as something else.

### The plan vs current practice

- **Current practice:** induct each aircraft into the depot on its due date, first-come first-served;
  expedite orders for grounded aircraft as they come up (budget 3); cannibalise reactively when a
  base is short, from any aircraft down for at least 3 more days.
- **FLIGHTLINE plan:** CP-SAT chooses each induction's day and depot (up to 10 days early, bay
  capacity, one induction crew per depot per day) and which orders to expedite, maximising
  sortie-days and then aircraft-days. It solves once against current practice's projection
  and once against its own, and the better plan by simulation wins. Any overdue induction is
  then pulled back to the earliest free bay if the simulator agrees. Cannibalisation happens only
  when its price is positive.
- **The headline delta is simulator vs simulator**, never the optimiser's own objective. Both
  plans run through the same simulator on the same predicted failures.

### Cannibalisation, priced rather than banned

A swap does not create a part; it moves the hole. Over a 30-day lookahead:

```
recipient gain = min(spare_ready, H) − min(swap_days, H)              (0 if it has another hole)
donor loss     = min(max(donor_free, spare_ready), H) − min(donor_free, H)
re-failure     = Δp(fail within H) × (lead + fit)
net            = recipient gain − donor loss − re-failure
```

- Swap labour is **2× a normal repair**, from GAO-02-86 (2001), *Military Aircraft: Services Need
  Strategies to Reduce Cannibalizations*.
- The moved part losing **20%** of its remaining life is a **modelled assumption**, and is labelled
  as such on screen.

Robbing a flying aircraft is always net negative, and is strictly negative whenever the donor's
wait exceeds the lookahead (tested). Robbing an aircraft that is down anyway can pay handsomely.

### Spares ranking

For each part at each base, one more unit is added and the spares queues are re-served with the
failure timeline held fixed. This is first-order, in the spirit of METRIC marginal analysis. The
j-th demand is served at `max(need_j, j-th earliest unit)`, so adding stock can only help:
monotone by construction (tested for +1, +2, +3).

### APH vs RMSE: two real models, same data

| | Short-horizon (RUL capped at 15 cycles) | FLIGHTLINE |
|---|---|---|
| RMSE, on each model's own target | **0.9 cycles** (capped, as most C-MAPSS papers report) | 48.6 cycles (true RUL) |
| RMSE, last 15 cycles before failure | **3.7** | 7.1 |
| **APH** | 32% | **99%** |
| Median warning lead ÷ decision window | 0.79× | 1.81× |
| Aircraft-days lost to late warnings, per 100 failures | 877 | 9 |
| Ground-truth fleet backtest, sorties lost in 90 days (no prognosis: 18) | 12 | **8** |

The capped model is more accurate near failure and still loses: it cannot see further than about
22 days, and most spares take longer than that to arrive. FLIGHTLINE warns at a median 1.8× the
window. That is early, but not at install, and the extra margin is spares on a shelf, not
aircraft on the ground. With fewer labelled failures, APH stays high: the conformal interval
widens and warns earlier (3.2× the window at 12 failures, 1.8× at 216). More data buys
efficiency, not safety.

---

## Tests (`pytest`)

The brief's five non-negotiables, plus the rest:

- Conformal intervals reach ≈90% empirical coverage on held-out units (also ≥85% near failure).
- Attribution components sum to the availability gap, in 5 scenarios × 3 projections.
- The optimiser never violates bay or crew capacity, and every due inspection is scheduled once.
- Cannibalisation nets negative whenever the donor's lead time exceeds the lookahead (12 cases).
- `spare_unlock_ranking` is sorted, and monotone in extra stock.
- Same seed gives the same numbers (simulator, optimiser and actions); a re-solve is under 2 s;
  the generator is deterministic; replay with no change reproduces the simulator exactly; the
  C-MAPSS loader switches provenance; the API answers.

---

## Where we departed from the brief, and why

1. **Python 3.14 here, pins valid for 3.11+.** Only 3.14 is installed on this machine; every
   pinned wheel was checked for 3.11.
2. **Chart.js loads from the vendored copy first** and falls back to the CDN only if that file is
   missing. The brief says to assume no internet, and trying the CDN first can stall offline.
3. **Abstention has a second clause** (see Prognosis): an interval wholly beyond the window means
   "monitor", not "inspect".
4. **Conformal intervals are Mondrian CQR**, not a single residual quantile. A single quantile
   gave 92% coverage overall but about 80% near failure, which is exactly the wrong place to be
   overconfident.
5. **A fifth attribution cause, `directed_grounding`**, appears only when the scenario grounds
   aircraft.
6. **`sortie_surge` is a percentage** of tasking over the next 14 days, so the slider means the
   same thing at every base.
7. **Expedited orders are not delayed by the convoy slider.** Air priority bypasses the surface
   convoy, so expediting is worth more when the convoy is late.
8. **`price_cannibalisation` returns `aircraft_days_gained_now`** as +1 aircraft-day when the
   swap fits in one day. It also returns `aircraft_gained_now` (a count) and `swap_days`, so
   aircraft and aircraft-days are never confused.
9. **Tier 2 is done:** the fine-tuning curve, `GET /api/why/{id}`, and a printable maintenance
   order (browser print, so it works offline with no PDF library).

## What we would need from the IAF to go further

1. **Labelled removals** for one LRU family, with time of removal and confirmed failure mode.
   Conformal calibration needs only a held-out set to keep its 90% promise.
2. **Spares data**: lead-time history per part number and stock levels by base.
3. **Depot data**: bay counts, induction crews and phase-inspection intervals for one type.
4. **Cannibalisation logs**, to replace the 20% handling assumption with a measured hazard.
5. **A sortie plan** at weekly granularity.

Everything above the degradation model is platform-agnostic: the twin, simulator, attribution,
optimiser, price and gate. It runs air-gapped on a single base server.

---

### Licences

- B612 and B612 Mono: SIL Open Font License; designed by Intactile Design for Airbus as a
  cockpit display face.
- Chart.js 4.4.1: MIT.
