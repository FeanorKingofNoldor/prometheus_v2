"""Basic integration tests for Prometheus monitoring/UI endpoints.

These tests exercise a subset of the FastAPI app used by the C2 UI to
ensure responses are structurally compatible with the Godot panels.

They are intentionally light and work against the mock/template
implementations without requiring a fully populated database.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from prometheus.monitoring.app import app


client = TestClient(app)


def test_status_overview_basic_shape() -> None:
    response = client.get("/api/status/overview")
    assert response.status_code == 200
    data = response.json()
    # Required top-level keys used by OverviewPanel.
    for key in [
        "pnl_today",
        "pnl_mtd",
        "pnl_ytd",
        "max_drawdown",
        "net_exposure",
        "gross_exposure",
        "leverage",
        "global_stability_index",
        "regimes",
        "alerts",
    ]:
        assert key in data


def test_status_pipeline_shape() -> None:
    response = client.get("/api/status/pipeline", params={"market_id": "US_EQ"})
    assert response.status_code == 200
    data = response.json()
    assert data.get("market_id") == "US_EQ"
    assert "market_state" in data
    assert isinstance(data.get("jobs", []), list)


def test_regime_and_stability_shape() -> None:
    r = client.get("/api/status/regime", params={"region": "US"})
    s = client.get("/api/status/stability", params={"region": "US"})
    assert r.status_code == 200
    assert s.status_code == 200
    regime = r.json()
    stab = s.json()
    for key in ["region", "current_regime", "confidence", "history"]:
        assert key in regime
    for key in [
        "region",
        "current_index",
        "liquidity_component",
        "volatility_component",
        "contagion_component",
        "history",
    ]:
        assert key in stab


def test_fragility_shape() -> None:
    response = client.get(
        "/api/status/fragility",
        params={"region": "GLOBAL", "entity_type": "ANY"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "entities" in data
    assert isinstance(data["entities"], list)


def test_meta_and_geo_basic_shape() -> None:
    meta_resp = client.get("/api/meta/configs")
    geo_resp = client.get("/api/geo/countries")
    assert meta_resp.status_code == 200
    assert geo_resp.status_code == 200
    # We only assert that responses are JSON arrays/objects; concrete
    # fields may evolve as specs are refined.
    assert meta_resp.json() is not None
    assert geo_resp.json() is not None
