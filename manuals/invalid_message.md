# MQTT 메시지 형식 오류 점검

장애 유형: INVALID_MESSAGE

## 판정과 범위
규칙 엔진은 상태 또는 응답 payload의 JSON 파싱과 필수 필드 검증이 실패하면 INVALID_MESSAGE를 기록한다. 오류 로그는 잘못된 필드나 자료형을 좁히는 근거이며 발행 코드의 정확한 결함 위치까지 증명하지는 않는다.

## 가능한 원인
깨진 JSON, 필수 `device_id`·`timestamp`·`sequence`·`status` 또는 응답 `request_id` 누락, 잘못된 자료형, 발행 프로그램의 메시지 계약 변경이 가능하다.

## 점검 순서
1. 장애에 연결된 로그의 topic, 검증 결과와 원본 payload를 확인한다.
2. payload가 유효한 JSON인지 확인하고 누락된 필수 필드를 찾는다.
3. 상태 메시지의 `device_id`, `status`, `sequence`, `timestamp` 및 응답 메시지의 `request_id` 자료형을 실제 수신 코드와 대조한다.
4. 발행 프로그램 버전과 메시지 계약을 확인한 뒤 정상 payload가 수신되는지 검증한다.

## 관련 로그 예시
검증 결과는 `INVALID:`로 시작하고 실패 이유가 붙는다. 예를 들어 `INVALID: JSON 문법 오류`, `INVALID: status 누락, 자료형 오류 또는 허용되지 않는 값`, `INVALID: sequence 누락 또는 음수가 아닌 정수 자료형 오류`, `INVALID: timestamp에 시간대 정보가 필요합니다`, `INVALID: request_id 누락 또는 자료형 오류`가 있다. 허용되는 status 값은 RUNNING, IDLE, STOPPED, ERROR다.

## 다른 장애와 구분
형식 오류는 메시지가 도착했지만 내용이 계약과 다른 경우다. 메시지가 아예 오지 않으면 CONNECTION_TIMEOUT, 형식은 맞지만 응답이 늦으면 RESPONSE_DELAY다. 형식이 잘못된 상태 메시지는 유효 메시지로 세지 않으므로, 오류가 10초 넘게 이어지면 CONNECTION_TIMEOUT도 함께 기록될 수 있다.

## 복구 판단
같은 topic에서 형식이 올바른 메시지가 다시 수신되면 시스템이 복구 시각을 자동으로 기록한다. 상태 topic의 오류는 정상 상태 메시지로, 응답 topic의 오류는 정상 응답으로만 복구된다.

## 조치 기록 작성 요령
오류 로그의 검증 결과 문구, 누락되거나 잘못된 필드, 수정한 발행 코드나 설정, 정상 payload가 다시 수신된 시각을 적는다. 수정 전후 payload 예시를 함께 남기면 같은 오류가 반복될 때 바로 비교할 수 있다.

## 추가 확인
상태 topic 오류와 응답 topic 오류는 각각의 정상 메시지가 들어와야 복구된다. 원본 payload에 민감 정보가 있다면 외부로 전달하지 않는다.
