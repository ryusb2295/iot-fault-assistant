import json
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

from .config import DEVICE_ID, REQUEST_TOPIC, RESPONSE_TOPIC, STATUS_TOPIC
from .db import utc_iso

TIMEOUT_SECONDS = 10.0
RESPONSE_SECONDS = 3.0
ALLOWED_STATUS = {"RUNNING", "IDLE", "STOPPED", "ERROR"}


class Clock:
    def utcnow(self):
        return datetime.now(timezone.utc)

    def monotonic(self):
        return time.monotonic()


class FaultEngine:
    def __init__(self, repository, clock=None, device_id=DEVICE_ID):
        self.repo = repository
        self.clock = clock or Clock()
        self.device_id = device_id
        self.lock = threading.RLock()
        self.pending = {}
        self.repo.ensure_device(device_id)
        saved = self.repo.get_device(device_id)
        self.last_valid_mono = None
        if saved["last_seen"]:
            age = max(0, (self.clock.utcnow() - datetime.fromisoformat(saved["last_seen"])).total_seconds())
            self.last_valid_mono = self.clock.monotonic() - age

    def _decode(self, payload):
        try:
            data = json.loads(payload.decode("utf-8") if isinstance(payload, bytes) else payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"JSON 문법 오류: {exc}") from exc
        if not isinstance(data, dict):
            raise ValueError("JSON 최상위 값은 객체여야 합니다")
        return data

    def _validate_common(self, data):
        if not isinstance(data.get("device_id"), str) or data["device_id"] != self.device_id:
            raise ValueError("device_id 누락, 자료형 오류 또는 장치 ID 불일치")
        stamp = data.get("timestamp")
        if not isinstance(stamp, str):
            raise ValueError("timestamp 누락 또는 자료형 오류")
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise ValueError("timestamp ISO 8601 형식 오류") from exc
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timestamp에 시간대 정보가 필요합니다")

    def _invalid(self, topic, payload, reason, at):
        event_id = self.repo.create_fault(self.device_id, "INVALID_MESSAGE", at, at, reason, topic)
        self.repo.add_log(self.device_id, topic, self._as_text(payload), f"INVALID: {reason}", at, event_id)
        return False

    @staticmethod
    def _as_text(payload):
        return payload.decode("utf-8", errors="replace") if isinstance(payload, bytes) else str(payload)

    def process_status(self, payload):
        with self.lock:
            at = self.clock.utcnow()
            try:
                data = self._decode(payload)
                self._validate_common(data)
                if not isinstance(data.get("status"), str) or data["status"] not in ALLOWED_STATUS:
                    raise ValueError("status 누락, 자료형 오류 또는 허용되지 않는 값")
                if type(data.get("sequence")) is not int or data["sequence"] < 0:
                    raise ValueError("sequence 누락 또는 음수가 아닌 정수 자료형 오류")
            except ValueError as exc:
                return self._invalid(STATUS_TOPIC, payload, str(exc), at)
            self.last_valid_mono = self.clock.monotonic()
            self.repo.update_device(self.device_id, "NORMAL", utc_iso(at), data)
            self.repo.recover_fault(self.device_id, "CONNECTION_TIMEOUT", at)
            self.repo.recover_fault(self.device_id, "INVALID_MESSAGE", at, STATUS_TOPIC)
            self.repo.add_log(self.device_id, STATUS_TOPIC, self._as_text(payload), "VALID", at)
            return True

    def register_request(self, request_id=None):
        with self.lock:
            request_id = request_id or uuid.uuid4().hex
            if request_id in self.pending:
                raise ValueError("중복 request_id")
            at = self.clock.utcnow()
            self.pending[request_id] = {"sent_mono": self.clock.monotonic(), "sent_at": at, "timed_out": False}
            payload = {"device_id": self.device_id, "request_id": request_id, "timestamp": utc_iso(at)}
            self.repo.add_log(self.device_id, REQUEST_TOPIC, json.dumps(payload), "SENT", at)
            return payload

    def cancel_request(self, request_id):
        with self.lock:
            self.pending.pop(request_id, None)

    def process_response(self, payload):
        with self.lock:
            at = self.clock.utcnow()
            try:
                data = self._decode(payload)
                self._validate_common(data)
                request_id = data.get("request_id")
                if not isinstance(request_id, str) or not request_id:
                    raise ValueError("request_id 누락 또는 자료형 오류")
            except ValueError as exc:
                return self._invalid(RESPONSE_TOPIC, payload, str(exc), at)
            if request_id not in self.pending:
                event_id = self.repo.get_active_fault_by_key(self.device_id, "RESPONSE_DELAY", request_id)
                if event_id:
                    self.repo.recover_fault(self.device_id, "RESPONSE_DELAY", at, request_id)
                    self.repo.recover_fault(self.device_id, "INVALID_MESSAGE", at, RESPONSE_TOPIC)
                    self.repo.add_log(self.device_id, RESPONSE_TOPIC, self._as_text(payload),
                        "LATE: 요청 추적 기간 이후 응답", at, event_id)
                    return True
                self.repo.add_log(self.device_id, RESPONSE_TOPIC, self._as_text(payload),
                    "UNMATCHED_RESPONSE: 알 수 없거나 이미 처리한 request_id", at)
                return False
            pending = self.pending.pop(request_id)
            elapsed = self.clock.monotonic() - pending["sent_mono"]
            self.repo.recover_fault(self.device_id, "INVALID_MESSAGE", at, RESPONSE_TOPIC)
            event_id = None
            if elapsed > RESPONSE_SECONDS:
                event_id = self.repo.create_fault(self.device_id, "RESPONSE_DELAY", pending["sent_at"], at,
                    f"요청 {request_id}: 응답 {elapsed:.2f}초 (기준 3초 초과)", request_id)
                self.repo.recover_fault(self.device_id, "RESPONSE_DELAY", at, request_id)
            self.repo.add_log(self.device_id, RESPONSE_TOPIC, self._as_text(payload),
                f"DELAYED: {elapsed:.2f}s" if event_id else f"VALID: {elapsed:.2f}s", at, event_id)
            return True

    def tick(self):
        with self.lock:
            at = self.clock.utcnow()
            now_mono = self.clock.monotonic()
            if self.last_valid_mono is not None and now_mono - self.last_valid_mono >= TIMEOUT_SECONDS:
                started = at - timedelta(seconds=now_mono - self.last_valid_mono - TIMEOUT_SECONDS)
                event_id = self.repo.create_fault(self.device_id, "CONNECTION_TIMEOUT", started, at,
                    "마지막 유효 상태 메시지 이후 10초 이상 미수신")
                self.repo.update_device(self.device_id, "FAULT")
                if event_id and not self.repo.get_event_logs(event_id):
                    self.repo.add_log(self.device_id, STATUS_TOPIC, "", "TIMEOUT: 10초 이상 미수신", at, event_id)
            for request_id, pending in list(self.pending.items()):
                elapsed = now_mono - pending["sent_mono"]
                if elapsed > RESPONSE_SECONDS and not pending["timed_out"]:
                    event_id = self.repo.create_fault(self.device_id, "RESPONSE_DELAY", pending["sent_at"], at,
                        f"요청 {request_id}: 3초 이내 응답 없음", request_id)
                    self.repo.add_log(self.device_id, REQUEST_TOPIC, request_id, "TIMEOUT: 응답 없음", at, event_id)
                    pending["timed_out"] = True
                if elapsed > 120:
                    self.pending.pop(request_id, None)
