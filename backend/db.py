import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import STATUS_TOPIC


def utc_now():
    return datetime.now(timezone.utc)


def utc_iso(value=None):
    return (value or utc_now()).astimezone(timezone.utc).isoformat(timespec="milliseconds")


class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def init_schema(self):
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'UNKNOWN',
                    last_seen TEXT,
                    recent_message TEXT
                );
                CREATE TABLE IF NOT EXISTS communication_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    validation_result TEXT NOT NULL,
                    event_id INTEGER,
                    FOREIGN KEY(event_id) REFERENCES fault_events(id)
                );
                CREATE TABLE IF NOT EXISTS fault_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    fault_type TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    recovered_at TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    description TEXT NOT NULL,
                    dedupe_key TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(device_id) REFERENCES devices(device_id)
                );
                CREATE UNIQUE INDEX IF NOT EXISTS uq_active_fault
                    ON fault_events(device_id, fault_type, dedupe_key)
                    WHERE recovered_at IS NULL;
                CREATE INDEX IF NOT EXISTS idx_fault_device_time ON fault_events(device_id, detected_at DESC);
                CREATE INDEX IF NOT EXISTS idx_log_device_time ON communication_logs(device_id, received_at DESC);
                CREATE TABLE IF NOT EXISTS action_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id INTEGER NOT NULL,
                    checklist TEXT NOT NULL,
                    action_text TEXT NOT NULL,
                    resolved INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(event_id) REFERENCES fault_events(id)
                );
            """)

    def ensure_device(self, device_id):
        with self.connection() as db:
            db.execute("INSERT OR IGNORE INTO devices(device_id) VALUES (?)", (device_id,))

    def get_device(self, device_id):
        with self.connection() as db:
            row = db.execute("SELECT * FROM devices WHERE device_id=?", (device_id,)).fetchone()
            return dict(row) if row else None

    def list_devices(self):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM devices ORDER BY device_id")]

    def update_device(self, device_id, status, last_seen=None, recent_message=None):
        self.ensure_device(device_id)
        with self.connection() as db:
            db.execute("""UPDATE devices SET status=?, last_seen=COALESCE(?, last_seen),
                recent_message=COALESCE(?, recent_message) WHERE device_id=?""",
                (status, last_seen, json.dumps(recent_message) if recent_message is not None else None, device_id))

    def add_log(self, device_id, topic, payload, result, at, event_id=None):
        with self.connection() as db:
            cursor = db.execute("""INSERT INTO communication_logs
                (device_id, topic, received_at, payload, validation_result, event_id)
                VALUES (?, ?, ?, ?, ?, ?)""", (device_id, topic, utc_iso(at), payload, result, event_id))
            return cursor.lastrowid

    def create_fault(self, device_id, fault_type, started_at, detected_at, description, dedupe_key=""):
        self.ensure_device(device_id)
        with self.connection() as db:
            db.execute("""INSERT OR IGNORE INTO fault_events
                (device_id, fault_type, started_at, detected_at, description, dedupe_key)
                VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, fault_type, utc_iso(started_at), utc_iso(detected_at), description, dedupe_key))
            row = db.execute("""SELECT id FROM fault_events WHERE device_id=? AND fault_type=?
                AND dedupe_key=? AND recovered_at IS NULL ORDER BY id DESC LIMIT 1""",
                (device_id, fault_type, dedupe_key)).fetchone()
            return row["id"] if row else None

    def recover_fault(self, device_id, fault_type, at, dedupe_key=None):
        with self.connection() as db:
            condition = "AND dedupe_key=?" if dedupe_key is not None else ""
            args = [utc_iso(at), device_id, fault_type]
            if dedupe_key is not None:
                args.append(dedupe_key)
            cursor = db.execute(f"""UPDATE fault_events SET recovered_at=?,
                status=CASE WHEN status='RESOLVED' THEN 'RESOLVED' ELSE 'RECOVERED' END
                WHERE device_id=? AND fault_type=? AND recovered_at IS NULL {condition}""", args)
            return cursor.rowcount

    def list_events(self, limit=200):
        with self.connection() as db:
            return [dict(row) for row in db.execute("""SELECT f.*,
                EXISTS(SELECT 1 FROM action_records a WHERE a.event_id=f.id) AS has_action
                FROM fault_events f ORDER BY f.detected_at DESC, f.id DESC LIMIT ?""", (limit,))]

    def get_event(self, event_id):
        with self.connection() as db:
            row = db.execute("""SELECT f.*,
                EXISTS(SELECT 1 FROM action_records a WHERE a.event_id=f.id) AS has_action
                FROM fault_events f WHERE f.id=?""", (event_id,)).fetchone()
            return dict(row) if row else None

    def get_active_fault_by_key(self, device_id, fault_type, dedupe_key):
        with self.connection() as db:
            row = db.execute("""SELECT id FROM fault_events WHERE device_id=? AND fault_type=?
                AND dedupe_key=? AND recovered_at IS NULL""",
                (device_id, fault_type, dedupe_key)).fetchone()
            return row["id"] if row else None

    def get_event_logs(self, event_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM communication_logs WHERE event_id=? ORDER BY received_at, id", (event_id,))]

    def add_action(self, event_id, checklist, action_text, resolved, at):
        with self.connection() as db:
            event = db.execute("SELECT id FROM fault_events WHERE id=?", (event_id,)).fetchone()
            if not event:
                return None
            cursor = db.execute("""INSERT INTO action_records(event_id, checklist, action_text, resolved, created_at)
                VALUES (?, ?, ?, ?, ?)""", (event_id, json.dumps(checklist), action_text, int(resolved), utc_iso(at)))
            if resolved:
                db.execute("UPDATE fault_events SET status='RESOLVED' WHERE id=?", (event_id,))
            return cursor.lastrowid

    def list_actions(self, limit=10):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM action_records ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))]

    def list_actions_for_event(self, event_id):
        with self.connection() as db:
            return [dict(row) for row in db.execute("SELECT * FROM action_records WHERE event_id=? ORDER BY created_at DESC, id DESC", (event_id,))]

    def dashboard_counts(self):
        with self.connection() as db:
            return {
                "devices": db.execute("SELECT COUNT(*) FROM devices").fetchone()[0],
                "normalDevices": db.execute("SELECT COUNT(*) FROM devices WHERE status='NORMAL'").fetchone()[0],
                "faults": db.execute("SELECT COUNT(*) FROM fault_events").fetchone()[0],
                "unrecoveredFaults": db.execute("SELECT COUNT(*) FROM fault_events WHERE recovered_at IS NULL").fetchone()[0],
                "unresolvedFaults": db.execute("SELECT COUNT(*) FROM fault_events WHERE status!='RESOLVED'").fetchone()[0],
            }

    def hourly_metrics(self, hours=7):
        end = utc_now().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(hours=hours - 1)
        with self.connection() as db:
            logs = [dict(row) for row in db.execute("""SELECT received_at, topic, validation_result
                FROM communication_logs WHERE received_at>=?
                AND ((topic=? AND validation_result='VALID') OR validation_result LIKE 'INVALID:%')""",
                (utc_iso(start), STATUS_TOPIC))]
            faults = [dict(row) for row in db.execute("SELECT detected_at FROM fault_events WHERE detected_at>=?", (utc_iso(start),))]
        points = []
        for offset in range(hours):
            hour = start + timedelta(hours=offset)
            next_hour = hour + timedelta(hours=1)
            normal = sum(1 for row in logs if row["topic"] == STATUS_TOPIC and row["validation_result"] == "VALID" and hour <= datetime.fromisoformat(row["received_at"]) < next_hour)
            warning = sum(1 for row in logs if row["validation_result"].startswith("INVALID:") and hour <= datetime.fromisoformat(row["received_at"]) < next_hour)
            error = sum(1 for row in faults if hour <= datetime.fromisoformat(row["detected_at"]) < next_hour)
            points.append({"label": hour.astimezone(timezone(timedelta(hours=9))).strftime("%H:%M"), "normal": normal, "warning": warning, "error": error})
        return points
