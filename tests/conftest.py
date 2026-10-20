import pytest

from flightline import config, datagen, engine


@pytest.fixture(scope="session")
def ctx():
    if not config.DB_PATH.exists():
        datagen.generate()
    engine.reset()
    return engine.context()


@pytest.fixture(scope="session")
def default_state(ctx):
    return engine.run(engine.normalise())


SCENARIOS = [
    dict(),
    dict(sortie_surge=40),
    dict(spares_delay_days=10),
    dict(ground_tails=["TAIL-01", "TAIL-03"]),
    dict(ground_tails=["TAIL-17", "TAIL-18"], spares_delay_days=20, sortie_surge=60),
]


@pytest.fixture(scope="session", params=range(len(SCENARIOS)), ids=lambda i: str(SCENARIOS[i]) or "default")
def state(request, ctx):
    return engine.run(engine.normalise(**SCENARIOS[request.param]))
