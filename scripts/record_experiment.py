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
        basis = "started_at (요청/메시지 오류 시작)"
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
    parser.add_argument("event_id", type=int)
    parser.add_argument("--db", type=Path, default=Path("backend/iot_faults.sqlite3"))
    parser.add_argument("--api", default="http://127.0.0.1:8000/api")
    parser.add_argument("--output", type=Path, default=Path("experiments/results.csv"))
    parser.add_argument("--experiment", required=True, help="실험 이름 (예: ethernet-reconnect-01)")
    parser.add_argument("--notes", default="")
    parser.add_argument("--skip-ai", action="store_true", help="AI 호출 없이 장애 시각만 기록")
    args = parser.parse_args()
    row = {"experiment": args.experiment, **event_record(args.db, args.event_id),
           "ai_response_seconds": "", "ai_status": "not_tested", "notes": args.notes}
    if not args.skip_ai:
        row["ai_response_seconds"], row["ai_status"] = measure_ai(args.api, args.event_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    exists = args.output.exists() and args.output.stat().st_size > 0
    with args.output.open("a", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        if not exists:
            writer.writeheader()
        writer.writerow(row)
    print(f"기록 완료: {args.output} / event_id={args.event_id} / ai_status={row['ai_status']}")


if __name__ == "__main__":
    main()
