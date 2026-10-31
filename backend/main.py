import json
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import DB_PATH, DEVICE_ID, STATUS_TOPIC, OLLAMA_BASE_URL, OLLAMA_MODEL, OLLAMA_TIMEOUT_SECONDS
from .db import Repository, utc_now
from . import rag

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


def device_json(row):
    return {
        "id": row["device_id"], "name": "라즈베리파이 5 설비",
        "status": "normal" if row["status"] == "NORMAL" else "unknown" if row["status"] == "UNKNOWN" else "fault",
        "rawStatus": row["status"], "lastReceivedAt": row["last_seen"],
        "intervalSeconds": 2, "topic": STATUS_TOPIC,
        "recentMessage": json.loads(row["recent_message"]) if row["recent_message"] else None,
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
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])

    @app.get("/api/health")
    def health():
        repository.dashboard_counts()
        return {"status": "ok", "database": "ready", "mqtt": "separate process"}

    @app.get("/api/dashboard")
    def dashboard():
        return repository.dashboard_counts()

    @app.get("/api/devices")
    def devices():
        return [device_json(row) for row in repository.list_devices()]

    @app.get("/api/devices/{device_id}")
    def device(device_id: str):
        row = repository.get_device(device_id)
        if not row:
            raise HTTPException(404, "장치를 찾을 수 없습니다")
        return device_json(row)

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
            log["validation_result"] for log in logs[-8:]))
        result = rag.generate(row, logs, evidence, base_url=OLLAMA_BASE_URL,
                              model=OLLAMA_MODEL, timeout=OLLAMA_TIMEOUT_SECONDS)
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

    @app.get("/api/actions/recent")
    def recent_actions():
        return [{"eventId": item["event_id"], "action": item["action_text"], "time": item["created_at"]}
                for item in repository.list_actions()]

    @app.get("/api/metrics/events")
    def event_metrics():
        return repository.hourly_metrics()

    return app


app = create_app()
