# IoT 설비 통신 장애 대응 지원 웹 대시보드

Vue 3 대시보드입니다. 기본값은 로컬 FastAPI의 MQTT·SQLite 데이터입니다. 현재 장치 데이터는 PC 시뮬레이터에서 생성한 것이며 실제 라즈베리파이 측정 데이터는 아닙니다. 장애 판정이나 장치 제어는 브라우저에서 수행하지 않습니다.

## 실행

Node.js 22.18 이상 또는 24.12 이상이 필요합니다.

```powershell
cd C:\dev\iot-fault-assistant\frontend
npm install
npm run dev
```

Vite가 출력하는 로컬 주소(기본 `http://localhost:5173`)로 접속합니다. 검증 명령은 `npm run build`, `npm run lint`입니다.

## 화면

UI 폰트는 `public/fonts/PretendardVariable.woff2`를 로컬에서 제공합니다. 폰트 파일은 [Pretendard 공식 배포본](https://github.com/orioncactus/pretendard) v1.3.9이며 라이선스는 `public/fonts/OFL-LICENSE.txt`에 포함했습니다. 로드할 수 없을 때는 `Pretendard`, `Malgun Gothic`, `sans-serif` 순서로 대체합니다.

| 경로 | 내용 |
| --- | --- |
| `/dashboard` | KPI, 단일 설비 상태, 최근 장애·조치, 통신 이벤트 차트 |
| `/devices` | RPI-01 상세 상태와 최근 JSON 메시지 |
| `/events` | 장애 유형·상태 필터, 검색, 페이지네이션 |
| `/events/:id` | 로그, 매뉴얼, 사례, 예시 설명, 점검 체크리스트, 조치 기록 |
| `/knowledge` | 실습용 매뉴얼 및 과거 조치 사례 검색 |

장애 상세의 체크 항목과 조치 결과는 모의 모드에서 브라우저 `localStorage`에만 저장됩니다. API 모드에서는 조치 기록을 SQLite에 저장합니다. 대시보드 KPI·장치·장애 목록은 2초 간격으로 조회합니다. AI 설명은 두 모드 모두 고정 문구이며 **예시 설명**으로 표시합니다.

## 파일 구조

```text
frontend/
├─ src/
│  ├─ assets/main.css         공통 디자인 및 반응형 스타일
│  ├─ components/             사이드바, 헤더, 카드, 표, 차트, 체크리스트 등
│  ├─ data/mockData.js        실습용 장치·장애·문서·차트 데이터
│  ├─ services/api.js         데이터 호출 및 조치 저장 인터페이스
│  ├─ utils/format.js         시각·기간 표시 함수
│  ├─ views/                  5개 메뉴 화면과 장애 상세 화면
│  ├─ router/index.js         Vue Router 경로
│  ├─ App.vue                 공통 레이아웃
│  └─ main.js                 앱 초기화
├─ index.html
└─ package.json
```

## FastAPI 연결

화면은 `src/services/api.js`의 함수만 호출합니다. 별도 `.env` 없이 실행하면 `/api` 요청을 Vite 프록시가 `127.0.0.1:8000`의 FastAPI로 전달합니다. 백엔드가 없으면 오류를 표시하며 모의 데이터로 대체하지 않습니다. 실습용 화면만 독립적으로 시연할 때는 `.env.local`에 다음을 넣고 Vite를 재시작합니다.

```env
VITE_DATA_SOURCE=mock
```

연결 API는 `GET /dashboard`, `GET /devices`, `GET /devices/RPI-01`, `GET /events`, `GET /events/{id}`, `GET /events/{id}/logs`, `GET /actions/recent`, `GET /metrics/events`, `POST /events/{id}/actions`입니다. 매뉴얼·과거 사례는 이번 단계에서 계속 실습용 데이터를 사용합니다. FastAPI는 기본 Vite 주소 `localhost:5173`, `127.0.0.1:5173`을 CORS로 허용합니다.

백엔드 및 Mosquitto 실행 순서는 [프로젝트 README](../README.md)를 참고하세요. 이후 매뉴얼·사례 검색 결과를 Ollama 입력 근거로 사용할 예정이며, LLM은 설명만 생성합니다.
