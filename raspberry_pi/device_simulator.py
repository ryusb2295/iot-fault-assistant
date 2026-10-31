"""RPI-01 MQTT device agent; runs on PC or Raspberry Pi OS."""
import argparse
import json
import logging
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

DEVICE_ID = "RPI-01"
STATUS_TOPIC = f"factory/{DEVICE_ID}/status"
REQUEST_TOPIC = f"factory/{DEVICE_ID}/request"
RESPONSE_TOPIC = f"factory/{DEVICE_ID}/response"
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)
CPU_TEMP_PATH = Path("/sys/class/thermal/thermal_zone0/temp")


def timestamp():
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def cpu_temperature_c(path=CPU_TEMP_PATH):
    """Optional Raspberry Pi CPU temperature; never blocks status publishing."""
    try:
        return round(int(path.read_text(encoding="ascii").strip()) / 1000, 1)
    except (OSError, ValueError):
        return None


def status_payload(sequence, temperature=None):
    payload = {"device_id": DEVICE_ID, "status": "RUNNING",
               "sequence": sequence, "timestamp": timestamp()}
    if temperature is not None:
        payload["cpu_temp_c"] = temperature
    return payload


def main():
    parser = argparse.ArgumentParser(description="PC/Raspberry Pi용 RPI-01 MQTT 장치 에이전트")
    parser.add_argument("--mode", choices=["normal", "disconnect", "delay", "invalid"], default="normal")
    parser.add_argument("--host", default=os.getenv("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", "1883")))
    args = parser.parse_args()
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="simulator-rpi-01")
    username = os.getenv("MQTT_USERNAME", "")
    password = os.getenv("MQTT_PASSWORD", "")
    if password and not username:
        parser.error("MQTT_PASSWORD를 설정하려면 MQTT_USERNAME도 필요합니다")
    if username:
        client.username_pw_set(username, password or None)
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    timers = []

    def on_connect(client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            logger.error("MQTT 연결 실패: %s", reason_code)
            return
        client.subscribe(REQUEST_TOPIC, qos=1)
        logger.info("%s 모드 시작 · 요청 구독: %s", args.mode.upper(), REQUEST_TOPIC)

    def on_message(_client, _userdata, message):
        try:
            request = json.loads(message.payload)
            request_id = request["request_id"]
        except (ValueError, KeyError, TypeError):
            logger.warning("잘못된 요청 payload 무시")
            return

        def respond():
            payload = {"device_id": DEVICE_ID, "request_id": request_id, "timestamp": timestamp()}
            client.publish(RESPONSE_TOPIC, json.dumps(payload), qos=1)
            logger.info("응답 발행: %s", request_id)

        if args.mode == "delay":
            timer = threading.Timer(4.2, respond)
            timer.daemon = True
            timers.append(timer)
            timer.start()
        else:
            respond()

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect_async(args.host, args.port, keepalive=30)
    client.loop_start()
    sequence = 0
    try:
        while True:
            if client.is_connected() and args.mode != "disconnect":
                sequence += 1
                if args.mode == "invalid":
                    if sequence % 3 == 1:
                        payload = json.dumps({"device_id": DEVICE_ID, "status": "RUNNING", "sequence": sequence})
                    elif sequence % 3 == 2:
                        payload = json.dumps({"device_id": DEVICE_ID, "status": 123,
                                              "sequence": "invalid", "timestamp": timestamp()})
                    else:
                        payload = "{invalid json"
                else:
                    payload = json.dumps(status_payload(sequence, cpu_temperature_c()))
                client.publish(STATUS_TOPIC, payload, qos=1)
                logger.info("상태 발행 #%s: %s", sequence, args.mode)
            time.sleep(2)
    except KeyboardInterrupt:
        logger.info("시뮬레이터를 종료합니다")
    finally:
        for timer in timers:
            timer.cancel()
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
