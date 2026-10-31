import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = Path(os.getenv("IOT_DB_PATH", str(ROOT / "backend" / "iot_faults.sqlite3")))
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
REQUEST_INTERVAL = float(os.getenv("REQUEST_INTERVAL_SECONDS", "6"))
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "exaone3.5:2.4b")
OLLAMA_TIMEOUT_SECONDS = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
DEVICE_ID = "RPI-01"
STATUS_TOPIC = f"factory/{DEVICE_ID}/status"
REQUEST_TOPIC = f"factory/{DEVICE_ID}/request"
RESPONSE_TOPIC = f"factory/{DEVICE_ID}/response"
