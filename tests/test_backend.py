import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from backend.db import Repository
from backend.engine import FaultEngine
from backend.main import create_app


class FakeClock:
    def __init__(self):
        self.wall = datetime(2026, 10, 27, 5, 0, tzinfo=timezone.utc)
        self.mono = 100.0

    def utcnow(self):
        return self.wall

    def monotonic(self):
        return self.mono

    def advance(self, seconds):
        self.wall += timedelta(seconds=seconds)
        self.mono += seconds


@pytest.fixture
def system(tmp_path):
    repo = Repository(tmp_path / "faults.sqlite3")
    clock = FakeClock()
    return repo, clock, FaultEngine(repo, clock)


def status(sequence=1, **changes):
    payload = {"device_id": "RPI-01", "status": "RUNNING", "sequence": sequence,
               "timestamp": "2026-10-27T14:00:00+09:00"}
    payload.update(changes)
    return json.dumps(payload).encode()


def response(request_id):
    return json.dumps({"device_id": "RPI-01", "request_id": request_id,
                       "timestamp": "2026-10-27T14:00:00+09:00"}).encode()


def test_unknown_then_normal_status(system):
    repo, _, engine = system
    assert repo.get_device("RPI-01")["status"] == "UNKNOWN"
    engine.tick()
    assert repo.list_events() == []
    assert engine.process_status(status()) is True
    assert repo.get_device("RPI-01")["status"] == "NORMAL"
    assert repo.get_device("RPI-01")["last_seen"].endswith("+00:00")


def test_connection_timeout_deduplicated_and_recovered(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(9.9)
    engine.tick()
    assert repo.list_events() == []
    clock.advance(0.1)
    engine.tick()
    assert repo.get_device("RPI-01")["status"] == "FAULT"
    assert repo.list_events()[0]["fault_type"] == "CONNECTION_TIMEOUT"
    clock.advance(4)
    engine.tick()
    assert len(repo.list_events()) == 1
    engine.process_status(status(2))
    event = repo.list_events()[0]
    assert event["recovered_at"] is not None
    assert event["status"] == "RECOVERED"
    assert repo.get_device("RPI-01")["status"] == "NORMAL"


def test_delayed_response_after_timeout_is_recovered(system):
    repo, clock, engine = system
    engine.register_request("req-1")
    clock.advance(3.1)
    engine.tick()
    clock.advance(1.1)
    assert engine.process_response(response("req-1")) is True
    events = repo.list_events()
    assert len(events) == 1
    assert events[0]["fault_type"] == "RESPONSE_DELAY"
    assert events[0]["recovered_at"] is not None
    assert len(repo.get_event_logs(events[0]["id"])) == 2


def test_normal_and_directly_delayed_responses(system):
    repo, clock, engine = system
    normal_request = engine.register_request("normal-request")
    assert normal_request["request_id"] == "normal-request"
    clock.advance(2.9)
    assert engine.process_response(response("normal-request")) is True
    assert repo.list_events() == []

    engine.register_request("slow-request")
    clock.advance(4.2)
    assert engine.process_response(response("slow-request")) is True
    event = repo.list_events()[0]
    assert event["fault_type"] == "RESPONSE_DELAY"
    assert event["dedupe_key"] == "slow-request"
    assert event["recovered_at"] is not None
    assert len(repo.list_events()) == 1


def test_response_after_pending_expiry_recovers_original_fault(system):
    repo, clock, engine = system
    engine.register_request("very-late")
    clock.advance(3.1)
    engine.tick()
    event_id = repo.list_events()[0]["id"]
    clock.advance(118)
    engine.tick()
    assert "very-late" not in engine.pending
    assert engine.process_response(response("very-late")) is True
    assert len(repo.list_events()) == 1
    assert repo.get_event(event_id)["recovered_at"] is not None
    assert repo.get_event_logs(event_id)[-1]["validation_result"].startswith("LATE:")


def test_unmatched_response_is_logged_without_format_fault(system):
    repo, _, engine = system
    assert engine.process_response(response("unknown")) is False
    assert repo.list_events() == []
    with repo.connection() as db:
        result = db.execute("SELECT validation_result FROM communication_logs").fetchone()[0]
    assert result.startswith("UNMATCHED_RESPONSE:")


def test_invalid_response_json_creates_format_fault(system):
    repo, _, engine = system
    assert engine.process_response(b"{broken") is False
    assert repo.list_events()[0]["fault_type"] == "INVALID_MESSAGE"


def test_status_does_not_recover_response_format_fault(system):
    repo, _, engine = system
    engine.process_response(b"{broken")
    engine.process_status(status())
    response_fault = repo.list_events()[0]
    assert response_fault["dedupe_key"] == "factory/RPI-01/response"
    assert response_fault["recovered_at"] is None
    engine.register_request("valid-after-error")
    engine.process_response(response("valid-after-error"))
    assert repo.get_event(response_fault["id"])["recovered_at"] is not None


def test_unanswered_request_is_only_registered_once(system):
    repo, clock, engine = system
    engine.register_request("missing")
    clock.advance(3.01)
    engine.tick()
    clock.advance(10)
    engine.tick()
    assert len(repo.list_events()) == 1
    assert repo.list_events()[0]["recovered_at"] is None


def test_different_failed_requests_keep_distinct_request_ids(system):
    repo, clock, engine = system
    engine.register_request("missing-a")
    clock.advance(3.1)
    engine.tick()
    engine.register_request("missing-b")
    clock.advance(3.1)
    engine.tick()
    assert {event["dedupe_key"] for event in repo.list_events()} == {"missing-a", "missing-b"}


def test_status_message_does_not_recover_unanswered_request(system):
    repo, clock, engine = system
    engine.register_request("unanswered")
    clock.advance(3.1)
    engine.tick()
    engine.process_status(status())
    assert repo.list_events()[0]["recovered_at"] is None
    assert repo.get_device("RPI-01")["status"] == "NORMAL"


@pytest.mark.parametrize("payload", [
    b"{bad json", status(status="BROKEN"), status(sequence="one"),
    json.dumps({"device_id": "RPI-01", "sequence": 1, "timestamp": "2026-10-27T14:00:00+09:00"}).encode(),
])
def test_invalid_message_logged_and_deduplicated(system, payload):
    repo, _, engine = system
    assert engine.process_status(payload) is False
    assert engine.process_status(payload) is False
    assert len(repo.list_events()) == 1
    assert repo.list_events()[0]["fault_type"] == "INVALID_MESSAGE"
    logs = repo.get_event_logs(repo.list_events()[0]["id"])
    assert len(logs) == 2
    assert all(log["validation_result"].startswith("INVALID:") for log in logs)


def test_invalid_recovers_on_valid_status(system):
    repo, _, engine = system
    engine.process_status(b"invalid")
    engine.process_status(status())
    assert repo.list_events()[0]["recovered_at"] is not None


def test_database_persists_between_repository_instances(system):
    repo, _, engine = system
    engine.process_status(status())
    second = Repository(repo.path)
    assert second.get_device("RPI-01")["status"] == "NORMAL"
    with second.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM communication_logs").fetchone()[0] == 1


def test_existing_fault_history_survives_repository_reopen(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(10)
    engine.tick()
    event = repo.list_events()[0]
    reopened = Repository(repo.path)
    assert reopened.get_event(event["id"])["detected_at"] == event["detected_at"]
    assert reopened.dashboard_counts()["faults"] == 1


def test_api_shape_and_action_record(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(10)
    engine.tick()
    client = TestClient(create_app(repo))
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/dashboard").json()["faults"] == 1
    assert client.get("/api/devices/RPI-01").json()["status"] == "fault"
    event = client.get("/api/events").json()[0]
    assert event["type"] == "message_timeout"
    assert event["status"] == "open"
    assert client.get(f"/api/events/{event['id']}/logs").json()[0]["level"] == "장애"
    saved = client.post(f"/api/events/{event['id']}/actions", json={
        "checklist": [0, 2], "action_text": "구독 연결 확인", "resolved": False})
    assert saved.status_code == 201
    assert client.get(f"/api/events/{event['id']}").json()["actions"][0]["actionText"] == "구독 연결 확인"
    assert client.get(f"/api/events/{event['id']}").json()["actionStatus"] == "in_progress"
    assert client.get("/api/events").json()[0]["actionStatus"] == "in_progress"
    assert client.get("/api/actions/recent").json()[0]["eventId"] == event["id"]
    assert client.get("/api/events/99999").status_code == 404


def test_action_completion_is_independent_of_recovery_and_persists(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(10)
    engine.tick()
    event_id = repo.list_events()[0]["id"]
    client = TestClient(create_app(repo))
    payload = {"checklist": [0], "action_text": "수신 복구 확인", "resolved": True}
    before = client.get("/api/dashboard").json()
    assert before["unrecoveredFaults"] == before["unresolvedFaults"] == 1
    engine.process_status(status(2))
    recovered = client.get(f"/api/events/{event_id}").json()
    assert recovered["recoveryStatus"] == "recovered"
    assert recovered["actionStatus"] == "unhandled"
    assert client.get("/api/dashboard").json()["unresolvedFaults"] == 1
    assert client.post(f"/api/events/{event_id}/actions", json=payload).status_code == 201
    assert Repository(repo.path).get_event(event_id)["status"] == "RESOLVED"
    completed = client.get(f"/api/events/{event_id}").json()
    assert completed["status"] == "resolved"
    assert completed["actionStatus"] == "completed"
    assert client.get("/api/dashboard").json()["unrecoveredFaults"] == 0
    assert client.get("/api/dashboard").json()["unresolvedFaults"] == 0


def test_action_can_be_completed_while_communication_is_unrecovered(system):
    repo, clock, engine = system
    engine.register_request("still-missing")
    clock.advance(3.1)
    engine.tick()
    event_id = repo.list_events()[0]["id"]
    client = TestClient(create_app(repo))
    assert client.post(f"/api/events/{event_id}/actions", json={
        "checklist": [0], "action_text": "요청 경로 점검 완료", "resolved": False,
    }).status_code == 201
    in_progress = client.get(f"/api/events/{event_id}").json()
    assert in_progress["actionStatus"] == "in_progress"
    assert in_progress["recoveryStatus"] == "unrecovered"

    assert client.post(f"/api/events/{event_id}/actions", json={
        "checklist": [0], "action_text": "조치 완료", "resolved": True,
    }).status_code == 201
    completed = client.get(f"/api/events/{event_id}").json()
    assert completed["actionStatus"] == "completed"
    assert completed["recoveryStatus"] == "unrecovered"
    counts = client.get("/api/dashboard").json()
    assert counts["unrecoveredFaults"] == 1
    assert counts["unresolvedFaults"] == 0


def test_hourly_metrics_count_only_status_validation_and_faults(system, monkeypatch):
    repo, clock, engine = system
    monkeypatch.setattr("backend.db.utc_now", clock.utcnow)
    assert len(repo.hourly_metrics()) == 7
    engine.process_status(status())
    engine.register_request("metric-request")
    engine.process_response(response("metric-request"))
    point = repo.hourly_metrics()[-1]
    assert point == {"label": "14:00", "normal": 1, "warning": 0, "error": 0}

    engine.process_status(b"{invalid json")
    point = repo.hourly_metrics()[-1]
    assert (point["normal"], point["warning"], point["error"]) == (1, 1, 1)

    clock.advance(2)
    engine.process_status(status(2))
    point = TestClient(create_app(repo)).get("/api/metrics/events").json()[-1]
    assert (point["normal"], point["warning"], point["error"]) == (2, 1, 1)
