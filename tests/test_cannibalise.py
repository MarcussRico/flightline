import pytest

from flightline import config
from flightline.cannibalise import INF_DAYS, price_core


@pytest.mark.parametrize("lead", [31, 45, 60, 90])
@pytest.mark.parametrize("swap_days", [1, 2, 3])
def test_net_is_negative_when_donor_lead_time_exceeds_lookahead(lead, swap_days):
    # A flying donor robbed today waits for the spare the recipient was waiting for.
    p = price_core(spare_ready_days=lead, donor_free_days=0, swap_days=swap_days, repair_hours=6,
                   refail_delta=0.0, refail_downtime_days=lead)
    assert lead > config.CANN_LOOKAHEAD_DAYS
    assert p["net_aircraft_days"] < 0
    assert p["donor_downtime_days"] == config.CANN_LOOKAHEAD_DAYS


def test_robbing_a_hangar_queen_pays():
    p = price_core(spare_ready_days=25, donor_free_days=INF_DAYS, swap_days=1, repair_hours=6,
                   refail_delta=0.05, refail_downtime_days=30)
    assert p["donor_downtime_days"] == 0
    assert p["net_aircraft_days"] > 20


def test_no_gain_when_recipient_has_another_hole():
    p = price_core(spare_ready_days=20, donor_free_days=0, swap_days=1, repair_hours=6,
                   refail_delta=0.0, refail_downtime_days=20, recipient_other_down_days=40)
    assert p["recipient_days_gained"] == 0
    assert p["net_aircraft_days"] < 0


def test_extra_manhours_are_twice_a_normal_repair():
    p = price_core(spare_ready_days=20, donor_free_days=0, swap_days=1, repair_hours=7,
                   refail_delta=0.0, refail_downtime_days=20)
    assert p["extra_manhours"] == 14.0


def test_engine_prices_every_candidate_consistently(default_state):
    for c in default_state.cann_candidates:
        assert c["base"] == default_state.ctx.world.tail_base[c["donor"]]
        assert 0 <= c["refailure_risk_delta"] <= 1
        assert c["verdict"]
