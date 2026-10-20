def test_spare_unlock_ranking_is_sorted_and_monotone(default_state):
    twin = default_state.twin
    ranking = twin.spare_unlock_ranking()
    assert len(ranking) == len(default_state.ctx.world.parts) * len(default_state.ctx.world.bases)
    keys = [(r["sortie_days_unlocked"], r["aircraft_days_unlocked"]) for r in ranking]
    assert keys == sorted(keys, reverse=True)
    for r in ranking:
        prev = {"sortie_days": 0, "aircraft_days": 0}
        for extra in (1, 2, 3):
            g = twin.spare_unlock(r["base"], r["part"], extra=extra)
            assert g["sortie_days"] >= prev["sortie_days"]
            assert g["aircraft_days"] >= prev["aircraft_days"]
            prev = g


def test_ranking_finds_something_worth_stocking(default_state):
    assert default_state.twin.spare_unlock_ranking()[0]["aircraft_days_unlocked"] > 0


def test_graph_joins_all_four_silos(default_state):
    s = default_state.twin.summary()
    for kind in ("tail", "lru", "part_number", "stock_location", "depot", "bay", "sortie_plan"):
        assert s["nodes"].get(kind, 0) > 0, kind
    for rel in ("installed", "instance_of", "stocked_at", "repaired_by", "inspection_due", "returns_to", "tasked_at"):
        assert s["edges"].get(rel, 0) > 0, rel


def test_criticality_is_bounded_by_the_horizon(default_state):
    for t in default_state.ctx.world.tails:
        assert 0 <= default_state.twin.criticality(t) <= default_state.ctx.world.horizon
