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
# 저사양 PC(CPU 전용)에서는 생성 길이와 근거 절 수를 줄여 응답 시간을 낮출 수 있다
OLLAMA_NUM_PREDICT = int(os.getenv("OLLAMA_NUM_PREDICT", "700"))
AI_EVIDENCE_LIMIT = int(os.getenv("AI_EVIDENCE_LIMIT", "6"))
DEVICE_ID = "RPI-01"
STATUS_TOPIC = f"factory/{DEVICE_ID}/status"
REQUEST_TOPIC = f"factory/{DEVICE_ID}/request"
RESPONSE_TOPIC = f"factory/{DEVICE_ID}/response"
