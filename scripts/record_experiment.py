"""Append one real fault event and optional AI latency to an experiment CSV."""

import argparse
import csv
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

FIELDS = ["experiment", "event_id", "fault_type", "device_id", "started_at_utc",
          "detected_at_utc", "recovered_at_utc", "detection_seconds", "latency_basis",
          "ai_response_seconds", "ai_status", "notes"]


def event_record(db_path, event_id):
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        event = db.execute("SELECT * FROM fault_events WHERE id=?", (event_id,)).fetchone()
        if event is None:
            raise ValueError(f"장애 ID {event_id}를 찾을 수 없습니다")
        event = dict(event)
        basis = ("요청 등록 시각 → 지연 감지 시각" if event["fault_type"] == "RESPONSE_DELAY"
                 else "잘못된 메시지 수신 시각 → 형식 판정 시각")
        reference = event["started_at"]
        if event["fault_type"] == "CONNECTION_TIMEOUT":
            row = db.execute("""SELECT MAX(received_at) FROM communication_logs
                WHERE device_id=? AND topic=? AND validation_result='VALID' AND received_at<=?""",
                (event["device_id"], f"factory/{event['device_id']}/status", event["started_at"])).fetchone()
            if row[0]:
                reference = row[0]
                basis = "마지막 유효 상태 수신 시각"
            else:
                reference = None
                basis = "마지막 유효 상태 로그 없음 (산출 불가)"
        seconds = round((datetime.fromisoformat(event["detected_at"]) - datetime.fromisoformat(reference)).total_seconds(), 3) if reference else ""
        if seconds == 0:
            seconds = ""
            basis += " (시각 해상도상 측정 불가)"
        return {"event_id": event_id, "fault_type": event["fault_type"], "device_id": event["device_id"],
                "started_at_utc": event["started_at"], "detected_at_utc": event["detected_at"],
                "recovered_at_utc": event["recovered_at"] or "", "detection_seconds": seconds,
                "latency_basis": basis}


def measure_ai(api_base, event_id, timeout=70):
    start = time.perf_counter()
    try:
        with urlopen(f"{api_base.rstrip('/')}/events/{event_id}/ai-guidance", timeout=timeout) as response:
            status = json.load(response).get("status", "unknown")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        status = f"request_error:{type(exc).__name__}"
    return round(time.perf_counter() - start, 3), status


def main():
    parser = argparse.ArgumentParser(description="SQLite 장애와 AI 응답 시간을 CSV로 기록")
    parser.add_argument("event_id", type=int, nargs="+", help="서로 다른 실험 장애 ID; 유형별 5개 지정 가능")
    parser.add_argument("--db", type=Path, default=Path("backend/iot_faults.sqlite3"))
    parser.add_argument("--api", default="http://127.0.0.1:8000/api")
    parser.add_argument("--output", type=Path, default=Path("experiments/results.csv"))
    parser.add_argument("--experiment", required=True, help="실험 이름 (예: ethernet-reconnect-01)")
    parser.add_argument("--notes", default="")
    parser.add_argument("--skip-ai", action="store_true", help="AI 호출 없이 장애 시각만 기록")
    parser.add_argument("--require-five", action="store_true", help="동일 장애 유형의 서로 다른 5개 ID 요구")
    args = parser.parse_args()
    if len(set(args.event_id)) != len(args.event_id):
        parser.error("중복 장애 ID는 반복 실험으로 인정하지 않습니다")
    records = [event_record(args.db, event_id) for event_id in args.event_id]
    if args.require_five and (len(records) != 5 or len({row["fault_type"] for row in records}) != 1):
        parser.error("--require-five는 동일 장애 유형의 서로 다른 ID 5개가 필요합니다")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    exists = args.output.exists() and args.output.stat().st_size > 0
    with args.output.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        for record in records:
            row = {"experiment": args.experiment, **record,
                   "ai_response_seconds": "", "ai_status": "not_tested", "notes": args.notes}
            if not args.skip_ai:
                row["ai_response_seconds"], row["ai_status"] = measure_ai(args.api, record["event_id"])
            writer.writerow(row)
    print(f"기록 완료: {args.output} / {len(records)}개 이벤트")


if __name__ == "__main__":
    main()
