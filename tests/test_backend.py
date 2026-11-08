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


def test_dashboard_breakdown_separates_recovery_from_action(system):
    repo, clock, _ = system
    first = repo.create_fault("RPI-01", "CONNECTION_TIMEOUT", clock.wall, clock.wall, "timeout")
    second = repo.create_fault("RPI-01", "RESPONSE_DELAY", clock.wall, clock.wall, "delay", "request-1")
    repo.recover_fault("RPI-01", "CONNECTION_TIMEOUT", clock.wall)
    repo.add_action(second, [], "checked", True, clock.wall)
    counts = repo.dashboard_counts()
    assert counts["faultsByType"] == {"CONNECTION_TIMEOUT": 1, "RESPONSE_DELAY": 1, "INVALID_MESSAGE": 0}
    assert counts["recoveredFaults"] == 1
    assert counts["unrecoveredFaults"] == 1
    assert counts["completedActions"] == 1
    assert counts["unresolvedFaults"] == 1


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
    assert client.get("/api/devices/RPI-01").json()["status"] == "unknown"
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


def test_device_alive_only_after_real_status(system):
    _, clock, engine = system
    assert engine.device_alive() is False
    engine.last_valid_mono = clock.monotonic()  # 브로커 연결 시점 보정은 장치 생존이 아니다
    assert engine.device_alive() is False
    engine.process_status(status())
    assert engine.device_alive() is True
    clock.advance(9.9)
    assert engine.device_alive() is True
    clock.advance(0.2)
    assert engine.device_alive() is False


def test_request_sent_after_device_stopped_is_not_a_response_delay(system):
    repo, clock, engine = system
    engine.process_status(status())          # 장치 정상
    clock.advance(1.0)                       # 장치가 멈춘 뒤
    engine.register_request("after-stop")    # 요청이 나감
    clock.advance(3.1)
    engine.tick()
    assert repo.list_events() == []          # 응답 지연으로 판정하지 않음
    clock.advance(6.0)                       # 마지막 상태 후 10초 경과
    engine.tick()
    types = [e["fault_type"] for e in repo.list_events()]
    assert types == ["CONNECTION_TIMEOUT"]


def test_delay_still_detected_when_device_keeps_sending_status(system):
    repo, clock, engine = system
    engine.process_status(status(1))
    engine.register_request("slow")
    clock.advance(2.0)
    engine.process_status(status(2))         # 장치는 살아 있음
    clock.advance(1.1)
    engine.tick()
    assert [e["fault_type"] for e in repo.list_events()] == ["RESPONSE_DELAY"]


def test_past_actions_reuse_same_type_records(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(10.1)
    engine.tick()                                    # 첫 번째 통신 중단
    first = repo.list_events()[0]["id"]
    client = TestClient(create_app(repo))
    client.post(f"/api/events/{first}/actions", json={
        "checklist": [0, 1], "action_text": "장치 발행 프로세스 재시작", "resolved": True})
    engine.process_status(status(2))                 # 복구
    clock.advance(10.1)
    engine.tick()                                    # 두 번째 통신 중단
    second = repo.list_events()[0]["id"]
    assert second != first
    past = client.get(f"/api/events/{second}/past-actions").json()
    assert [p["eventId"] for p in past] == [first]
    assert past[0]["action"] == "장치 발행 프로세스 재시작"
    assert past[0]["faultType"] == "CONNECTION_TIMEOUT"
    assert client.get(f"/api/events/{first}/past-actions").json() == []   # 자기 자신 제외
    recent = client.get("/api/actions/recent").json()
    assert recent[0]["eventId"] == first and recent[0]["type"] == "message_timeout"


def test_minute_metrics_show_recent_activity(system, monkeypatch):
    repo, clock, engine = system
    monkeypatch.setattr("backend.db.utc_now", clock.utcnow)
    points = repo.minute_metrics(15)
    assert len(points) == 15 and points[-1]["label"] == "14:00"
    engine.process_status(status())
    engine.process_status(b"{bad")
    point = TestClient(create_app(repo)).get("/api/metrics/recent").json()[-1]
    assert (point["normal"], point["warning"], point["error"]) == (1, 1, 1)


def test_queued_request_answered_after_reconnect_is_not_a_delay(system):
    repo, clock, engine = system
    engine.process_status(status())
    clock.advance(1.0)
    engine.register_request("queued")         # 장치가 꺼진 직후 보낸 요청
    clock.advance(9.1)
    engine.tick()                              # 통신 중단 판정, 요청은 정리
    clock.advance(20.0)
    engine.tick()
    assert engine.process_response(response("queued")) is True   # 재연결 후 뒤늦은 응답
    engine.process_status(status(2))
    events = repo.list_events()
    assert [e["fault_type"] for e in events] == ["CONNECTION_TIMEOUT"]
    assert events[0]["recovered_at"] is not None


def test_event_ids_stay_sequential_during_long_outage(system):
    repo, clock, engine = system
    engine.process_status(status())
    for _ in range(200):                       # 50초 동안 0.25초마다 tick
        clock.advance(0.25)
        engine.tick()
    engine.process_status(status(2))
    clock.advance(10.1)
    engine.tick()
    ids = sorted(e["id"] for e in repo.list_events())
    assert ids == [ids[0], ids[0] + 1]


def test_ids_have_no_gaps_across_fault_types(system):
    repo, clock, engine = system
    engine.process_status(status())
    for payload in (b"{bad", b"{bad", b"{bad"):       # 같은 형식 오류 반복
        engine.process_status(payload)
    engine.process_status(status(2))                  # 형식 오류 복구
    engine.register_request("slow")
    clock.advance(2.0); engine.process_status(status(3))
    clock.advance(1.1); engine.tick()                 # 응답 지연 판정
    clock.advance(1.2); engine.process_response(response("slow"))   # 늦은 응답으로 복구
    ids = sorted(e["id"] for e in repo.list_events())
    assert len(ids) == 2
    assert ids == list(range(ids[0], ids[0] + len(ids)))


def test_request_lost_to_device_restart_is_not_a_delay(system):
    repo, clock, engine = system
    engine.process_status(status(10))
    engine.register_request("in-flight")      # 요청 직후 장치 프로세스가 재시작됨
    clock.advance(1.5)
    engine.process_status(status(1))          # sequence가 1로 돌아옴 = 재시작
    clock.advance(2.0)
    engine.process_status(status(2))
    engine.tick()
    assert repo.list_events() == []
    assert "in-flight" in engine.pending and engine.pending["in-flight"]["timed_out"]
