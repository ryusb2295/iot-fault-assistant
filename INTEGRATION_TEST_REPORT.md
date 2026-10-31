# End-to-End 통합 테스트 보고서

- 실행일: 2026-10-31 (Asia/Seoul)
- 대상: `C:\dev\iot-fault-assistant`의 현재 작업 트리 (미커밋 RAG 변경 포함)
- 격리 환경: 기존 1883/8000 프로세스는 유지. 테스트용 Mosquitto `127.0.0.1:1884`, FastAPI `127.0.0.1:8001`, Vite `127.0.0.1:5173`, 임시 DB `%TEMP%\iot-fault-e2e\integration.sqlite3` 사용. Ollama `127.0.0.1:11434`는 기존 로컬 서버 사용.
- 브라우저: 설치된 Chrome을 Playwright로 headless 실행. 브라우저 연결 도구는 접근 호스트 오류로 사용하지 못해 Playwright를 `%TEMP%\iot-e2e-tools`에 별도 설치함.

## 실행 환경

| 항목 | 결과 | 확인 내용 |
| --- | --- | --- |
| Mosquitto | PASS | 1884 포트 TCP 연결 및 worker 구독 로그 확인 |
| FastAPI | PASS | 8001 `/api/health` 200, `/api/manuals` 200 및 문서 3개 |
| MQTT Worker | PASS | 1884 연결·구독, 상태/응답 로그 처리 확인 |
| 장치 시뮬레이터 | PASS | `normal`, `delay`, `invalid` 모드 실행 및 실제 이벤트 생성 |
| Ollama | PASS | 11434 `/api/tags` 응답 및 `exaone3.5:2.4b` 실제 한국어 응답 확인 |
| Vue 3 | PASS | 5173 Vite 실행, Chrome에서 대시보드·상세 화면 표시 |

### 실행 명령

```powershell
& 'C:\Program Files\mosquitto\mosquitto.exe' -p 1884 -v
$env:IOT_DB_PATH = Join-Path $env:TEMP 'iot-fault-e2e\integration.sqlite3'
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001
$env:IOT_DB_PATH = Join-Path $env:TEMP 'iot-fault-e2e\integration.sqlite3'
$env:MQTT_PORT = '1884'
.\.venv\Scripts\python.exe -m backend.mqtt_worker
$env:MQTT_PORT = '1884'
.\.venv\Scripts\python.exe -m raspberry_pi.device_simulator --mode normal
# 시나리오 전환 시 위 프로세스를 종료하고 --mode delay 또는 --mode invalid 사용
$env:VITE_API_BASE_URL = 'http://127.0.0.1:8001/api'
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

각 서버·worker·시뮬레이터는 별도 프로세스로 실행했다. Ollama는 기존 `ollama serve` 프로세스를 사용했다. 기존 8000 서버는 이전 코드로 실행 중이어서 새 API가 404였으며 테스트에 사용하지 않았다.

## 브라우저 전체 시나리오

| 번호 | 결과 | 실제 관찰 |
| --- | --- | --- |
| 1 정상 MQTT 수신 | PASS | 대시보드 `RPI-01`, `통신 정상`, 최근 수신 시각 및 `API 연결 정상` 표시 |
| 2 상태 중단 | PASS | 시뮬레이터 종료 후 `CONNECTION_TIMEOUT` 이벤트 8 생성, 초기 `unrecovered` |
| 3 이력·상세 | PASS | `/events/8`에 실제 규칙 판정, 연결 로그와 상태 표시 |
| 4 AI API | PASS | 브라우저 네트워크 응답 `/api/events/8/ai-guidance` 200 |
| 5 한국어 답변 | PASS | `Ollama 실제 응답` 및 가능한 원인·점검 순서·추가 확인 사항 표시 |
| 6 문서 위치 | PASS | `MQTT 상태 메시지 미수신 점검`, 절과 `manuals/connection_timeout.md:12–15` 등 4개 근거 표시 |
| 7 설명·근거 일치 | PASS | 최종 재검증에서 위 매뉴얼의 원인 후보·점검 항목과 답변을 대조. 초기 답변의 근거 없는 마지막 정상 수신 시각 단정은 프롬프트 수정 후 재호출에서 발견되지 않음. 생성형 답변이므로 모든 미래 응답의 사실 일치를 보장하는 테스트는 아님 |
| 8 체크리스트·조치 | PASS | 첫 항목 선택, 조치 문장 입력, 조치 완료 선택·저장 알림. API에서 `checklist:[0]`, `actionStatus:completed` 확인 |
| 9 통신 재개 | PASS | normal 시뮬레이터 재실행 후 이벤트 8 `recoveryStatus:recovered`, 복구 시각 표시 |
| 10 SQLite 저장 | PASS | `fault_events` 이벤트 8은 `RESOLVED` 및 `recovered_at` 기록, `action_records`에 체크 항목·문장·완료 값 저장 |

## 추가 테스트

| 항목 | 결과 | 관찰 |
| --- | --- | --- |
| RESPONSE_DELAY | PASS | `delay` 시뮬레이터로 이벤트 생성. 브라우저 상세에서 응답 지연·실제 AI 응답·`response_delay.md` 근거 표시. 복구된 이벤트 216은 `복구됨`·`미조치` |
| INVALID_MESSAGE | PASS | `invalid` 시뮬레이터로 이벤트 218 생성. 브라우저 상세에서 형식 오류·실제 AI 응답·`invalid_message.md` 근거 표시. normal 재개 뒤 `복구됨`·`미조치` |
| Ollama 미실행 대응 | PASS | 실제 Ollama 프로세스는 중단하지 않고 테스트 앱의 주소를 미사용 11435로 지정. AI API 200 `unavailable`, health 200, 장애 목록 조회 정상 |
| 근거 없음 | PASS | 테스트에서 검색 결과를 빈 목록으로 주입. API `no_evidence`, `origin:none`, 출처 빈 목록이며 모델 호출 없음 |
| API/Mock 혼용 | PASS | 실제 모드에는 규칙 판정·Ollama 응답 표시, 조치 사례는 예시라고 명시. 별도 5174 Mock 모드에서 AI 요청 0건, 실제 응답 표시 없음 |
| 복구/조치 분리 | PASS | 이벤트 8은 조치 완료·통신 미복구 상태를 먼저 확인한 뒤 통신 복구. 이벤트 216/218은 통신 복구·미조치 상태를 브라우저에서 확인 |
| 브라우저 콘솔 | PASS | Playwright에서 관찰한 console error와 pageerror 0건 |
| FastAPI 오류 | PASS | 테스트 FastAPI stderr에서 기동 로그만 확인, 예외 traceback 없음 |
| Vue 빌드 | PASS | `npm run build` 성공. 기존 번들 크기 경고는 남음 |
| 백엔드 회귀 | PASS | `.\.venv\Scripts\python.exe -m pytest -q`: 27 passed, 1 StarletteDeprecationWarning |
| 실제 하드웨어 | NOT TESTED | Raspberry Pi 5 / STM32 연동은 이번 범위 밖 |

## 발견 오류와 수정

1. 초기 실제 AI 답변이 로그에 없는 마지막 정상 수신 시각을 구체적으로 단정했다. `backend/rag.py`의 프롬프트에 시각·장치·브로커 상태를 근거 없이 특정하지 말라는 조건을 추가하고 생성 길이를 늘렸다. 수정 후 현재 코드로 실제 Ollama 재호출 및 브라우저 표시를 다시 확인했다.
2. Ollama 호출 실패가 프론트엔드의 공통 API 연결 상태를 오류로 바꿀 수 있어 `frontend/src/services/api.js`에서 AI 요청 오류를 모니터링 연결 상태와 분리했다.
3. 근거 문서가 없을 때 API가 모델을 호출하지 않는 회귀 검증을 `tests/test_rag.py`에 추가했다.

## 최종 상태

`git diff --check`는 공백 오류 없이 통과했다. 모든 변경은 로컬 작업 트리에 있으며 아직 Git Commit/Push는 하지 않았다. 보고서는 테스트용 임시 DB와 브라우저 도구를 저장소에 포함하지 않는다. 기존 1883/8000 서비스와 사용자 데이터는 변경하지 않았다.
검증 후 테스트용 1884/8001/5173/5174 프로세스는 종료했고 기존 1883/8000/11434 서비스의 연결은 유지됨을 확인했다.
