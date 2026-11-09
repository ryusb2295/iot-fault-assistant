const minutesAgo = (minutes) => new Date(Date.now() - minutes * 60_000).toISOString()

export const device = {
  id: 'RPI-01', name: 'PC 시뮬레이터', status: 'normal',
  lastReceivedAt: minutesAgo(0.08), intervalSeconds: 5,
  topic: 'facility/rpi-01/status',
  recentMessage: { device_id: 'RPI-01', status: 'running', temperature: 36.8, timestamp: minutesAgo(0.08) },
}

export const events = [
  { id: 'EVT-20261027-006', deviceId: 'RPI-01', type: 'message_timeout', occurredAt: minutesAgo(18), recoveredAt: null, status: 'open', summary: '상태 메시지 10초 이상 미수신', durationSeconds: null },
  { id: 'EVT-20261027-005', deviceId: 'RPI-01', type: 'response_delay', occurredAt: minutesAgo(95), recoveredAt: minutesAgo(91), status: 'resolved', summary: '요청·응답 소요 시간 3.8초', durationSeconds: 240 },
  { id: 'EVT-20261027-004', deviceId: 'RPI-01', type: 'format_error', occurredAt: minutesAgo(310), recoveredAt: minutesAgo(307), status: 'resolved', summary: 'status 필드 자료형 불일치', durationSeconds: 180 },
  { id: 'EVT-20261026-003', deviceId: 'RPI-01', type: 'message_timeout', occurredAt: minutesAgo(1380), recoveredAt: minutesAgo(1374), status: 'resolved', summary: '상태 메시지 10초 이상 미수신', durationSeconds: 360 },
  { id: 'EVT-20261026-002', deviceId: 'RPI-01', type: 'response_delay', occurredAt: minutesAgo(1720), recoveredAt: minutesAgo(1718), status: 'resolved', summary: '요청·응답 소요 시간 3.3초', durationSeconds: 120 },
  { id: 'EVT-20261025-001', deviceId: 'RPI-01', type: 'format_error', occurredAt: minutesAgo(2870), recoveredAt: minutesAgo(2868), status: 'resolved', summary: 'device_id 필드 누락', durationSeconds: 120 },
]

export const eventTypes = {
  message_timeout: '메시지 수신 중단', response_delay: '응답 지연', format_error: '메시지 형식 오류', system: '감시 시스템',
}

export const manuals = [
  { id: 'MAN-01', type: 'message_timeout', title: 'MQTT 상태 메시지 미수신 점검', updatedAt: '2026-10-20', steps: ['라즈베리파이 전원과 네트워크 연결을 확인합니다.', 'Mosquitto 브로커 실행 상태와 접속 정보를 확인합니다.', '장치 발행 주기와 topic 구독 상태를 확인합니다.'] },
  { id: 'MAN-02', type: 'response_delay', title: '요청·응답 지연 점검', updatedAt: '2026-10-20', steps: ['요청 시각과 응답 시각의 로그를 비교합니다.', '장치 CPU 사용률과 네트워크 지연을 확인합니다.', '동일 요청을 재시도하여 지연이 반복되는지 확인합니다.'] },
  { id: 'MAN-03', type: 'format_error', title: '메시지 JSON 형식 점검', updatedAt: '2026-10-20', steps: ['원본 payload가 유효한 JSON인지 확인합니다.', 'device_id, status, timestamp 필드의 존재 여부를 확인합니다.', '각 필드의 자료형과 발행 프로그램 버전을 확인합니다.'] },
]

export const cases = [
  { id: 'CASE-09', type: 'format_error', title: 'timestamp 시간대 정보 누락', date: '2026-10-26', action: '발행 코드의 timestamp를 시간대가 포함된 ISO 8601 형식으로 바꾸고 정상 수신을 확인함' },
  { id: 'CASE-08', type: 'response_delay', title: '응답 topic 오타로 인한 응답 미수신', date: '2026-10-25', action: '장치가 factory/RPI-01/respone로 발행하던 topic을 수정하고 request_id 매칭을 재확인함' },
  { id: 'CASE-07', type: 'message_timeout', title: '장치 IP 변경 후 브로커 주소 불일치', date: '2026-10-25', action: 'DHCP로 바뀐 브로커 주소를 MQTT_HOST에 반영하고 상태 메시지 재수신을 확인함' },
  { id: 'CASE-06', type: 'format_error', title: 'status 값에 허용되지 않는 문자열 사용', date: '2026-10-24', action: '발행 코드의 status 값을 RUNNING, IDLE, STOPPED, ERROR 중 하나로 고정함' },
  { id: 'CASE-05', type: 'response_delay', title: '로그 파일 과다 기록으로 인한 처리 지연', date: '2026-10-23', action: '장치의 디버그 로그 레벨을 낮추고 응답 시간이 3초 이내로 돌아온 것을 재측정함' },
  { id: 'CASE-04', type: 'message_timeout', title: '장치 발행 프로세스 비정상 종료', date: '2026-10-23', action: '발행 프로세스를 재시작하고 자동 재시작 설정을 추가한 뒤 10분간 수신을 관찰함' },
  { id: 'CASE-03', type: 'message_timeout', title: '브로커 재시작 이후 구독 복구', date: '2026-10-24', action: '브로커 서비스 상태 확인 후 구독 연결을 복구하고 5분간 수신을 관찰함' },
  { id: 'CASE-02', type: 'response_delay', title: '장치 부하로 인한 응답 지연', date: '2026-10-22', action: '장치의 중복 처리 작업을 종료하고 응답 시간을 재측정함' },
  { id: 'CASE-01', type: 'format_error', title: '발행 메시지의 필수 필드 누락', date: '2026-10-21', action: '발행 코드에서 device_id 필드를 추가하고 JSON 스키마를 재확인함' },
]

export const logs = [
  { time: minutesAgo(18.3), level: '정보', message: 'RPI-01 상태 메시지 수신' },
  { time: minutesAgo(18.1), level: '경고', message: '마지막 수신 이후 10초 경과' },
  { time: minutesAgo(18), level: '장애', message: '메시지 수신 중단 규칙 충족 · EVT-20261027-006 기록' },
]

export const recentActions = [
  { eventId: 'EVT-20261027-005', action: '응답 시간 재측정 후 정상 범위 확인', time: minutesAgo(91) },
  { eventId: 'EVT-20261027-004', action: 'status 필드 자료형 수정 후 재발행 확인', time: minutesAgo(307) },
  { eventId: 'EVT-20261026-003', action: 'MQTT 구독 연결 복구 및 수신 확인', time: minutesAgo(1374) },
]

export const chartPoints = [
  { label: '09:00', normal: 41, warning: 0, error: 0 }, { label: '10:00', normal: 43, warning: 1, error: 0 },
  { label: '11:00', normal: 42, warning: 0, error: 1 }, { label: '12:00', normal: 40, warning: 1, error: 0 },
  { label: '13:00', normal: 44, warning: 0, error: 0 }, { label: '14:00', normal: 41, warning: 1, error: 1 },
  { label: '15:00', normal: 43, warning: 0, error: 0 },
]
