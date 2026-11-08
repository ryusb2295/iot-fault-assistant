"""Capture real app screenshots for the presentation (run on the demo PC).

Prerequisites: start_demo.ps1 and rehearsal.ps1 already ran (all 3 fault types
exist and the RPI-01 device window is running).

What it does
  1. saves an inspection record for each rehearsal fault through the real API
     (texts describe what the rehearsal actually did)
  2. captures dashboard / devices / fault list / manuals / records
  3. asks you to press Ctrl+C in the device window -> captures the outage
     (red dashboard, new fault detail with AI guidance and the previous record)
  4. asks you to restart the device -> captures recovery
Images go to presentation/screens/*.png

Usage (project root, PowerShell):
  .\\.venv\\Scripts\\python.exe -m pip install playwright
  .\\.venv\\Scripts\\python.exe scripts\\capture_screens.py
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "presentation" / "screens"
WEB = os.getenv("DEMO_WEB", "http://localhost:5173")
API = os.getenv("DEMO_API", "http://127.0.0.1:8000/api")
VIEW = {"width": 1600, "height": 900}

# true descriptions of what rehearsal.ps1 did for each fault type
ACTION_TEXT = {
    "RESPONSE_DELAY": "시뮬레이터가 delay 모드(4.2초 후 응답)로 실행 중인 것을 확인함. normal 모드로 전환 후 응답이 3초 이내로 돌아온 것을 로그에서 확인",
    "INVALID_MESSAGE": "로그에서 timestamp 누락, 자료형 오류, JSON 문법 오류를 확인함. invalid 모드 발행을 중단하고 정상 payload 수신을 확인",
    "CONNECTION_TIMEOUT": "장치 발행 프로세스가 종료된 것을 확인하고 재시작함. 상태 메시지 재수신 확인",
}


def api(path, data=None):
    req = urllib.request.Request(f"{API}{path}", method="POST" if data is not None else "GET",
                                 data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as res:
        return json.load(res)


def say(text):
    print(f"\n== {text}", flush=True)


def wait_until(check, timeout, label):
    end = time.time() + timeout
    while time.time() < end:
        try:
            if check():
                return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"   (timed out waiting for: {label})")
    return False


def launch(p):
    exe = os.getenv("CAPTURE_BROWSER")          # test override
    if exe:
        return p.chromium.launch(executable_path=exe, args=["--no-sandbox"])
    for channel in ("msedge", "chrome"):        # use a browser already on Windows
        try:
            return p.chromium.launch(channel=channel)
        except Exception:
            continue
    return p.chromium.launch()


def panel(page, title):
    return page.locator("section.panel", has=page.locator("h3", has_text=title)).first


def shot(target, name, **kw):
    path = OUT / f"{name}.png"
    target.screenshot(path=str(path), **kw)
    print(f"   saved {path.relative_to(ROOT)}")


def wait_ai(page, timeout=120):
    page.wait_for_function(
        "() => document.body.innerText.includes('검색된 근거 문서') || document.body.innerText.includes('불러오지 못했습니다')",
        timeout=timeout * 1000)
    page.wait_for_timeout(800)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    try:
        api("/health")
    except Exception:
        sys.exit("API not reachable. Run start_demo.ps1 (and rehearsal.ps1) first.")
    events = api("/events")
    if not events:
        sys.exit("No faults yet. Run rehearsal.ps1 first.")

    say("1/4 saving inspection records for the rehearsal faults")
    for e in sorted(events, key=lambda e: e["id"]):
        if e["actionStatus"] == "unhandled" and e["faultType"] in ACTION_TEXT:
            api(f"/events/{e['id']}/actions", {"checklist": [0, 1, 2], "action_text": ACTION_TEXT[e["faultType"]], "resolved": True})
            print(f"   #{e['id']} {e['faultType']}: saved")

    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_page(viewport=VIEW, device_scale_factor=1.5)
        # hide the Vite/Vue devtools floating button in screenshots
        page.add_init_script("""document.addEventListener('DOMContentLoaded', () => {
          const s = document.createElement('style');
          s.textContent = '[id^="__vue-devtools"], .vue-devtools__anchor, #vue-devtools-anchor { display: none !important; }';
          document.head.appendChild(s); });""")

        say("2/4 normal-state screens")
        wait_until(lambda: api("/devices/RPI-01")["status"] == "normal", 30, "device normal")
        page.goto(f"{WEB}/dashboard"); page.wait_for_timeout(3500)
        shot(page, "01_dashboard_normal")
        page.goto(f"{WEB}/devices"); page.wait_for_timeout(2500)
        shot(page, "02_devices", full_page=True)
        page.goto(f"{WEB}/knowledge"); page.wait_for_timeout(2500)
        shot(page, "03_knowledge_manuals", full_page=True)
        page.get_by_role("tab", name="실제 조치 기록").click(); page.wait_for_timeout(800)
        shot(page, "04_knowledge_records", full_page=True)
        page.get_by_role("tab", name="실습용 조치 사례").click(); page.wait_for_timeout(800)
        shot(page, "05_knowledge_cases", full_page=True)
        # one detail per rehearsal fault type (logs show the real validation results)
        for ftype, name in (("RESPONSE_DELAY", "06_detail_delay"), ("INVALID_MESSAGE", "07_detail_invalid")):
            e = next((e for e in api("/events") if e["faultType"] == ftype), None)
            if e:
                page.goto(f"{WEB}/events/{e['id']}"); page.wait_for_timeout(2500)
                shot(panel(page, "관련 통신 로그"), f"{name}_logs")

        say("3/4 OUTAGE: click the blue RPI-01 device window title bar and press Ctrl+C now")
        before = {e["id"] for e in api("/events")}
        page.goto(f"{WEB}/dashboard")
        # countdown screen around 6s after the last message
        wait_until(lambda: (time.time() - _last_seen()) >= 6, 120, "device stopped")
        page.wait_for_timeout(500)
        shot(page, "08_dashboard_counting")
        wait_until(lambda: api("/devices/RPI-01")["status"] == "fault", 30, "fault judged")
        page.wait_for_timeout(2500)
        shot(page, "09_dashboard_fault")
        new = [e for e in api("/events") if e["id"] not in before and e["faultType"] == "CONNECTION_TIMEOUT"]
        if new:
            eid = new[0]["id"]
            page.goto(f"{WEB}/events/{eid}")
            print("   waiting for the local AI guidance (up to 2 min)...")
            try:
                wait_ai(page)
            except Exception:
                print("   (AI guidance did not finish; capturing anyway)")
            shot(page, "10_detail_top")
            shot(page, "11_detail_full", full_page=True)
            shot(panel(page, "같은 유형의 이전 조치 기록"), "12_detail_past_actions")
            shot(panel(page, "AI 점검 안내"), "13_detail_ai")
            shot(panel(page, "관련 통신 로그"), "14_detail_logs")
            # fill the checklist + action like an operator, then capture before saving
            boxes = panel(page, "사용자 점검 체크리스트").locator("label.el-checkbox")
            for i in range(min(2, boxes.count())):
                boxes.nth(i).scroll_into_view_if_needed()
                boxes.nth(i).click()
            page.get_by_placeholder("점검 결과와 실제 수행한 조치를 입력하세요").fill(ACTION_TEXT["CONNECTION_TIMEOUT"])
            page.wait_for_timeout(500)
            shot(panel(page, "사용자 점검 체크리스트"), "15_detail_checklist")
            shot(panel(page, "최종 조치 결과"), "16_detail_action_form")
            page.get_by_role("button", name="조치 기록 저장").click(); page.wait_for_timeout(1500)

            say("4/4 RECOVERY: in the device window type  .\\scripts\\device.ps1  and press Enter")
            wait_until(lambda: api(f"/events/{eid}")["recoveredAt"], 300, "recovery")
            page.wait_for_timeout(2500)
            page.evaluate("window.scrollTo(0, 0)"); page.wait_for_timeout(400)
            shot(page, "17_detail_recovered")
            page.goto(f"{WEB}/events"); page.wait_for_timeout(2500)
            shot(page, "18_events_list", full_page=True)
            page.goto(f"{WEB}/dashboard"); page.wait_for_timeout(3500)
            shot(page, "19_dashboard_after")
        else:
            print("   no new CONNECTION_TIMEOUT found; skipped outage screens")
        browser.close()
    print(f"\nDone. {len(list(OUT.glob('*.png')))} images in {OUT}")


def _last_seen():
    from datetime import datetime
    seen = api("/devices/RPI-01")["lastReceivedAt"]
    return datetime.fromisoformat(seen).timestamp() if seen else time.time()


if __name__ == "__main__":
    main()
