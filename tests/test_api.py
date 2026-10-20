from fastapi.testclient import TestClient

from flightline.api import app


def test_endpoints():
    with TestClient(app) as c:
        s = c.get("/api/state").json()
        assert s["provenance"]["badge"] == "SYNTHETIC SCENARIO"
        assert c.get("/").status_code == 200
        assert c.get("/static/vendor/chart.umd.min.js").status_code == 200
        r = c.post("/api/scenario", json={"ground_tails": ["TAIL-04"], "spares_delay_days": 5, "sortie_surge": 20})
        assert r.status_code == 200
        body = r.json()
        assert body["scenario"] == {"ground_tails": ["TAIL-04"], "spares_delay_days": 5, "sortie_surge": 20}
        acts = c.get("/api/actions").json()["actions"]
        assert acts and all("aircraft_days_gained" in a and a["reason"] for a in acts)
        why = c.get(f"/api/why/{acts[0]['id']}").json()
        assert why["trace"]
        assert c.get("/api/why/nope").status_code == 404
        bad = c.post("/api/cannibalise", json={"donor": "TAIL-01", "recipient": "TAIL-02", "part": "PN-NOPE"})
        assert bad.status_code == 422
        assert c.post("/api/scenario", json={"spares_delay_days": -3}).status_code == 422
        c.post("/api/scenario", json={})
