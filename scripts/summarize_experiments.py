"""Summarize recorded experiment rows without treating missing timings as zero."""

import argparse
import csv
import html
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LABELS = {
    "CONNECTION_TIMEOUT": "통신 중단",
    "RESPONSE_DELAY": "응답 지연",
    "INVALID_MESSAGE": "형식 오류",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "experiments" / "results_pc_measurement_2.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "presentation" / "experiment_summary.md")
    args = parser.parse_args()
    with args.input.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    trials = [row for row in rows if row["experiment"].startswith("pc-isolated-")]
    ai = [row for row in rows if row["experiment"].startswith("pc-ai-")]
    lines = ["# 실험 결과 요약", "", f"출처: `{args.input.relative_to(ROOT).as_posix()}`", "",
             "## 규칙 기반 장애 탐지", "", "| 유형 | 횟수 | 측정 가능한 탐지 시간 평균 | 범위 |", "| --- | ---: | ---: | ---: |"]
    for fault_type, label in LABELS.items():
        subset = [row for row in trials if row["fault_type"] == fault_type]
        values = [float(row["detection_seconds"]) for row in subset if row["detection_seconds"]]
        mean = f"{statistics.mean(values):.3f}초" if values else "측정 불가"
        span = f"{min(values):.3f}~{max(values):.3f}초" if values else "수신·판정 시각 해상도 동일"
        lines.append(f"| {label} | {len(subset)} | {mean} | {span} |")
    times = [float(row["ai_response_seconds"]) for row in ai if row["ai_status"] == "ready" and row["ai_response_seconds"]]
    lines += ["", "통신 중단 시간은 마지막 유효 상태 수신부터 탐지까지이며, 응답 지연 시간은 요청 등록부터 탐지까지입니다. 서로 다른 기준이므로 직접 비교하지 않습니다.",
              "", "## 로컬 AI 응답", "", f"성공 {len(times)}/{len(ai)}회 · 평균 {statistics.mean(times):.3f}초 · 중앙값 {statistics.median(times):.3f}초 · 범위 {min(times):.3f}~{max(times):.3f}초",
              "", "| 호출 | 응답 시간 |", "| --- | ---: |"]
    lines += [f"| {row['experiment']} | {float(row['ai_response_seconds']):.3f}초 |" for row in ai if row["ai_response_seconds"]]
    lines += ["", "5회는 모두 동일한 형식 오류 이벤트 ID 77에 대한 호출입니다. 다른 장애 유형으로 일반화할 수 없습니다.",
              "CSV에는 AI 응답 문장과 출처 대조 결과가 없습니다. 성공률은 응답 생성 성공률이며 설명의 사실 정확도 점수가 아닙니다.", ""]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines), encoding="utf-8")
    chart = args.output.with_name("experiment_charts.html")
    detection_rows = []
    for fault_type, label in LABELS.items():
        values = [float(row["detection_seconds"]) for row in trials
                  if row["fault_type"] == fault_type and row["detection_seconds"]]
        if values:
            mean = statistics.mean(values)
            detection_rows.append(f'<div class="row"><span>{html.escape(label)}</span><div class="track"><i style="width:{mean / 12 * 100:.1f}%"></i></div><b>{mean:.3f}초</b></div>')
        else:
            detection_rows.append(f'<div class="row"><span>{html.escape(label)}</span><div class="unmeasured">시각 해상도상 측정 불가</div><b>—</b></div>')
    ai_rows = [f'<div class="row"><span>{index}회</span><div class="track"><i style="width:{value / 10 * 100:.1f}%"></i></div><b>{value:.3f}초</b></div>'
               for index, value in enumerate(times, 1)]
    chart.write_text("""<!doctype html><html lang="ko"><meta charset="utf-8"><title>IoT 장애 실험 결과</title>
<style>body{max-width:980px;margin:48px auto;padding:0 28px;background:#f4f6f9;color:#1f2a3d;font:17px/1.5 'Malgun Gothic',sans-serif}h1{font-size:32px}h2{font-size:23px;margin-top:36px}.row{display:grid;grid-template-columns:130px 1fr 100px;align-items:center;gap:18px;margin:14px 0}.track{height:23px;background:#e5eaf2;border-radius:4px}.track i{display:block;height:100%;background:#3476dc;border-radius:4px}.row b{text-align:right;font-variant-numeric:tabular-nums}.unmeasured{color:#6c788b}small{color:#657287}.note{border-left:3px solid #5c91d7;padding-left:14px;margin-top:24px}@media(max-width:600px){.row{grid-template-columns:90px 1fr 78px;gap:8px;font-size:13px}}</style>
<h1>IoT 장애 실험 결과</h1><h2>장애 탐지 시간 평균</h2>""" + "".join(detection_rows) + """
<p class="note">통신 중단과 응답 지연은 측정 시작점이 다릅니다. 형식 오류 시간은 0초가 아니라 측정 불가입니다.</p>
<h2>로컬 AI 응답 시간</h2>""" + "".join(ai_rows) + """
<p class="note">동일한 형식 오류 이벤트를 5회 호출했습니다. 응답 생성 성공 5/5회이며 설명의 정확도를 검증한 수치는 아닙니다.</p>
<small>출처: experiments/results_pc_measurement_2.csv</small></html>""", encoding="utf-8")
    print(args.output)
    print(chart)


if __name__ == "__main__":
    main()
