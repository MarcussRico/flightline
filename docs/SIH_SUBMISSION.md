# SIH portal submission: SIH26249

Text for the idea-submission form, ready to paste. Every number comes from the engine at seed 26249 (see `deck/dump_numbers.py`); re-check them if the scenario changes.

## Idea title (89 / 100 characters)

```
FLIGHTLINE: Fleet Availability Twin that Turns Failure Predictions into Sortie-Days Saved
```

## Technology bucket

If the dropdown lists technologies: **Artificial Intelligence / Machine Learning**. If it lists SIH themes: **Smart Automation** (next best: Transportation & Logistics). Use the same theme on slide 1 of the deck.

## Abstract (2,441 / 10,000 characters)

```
FLIGHTLINE is a fleet availability twin for SIH26249 (Air Power: Predictive Maintenance & Fleet Availability). The problem statement describes aircraft maintenance as fragmented and largely reactive: health monitoring, technical records, spares and MRO agencies are not adequately integrated. A fault predicted early is of no use if the spare takes six weeks to arrive or no depot bay is free, so the aircraft sits on the ground anyway.

FLIGHTLINE joins the four silos into one graph (aircraft → installed LRU → part number → stock location → depot bay → sortie plan) and answers the question a maintenance officer actually faces: how many sortie-days is the fleet about to lose, and which single action saves the most of them?

It has four parts. (1) Prognosis: a gradient-boosted model with conformalised quantile regression gives each part's remaining life as a 90% interval, and abstains (recommends inspection) when the interval is too wide to act on. (2) Simulator: a day-by-day, 90-day fleet simulation of sorties, wear, spares lead times and depot bays that attributes every lost aircraft-day to a cause. (3) Optimiser: Google OR-Tools CP-SAT re-sequences depot inductions and chooses which spares orders to expedite. (4) Decision layer: every cannibalisation is priced in aircraft-days, and all actions are ranked by aircraft-days gained, each with a traceable "why this number".

We score prediction by Actionable Prediction Horizon (APH): the share of failures warned early enough to get the spare, the bay and the crew in place. On held-out run-to-failure data FLIGHTLINE warns in time for 99% of failures, against 32% for a conventional capped-RUL model that has the better RMSE. In a synthetic 24-aircraft, three-base scenario, the plan raises operational availability from 82.7% to 85.6% (+64 aircraft-days in 90 days) and cuts tasked sorties lost from 23 to 5 with the same aircraft, parts and bays. Officers can ground aircraft, delay spares or surge sorties live, and both plans re-solve in about a second.

The prototype runs fully offline on one machine (Python, FastAPI, SQLite; no GPU, no cloud, no LLM), is deterministic and is covered by 77 automated tests. All data is synthetic and labelled as such on every screen; the degradation model follows the shape of NASA N-CMAPSS and retrains on real files when supplied. FLIGHTLINE ranks and prices actions; it never authorises them. The decision stays with the officer.
```

## Idea description (10,750 / 50,000 characters)

```
1. THE PROBLEM

The problem statement does not say that failure-prediction models are inaccurate. It says maintenance is "fragmented and largely reactive" and that health monitoring, technical records, spares and MRO agencies are "not adequately integrated". That is the real cause of lost availability:
- A fault predicted on Tuesday collides with a six-week spares lead time, and the aircraft sits on the ground anyway.
- Depot bays are booked by calendar, not by what the fleet will need next month.
- Cannibalisation is signed every day without a price. The US GAO (GAO-02-86) found about 850,000 cannibalisations and about 5.3 million extra maintenance hours across the US Navy and Air Force in FY1996–2000, each taking at least twice the labour of a normal repair.
- Remaining-useful-life (RUL) models are judged on RMSE. Nobody reports how many aircraft-days they saved.

2. OUR IDEA

Every other approach predicts when a part fails. FLIGHTLINE predicts how many sortie-days the fleet is about to lose, and names the single action that saves the most of them.

A prediction is worth nothing if it arrives after the last day on which anyone could have acted on it. So we measure prognosis by Actionable Prediction Horizon (APH):

APH = share of failures where the warning arrives before (failure time − spares lead time − depot queue − bay time)

and we optimise the number the Air Force already runs on: operational availability (Ao), in aircraft-days and sortie-days.

3. PROPOSED SOLUTION

FLIGHTLINE is a digital twin of the maintenance system, not of the engine. It has six parts.

3.1 Fleet twin
One NetworkX graph joins the four silos: aircraft → installed LRU → part number → stock location → depot bay → sortie plan. The prototype scenario has 24 aircraft at three bases, 144 installed LRUs across 6 part numbers (spares lead times 7–60 days), 18 stock locations, 2 depots with 3 bays, and 14 phase inspections due: 200 nodes and 392 edges.

3.2 Prognosis with honest intervals
- A HistGradientBoosting model reads rolling mean, standard deviation and slope of each sensor plus component age.
- Conformalised quantile regression turns its output into a 90% interval on remaining life. It is calibrated separately in three bands of predicted life (Mondrian), so the guarantee holds near failure and not only on average.
- Abstention gate: when the interval is wider than the part's decision window and its lower edge falls inside it, the system does not guess. It recommends an inspection.
- Result on held-out data: 91.6% coverage overall, 94% in the last 20 cycles before failure.

3.3 Fleet simulator and availability attribution
A day-by-day, 90-day simulator models sorties flown, wear, base-stock spares with FIFO queues, orders in transit, depot bays and induction crews. Every grounded aircraft-day is recorded once under its highest-priority cause, so the causes add up exactly to the gap between actual availability and the inspection-only ceiling. This is a unit-tested invariant.

3.4 Optimiser
Google OR-Tools CP-SAT chooses the induction day and depot for each inspection and which spares orders to expedite. It maximises sortie-days, then aircraft-days. It runs two passes with a deterministic time budget. Every plan is re-scored by the full simulator, so the headline gain is always simulator against simulator, never the optimiser's own objective.

3.5 Cannibalisation, priced
Net value = recipient's gain − donor's loss − re-failure risk, in aircraft-days over the next 30 days. The donor takes the recipient's place in the spares queue: a swap moves the hole, it does not fill it. Swap labour is costed at twice a normal repair (GAO). The moved part is assumed to lose 20% of its remaining life; this assumption is shown on screen.

3.6 Decision layer and dashboard
- Ranked actions (order now, inspect, move an induction, expedite, cannibalise), each scored in aircraft-days gained, with a "Why this number?" trace of which silo said what.
- An availability attribution chart answering "why is Ao what it is?".
- A spares unlock ranking: which extra unit, stocked where, frees the most aircraft-days.
- A line board of every aircraft for 90 days under current practice and under the plan.
- Live what-if: ground aircraft, delay spares deliveries, surge sorties. Both plans re-solve in about one second.
- A printable draft maintenance order. FLIGHTLINE ranks and prices; it never authorises. The signature stays with the officer.

4. HOW IT ADDRESSES THE PROBLEM STATEMENT

- Fragmentation: the four silos meet in one graph and one simulator, so a prognosis is judged against the actual spares lead time and bay queue.
- Reactive maintenance: inspections and spares orders are scheduled from forecast need, and pre-emptive orders are placed only when the model is confident enough.
- Fleet availability: every recommendation is expressed in aircraft-days and sortie-days, the units commanders plan in.
- Trust: every number is traceable, the model says when it does not know, and nothing is authorised automatically.

5. INNOVATION AND UNIQUENESS

- APH instead of RMSE. On the same training data and held-out units, a conventional model trained on RUL capped at 15 cycles (the common C-MAPSS convention) has RMSE 0.9 on its capped target, against 48.6 for FLIGHTLINE on the full horizon. Yet it warns in time for only 32% of failures; FLIGHTLINE warns in time for 99%. The capped model cannot see past about 15 cycles, and most spares take longer than that to arrive. In a 90-day fleet backtest on true failures, sorties lost were 18 with no prognosis, 12 with the capped model and 8 with FLIGHTLINE.
- Cannibalisation with a price. For the same radar transmitter for grounded TAIL-02, taking it from an aircraft that is down anyway is worth +8.9 aircraft-days; taking it from a flying aircraft is −2.0.
- Abstention. The system says "inspect" instead of producing a confident but wrong number.
- Lost-availability attribution by cause, adding up exactly.
- Platform-agnostic decision layer: swap the degradation model and the twin, simulator, optimiser and pricing are unchanged.

6. RESULTS ON THE SYNTHETIC SCENARIO (seed 26249, 24 aircraft, 90 days)

- Operational availability 82.7% under current practice → 85.6% under the FLIGHTLINE plan: +64 aircraft-days and +18 sorties flown, with the same aircraft, parts and bays.
- Tasked sorties lost to unavailability: 23 → 5.
- Mean days an inspection waits for a depot bay: 1.9 → 0.5.
- Why availability is 82.7% and not the 93.7% ceiling (11.0 points, 237 aircraft-days): waiting for spares 8.0 points (173 aircraft-days), unscheduled removal 1.6 (34), waiting for a depot bay 1.3 (27), cannibalisation cascade 0.1 (3).
- Stress tests, run live:
  - Ground TAIL-01 and TAIL-03: Ao falls to 79.0%; the new top action is to take the radar from grounded TAIL-03 for TAIL-02, +28 aircraft-days.
  - Spares 10 days late: spares' share of the gap rises from 8.0 to 9.9 points, and parts flagged "order now" rise from 3 to 10.
  - 40% sortie surge: 64 sorties lost under current practice against 39 under the plan (+83 aircraft-days).
- With few recorded failures the model stays safe: APH stays between 95% and 100% from 12 to 216 labelled failures. With less data the interval widens and the model warns earlier, not later.

7. TECHNICAL APPROACH AND STACK

- Data: SQLite, a seeded scenario generator, and a loader for NASA N-CMAPSS / C-MAPSS files.
- Machine learning: scikit-learn HistGradientBoosting, split conformal prediction (conformalised quantile regression, Mondrian bands).
- Optimisation: Google OR-Tools CP-SAT.
- Graph: NetworkX.
- Serving: Python, FastAPI, uvicorn; dashboard in HTML with Tailwind CSS and Chart.js, bundled for offline use.
- Assurance: 77 automated pytest tests; deterministic (same seed, same numbers).
- API: fleet state, ranked actions, scenario re-solve, the trace behind each action, cannibalisation pricing, and per-part prediction.
Pipeline: four silos → fleet twin → prognosis with abstention → 90-day simulator → CP-SAT optimiser → decision layer → dashboard and draft maintenance order.

8. FEASIBILITY, RISKS AND MITIGATIONS

The prototype is built and running. It works on a single laptop with no internet, GPU or external API, and re-solves both 90-day plans in about one second. A two-minute demo video was recorded from the running prototype.
- No IAF data: we do not claim any. A "SYNTHETIC SCENARIO" badge is on every screen. Ground truth is used only for backtesting and is never seen by the decisions.
- Model trained on another platform: the decision layer is platform-agnostic, and conformal intervals recalibrate on a small held-out set of real removals.
- Overconfidence near failure: per-band calibration (94% coverage in the last 20 cycles) and the abstention gate.
- Classified data: air-gapped by design. One base server, one SQLite file, open-source stack, nothing leaves the base network.
- Trust in automated advice: it ranks and prices, never authorises; every number has a trace; every plan is re-checked by the full simulator.

9. IMPACT AND BENEFITS

- Base Maintenance Officer: why availability is what it is, by cause; which depot induction to move, and when.
- Logistics Officer: which spare, stocked where, unlocks the most aircraft-days; which order to expedite.
- Engineering Officer: cannibalisation priced before it is signed; inspect or order, with the model's own uncertainty shown.
- Command: more aircraft available from the same fleet, parts and bays, by joining existing data rather than buying anything new.

10. PATH TO DEPLOYMENT

1. Data: one LRU family at one base (removals, spares lead times, stock by base, bay counts, cannibalisation logs).
2. Retrain the degradation model on real removals and recalibrate the conformal intervals.
3. Shadow mode for 90 days: officers keep deciding, FLIGHTLINE only advises.
4. Measure APH and aircraft-days against what actually happened.
5. Expand to more LRU families, then more bases and aircraft types.

11. REFERENCES

- Arias Chao M. et al. Aircraft engine run-to-failure dataset under real flight conditions for prognostics and diagnostics (N-CMAPSS). Data 6(1):5, 2021.
- Saxena A. et al. Damage propagation modeling for aircraft engine run-to-failure simulation (C-MAPSS). PHM 2008.
- Romano Y., Patterson E., Candès E. Conformalized quantile regression. NeurIPS 2019.
- Vovk V., Gammerman A., Shafer G. Algorithmic Learning in a Random World. Springer, 2005.
- US GAO. GAO-02-86, Military Aircraft: Services Need Strategies to Reduce Cannibalizations. November 2001.
- Sherbrooke C. METRIC: a multi-echelon technique for recoverable item control. Operations Research 16(1), 1968.
- Google OR-Tools (CP-SAT), scikit-learn, NetworkX.
```
