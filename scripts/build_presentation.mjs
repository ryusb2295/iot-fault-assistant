import fs from 'node:fs/promises'
import path from 'node:path'
import MarkdownIt from '../frontend/node_modules/markdown-it/dist/markdown-it.mjs'

const root = path.resolve(import.meta.dirname, '..')
const source = await fs.readFile(path.join(root, 'presentation/20min_deck.md'), 'utf8')
const markdown = new MarkdownIt({ html: false })
const visualBodies = [
  '<div class="hero">MQTT 수신부터 규칙 판정,<br>근거 기반 점검 안내까지</div><p class="subtle">PC 시뮬레이터 · FastAPI · SQLite · Vue · Ollama</p>',
  '<div class="hero">알림 한 건에 필요한 맥락</div><div class="trio"><span>언제 메시지가 멈췄나</span><span>어떤 규칙이 장애를 판정했나</span><span>무엇을 확인해야 하나</span></div>',
  '<div class="flow"><span>PC 시뮬레이터</span><span>MQTT Broker</span><span>Python Worker</span><span>SQLite</span><span>FastAPI · Vue</span></div><p class="accent-line">AI 점검 안내는 장애 상세에서만 생성한다.</p>',
  '<div class="rules"><div><b>01</b><h3>통신 중단</h3><p>마지막 유효 상태 메시지 후<br>10초 이상 미수신</p></div><div><b>02</b><h3>응답 지연</h3><p>요청 후 약 3초 내<br>일치하는 응답 없음</p></div><div><b>03</b><h3>형식 오류</h3><p>메시지 필수 값과<br>형식 검증 실패</p></div></div><p class="accent-line">통신 복구와 사용자 조치 완료는 별도로 기록한다.</p>',
  '<div class="shot-layout"><img src="video/events_frame.png" alt="실제 대시보드 화면"><div><h3>운영 화면</h3><p>장애 유형별 건수</p><p>복구·미복구 상태</p><p>사용자 조치 현황</p><small>실제 MQTT 시연 녹화 화면</small></div></div>',
  '<div class="demo-layout"><video controls preload="metadata" poster="video/events_frame.png" src="video/mqtt_fault_demo_2026-11-06T13-53-32-334Z.webm"></video><ol><li>정상 메시지 수신</li><li>지연 모드 전환</li><li>장애 이력·로그 확인</li><li>정상 복귀</li></ol></div>',
  '<div class="results"><div><strong>10.106초</strong><span>통신 중단 · 5회 평균</span><i style="width:84%"></i></div><div><strong>3.190초</strong><span>응답 지연 · 5회 평균</span><i style="width:27%"></i></div><div><strong>측정 불가</strong><span>형식 오류 · 5회</span><p>수신·판정 기록의 시각 해상도 동일</p></div></div><p class="fine">두 시간 측정은 시작점이 달라 직접 비교하지 않는다.</p>',
  '<div class="range"><div><span>통신 중단</span><i><b style="left:83.4%;width:1.7%"></b></i><strong>10.003–10.207초</strong></div><div><span>응답 지연</span><i><b style="left:25.1%;width:2.2%"></b></i><strong>3.010–3.269초</strong></div></div><p class="fine">각 막대는 0~12초 축에 표시한 5회 측정 범위. PC 환경 결과다.</p>',
  '<div class="rag"><div class="rag-steps"><span>장애 유형</span><span>해당 매뉴얼 절 + 연결 로그</span><span>로컬 Ollama</span><span>점검 안내 + 출처</span></div><img src="video/detail_frame.png" alt="장애 상세 화면"></div><p class="accent-line">검색 근거가 없으면 모델을 호출하지 않는다.</p>',
  '<div class="ai"><div class="big">5<small>/5</small><p>동일 이벤트의 응답 생성 성공</p></div><div class="bars"><div><span>1회</span><i style="width:89%"></i><b>8.908s</b></div><div><span>2회</span><i style="width:36%"></i><b>3.556s</b></div><div><span>3회</span><i style="width:36%"></i><b>3.641s</b></div><div><span>4회</span><i style="width:36%"></i><b>3.576s</b></div><div><span>5회</span><i style="width:36%"></i><b>3.638s</b></div></div></div><p class="fine">별도 답변 1건의 근거 검토는 부분 적합. 출처 밖 권고가 남았다.</p>',
  '<div class="limits"><div><h3>이번에 확인</h3><p>PC 시뮬레이터의 세 장애 유형</p><p>분리된 SQLite와 실제 MQTT 시연</p><p>Ollama 실패 시 모니터링 유지</p></div><div><h3>다음에 검증</h3><p>실제 Raspberry Pi 네트워크 단절</p><p>AI 답변 5건의 문장별 근거 대조</p><p>장기 운영 시 오탐과 누락</p></div></div>',
  '<div class="hero">장애 판정은 규칙으로,<br>점검은 근거와 함께</div><p class="subtle">질문 감사합니다.</p>',
]
const slideTitles = [
  'IoT 통신 장애 감지와 대응 보조 시스템',
  '운영자가 확인해야 할 세 가지',
  '수신부터 대응 화면까지',
  '세 가지 장애 판정 규칙',
  '장애 상태를 한 화면에서',
  '실시간 시연',
  '규칙 기반 탐지 실험 15회',
  '측정 범위와 해석',
  '근거 문서 기반 점검 안내',
  'AI 응답 시간과 근거 검토',
  '검증 범위와 남은 과제',
  '결론',
]
const sections = [...source.matchAll(/^## (\d+)\. (.+)$/gm)]
const slides = sections.map((match, index) => {
  const start = match.index + match[0].length
  const end = sections[index + 1]?.index ?? source.indexOf('## 근거 자료', start)
  const body = source.slice(start, end > start ? end : undefined).trim()
  return `<section class="slide slide-${index + 1}" aria-label="${index + 1}번 슬라이드"><header><span>IoT FAULT MONITORING</span><span>${String(index + 1).padStart(2, '0')} / ${sections.length}</span></header><h1>${markdown.utils.escapeHtml(slideTitles[index])}</h1><div class="content">${visualBodies[index]}</div><aside class="notes">${markdown.render(body)}</aside></section>`
})
const output = `<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>IoT 통신 장애 감지와 대응 보조 시스템</title>
<link rel="stylesheet" href="deck.css"><main>${slides.join('')}</main><div class="controls"><button type="button" id="prev" aria-label="이전 슬라이드">이전</button><span id="count"></span><button type="button" id="next" aria-label="다음 슬라이드">다음</button><button type="button" id="notes">발표자 노트</button><button type="button" id="full">전체 화면</button></div>
<script>const slides=[...document.querySelectorAll('.slide')];let current=0;function show(n){current=Math.max(0,Math.min(slides.length-1,n));slides.forEach((s,i)=>s.classList.toggle('active',i===current));document.getElementById('count').textContent=(current+1)+' / '+slides.length;location.hash='slide-'+(current+1)}document.getElementById('prev').onclick=()=>show(current-1);document.getElementById('next').onclick=()=>show(current+1);document.getElementById('notes').onclick=()=>document.body.classList.toggle('show-notes');document.getElementById('full').onclick=()=>document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen();document.addEventListener('keydown',e=>{if(e.key==='ArrowRight'||e.key==='PageDown')show(current+1);if(e.key==='ArrowLeft'||e.key==='PageUp')show(current-1);if(e.key.toLowerCase()==='n')document.body.classList.toggle('show-notes');if(e.key.toLowerCase()==='f')document.fullscreenElement?document.exitFullscreen():document.documentElement.requestFullscreen()});show(Math.max(0,Number(location.hash.replace('#slide-',''))-1||0))</script></html>`
const target = path.join(root, 'presentation/20min_deck.html')
await fs.writeFile(target, output, 'utf8')
console.log(target)
