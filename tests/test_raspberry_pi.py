import json
import csv
import sys
from datetime import datetime, timedelta, timezone

from backend.db import Repository
from backend.engine import FaultEngine
from backend.main import device_name
from raspberry_pi.device_simulator import board_model, cpu_temperature_c, status_payload
from scripts.record_experiment import event_record, main


def test_optional_pi_temperature_preserves_status_schema(tmp_path):
    sensor = tmp_path / "temp"
    sensor.write_text("48321\n", encoding="ascii")
    assert cpu_temperature_c(sensor) == 48.3
    payload = status_payload(7, cpu_temperature_c(sensor))
    assert payload["cpu_temp_c"] == 48.3
    assert payload["device_id"] == "RPI-01"
    assert payload["status"] == "RUNNING"
    assert payload["sequence"] == 7
    assert "timestamp" in payload
    engine = FaultEngine(Repository(tmp_path / "faults.sqlite3"))
    assert engine.process_status(json.dumps(payload).encode()) is True
    sensor.write_text("invalid", encoding="ascii")
    assert cpu_temperature_c(sensor) is None
    assert "cpu_temp_c" not in status_payload(8, cpu_temperature_c(sensor))


def test_board_model_marks_real_raspberry_pi(tmp_path):
    model_file = tmp_path / "model"
    model_file.write_bytes(b"Raspberry Pi 5 Model B Rev 1.0\x00")
    model = board_model(model_file)
    assert model == "Raspberry Pi 5 Model B Rev 1.0"
    assert board_model(tmp_path / "missing") is None
    payload = status_payload(3, 51.2, model)
    assert payload["model"] == model
    assert "model" not in status_payload(4, None, None)
    engine = FaultEngine(Repository(tmp_path / "faults.sqlite3"))
    assert engine.process_status(json.dumps(payload).encode()) is True
    assert device_name(model) == "Raspberry Pi 5"
    assert device_name(None) == "PC 시뮬레이터"


def test_experiment_latency_uses_last_valid_status_for_connection_timeout(tmp_path):
    repo = Repository(tmp_path / "faults.sqlite3")
    at = datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc)
    repo.add_log("RPI-01", "factory/RPI-01/status", "{}", "VALID", at)
    event_id = repo.create_fault("RPI-01", "CONNECTION_TIMEOUT", at + timedelta(seconds=10),
                                 at + timedelta(seconds=10.25), "미수신")
    row = event_record(repo.path, event_id)
    assert row["detection_seconds"] == 10.25
    assert row["latency_basis"] == "마지막 유효 상태 수신 시각"
    assert row["recovered_at_utc"] == ""


def test_experiment_cli_writes_csv_without_calling_ai(tmp_path, monkeypatch):
    repo = Repository(tmp_path / "faults.sqlite3")
    at = datetime(2026, 10, 31, 11, 0, tzinfo=timezone.utc)
    event_id = repo.create_fault("RPI-01", "INVALID_MESSAGE", at, at, "JSON 오류")
    output = tmp_path / "results.csv"
    monkeypatch.setattr(sys, "argv", ["record_experiment.py", str(event_id), "--db", str(repo.path),
                                   "--output", str(output), "--experiment", "invalid-01", "--skip-ai"])
    main()
    with output.open(encoding="utf-8-sig", newline="") as file:
        row = next(csv.DictReader(file))
    assert row["experiment"] == "invalid-01"
    assert row["fault_type"] == "INVALID_MESSAGE"
    assert row["detection_seconds"] == ""
    assert "측정 불가" in row["latency_basis"]
    assert row["ai_status"] == "not_tested"
