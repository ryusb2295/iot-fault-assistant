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

## 추가 확인
상태 topic 오류와 응답 topic 오류는 각각의 정상 메시지가 들어와야 복구된다. 원본 payload에 민감 정보가 있다면 외부로 전달하지 않는다.
