"""Generate the scenario, train and cache the model, compute the metrics.

    python -m flightline.seed [--seed N]
"""

from __future__ import annotations

import argparse
import time

from . import config, datagen, engine, metrics
from .data import connect, load_degradation, load_world
from .ncmapss import load_if_present
from .prognosis import fingerprint, load_or_train


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=config.SEED)
    args = ap.parse_args(argv)
    t0 = time.perf_counter()

    counts = datagen.generate(seed=args.seed)
    print(f"[1/4] scenario written to {config.DB_PATH.relative_to(config.ROOT)} (seed {args.seed})")
    print("      " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))

    con = connect()
    world = load_world(con)
    deg = load_degradation(con)
    con.close()
    deg = load_if_present(deg) or deg
    model, cached = load_or_train(deg, list(world.parts))
    ev = model.evaluate(deg)
    print(f"[2/4] degradation model ({deg.source}) {'loaded from cache' if cached else 'trained and cached'}")
    print(f"      90% interval coverage on {ev['n_test_points']} held-out points: {ev['coverage']:.1%}; "
          f"RMSE {ev['rmse_cycles']:.1f} cycles")

    m = metrics.compute(world, deg, model)
    metrics.save(m, fingerprint(deg))
    f, s = m["models"]["flightline"], m["models"]["short_horizon"]
    print(f"[3/4] APH  FLIGHTLINE {f['aph']:.0%} (RMSE {f['rmse_cycles']:.1f})  vs  "
          f"short-horizon {s['aph']:.0%} (RMSE {s['rmse_cycles']:.1f}, capped target)")
    if m["backtest"]:
        bt = m["backtest"]
        print("      backtest sortie-days lost: " + ", ".join(f"{k} {v['sortie_days_lost']}" for k, v in bt.items()))

    engine.reset()
    st = engine.run(engine.normalise())
    b, p = st.baseline.summary(), st.plan.summary()
    print(f"[4/4] Ao current practice {b['ao']:.1%} -> FLIGHTLINE plan {p['ao']:.1%} "
          f"({p['aircraft_days_available'] - b['aircraft_days_available']:+d} aircraft-days, "
          f"{p['sortie_days_delivered'] - b['sortie_days_delivered']:+d} sortie-days); "
          f"scenario solved in {st.timings['total'] * 1000:.0f} ms")
    print("      spare unlock ranking (one more unit on the shelf today):")
    for r in st.twin.spare_unlock_ranking()[:6]:
        print(f"        {r['part']:<12} at {r['base']}: {r['sortie_days_unlocked']:+3d} sortie-days, "
              f"{r['aircraft_days_unlocked']:+3d} aircraft-days  (on hand {r['on_hand']}, lead {r['lead_time_days']} d)")
    print(f"done in {time.perf_counter() - t0:.1f} s. Next: uvicorn flightline.api:app --reload")


if __name__ == "__main__":
    main()
