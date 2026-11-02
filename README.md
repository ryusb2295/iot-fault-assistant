# IoT 설비 통신 장애 대응 지원 시스템

MQTT 설비 메시지를 수집하고 통신 이상을 감지해, 운영자가 Vue 대시보드에서 장애 이력과 조치 내역을 확인하는 로컬 개발 프로젝트입니다. PC의 `RPI-01` 시뮬레이터로 통신 장애 시나리오를 검증했으며, Raspberry Pi 5 실기기 실행 절차는 [연동 가이드](RASPBERRY_PI_SETUP.md)에 정리했습니다.

## 시스템 아키텍처

```text
PC 장치 시뮬레이터 또는 Raspberry Pi 5 에이전트 (STM32는 향후 연동)
    ↕ MQTT: factory/RPI-01/{status,request,response}
Mosquitto broker
    ↕
backend.mqtt_worker → 규칙 기반 감지 → SQLite
                                       ↕
                              FastAPI (/api)
                                       ↕
                              Vue 3 + Vite 대시보드
```

MQTT 수신 프로세스와 FastAPI 서버는 별도로 실행하며 같은 SQLite 파일을 사용합니다.

## 기술 스택

Vue 3, Vite, Element Plus, ECharts, Axios / Python FastAPI, Uvicorn, paho-mqtt, httpx / Mosquitto / SQLite / Ollama 로컬 LLM. Raspberry Pi 5 및 STM32 실기기 연동은 개발 예정입니다.

## 폴더 구조

```text
backend/         API(main.py), MQTT 수신(mqtt_worker.py), 감지(engine.py), DB(db.py), 설정(config.py)
frontend/        Vue 앱(src/), Vite 설정, npm 의존성
raspberry_pi/    PC/Raspberry Pi OS 공용 MQTT 장치 에이전트
scripts/         실험 시각·AI 응답 시간 CSV 기록
experiments/     실험 결과 기록 양식 (실제 결과는 Git 제외)
tests/           백엔드 테스트
requirements.txt
.env.example     환경변수 예시 (자동 로드되지 않음)
```

## 개발 환경 설정

Python 3.12, Node.js 22.18 이상 또는 24.12 이상, npm, Mosquitto가 필요합니다. Windows PowerShell에서 프로젝트 루트를 기준으로 실행합니다.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
cd frontend
npm ci
cd ..
```

기본 MQTT 주소는 `localhost:1883`, DB는 `backend/iot_faults.sqlite3`입니다. 필요하면 각 PowerShell 창에서 `$env:MQTT_HOST`, `$env:MQTT_PORT`, `$env:REQUEST_INTERVAL_SECONDS`, `$env:IOT_DB_PATH`를 설정하세요. `.env.example`은 참고용이며 Python 코드가 자동으로 읽지 않습니다. 프론트엔드 API 주소를 바꿀 때만 `frontend/.env.local`에 `VITE_API_BASE_URL=http://127.0.0.1:8000/api`를 설정하세요. 기본값 `/api`는 Vite 프록시를 사용합니다.

## 실행 방법

각 명령은 별도 PowerShell 창에서 프로젝트 루트에서 실행합니다.

```powershell
# 1. 설치된 Mosquitto 실행 (기본 설치 경로)
& 'C:\Program Files\mosquitto\mosquitto.exe' -v

# 2. MQTT 수신 및 장애 감지
.\.venv\Scripts\python.exe -m backend.mqtt_worker

# 3. FastAPI
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000

# 4. 장치 시뮬레이터
.\.venv\Scripts\python.exe -m raspberry_pi.device_simulator --mode normal

# 5. Vue 프론트엔드
cd frontend
npm run dev
```

브라우저에서 Vite가 안내하는 주소(기본 `http://localhost:5173`)로 접속합니다. API 문서는 `http://127.0.0.1:8000/docs`, 상태 확인은 `http://127.0.0.1:8000/api/health`입니다. Mosquitto 설치 경로가 다르면 실제 경로를 사용하세요. 시뮬레이터의 `--mode`는 `normal`, `disconnect`, `delay`, `invalid` 중 하나입니다. Raspberry Pi 등 다른 호스트에서 시뮬레이터를 실행할 때는 `--host`에 브로커 IP를 지정할 수 있습니다.

`/api/health`의 `status`는 FastAPI 요청 처리 상태입니다. `worker`, `broker`, `deviceHeartbeat`, `overall`은 별도 상태입니다. Worker의 DB heartbeat가 3초 넘게 갱신되지 않으면 `stopped`로 표시하고, 이때 Broker·장치 상태는 `unknown`입니다. Worker가 살아 있으나 Broker 연결이 끊기면 장치 상태도 `unknown`이며 장치 고장으로 단정하지 않습니다. Broker가 연결된 상태에서 유효한 장치 상태 메시지가 10초 이상 없으면 `timeout`입니다. 장치 ID와 Topic은 PC 실습에서도 기존 `RPI-01`, `factory/RPI-01/*`를 유지합니다.

실험 기록은 운영 DB 대신 `IOT_DB_PATH`로 분리한 실습 DB를 사용하세요. `scripts/record_experiment.py`에 동일 장애 유형의 서로 다른 이벤트 ID 5개와 `--require-five`를 주면 각 실행을 CSV 한 행으로 기록합니다. `CONNECTION_TIMEOUT`은 마지막 유효 상태 메시지 수신부터 탐지까지, `RESPONSE_DELAY`는 요청 등록부터 지연 탐지까지 측정합니다. `INVALID_MESSAGE`는 수신과 판정이 같은 시각 해상도에 기록되므로 소요 시간을 빈 값과 `측정 불가`로 남깁니다. AI 시간은 HTTP 요청 시작부터 응답 종료까지의 벽시계 시간이며 `ai_status=ready`인 행만 실제 AI 응답 성공으로 해석합니다. CSV의 빈 값과 요청 오류는 0초 처리로 해석하지 않습니다. 실험 CSV는 Git에서 제외합니다.

## 구현 상태

**구현 완료:** MQTT 상태·요청·응답 수신, 규칙 기반 연결 시간 초과·응답 지연·메시지 형식 오류 감지, SQLite 장애·로그·조치 기록, FastAPI 조회 및 조치 API, Vue 대시보드·장치·장애 화면, PC 장치 시뮬레이터의 네 가지 모드. 테스트는 `.\.venv\Scripts\python.exe -m pytest -q`로 실행합니다.

**구현 완료:** `manuals/`의 장애 유형별 실습용 매뉴얼 검색, 실제 장애 로그와 검색 문서를 참고하는 Ollama AI 점검 안내 API, Vue 장애 상세 화면의 AI 응답 및 문서 제목·절·줄 위치 표시. AI 응답은 규칙 엔진의 판정과 별개입니다. 조치 사례는 여전히 실습용 예시 데이터입니다.

**실기기 준비 완료:** Raspberry Pi OS용 MQTT 인증·재연결·선택적 CPU 온도 발행 코드와 설치·실험 가이드. 실제 Pi Ethernet 단절·재연결 검증은 아직 수행하지 않았습니다.

**개발 예정:** 실제 Raspberry Pi 5 실기기 연결 검증, STM32 연동, 실제 운영 매뉴얼과 조치 사례 축적.

## 로컬 AI 점검 안내

Ollama를 설치해 서버를 실행하고 `exaone3.5:2.4b` 모델을 준비합니다. 이미 Ollama가 실행 중이면 서버 명령은 생략합니다.

```powershell
ollama serve
ollama pull exaone3.5:2.4b
ollama list
```

기본 API 주소는 `http://127.0.0.1:11434`입니다. 다른 주소나 모델을 사용하려면 FastAPI 실행 창에서 `$env:OLLAMA_BASE_URL`, `$env:OLLAMA_MODEL`, `$env:OLLAMA_TIMEOUT_SECONDS`를 설정합니다. 기본 생성 제한은 60초입니다. Ollama 서버가 없거나 시간 초과가 나면 AI 안내만 사용 불가로 표시하며, MQTT 수신과 장애 판정·조회 API는 계속 작동합니다. 상세 화면의 **다시 생성** 버튼으로 재시도할 수 있습니다.

`GET /api/manuals`는 실제 `manuals/*.md` 문서에서 점검 순서를 읽습니다. `GET /api/events/{id}/ai-guidance`는 해당 장애 유형의 문서 절을 검색하고 연결된 로그와 함께 로컬 모델에 전달합니다. 응답의 `sources`는 검색된 문서의 제목, 절, 파일 및 줄 위치를 담습니다. 매뉴얼이 없으면 모델을 호출하지 않고 근거 부족으로 답합니다. AI 문장은 가능한 점검 가설이므로 현장 조치와 복구 판단은 실제 로그로 확인해야 합니다.
