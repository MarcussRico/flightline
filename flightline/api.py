"""HTTP API and the dashboard.

    uvicorn flightline.api:app --reload      ->  http://127.0.0.1:8000
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import config, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine.current()  # load the model and solve the default scenario before the first request
    yield


app = FastAPI(title="FLIGHTLINE", version="1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=config.STATIC_DIR), name="static")


class ScenarioIn(BaseModel):
    ground_tails: list[str] = Field(default_factory=list, description="Tails grounded for the whole horizon")
    spares_delay_days: int = Field(0, ge=0, le=60, description="Days added to every surface spares delivery")
    sortie_surge: int = Field(0, ge=0, le=100, description="% more aircraft tasked over the next 14 days")


class CannIn(BaseModel):
    donor: str
    recipient: str
    part: str


def _payload(st: engine.ScenarioState, started: float) -> dict:
    out = st.state_json()
    out["actions"] = [{k: v for k, v in a.items() if k != "trace"} for a in st.actions]
    out["response_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return out


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(config.STATIC_DIR / "index.html")


@app.get("/api/state")
def state():
    """Fleet status, Ao for current practice and the plan, attribution, prognosis, spares, depot."""
    t0 = time.perf_counter()
    return _payload(engine.current(), t0)


@app.get("/api/actions")
def actions():
    """Ranked recommendations, each with aircraft_days_gained and a plain-English reason."""
    st = engine.current()
    return {"scenario": engine._scenario_json(st.scenario),
            "actions": [{k: v for k, v in a.items() if k != "trace"} for a in st.actions]}


@app.post("/api/scenario")
def scenario(body: ScenarioIn):
    """Re-run everything for {ground_tails, spares_delay_days, sortie_surge} and return the new state."""
    t0 = time.perf_counter()
    sc = engine.normalise(body.ground_tails, body.spares_delay_days, body.sortie_surge)
    return _payload(engine.run(sc), t0)


@app.get("/api/why/{action_id}")
def why(action_id: str):
    """The causal trace behind one recommendation: which silo said what, and how it was valued."""
    st = engine.current()
    for a in st.actions:
        if a["id"] == action_id:
            return a
    raise HTTPException(404, f"no action {action_id} in the current scenario")


@app.post("/api/cannibalise")
def cannibalise(body: CannIn):
    """Price one cannibalisation against the current scenario."""
    out = engine.current().price_cannibalisation(body.donor, body.recipient, body.part)
    if "error" in out:
        raise HTTPException(422, out["error"])
    return out


@app.get("/api/predict/{tail}/{part}")
def predict(tail: str, part: str):
    """RUL interval (days and cycles) and the abstention decision for one installed LRU."""
    out = engine.current().predict(tail, part)
    if "error" in out:
        raise HTTPException(404, out["error"])
    return out


@app.get("/api/health")
def health():
    ctx = engine.context()
    return {"ok": True, "provenance": ctx.provenance, "model_cached": ctx.model_cached,
            "load_seconds": round(ctx.load_seconds, 2)}
