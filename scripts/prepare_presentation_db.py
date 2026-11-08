"""Create an isolated, empty SQLite database for a live presentation."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.config import DEVICE_ID  # noqa: E402
from backend.db import Repository  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "backend" / "iot_presentation.sqlite3")
    args = parser.parse_args()
    output = args.output.resolve()
    development = (ROOT / "backend" / "iot_faults.sqlite3").resolve()
    if output == development:
        parser.error("개발 DB를 발표용 출력으로 지정할 수 없습니다.")
    if output.exists():
        parser.error(f"파일이 이미 있습니다: {output}. 기존 발표 기록을 보호하기 위해 덮어쓰지 않습니다.")
    repo = Repository(output)
    repo.ensure_device(DEVICE_ID)
    print(f"발표용 빈 DB 생성: {output}")
    print("FastAPI와 MQTT Worker를 시작하기 전, 두 PowerShell 창에 같은 IOT_DB_PATH를 설정하세요.")


if __name__ == "__main__":
    main()
