from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from backend import rag
from backend.db import Repository
from backend.main import create_app


@pytest.mark.parametrize("fault_type,section", [
    ("CONNECTION_TIMEOUT", "상태 메시지"),
    ("RESPONSE_DELAY", "요청"),
    ("INVALID_MESSAGE", "JSON"),
])
def test_retrieval_is_scoped_and_cited(fault_type, section):
    found = rag.search(fault_type, section)
    assert found
    assert all(item["path"].startswith("manuals/") and item["lineStart"] <= item["lineEnd"] for item in found)
    assert all(fault_type.lower().split("_")[0] in item["path"] or item["path"] == "manuals/connection_timeout.md" for item in found)
    for item in found:
        lines = (rag.ROOT / item["path"]).read_text(encoding="utf-8").splitlines()
        assert item["content"] == "\n".join(lines[item["lineStart"] - 1:item["lineEnd"]]).strip()


def test_missing_manual_does_not_call_model(tmp_path, monkeypatch):
    monkeypatch.setattr(rag.httpx, "post", lambda *a, **kw: pytest.fail("model must not be called"))
    assert rag.search("CONNECTION_TIMEOUT", directory=tmp_path) == []
    assert rag.generate({}, [], [])["status"] == "no_evidence"


def test_event_to_retrieval_to_ollama_api_and_monitoring_survives_failure(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "test.sqlite3")
    now = datetime.now(timezone.utc)
    event_id = repo.create_fault("RPI-01", "INVALID_MESSAGE", now, now, "잘못된 JSON")
    repo.add_log("RPI-01", "factory/RPI-01/status", "{broken", "INVALID:JSON", now, event_id)
    seen = {}

    def answer(_url, json, timeout):
        seen["prompt"] = json["prompt"]
        return httpx.Response(200, json={"response": "가능한 원인: JSON 형식 오류 가능성.\n점검 순서: 원본 payload 확인.\n추가 확인 사항: 발행 버전 확인."}, request=httpx.Request("POST", _url))

    monkeypatch.setattr(rag.httpx, "post", answer)
    client = TestClient(create_app(repo))
    result = client.get(f"/api/events/{event_id}/ai-guidance")
    assert result.status_code == 200
    body = result.json()
    assert body["status"] == "ready" and body["origin"] == "ollama"
    assert body["sources"] and "invalid_message.md" in body["sources"][0]["path"]
    assert "INVALID:JSON" in seen["prompt"] and "잘못된 JSON" in seen["prompt"]
    assert client.get("/api/manuals").json()[2]["faultType"] == "INVALID_MESSAGE"

    def offline(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(rag.httpx, "post", offline)
    assert client.get(f"/api/events/{event_id}/ai-guidance").json()["status"] == "unavailable"
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/events").json()[0]["faultType"] == "INVALID_MESSAGE"
    assert client.get("/api/events/999999/ai-guidance").status_code == 404

    monkeypatch.setattr(rag, "search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(rag.httpx, "post", lambda *_args, **_kwargs: pytest.fail("model must not run without evidence"))
    unsupported = client.get(f"/api/events/{event_id}/ai-guidance").json()
    assert unsupported["status"] == "no_evidence"
    assert unsupported["origin"] == "none" and unsupported["sources"] == []
