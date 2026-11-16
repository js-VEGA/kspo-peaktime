"""KCISA 대용량 API(API_CPM_008/009)를 5,000건 단위로 받아 gzip 으로 저장한다(재개 가능).

- 429/5xx/시간초과는 지수 백오프로 재시도한다. 모든 시도는 하루 호출 예산(기본 950, 개발계정 한도 1,000)에 센다.
- 이미 받은 페이지는 건너뛴다. 페이지 경계가 서버 적재로 바뀔 수 있어 병합 시 LOCAL_ID 로 중복 제거한다.
- 키는 출력·저장하지 않는다.
실행: python -u -X utf8 -I src/fetch_bulk.py allzone --rows 5000
"""
import argparse
import gzip
import os
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
K = "https://api.kcisa.kr/openapi/"
APIS = {
    "linked": (K + "API_CPM_009/request", "KCISA_SERVICE_KEY_LINKED"),
    "allzone": (K + "API_CPM_008/request", "KCISA_SERVICE_KEY_ALLZONE"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name", choices=APIS)
    ap.add_argument("--rows", type=int, default=5000)
    ap.add_argument("--start-page", type=int, default=1)
    ap.add_argument("--end-page", type=int, default=0, help="0이면 totalCount 로 계산")
    ap.add_argument("--budget", type=int, default=950)
    ap.add_argument("--sleep", type=float, default=8.0)
    ap.add_argument("--retries", type=int, default=5)
    a = ap.parse_args()

    url, env = APIS[a.name]
    key = os.getenv(env, "").strip()
    if not key:
        sys.exit(f".env 에 {env} 가 없음")
    out = ROOT / "data" / "raw" / "kcisa" / f"{a.name}_bulk{a.rows}"
    out.mkdir(parents=True, exist_ok=True)
    cfile = ROOT / "data" / "raw" / "kcisa" / f"_calls_{date.today():%Y%m%d}.txt"
    used = int(cfile.read_text()) if cfile.exists() else 0
    log = open(out / "_log.txt", "a", encoding="utf-8")

    def say(msg):
        line = f"{datetime.now():%H:%M:%S} {msg}"
        print(line, flush=True)
        log.write(line + "\n"); log.flush()

    def call(page):
        nonlocal used
        for attempt in range(a.retries):
            if used >= a.budget:
                say(f"하루 호출 예산 {a.budget} 도달: 중단(page {page}부터 이어서)")
                return None, "budget"
            try:
                r = requests.get(url, params={"serviceKey": key, "numOfRows": a.rows, "pageNo": page}, timeout=150)
                status, text = r.status_code, r.text
            except requests.RequestException as e:
                status, text = None, type(e).__name__
            used += 1
            cfile.write_text(str(used))
            if status == 200 and "<item>" in text:
                return text, "ok"
            if status == 200 and "<item>" not in text:
                return text, "empty"
            wait = min(30 * 2 ** attempt, 300)
            say(f"page {page}: status={status} (시도 {attempt + 1}/{a.retries}), {wait}s 대기")
            time.sleep(wait)
        return None, "fail"

    total = None
    end = a.end_page
    page = a.start_page
    while True:
        if end and page > end:
            break
        f = out / f"page_{page:06d}.xml.gz"
        if f.exists():
            page += 1
            continue
        text, st = call(page)
        if st in ("budget", "fail"):
            if st == "fail":
                say(f"page {page}: 재시도 한도 초과, 중단")
            break
        if st == "empty":
            say(f"page {page}: 항목 없음, 끝으로 판단")
            break
        n = text.count("<item>")
        if total is None:
            m = re.search(r"<totalCount>(\d+)", text)
            total = int(m.group(1)) if m else None
            if total and not end:
                end = -(-total // a.rows)
            say(f"totalCount={total}, 마지막 페이지={end}")
        with gzip.open(f, "wt", encoding="utf-8", compresslevel=6) as g:
            g.write(text.replace(key, "<KEY>"))
        say(f"page {page}/{end}: {n}건 저장 (오늘 호출 {used})")
        page += 1
        time.sleep(a.sleep)
    say(f"종료: 다음 page={page}, 오늘 호출 {used}")


if __name__ == "__main__":
    main()
