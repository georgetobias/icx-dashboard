"""Dashboard contract checks against generated fictional ratings only."""
from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient
from backend.app import metrics, settings
from backend.app.main import app


@pytest.fixture(autouse=True)
def isolated_demo(tmp_path, monkeypatch):
    monkeypatch.setenv("ICX_APP_DATA_DIR", str(tmp_path / "cache"))
    monkeypatch.delenv("ICX_MASTER_CSV", raising=False)
    settings.set_runtime_master_csv(None)
    metrics.load_master_cached.cache_clear()
    yield
    settings.set_runtime_master_csv(None)
    metrics.load_master_cached.cache_clear()


client = TestClient(app)


@pytest.mark.parametrize("perspective", ["provider", "customer"])
def test_home_reconciles_with_active_rows(perspective):
    payload = client.get("/api/home-summary", params={"perspective": perspective}).json()
    assert payload["status"]["ok"]
    assert payload["tiles"]["total_ratings"] == 54
    assert sum(row["ratings"] for row in payload["rows"]) == 54
    assert len(payload["rows"]) == 3
    assert all(row["group_name"].startswith("Demo ") for row in payload["rows"])


@pytest.mark.parametrize("perspective", ["provider", "customer"])
@pytest.mark.parametrize("analysis", ["groups", "service_clusters", "division_only", "division_territory", "territory_only"])
def test_scatter_views_use_active_data(perspective, analysis):
    response = client.get("/api/chart/criticality-scatter", params={"perspective": perspective, "analysis": analysis, "group": "All Groups"})
    assert response.status_code == 200
    assert response.json()["kind"] == "plotly"


@pytest.mark.parametrize("view", ["frequency-heatmap", "frequency-attention", "service-cluster-scatter", "received-gave-gap", "inter-intra-gap", "blue-attention-queue"])
def test_chart_contracts(view):
    response = client.get(f"/api/chart/{view}", params={"group": "Demo Operations"})
    assert response.status_code == 200
    assert response.json()["kind"] in {"plotly", "attention-queue"}


@pytest.mark.parametrize("group", ["All Groups", "Demo Operations", "Demo Support", "Demo Technology"])
def test_profiles_do_not_return_individual_records(group):
    response = client.get(f"/api/group/{group}")
    assert response.status_code == 200
    body = json.dumps(response.json())
    assert "@example.invalid" not in body
    assert "DEMO-000" not in body
    assert "Email Address" not in body


@pytest.mark.parametrize("analysis", ["groups", "service", "division", "territory"])
def test_rating_breakdown_contracts(analysis):
    response = client.get("/api/blue-breakdown", params={"analysis": analysis, "group": "Demo Operations"})
    assert response.status_code == 200
    assert isinstance(response.json()["rows"], list)


def test_no_implicit_fixed_reference_group():
    assert "Data Group (Special)" not in client.get("/api/groups").json()["groups"]
    assert client.get("/api/data-qa").json()["status"]["ok"]
