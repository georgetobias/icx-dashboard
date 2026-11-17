"""Release checks use isolated data folders; never alter the user's active CSV."""
from __future__ import annotations

import io
from pathlib import Path
import pytest
import pandas as pd
from fastapi.testclient import TestClient

from backend.app import metrics, settings
from backend.app.main import app
from backend.app.lifecycle import BrowserSessions

client = TestClient(app)


@pytest.fixture
def isolated_source(tmp_path, monkeypatch):
    monkeypatch.setenv("ICX_APP_DATA_DIR", str(tmp_path / "user-data"))
    settings.set_runtime_master_csv(None)
    metrics.load_master_cached.cache_clear()
    frame = pd.read_csv(settings.default_master_csv_path(), dtype={"Employee ID": "string"})
    yield frame
    settings.set_runtime_master_csv(None)
    metrics.load_master_cached.cache_clear()


def upload(frame):
    return client.post("/api/app-settings/csv-source/upload", content=frame.to_csv(index=False).encode("utf-8-sig"), headers={"X-Filename": "updated-master.csv"})


def test_updated_master_changes_every_real_view_and_survives_restart(isolated_source, monkeypatch):
    frame = isolated_source.iloc[:12].copy()
    frame["Rating"] = "BUSTED"
    frame["Group"] = "QA Customer"
    frame["Group Rated"] = "QA Provider"
    frame["Employee ID"] = [f"QA-{i:03}" for i in range(12)]
    frame["Email Address"] = [f"qa-{i}@example.invalid" for i in range(12)]
    frame["Band"] = "Band Z"
    frame["Service"] = "QA Service"
    frame["Division Rated"] = "QA Division serving Territory 1"
    frame.loc[frame.index[:6], "Division Rated"] = "QA Division"
    frame["Territory"] = "QA Territory"
    frame["Territory Grouping"] = "QA Territory"
    frame["Criticality Score"] = 4
    # A configured old source must not override an explicit uploaded master.
    monkeypatch.setenv("ICX_MASTER_CSV", str(settings.default_master_csv_path()))
    before_revision = metrics.source_revision()
    assert upload(frame).status_code == 200
    assert metrics.source_revision() != before_revision
    assert metrics.source_path() == settings.persisted_master_csv_path()
    status = client.get("/api/status").json()
    assert status["ok"] and status["source_rows"] == 12 and status["overall_nps"] == -100
    assert status["baseline_matches"]
    assert client.get("/api/home-summary").json()["tiles"]["total_ratings"] == 12
    assert "QA Provider" in client.get("/api/groups").json()["groups"]
    assert "QA Customer" in client.get("/api/groups?perspective=customer").json()["groups"]
    profile = client.get("/api/group/QA Customer").json()
    band = next(chart for chart in profile["demographics"] if chart["key"] == "band")
    assert band["total"] == 12 and band["rows"] == [{"label": "Band Z", "count": 12, "pct": 100.0}]
    for analysis in ["groups", "service_clusters", "division_only", "territory_only", "division_territory"]:
        summary = metrics.summary_for_analysis("provider", analysis, "All Groups", min_ratings=1, include_low_info=True)
        assert not summary.empty, analysis
        assert set(summary["nps"]) == {-100.0}, analysis
    for view in ["criticality-scatter", "frequency-heatmap", "frequency-attention", "received-gave-gap", "inter-intra-gap", "blue-attention-queue"]:
        response = client.get(f"/api/chart/{view}", params={"group": "QA Provider", "analysis": "service_clusters", "min_ratings": 1})
        assert response.status_code == 200, (view, response.text[:200])
    assert client.get("/api/data-qa").json()["status"]["ok"]
    for analysis in ["service", "division", "territory"]:
        response = client.get("/api/blue-breakdown", params={"analysis": analysis, "group": "QA Provider"})
        assert response.status_code == 200
        assert all(row["nps"] == -100 for row in response.json()["rows"])
    settings.set_runtime_master_csv(None)
    metrics.load_master_cached.cache_clear()
    assert metrics.load_master()["blue_rating"].eq("Busted").all()
    assert client.post("/api/app-settings/csv-source", json={"path": None}).status_code == 200
    assert metrics.source_path() == settings.default_master_csv_path()


@pytest.mark.parametrize("invalid", ["empty", "rating", "criticality", "group", "identity", "duplicate", "malformed", "missing"])
def test_invalid_import_preserves_previous_source(isolated_source, invalid):
    frame = isolated_source.iloc[:5].copy()
    assert upload(frame).status_code == 200
    saved = settings.persisted_master_csv_path().read_bytes()
    candidate = frame.copy()
    if invalid == "empty": candidate = candidate.iloc[:0]
    if invalid == "rating": candidate.loc[candidate.index[0], "Rating"] = "not a BLUE rating"
    if invalid == "criticality": candidate.loc[candidate.index[0], "Criticality Score"] = 99
    if invalid == "group": candidate.loc[candidate.index[0], "Group"] = " "
    if invalid == "identity": candidate.loc[candidate.index[0], ["Employee ID", "Email Address"]] = None
    if invalid == "duplicate": candidate["Service Cluster"] = candidate["Service"]
    if invalid == "missing": candidate = candidate.drop(columns="Age Range")
    if invalid == "malformed":
        response = client.post("/api/app-settings/csv-source/upload", content=b'bad,"unterminated', headers={"X-Filename": "broken.csv"})
    else:
        response = upload(candidate)
    assert response.status_code == 400, invalid
    assert settings.persisted_master_csv_path().read_bytes() == saved


def test_normalized_headers_aliases_extra_columns_and_leading_zero_ids(isolated_source):
    frame = isolated_source.iloc[:2].copy()
    frame["Employee ID"] = ["001", "01"]
    frame = frame.rename(columns={"Service": "Service Cluster"})
    frame["Future reporting field"] = "ignored"
    frame.columns = [f" {col.lower()} " for col in frame.columns]
    assert upload(frame).status_code == 200
    assert list(metrics.load_master()["Employee ID"]) == ["001", "01"]


def test_rapid_replacement_changes_cache(isolated_source):
    frame = isolated_source.iloc[:3].copy()
    frame["Rating"] = "BUSTED"
    assert upload(frame).status_code == 200
    assert metrics.data_status()["overall_nps"] == -100
    frame["Rating"] = "EXCEPTIONAL"
    assert upload(frame).status_code == 200
    assert metrics.data_status()["overall_nps"] == 100


@pytest.mark.parametrize("missing", ["Email Address", "Employee ID"])
def test_either_identity_column_supports_demographics(isolated_source, missing):
    frame = isolated_source.iloc[:3].drop(columns=missing)
    assert upload(frame).status_code == 200
    assert client.get("/api/group/All Groups").status_code == 200


def test_conflicting_demographics_rejected(isolated_source):
    frame = pd.concat([isolated_source.iloc[:1]] * 2, ignore_index=True)
    frame.loc[1, "Band"] = "Conflicting Band"
    assert upload(frame).status_code == 400


def test_lifecycle_refresh_multiple_tabs_and_reopen(monkeypatch):
    now = [0.0]
    monkeypatch.setattr("backend.app.lifecycle.time.monotonic", lambda: now[0])
    manager = BrowserSessions()
    manager.start(grace=8)
    manager.connect("first")
    manager.connect("second")
    manager.disconnect("first")
    now[0] = 1000
    assert not manager.expired()
    manager.disconnect("second")
    now[0] += 7
    assert not manager.expired()
    manager.connect("refreshed")
    now[0] += 1000
    assert not manager.expired()
    manager.disconnect("refreshed")
    now[0] += 9
    assert manager.expired()
    manager.reopening()
    assert not manager.expired()


def test_unknown_api_and_websocket_origin():
    assert client.get("/api/not-a-real-endpoint").status_code == 404
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/session", headers={"Origin": "https://example.invalid"}):
            pass
    with client.websocket_connect("/api/session") as socket:
        socket.send_text("connected")
