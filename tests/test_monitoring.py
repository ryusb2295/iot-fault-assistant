from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.db import Repository, utc_iso
from backend.main import create_app


def test_stopped_worker_does_not_reuse_saved_normal(tmp_path):
    repo = Repository(tmp_path / "practice.sqlite3")
    repo.update_device("RPI-01", "NORMAL", utc_iso())
    repo.update_worker_runtime(True, datetime.now(timezone.utc) - timedelta(seconds=30))
    client = TestClient(create_app(repo))
    health = client.get("/api/health").json()
    assert health["worker"] == "stopped"
    assert health["broker"] == "unknown"
    assert health["deviceHeartbeat"] == "unknown"
    assert health["overall"] == "degraded"
    assert client.get("/api/devices/RPI-01").json()["status"] == "unknown"


def test_broker_outage_is_not_device_timeout(tmp_path):
    repo = Repository(tmp_path / "practice.sqlite3")
    repo.update_device("RPI-01", "NORMAL", utc_iso(datetime.now(timezone.utc) - timedelta(seconds=30)))
    repo.update_worker_runtime(False)
    client = TestClient(create_app(repo))
    health = client.get("/api/health").json()
    assert health["worker"] == "running"
    assert health["broker"] == "disconnected"
    assert health["deviceHeartbeat"] == "unknown"
    assert client.get("/api/devices/RPI-01").json()["status"] == "unknown"


def test_connected_broker_with_missing_status_is_timeout(tmp_path):
    repo = Repository(tmp_path / "practice.sqlite3")
    repo.update_device("RPI-01", "NORMAL", utc_iso(datetime.now(timezone.utc) - timedelta(seconds=30)))
    repo.update_worker_runtime(True)
    client = TestClient(create_app(repo))
    health = client.get("/api/health").json()
    assert health["worker"] == "running"
    assert health["broker"] == "connected"
    assert health["deviceHeartbeat"] == "timeout"
    assert client.get("/api/devices/RPI-01").json()["status"] == "fault"
