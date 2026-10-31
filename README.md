# IoT 설비 통신 장애 대응 지원 시스템

MQTT 설비 메시지를 수집하고 통신 이상을 감지해, 운영자가 Vue 대시보드에서 장애 이력과 조치 내역을 확인하는 로컬 개발 프로젝트입니다. 현재 PC의 `RPI-01` 시뮬레이터로 Raspberry Pi 5 연동 전 통신 장애 시나리오를 검증합니다.

## 시스템 아키텍처

```text
PC 장치 시뮬레이터 (향후 Raspberry Pi 5 / STM32)
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

Vue 3, Vite, Element Plus, ECharts, Axios / Python FastAPI, Uvicorn, paho-mqtt / Mosquitto / SQLite. Ollama 기반 로컬 LLM과 Raspberry Pi 5 및 STM32 실기기 연동은 개발 예정입니다.

## 폴더 구조

```text
backend/         API(main.py), MQTT 수신(mqtt_worker.py), 감지(engine.py), DB(db.py), 설정(config.py)
frontend/        Vue 앱(src/), Vite 설정, npm 의존성
raspberry_pi/    PC용 MQTT 장치 시뮬레이터
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

## 구현 상태

**구현 완료:** MQTT 상태·요청·응답 수신, 규칙 기반 연결 시간 초과·응답 지연·메시지 형식 오류 감지, SQLite 장애·로그·조치 기록, FastAPI 조회 및 조치 API, Vue 대시보드·장치·장애 화면, PC 장치 시뮬레이터의 네 가지 모드. 테스트는 `.\.venv\Scripts\python.exe -m pytest -q`로 실행합니다.

**개발 예정:** Ollama 로컬 LLM을 이용한 장애 대응 지원, 지식 문서의 실제 저장·검색, Raspberry Pi 5 및 STM32 실기기 연동. 현재 지식 화면의 매뉴얼·사례와 AI 설명은 예시 데이터이며, 실제 LLM 연동 기능이 아닙니다.
