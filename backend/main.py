import json
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import DB_PATH, DEVICE_ID, STATUS_TOPIC, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_NUM_PREDICT, AI_EVIDENCE_LIMIT
from .db import Repository, utc_now
from . import rag

WORKER_STALE_SECONDS = 3
DEVICE_TIMEOUT_SECONDS = 10


def monitoring_state(repository):
    now = datetime.now(timezone.utc)
    runtime = repository.get_worker_runtime()
    worker = "running" if runtime and (now - datetime.fromisoformat(runtime["heartbeat_at"])).total_seconds() <= WORKER_STALE_SECONDS else "stopped"
    broker = ("connected" if runtime["broker_connected"] else "disconnected") if worker == "running" else "unknown"
    device = repository.get_device(DEVICE_ID)
    last_seen = device["last_seen"] if device else None
    if worker != "running" or broker != "connected":
        heartbeat = "unknown"
    elif not last_seen:
        heartbeat = "waiting"
    elif (now - datetime.fromisoformat(last_seen)).total_seconds() >= DEVICE_TIMEOUT_SECONDS:
        heartbeat = "timeout"
    else:
        heartbeat = "normal"
    return {"worker": worker, "broker": broker, "deviceHeartbeat": heartbeat}

TYPE_TO_UI = {
    "CONNECTION_TIMEOUT": "message_timeout",
    "RESPONSE_DELAY": "response_delay",
    "INVALID_MESSAGE": "format_error",
}


def event_json(row):
    end = datetime.fromisoformat(row["recovered_at"]) if row["recovered_at"] else None
    start = datetime.fromisoformat(row["started_at"])
    action_status = "completed" if row["status"] == "RESOLVED" else "in_progress" if row["has_action"] else "unhandled"
    return {
        "id": row["id"], "deviceId": row["device_id"], "type": TYPE_TO_UI[row["fault_type"]],
        "faultType": row["fault_type"], "occurredAt": row["started_at"],
        "detectedAt": row["detected_at"], "recoveredAt": row["recovered_at"],
        "durationSeconds": int((end - start).total_seconds()) if end else None,
        "status": "resolved" if row["status"] == "RESOLVED" else "open",
        "lifecycleStatus": row["status"], "summary": row["description"],
        "recoveryStatus": "recovered" if end else "unrecovered",
        "actionStatus": action_status,
    }


def device_name(model):
    """상태 메시지의 model 필드로 실기기와 PC 시뮬레이터를 구분해 표시한다."""
    if model and "Raspberry Pi" in model:
        parts = model.split()
        return " ".join(parts[:3]) if len(parts) >= 3 else model
    return model or "PC 시뮬레이터"


def device_json(row, heartbeat="unknown"):
    effective = "normal" if heartbeat == "normal" else "fault" if heartbeat == "timeout" else "unknown"
    recent = json.loads(row["recent_message"]) if row["recent_message"] else None
    recent_dict = recent if isinstance(recent, dict) else {}
    return {
        "id": row["device_id"], "name": device_name(recent_dict.get("model")),
        "model": recent_dict.get("model"), "cpuTempC": recent_dict.get("cpu_temp_c"),
        "status": effective,
        "rawStatus": row["status"], "lastReceivedAt": row["last_seen"],
        "intervalSeconds": 2, "topic": STATUS_TOPIC,
        "recentMessage": recent,
    }


def log_json(row):
    result = row["validation_result"]
    level = "장애" if result.startswith(("INVALID", "TIMEOUT", "DELAYED", "LATE")) else "경고" if result.startswith("UNMATCHED_RESPONSE") else "정보"
    return {"id": row["id"], "time": row["received_at"], "level": level,
            "message": result, "topic": row["topic"], "payload": row["payload"]}


def action_json(row):
    return {"id": row["id"], "eventId": row["event_id"], "checklist": json.loads(row["checklist"]),
            "actionText": row["action_text"], "resolved": bool(row["resolved"]), "createdAt": row["created_at"]}


class ActionIn(BaseModel):
    checklist: list[int] = Field(default_factory=list)
    action_text: str = Field(min_length=1, max_length=1000)
    resolved: bool = False


def create_app(repo=None):
    repository = repo or Repository(DB_PATH)
    repository.ensure_device(DEVICE_ID)
    app = FastAPI(title="IoT Fault Monitoring API", version="0.2.0")
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                                                    "http://localhost:5175", "http://127.0.0.1:5175"],
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        repository.dashboard_counts()
        state = monitoring_state(repository)
        return {"status": "ok", "database": "ready", "api": "running", **state,
                "overall": "ok" if state == {"worker": "running", "broker": "connected", "deviceHeartbeat": "normal"} else "degraded"}

    @app.get("/api/dashboard")
    def dashboard():
        counts = repository.dashboard_counts()
        if monitoring_state(repository)["deviceHeartbeat"] != "normal":
            counts["normalDevices"] = 0
        return counts

    @app.get("/api/devices")
    def devices():
        heartbeat = monitoring_state(repository)["deviceHeartbeat"]
        return [device_json(row, heartbeat) for row in repository.list_devices()]

    @app.get("/api/devices/{device_id}")
    def device(device_id: str):
        row = repository.get_device(device_id)
        if not row:
            raise HTTPException(404, "장치를 찾을 수 없습니다")
        return device_json(row, monitoring_state(repository)["deviceHeartbeat"])

    @app.get("/api/events")
    def events():
        return [event_json(row) for row in repository.list_events()]

    @app.get("/api/events/{event_id}")
    def event(event_id: int):
        row = repository.get_event(event_id)
        if not row:
            raise HTTPException(404, "장애를 찾을 수 없습니다")
        result = event_json(row)
        result["actions"] = [action_json(item) for item in repository.list_actions_for_event(event_id)]
        return result

    @app.get("/api/events/{event_id}/logs")
    def event_logs(event_id: int):
        if not repository.get_event(event_id):
            raise HTTPException(404, "장애를 찾을 수 없습니다")
        return [log_json(row) for row in repository.get_event_logs(event_id)]

    @app.get("/api/manuals")
    def manuals():
        return rag.list_manuals()

    @app.get("/api/events/{event_id}/ai-guidance")
    def ai_guidance(event_id: int):
        row = repository.get_event(event_id)
        if not row:
            raise HTTPException(404, "장애를 찾을 수 없습니다")
        logs = repository.get_event_logs(event_id)
        evidence = rag.search(row["fault_type"], f"{row['description']} " + " ".join(
            log["validation_result"] for log in logs[-8:]), limit=AI_EVIDENCE_LIMIT)
        result = rag.generate(row, logs, evidence, base_url=OLLAMA_BASE_URL,
                              model=OLLAMA_MODEL, timeout=OLLAMA_TIMEOUT_SECONDS,
                              num_predict=OLLAMA_NUM_PREDICT)
        return {"eventId": event_id, "faultType": row["fault_type"], "origin": "ollama" if result["status"] == "ready" else "none",
                "model": OLLAMA_MODEL if result["status"] == "ready" else None, **result}

    @app.post("/api/events/{event_id}/actions", status_code=201)
    def add_action(event_id: int, payload: ActionIn):
        if not payload.action_text.strip():
            raise HTTPException(422, "조치 결과를 입력해야 합니다")
        try:
            action_id = repository.add_action(event_id, payload.checklist, payload.action_text.strip(), payload.resolved, utc_now())
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
        if action_id is None:
            raise HTTPException(404, "장애를 찾을 수 없습니다")
        return {"id": action_id, "eventId": event_id, "saved": True}

    def knowledge_action_json(item):
        return {"id": item["id"], "eventId": item["event_id"], "faultType": item["fault_type"],
                "type": TYPE_TO_UI[item["fault_type"]], "summary": item["description"],
                "action": item["action_text"], "resolved": bool(item["resolved"]),
                "checklist": json.loads(item["checklist"]), "time": item["created_at"],
                "occurredAt": item["started_at"], "recoveredAt": item["recovered_at"]}

    @app.get("/api/actions/recent")
    def recent_actions(limit: int = 10):
        return [{**knowledge_action_json(item)} for item in repository.list_actions_with_events(limit=min(limit, 200))]

    @app.get("/api/events/{event_id}/past-actions")
    def past_actions(event_id: int):
        """같은 장애 유형에서 과거에 기록된 실제 조치 (현재 장애 제외)."""
        row = repository.get_event(event_id)
        if not row:
            raise HTTPException(404, "장애를 찾을 수 없습니다")
        return [knowledge_action_json(item) for item in repository.list_actions_with_events(
            limit=5, fault_type=row["fault_type"], exclude_event_id=event_id)]

    @app.get("/api/metrics/recent")
    def recent_metrics(minutes: int = 15):
        return repository.minute_metrics(max(5, min(minutes, 60)))

    @app.get("/api/metrics/events")
    def event_metrics():
        return repository.hourly_metrics()

    return app


app = create_app()
