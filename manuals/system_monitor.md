# 감시 시스템(Broker·Worker) 상태 점검

장애 유형: 해당 없음 (감시 시스템 자체 점검)

## 판정과 범위
`/api/health`는 API 처리 상태와 별도로 `worker`, `broker`, `deviceHeartbeat`, `overall`을 보고한다. Worker가 DB에 남기는 heartbeat가 3초 넘게 갱신되지 않으면 `worker`는 stopped가 되고 Broker와 장치 상태는 unknown으로 표시한다. 이 상태는 장치 장애가 아니므로 장애 이력에 기록하지 않는다.

## 가능한 원인
MQTT Worker 프로세스 종료, Mosquitto 미실행 또는 포트(1883) 충돌, `MQTT_HOST`·`MQTT_PORT` 설정 오류, Worker와 FastAPI가 서로 다른 `IOT_DB_PATH`를 사용하는 경우가 가능하다.

## 점검 순서
1. `/api/health` 응답에서 `worker`, `broker`, `deviceHeartbeat` 값을 각각 확인한다.
2. `worker`가 stopped이면 MQTT Worker 프로세스가 실행 중인지 확인하고 다시 시작한다.
3. `broker`가 disconnected이면 Mosquitto 실행 상태와 1883 포트 사용 여부를 확인한다.
4. Worker와 FastAPI 실행 창의 `IOT_DB_PATH`가 같은 파일을 가리키는지 확인한다.

## 다른 장애와 구분
감시 시스템이 멈춘 동안에는 장치 메시지를 받을 수 없으므로 장치가 정상이어도 상태 메시지 미수신처럼 보인다. 시스템은 이때 장치 상태를 unknown으로 두고 CONNECTION_TIMEOUT을 만들지 않는다. Broker와 Worker가 정상인데 장치 메시지만 없을 때 장치 장애로 판정한다.

## 복구 판단
Worker heartbeat가 다시 갱신되고 Broker 연결이 connected로 바뀌면 감시가 재개된다. 그 뒤 장치 상태 메시지가 수신되면 `deviceHeartbeat`가 normal로 돌아온다.

## 추가 확인
발표나 실험 전에는 `scripts/start_demo.ps1`로 모든 프로세스를 같은 DB 경로로 함께 시작하면 경로 불일치를 줄일 수 있다.
