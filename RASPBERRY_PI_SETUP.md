# Raspberry Pi 5 실기기 연동 및 장애 실험 가이드

이 문서는 `raspberry_pi/device_simulator.py`를 Raspberry Pi OS에서 실행하는 절차다. PC와 Pi는 기존 `factory/RPI-01/{status,request,response}` topic과 JSON 계약을 그대로 사용한다. **실기기 Ethernet 실험 결과는 아직 기록되지 않았다.** 실제 장치를 연결한 뒤 아래 절차로 확인한다.

## 1. 네트워크와 브로커 준비 (PC)

PC와 Pi를 같은 실험용 LAN에 연결하고 PC의 IPv4 주소를 `ipconfig`로 확인한다. Pi에서 해당 PC 주소로 통신 가능한지 `ping <PC_IP>`로 확인한다. PC 방화벽에서 테스트용 MQTT 포트(아래 예시는 1884/TCP)를 **Pi 주소에만** 허용한다. 기존 1883 브로커 설정이나 실행 중인 서비스를 바꾸지 않으려면 별도 1884 listener를 사용한다.

Mosquitto 인증 파일과 설정은 저장소 밖에 둔다. 아래는 PC의 별도 실험 브로커 설정 예시다. `password_file`에는 실제 PC의 절대 경로를 적는다. `mosquitto_passwd`가 암호를 대화형으로 묻도록 실행하고, 암호나 해시 파일을 Git에 넣지 않는다.

```text
# 예: PC 로컬 전용 설정 파일 (저장소 밖)
listener 1884 0.0.0.0
allow_anonymous false
password_file C:/경로/외부설정/mosquitto.passwd
```

```powershell
& 'C:\Program Files\mosquitto\mosquitto_passwd.exe' -c 'C:\경로\외부설정\mosquitto.passwd' rpi01
& 'C:\Program Files\mosquitto\mosquitto.exe' -c 'C:\경로\외부설정\mosquitto.conf' -v
```

PC의 MQTT Worker와 Pi 에이전트에는 **같은 브로커 주소·포트·계정**을 설정한다. 현재 코드의 Worker와 Pi는 인증을 선택적으로 사용한다. 인증 없는 기존 로컬 브로커는 환경변수를 비워 두면 그대로 동작한다. 암호는 셸 기록이나 스크린샷에 남기지 말고 각 실행 환경에 안전하게 주입한다. MQTT는 이 예시에서 TLS를 사용하지 않으므로 신뢰할 수 있는 격리 LAN에서만 실행한다.

## 2. PC 서비스 실행

프로젝트 루트에서 별도 PowerShell 창으로 실행한다. PC용 `device_simulator.py`가 이미 실행 중이면 먼저 종료한다. FastAPI와 Vue, Ollama는 기존 방식으로 실행한다.

```powershell
$env:MQTT_HOST = '127.0.0.1'
$env:MQTT_PORT = '1884'
$env:MQTT_USERNAME = 'rpi01'
$env:MQTT_PASSWORD = Read-Host 'MQTT password'
.\.venv\Scripts\python.exe -m backend.mqtt_worker
```

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

```powershell
cd frontend
npm run dev
```

Ollama는 PC에서 `ollama serve`와 `ollama list`로 확인한다. 이 서비스는 Pi에 설치할 필요가 없다. API와 Vue는 PC의 localhost에서 접근한다. MQTT Worker는 DB를 통해 API와 데이터를 공유한다.

## 3. Raspberry Pi OS 설치와 실행

Pi에 Python 3, `python3-venv`, Git을 준비하고 이 Private 저장소를 인증된 방식으로 복제하거나 프로젝트 파일을 안전하게 복사한다. Pi에서 프로젝트 루트를 기준으로 실행한다. Pi에는 프론트엔드와 Ollama를 설치하지 않는다.

```bash
sudo apt update
sudo apt install -y python3 python3-venv git
python3 -m venv .venv
./.venv/bin/python -m pip install 'paho-mqtt>=2.1,<3.0'
```

```bash
export MQTT_HOST='<PC_IP>'
export MQTT_PORT=1884
export MQTT_USERNAME='rpi01'
read -rsp 'MQTT password: ' MQTT_PASSWORD; echo
export MQTT_PASSWORD
./.venv/bin/python -m raspberry_pi.device_simulator --mode normal
```

`MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD`는 환경변수다. `--host`, `--port`는 주소·포트를 일시적으로 덮어쓴다. Pi의 `/sys/class/thermal/thermal_zone0/temp`를 읽을 수 있으면 정상 상태 JSON에 선택적 `cpu_temp_c` 숫자를 추가한다. 읽을 수 없으면 기존 필드만 발행한다. 인증 거절은 연결 로그에 남으며 상태 메시지를 발행하지 않는다.

**중복 실행 금지:** PC 시뮬레이터와 Pi 에이전트는 모두 장치 ID `RPI-01` 및 MQTT Client ID `simulator-rpi-01`을 사용한다. 동시에 실행하면 브로커가 한 연결을 끊고 재접속 경쟁이 발생한다. Pi를 시작하기 전에 PC 시뮬레이터를 종료하고, 실험마다 Pi 에이전트 한 개만 실행한다. MQTT Worker의 Client ID는 `fault-monitor-rpi-01`로 별개다.

## 4. 실험 절차

각 실험 전 `/api/health` 200, `/api/devices/RPI-01`의 최근 수신 시각, Worker의 구독 로그를 확인한다. 장치가 한 번 이상 유효한 상태 메시지를 보낸 **후** 중단 실험을 시작해야 `CONNECTION_TIMEOUT`을 판정한다. 매 실험의 모드를 바꿀 때는 Pi 에이전트를 `Ctrl+C`로 종료하고 다시 실행한다.

| 실험 | Pi 실행 또는 조작 | 기대 결과 |
| --- | --- | --- |
| 정상 | `--mode normal` | 2초 간격 상태 발행, 요청에 즉시 응답, Vue `통신 정상` |
| 상태 메시지 중단 | normal 확인 후 `--mode disconnect`로 재실행 | 상태 메시지 약 10초 미수신 후 `CONNECTION_TIMEOUT`. 이 모드는 요청 응답은 계속 보내므로 실제 Ethernet 단절과 다름 |
| 응답 지연 | `--mode delay` | 요청 응답 4.2초 지연, `RESPONSE_DELAY` 기록. 상태 발행은 계속됨 |
| 형식 오류 | `--mode invalid` | 필수 필드 누락·자료형 오류·깨진 JSON이 순환 발행되어 `INVALID_MESSAGE` 기록 |
| 실제 Ethernet 단절·재연결 | normal 상태에서 Pi Ethernet 케이블을 분리한 뒤 다시 연결 | 상태 수신 중단에 따른 `CONNECTION_TIMEOUT`, 요청 응답 누락에 따른 `RESPONSE_DELAY`도 발생 가능. 재연결 후 유효 상태 수신 시 통신 장애 자동 복구 |

실제 Ethernet 실험에서는 Wi-Fi 등 대체 경로로 MQTT가 계속 전달되지 않는지 확인한다. 케이블을 뽑기 전후 Pi의 네트워크 경로와 PC의 수신 로그를 비교한다. Pi 에이전트는 paho-mqtt의 재연결 지연(1~10초)을 사용하고 재연결 시 요청 topic을 다시 구독한다. 복구 여부는 Pi의 연결 로그만으로 판단하지 말고 PC의 유효 상태 수신 로그와 이벤트의 `recovered_at`으로 확인한다. 실제 장애 원인과 AI의 점검 가설은 구분한다.

## 5. 시간 기록

PC와 Pi의 시스템 시각을 동기화한다. DB의 `started_at`, `detected_at`, `recovered_at`은 UTC다. `CONNECTION_TIMEOUT`의 `started_at`은 마지막 메시지 시각이 아니라 **10초 미수신 기준에 도달한 시각**이므로, 감지 소요 시간은 마지막 유효 상태 로그부터 `detected_at`까지 계산한다. `RESPONSE_DELAY`은 요청 시작부터, `INVALID_MESSAGE`는 오류 메시지 수신부터 계산한다. AI 응답 시간은 API 호출 전후의 경과 시간이며 모델 생성 시간에 HTTP 시간을 더한 값이다.

장애 상세 화면에서 ID를 확인한 뒤, PC 프로젝트 루트에서 다음 명령을 실행한다. 복구 시각도 남기려면 통신 재개 후 실행한다. AI 호출 없이 시각만 기록하려면 `--skip-ai`를 붙인다.

```powershell
.\.venv\Scripts\python.exe scripts\record_experiment.py 123 --experiment ethernet-reconnect-01 --notes '케이블 분리 후 재연결'
```

기본 출력은 Git에서 제외되는 `experiments/results.csv`다. 공유용 빈 양식은 [`experiments/RESULT_TEMPLATE.csv`](experiments/RESULT_TEMPLATE.csv)다. 이벤트 ID, 실제 현장 시작/종료 시각, 네트워크 조건, 원인 확인 결과를 `notes`에 기록한다. 테스트가 수행되지 않은 칸은 비워 두고 결과를 만들어 쓰지 않는다.

## 검증 범위

개발 PC에서 기존 27개 테스트와 신규 3개 테스트가 통과했고 Vue 빌드가 성공했다. 별도 로컬 Mosquitto 포트·임시 DB에서 이 에이전트의 정상 발행, 상태 중단 판정, 재실행 후 자동 복구를 관찰했다. **Raspberry Pi 5 장치의 실행, 실제 Ethernet 케이블 단절·재연결, CPU 온도 센서 읽기, 인증된 LAN 브로커 접속은 아직 실기기로 검증하지 않았다.** 이 항목은 위 절차를 실제 장치에서 수행한 뒤 결과 양식에 기록해야 한다.
