"""Cannibalisation, priced rather than banned.

Cannibalisation moves a serviceable part from a donor airframe to a recipient
that is waiting for it. It does not create a part: the hole moves to the
donor, which then waits for the spare the recipient was waiting for. So the
trade is worth it only when the donor was going to be on the ground anyway
(consolidating two holes into one "hangar queen"), and it always costs labour
and some risk on the moved component.

Units: days, aircraft-days, man-hours. The lookahead is 30 days.
"""

from __future__ import annotations

import math

from . import config

INF_DAYS = 10_000.0


def refailure_delta(point_cycles: float, lo_cycles: float, hi_cycles: float, cycles_per_day: float,
                    lookahead_days: float, penalty: float = config.HANDLING_LIFE_PENALTY) -> float:
    """Extra probability that the moved component fails inside the lookahead because it was moved.

    The component's remaining life in days is treated as normal with mean at the
    point estimate and a sd implied by its 90% interval (half-width / 1.645).
    Moving it scales remaining life by (1 - penalty) -- a modelled assumption.
    Returns P(fail | moved) - P(fail | left in place), in [0, 1].
    """
    u = max(cycles_per_day, 1e-6)
    mu = point_cycles / u
    sd = max(hi_cycles - lo_cycles, 0.0) / (2 * 1.645) / u

    def p_fail_within(h: float) -> float:
        if sd < 1e-9:
            return 1.0 if mu < h else 0.0
        return 0.5 * (1 + math.erf((h - mu) / (sd * math.sqrt(2))))

    moved = p_fail_within(lookahead_days / (1 - penalty))
    stays = p_fail_within(lookahead_days)
    return max(0.0, moved - stays)


def price_core(*, spare_ready_days: float, donor_free_days: float, swap_days: int, repair_hours: float,
               refail_delta: float, refail_downtime_days: float, recipient_other_down_days: float = 0.0,
               lookahead_days: float = config.CANN_LOOKAHEAD_DAYS) -> dict:
    """Net aircraft-days of one cannibalisation over the lookahead.

    spare_ready_days: days until the recipient's awaited spare arrives and is
        installed -- when it would fly without the swap.
    recipient_other_down_days: days the recipient stays down for *other*
        reasons (a second missing part, a bay slot). A swap cannot fly an
        aircraft that has another hole.
    donor_free_days: days until the donor would fly anyway (0 if flying today;
        INF if grounded beyond the lookahead).
    swap_days: elapsed days of the swap job -- twice a normal repair.
    refail_delta / refail_downtime_days: extra failure probability on the moved
        part and the downtime a failure would cause (spare lead + install), so
        their product is the expected aircraft-days lost to re-failure.
    """
    H = float(lookahead_days)
    rec_without = max(spare_ready_days, recipient_other_down_days)
    rec_with = max(float(swap_days), recipient_other_down_days)
    recipient_gain = min(rec_without, H) - min(rec_with, H)
    # The donor inherits the recipient's place in the spares queue, so it flies
    # again when that spare is fitted -- or later, if it was down longer.
    donor_back_with = max(donor_free_days, spare_ready_days)
    donor_downtime = max(0.0, min(donor_back_with, H) - min(donor_free_days, H))
    refail_cost = refail_delta * min(refail_downtime_days, H)
    net = recipient_gain - donor_downtime - refail_cost
    return {
        "aircraft_gained_now": 1 if recipient_other_down_days <= swap_days else 0,
        # +1 aircraft-day on the next flying day when the swap fits in one day
        # and nothing else holds the recipient down.
        "aircraft_days_gained_now": 1.0 if swap_days <= 1 and recipient_other_down_days <= 1 else 0.0,
        "swap_days": int(swap_days),
        "recipient_days_gained": round(recipient_gain, 2),
        "donor_downtime_days": round(donor_downtime, 2),
        # 2x normal repair: the swap (removal + installation, 2x) plus the
        # donor's own installation when its spare arrives (1x), versus the 1x
        # the recipient needed anyway.
        "extra_manhours": round(config.CANN_LABOUR_MULTIPLIER * repair_hours, 1),
        "refailure_risk_delta": round(refail_delta, 4),
        "refailure_expected_days": round(refail_cost, 2),
        "net_aircraft_days": round(net, 2),
        "lookahead_days": int(H),
    }


def verdict(p: dict, donor: str, recipient: str, donor_free_days: float, spare_ready_days: float) -> str:
    """One-sentence recommendation for a priced cannibalisation."""
    H = p["lookahead_days"]
    net = p["net_aircraft_days"]
    if net > 0.5:
        why = "is grounded beyond the lookahead" if donor_free_days >= H else f"is down for {donor_free_days:.0f} more days anyway"
        return (f"Cannibalise: {donor} {why}, so the swap consolidates two holes into one "
                f"and nets {net:+.1f} aircraft-days over {H} days.")
    if donor_free_days <= 0:
        return (f"Do not cannibalise unless tomorrow's sortie is mission-critical: it moves the hole to "
                f"{donor} for {p['donor_downtime_days']:.0f} days and nets {net:+.1f} aircraft-days over {H}.")
    if p["recipient_days_gained"] <= 0:
        return (f"Do not cannibalise: {recipient} has another reason to stay on the ground, so the swap "
                f"gains nothing and costs {p['donor_downtime_days']:.0f} donor days.")
    return (f"Marginal: {recipient} flies in {p['swap_days']} day(s) instead of {min(spare_ready_days, H):.0f}, "
            f"but {donor} loses {p['donor_downtime_days']:.0f} days; net {net:+.1f} aircraft-days over {H}. "
            f"Only if the sortie is mission-critical.")


def price_cannibalisation(donor_tail: str, recipient_tail: str, part: str, *, engine_state=None) -> dict:
    """Price moving `part` from donor to recipient, against the current projection.

    Returns aircraft_days_gained_now, donor_downtime_days, extra_manhours,
    refailure_risk_delta, net_aircraft_days (30-day lookahead) and a verdict.
    `engine_state` is the scenario result from engine.run(); defaults to the
    engine's current scenario.
    """
    if engine_state is None:
        from . import engine
        engine_state = engine.current()
    return engine_state.price_cannibalisation(donor_tail, recipient_tail, part)
