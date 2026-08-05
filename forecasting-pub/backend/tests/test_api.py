"""End-to-end API tests against an in-memory seeded database."""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient

_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"

from app.main import app  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_and_seed(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    bus = client.get("/api/business-units").json()
    assert {b["code"] for b in bus} == {"SP", "DE"}
    sp = next(b for b in bus if b["code"] == "SP")
    assert sp["configs"][0]["levels"] == [
        {"key": "seller", "label": "Seller"},
        {"key": "account", "label": "Account"},
        {"key": "product_bucket", "label": "Product Bucket"},
    ]


def test_periods_and_dimensions(client):
    periods = client.get("/api/periods").json()
    assert [p["code"] for p in periods] == ["2026 Q1", "2026 Q2", "2026 Q3", "2026 Q4", "2027 Q1"]
    dims = client.get("/api/dimensions").json()
    assert any(d["key"] == "product_rollup" and d["derived"] for d in dims)


def _sp_config(client):
    bus = client.get("/api/business-units").json()
    sp = next(b for b in bus if b["code"] == "SP")
    return sp["configs"][0]


def _de_config(client):
    bus = client.get("/api/business-units").json()
    de = next(b for b in bus if b["code"] == "DE")
    return de["configs"][0]


def test_grid_math(client):
    cfg = _sp_config(client)
    grid = client.get(
        "/api/forecast/grid", params={"config_id": cfg["id"], "periods": ["2026 Q3"]}
    ).json()
    rows = grid["rows"]
    assert rows, "grid should have rows"
    for r in rows:
        assert r["suggested_all_bfo"] == pytest.approx(r["actuals"] + r["pipeline_open"], abs=0.05)
        assert r["suggested_buildup"] == pytest.approx(r["actuals"] + r["pipeline_weighted"], abs=0.05)
        assert r["pipeline_weighted"] <= r["pipeline_open"] + 0.01
    # seeded entry with adjustment shows through
    adj_row = next(
        r
        for r in rows
        if r["slice_values"]
        == {"seller": "Adam Roberts", "account": "Switch Communications", "product_bucket": "3ph"}
    )
    assert adj_row["adjustment"] == -1_250_000.0
    assert adj_row["effective_total"] == pytest.approx(adj_row["suggested_buildup"] - 1_250_000.0, abs=0.05)


def test_grid_future_period_has_rows(client):
    cfg = _sp_config(client)
    grid = client.get(
        "/api/forecast/grid", params={"config_id": cfg["id"], "periods": ["2027 Q1"]}
    ).json()
    assert grid["rows"], "future quarters must be enterable"


def test_rollup_dimension(client):
    cfg = _de_config(client)
    grid = client.get(
        "/api/forecast/grid", params={"config_id": cfg["id"], "periods": ["2026 Q3"]}
    ).json()
    groups = {r["slice_values"]["product_rollup"] for r in grid["rows"]}
    assert groups <= {"Grid Hardware", "Digital Grid", "Services", "Other"}
    assert "Grid Hardware" in groups


def test_entry_upsert_and_audit(client):
    cfg = _sp_config(client)
    slice_values = {"seller": "Maria Chen", "account": "Equinix", "product_bucket": "Software"}

    r = client.put(
        f"/api/forecast/configs/{cfg['id']}/entries",
        json={
            "period_code": "2026 Q3",
            "slice_values": slice_values,
            "adjustment": 500000,
            "set_fields": ["adjustment"],
        },
        headers={"X-User": "maria.chen"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["adjustment"] == 500000

    # explicit total overrides and clears adjustment (last-edited wins)
    r = client.put(
        f"/api/forecast/configs/{cfg['id']}/entries",
        json={
            "period_code": "2026 Q3",
            "slice_values": slice_values,
            "total_forecast": 2000000,
            "set_fields": ["total_forecast"],
        },
        headers={"X-User": "maria.chen"},
    )
    assert r.json()["total_forecast"] == 2000000
    assert r.json()["adjustment"] is None

    audit = client.get(
        f"/api/forecast/configs/{cfg['id']}/audit", params={"period_code": "2026 Q3"}
    ).json()
    fields = [(a["field"], a["new_value"]) for a in audit if a["changed_by"] == "maria.chen"]
    assert ("adjustment", "500000.0") in fields
    assert ("total_forecast", "2000000.0") in fields

    grid = client.get(
        "/api/forecast/grid", params={"config_id": cfg["id"], "periods": ["2026 Q3"]}
    ).json()
    row = next(r for r in grid["rows"] if r["slice_values"] == slice_values)
    assert row["effective_total"] == 2000000
    assert row["effective_adjustment"] == pytest.approx(2000000 - row["suggested_buildup"], abs=0.05)


def test_onboard_new_bu(client):
    r = client.post(
        "/api/business-units",
        json={"code": "IND", "name": "Industry", "description": "Industrial automation"},
    )
    assert r.status_code == 201
    bu_id = r.json()["id"]

    r = client.post(
        f"/api/business-units/{bu_id}/configs",
        json={
            "name": "OEM",
            "levels": [
                {"key": "manager", "label": "Manager"},
                {"key": "account_segment", "label": "Segment"},
            ],
            "metric_rules": {"default": "sales", "overrides": []},
            "pipeline_weighting": {"mode": "flat", "rate": 0.3},
        },
    )
    assert r.status_code == 201, r.text
    cfg_id = r.json()["id"]

    grid = client.get(
        "/api/forecast/grid", params={"config_id": cfg_id, "periods": ["2026 Q3"]}
    )
    assert grid.status_code == 200


def test_config_validation(client):
    bus = client.get("/api/business-units").json()
    bu_id = bus[0]["id"]
    r = client.post(
        f"/api/business-units/{bu_id}/configs",
        json={"name": "bad", "levels": [{"key": "nonsense", "label": "X"}]},
    )
    assert r.status_code == 422
    r = client.post(
        f"/api/business-units/{bu_id}/configs",
        json={"name": "bad2", "levels": [{"key": "product_rollup", "label": "X"}]},
    )
    assert r.status_code == 422  # rollup level without bucket_rollups
