"""Independent MQTT subscriber and rule engine process.

Run from the project root: python -m backend.mqtt_worker
"""
import json
import logging
import time

import paho.mqtt.client as mqtt

from .config import DB_PATH, MQTT_HOST, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, REQUEST_INTERVAL, RESPONSE_TOPIC, REQUEST_TOPIC, STATUS_TOPIC
from .db import Repository
from .engine import FaultEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main():
    repository = Repository(DB_PATH)
    engine = FaultEngine(repository)
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="fault-monitor-rpi-01")
    if MQTT_PASSWORD and not MQTT_USERNAME:
        raise ValueError("MQTT_PASSWORD를 설정하려면 MQTT_USERNAME도 필요합니다")
    if MQTT_USERNAME:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD or None)

    def on_connect(client, _userdata, _flags, reason_code, _properties):
        if reason_code.is_failure:
            logger.error("MQTT 연결 실패: %s", reason_code)
            repository.update_worker_runtime(False)
            return
        repository.update_worker_runtime(True)
        with engine.lock:
            engine.last_valid_mono = time.monotonic()
        client.subscribe([(STATUS_TOPIC, 1), (RESPONSE_TOPIC, 1)])
        logger.info("MQTT 구독 시작: %s, %s", STATUS_TOPIC, RESPONSE_TOPIC)

    def on_disconnect(_client, _userdata, _flags, _reason_code, _properties):
        repository.update_worker_runtime(False)

    def on_message(_client, _userdata, message):
        if message.topic == STATUS_TOPIC:
            valid = engine.process_status(message.payload)
            logger.info("상태 메시지 %s", "유효" if valid else "형식 오류")
        elif message.topic == RESPONSE_TOPIC:
            valid = engine.process_response(message.payload)
            logger.info("응답 메시지 %s", "처리" if valid else "형식 오류")

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    logger.info("브로커 연결: %s:%s", MQTT_HOST, MQTT_PORT)
    client.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
    client.loop_start()
    next_request = time.monotonic() + 2
    try:
        while True:
            connected = client.is_connected()
            repository.update_worker_runtime(connected)
            if connected:
                engine.tick()
            if connected and time.monotonic() >= next_request:
                payload = engine.register_request()
                result = client.publish(REQUEST_TOPIC, json.dumps(payload), qos=1)
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    engine.cancel_request(payload["request_id"])
                    logger.error("요청 발행 실패: %s", result.rc)
                next_request = time.monotonic() + REQUEST_INTERVAL
            time.sleep(0.25)
    except KeyboardInterrupt:
        logger.info("MQTT 수신기를 종료합니다")
    finally:
        repository.update_worker_runtime(False)
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
