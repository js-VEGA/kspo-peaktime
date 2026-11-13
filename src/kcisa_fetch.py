"""KCISA(문화포털) API 페이지 수집기. 응답 원문을 페이지 단위로 data/raw/kcisa/<이름>/ 에 저장한다.

- 형식을 가정하지 않고 원문 그대로 저장한다(파싱은 응답 형식 확인 후 별도 단계).
- 이미 받은 페이지는 건너뛰므로 중단 후 이어서 실행할 수 있다(재개).
- 개발 계정 일 1,000건 한도를 지키려고 하루 호출 수를 기록하고 --budget(기본 900)에서 멈춘다.
- 연속 실패가 --max-fail 회에 이르면 서버 문제로 보고 멈춘다(한도 낭비 방지).
- 키는 출력·저장하지 않는다.

실행 예: python -I src/kcisa_fetch.py linked --rows 1000 --max-pages 10
"""
import argparse
import os
import re
import sys
import time
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
APIS = {
    "linked": ("API_CPM_009", "KCISA_SERVICE_KEY_LINKED"),  # 올림픽공원 2025 차량입출차·공연·날씨 연계
    "allzone": ("API_CPM_008", "KCISA_SERVICE_KEY_ALLZONE"),  # 올림픽공원 2025 입출차정보(전체구역)
}
BASE = "https://api.kcisa.kr/openapi/{}/request"


def calls_today(d: Path) -> tuple[Path, int]:
    f = d.parent / f"_calls_{date.today():%Y%m%d}.txt"
    n = int(f.read_text()) if f.exists() else 0
    return f, n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=APIS)
    ap.add_argument("--rows", type=int, default=100, help="numOfRows")
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--max-pages", type=int, default=5)
    ap.add_argument("--budget", type=int, default=900, help="하루 최대 호출 수")
    ap.add_argument("--max-fail", type=int, default=3)
    ap.add_argument("--sleep", type=float, default=0.5)
    a = ap.parse_args()

    api, env = APIS[a.name]
    key = os.getenv(env, "").strip()
    if not key:
        sys.exit(f".env 에 {env} 가 없음")
    out = ROOT / "data" / "raw" / "kcisa" / f"{a.name}_rows{a.rows}"
    out.mkdir(parents=True, exist_ok=True)
    counter, used = calls_today(out)

    fails, saved, total = 0, 0, None
    for page in range(a.start_page, a.start_page + a.max_pages):
        f = out / f"page_{page:06d}.txt"
        if f.exists():
            continue
        if used >= a.budget:
            print(f"하루 호출 예산 {a.budget} 도달: 중단 (page {page}부터 이어서)")
            break
        try:
            r = requests.get(BASE.format(api), params={"serviceKey": key, "numOfRows": a.rows, "pageNo": page}, timeout=60)
            status, text = r.status_code, r.text.replace(key, "<KEY>")
        except requests.RequestException as e:
            status, text = None, ""
            print(f"page {page}: {type(e).__name__}")
        used += 1
        counter.write_text(str(used))
        if status == 200 and text.strip():
            f.write_text(text, encoding="utf-8")
            saved += 1
            fails = 0
            if total is None:
                m = re.search(r"totalCount[^0-9]{0,12}(\d+)", text, re.I)
                total = int(m.group(1)) if m else None
                print(f"totalCount={total}" if total else "totalCount 표기 없음(응답 형식 확인 필요)")
            print(f"page {page}: ok {len(text):,} chars (오늘 호출 {used})")
        else:
            fails += 1
            print(f"page {page}: status={status} (연속 실패 {fails})")
            if fails >= a.max_fail:
                print("연속 실패 한도: 서버 문제로 보고 중단")
                break
        time.sleep(a.sleep)
    print(f"saved {saved} pages -> {out.relative_to(ROOT)} | 오늘 호출 누계 {used}")


if __name__ == "__main__":
    main()
