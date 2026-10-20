"""Actionable Prognostic Horizon, and why it beats RMSE as the thing to optimise.

    APH = P( t_warning <= t_failure - decision_window )

A warning is actionable only if it arrives early enough to get the spare,
the bay and the crew in place before the part fails.

Two real models are compared on the same held-out run-to-failure units:

  short-horizon  trained on RUL capped at CAP_CYCLES -- the piecewise-linear
                 target used across the C-MAPSS literature. Its RMSE, measured
                 against that capped target as the papers do, looks excellent.
                 But it cannot see further than the cap, so it cannot warn
                 earlier than the cap.
  FLIGHTLINE     uncapped target, conformal 90% interval, warns when the
                 interval's lower edge enters the decision window. Worse RMSE.

Then both drive pre-emptive spares orders in a ground-truth backtest of the
fleet, and the outcome is counted in sortie-days.

Units: cycles for RUL and RMSE; days for windows and lead; sortie-days and
aircraft-days for outcomes.
"""

from __future__ import annotations

import json
import time

import numpy as np

from . import config
from .data import DegradationSet, Unit, World

CAP_CYCLES = 15.0
FINE_TUNE_SIZES = (12, 24, 48, 96, 144)


def _windows(world: World) -> dict[str, float]:
    """Decision window per part with no scenario delay and an empty depot queue (days)."""
    return {p: float(part.lead_time_days + part.repair_days) for p, part in world.parts.items()}


def _nominal_util(world: World) -> float:
    from .availability import Scenario, utilisation

    u = utilisation(world, Scenario())
    return float(np.mean(list(u.values())))


def warning_cycle(model, unit: Unit, start: int, window_days: float, util: float, rule: str) -> int | None:
    """First observed cycle at which the model would raise a warning, or None.

    rule "interval": lower edge of the conformal interval <= window.
    rule "capped":   point <= min(window, cap - 1) -- a capped model's
                     predictions carry no information above its cap.
    """
    life = len(unit.sensors)
    cuts = np.arange(max(start, 1), life + 1)
    if len(cuts) == 0:
        return None
    p, lo, _ = model.predict_rows(model.features(unit, cuts))
    w_cycles = window_days * util
    if rule == "interval":
        hit = lo <= w_cycles
    else:
        hit = p <= min(w_cycles, model.cap - 1.0)
    idx = np.flatnonzero(hit)
    return int(cuts[idx[0]]) if len(idx) else None


def aph(model, units: list[Unit], windows: dict[str, float], util: float, rule: str) -> dict:
    """APH on run-to-failure units, plus aircraft-days lost to late warnings."""
    actionable, leads, lost, ratio = [], [], [], []
    for u in units:
        w = windows[u.part_number]
        c = warning_cycle(model, u, 3, w, util, rule)
        lead_days = 0.0 if c is None else (u.life_cycles - c) / util
        actionable.append(lead_days >= w)
        leads.append(lead_days)
        lost.append(max(0.0, w - lead_days))
        ratio.append(lead_days / w)
    return {
        "aph": float(np.mean(actionable)),
        "mean_warning_lead_days": float(np.mean(leads)),
        # How early, relative to the window: 1.0 is just in time; above it is
        # spares held on the shelf for longer than strictly needed.
        "median_lead_over_window": float(np.median(ratio)),
        "aircraft_days_lost_per_100_failures": float(100 * np.mean(lost)),
        "n_failures": len(units),
    }


def rmse_report(model, deg: DegradationSet) -> dict:
    """RMSE in cycles: against the model's own target, and on the last CAP_CYCLES where every target agrees."""
    X, y, _ = model.eval_rows(deg.split("test"), tag=13)
    p, _, _ = model.predict_rows(X)
    own_y = np.minimum(y, model.cap) if model.cap is not None else y
    near = y <= CAP_CYCLES
    return {
        "rmse_cycles": float(np.sqrt(np.mean((p - own_y) ** 2))),
        "rmse_target": f"RUL capped at {model.cap:g} cycles" if model.cap is not None else "true RUL (uncapped)",
        "rmse_last_cycles": float(np.sqrt(np.mean((p[near] - y[near]) ** 2))),
    }


def fleet_backtest(world: World, deg: DegradationSet, models: dict, windows: dict[str, float]) -> dict:
    """Sortie-days delivered under ground truth when each model's warnings trigger spares orders.

    Same fleet, same current-practice maintenance plan, true failure times.
    Only the moment each replacement is ordered differs.
    """
    from .availability import Plan, Scenario, fresh_life_truth, simulate, utilisation
    from .scheduler import schedule_greedy

    sc = Scenario()
    util = utilisation(world, sc)
    greedy = schedule_greedy(world, sc)
    remaining = dict(deg.installed_truth_remaining)
    serviceable = {k: v for k, v in remaining.items() if not world.lrus[k].failed}
    out = {}
    policies = {"none": None, **models}
    for name, entry in policies.items():
        pre = {}
        if entry is not None:
            model, rule = entry
            for key, full in deg.installed_full.items():
                if key not in serviceable:
                    continue
                age = deg.installed_age[key]
                c = warning_cycle(model, full, age, windows[key[1]], util[world.tail_base[key[0]]], rule)
                if c is not None:
                    pre[key] = float(c - age)
        res = simulate(world, sc, Plan(f"backtest-{name}", greedy, "reactive", preorder_at_cycles=pre),
                       serviceable, fresh_life_truth(world))
        s = res.summary()
        out[name] = {"sortie_days_delivered": s["sortie_days_delivered"], "sortie_days_lost": s["sortie_days_lost"],
                     "aircraft_days_available": s["aircraft_days_available"], "ao": s["ao"],
                     "preorders": len(pre)}
    return out


def compute(world: World, deg: DegradationSet, model) -> dict:
    """The full APH-vs-RMSE comparison, fleet backtest and fine-tuning curve."""
    from .prognosis import Prognosis

    t0 = time.perf_counter()
    windows = _windows(world)
    util = _nominal_util(world)
    test = deg.split("test")
    short = Prognosis(list(world.parts), seed=config.SEED).fit(deg, cap=CAP_CYCLES)
    ours = {"name": "FLIGHTLINE (uncapped, conformal)", **rmse_report(model, deg),
            **aph(model, test, windows, util, "interval"),
            "warns_up_to_days": None}
    shortm = {"name": f"Short-horizon (RUL capped at {CAP_CYCLES:g})", **rmse_report(short, deg),
              **aph(short, test, windows, util, "capped"),
              "warns_up_to_days": float((CAP_CYCLES - 1) / util)}
    backtest = None
    if deg.installed_full:
        backtest = fleet_backtest(world, deg, {"short_horizon": (short, "capped"), "flightline": (model, "interval")},
                                  windows)
    # Fine-tuning curve: APH as a function of how many labelled run-to-failure
    # events the model was trained on (subsampled, calibration set fixed).
    train = sorted(deg.split("train"), key=lambda u: u.unit_id)
    rng = np.random.default_rng([config.SEED, 21])
    order = [train[i] for i in rng.permutation(len(train))]
    curve = []
    for n in [s for s in FINE_TUNE_SIZES if s < len(train)] + [len(train)]:
        sub = order[:n]
        if len({u.part_number for u in sub}) < len(world.parts):
            continue
        m = Prognosis(list(world.parts), seed=config.SEED).fit(deg, train_units=sub)
        a = aph(m, test, windows, util, "interval")
        ev = m.evaluate(deg)
        curve.append({"labelled_failures": n, "aph": a["aph"], "median_lead_over_window": a["median_lead_over_window"],
                      "coverage": ev["coverage"], "mean_width_cycles": ev["mean_width_cycles"]})
    per_part = {}
    for p in world.parts:
        units = [u for u in test if u.part_number == p]
        per_part[p] = {"window_days": windows[p],
                       "flightline": aph(model, units, windows, util, "interval")["aph"],
                       "short_horizon": aph(short, units, windows, util, "capped")["aph"]}
    return {
        "nominal_cycles_per_day": util,
        "cap_cycles": CAP_CYCLES,
        "models": {"flightline": ours, "short_horizon": shortm},
        "per_part": per_part,
        "backtest": backtest,
        "fine_tuning": curve,
        "source": deg.source,
        "compute_seconds": time.perf_counter() - t0,
    }


def _path():
    return config.MODEL_DIR / "metrics.json"


def save(m: dict, fp: str) -> None:
    config.MODEL_DIR.mkdir(parents=True, exist_ok=True)
    _path().write_text(json.dumps({"fingerprint": fp, "metrics": m}, indent=1))


def load_cached(deg: DegradationSet) -> dict | None:
    """Metrics computed at seed time, if they match the current data."""
    from .prognosis import fingerprint

    p = _path()
    if not p.exists():
        return None
    try:
        blob = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return blob["metrics"] if blob.get("fingerprint") == fingerprint(deg) else None
