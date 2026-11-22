"""KOPIS(공연예술통합전산망) OPEN API 수집기. 응답 원문(XML)을 data/raw/kopis/ 에 캐시한다.

- 키는 .env 의 KOPIS_SERVICE_KEY 에서 읽고, 출력·저장하지 않는다(오류 메시지에도 URL을 찍지 않는다).
- 캐시가 있으면 다시 부르지 않는다. 호출 간격 0.35초(제한: 1초 10회), 429·5xx·연결 오류는 최대 3회 재시도.
- 출처: (재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)

실행 예:
  python -I src/kopis_fetch.py facility            # 올림픽공원 시설(FC001247) 상세
  python -I src/kopis_fetch.py list --from 2025-01-01 --to 2025-12-31
  python -I src/kopis_fetch.py detail              # list 결과의 공연별 상세
  python -I src/kopis_fetch.py list --from 2026-11-22 --to 2027-03-31 --tag upcoming
"""
import argparse
import hashlib
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
BASE = "http://www.kopis.or.kr/openApi/restful/"
FACILITY = "FC001247"  # 올림픽공원 (KOPIS 문서 예시 응답에서 확인)
RAW = ROOT / "data" / "raw" / "kopis"
CALLS = {"n": 0}
HEADERS = {"User-Agent": "kspo-peaktime-fetch/1.0"}  # 기본 python-requests 식별자는 KOPIS 방화벽이 400(Request Blocked)으로 막는다


def key():
    k = os.getenv("KOPIS_SERVICE_KEY", "").strip()
    if not k:
        sys.exit(".env 에 KOPIS_SERVICE_KEY 가 없음")
    return k


def get(path, params, cache: Path, retries=3):
    """캐시가 있으면 읽고, 없으면 호출해 저장한다. 키는 params 에 넣지 않고 여기서만 붙인다."""
    if cache.exists():
        return cache.read_text(encoding="utf-8")
    q = dict(params)
    q["service"] = key()
    for i in range(retries + 1):
        time.sleep(0.35)
        CALLS["n"] += 1
        try:
            r = requests.get(BASE + path, params=q, headers=HEADERS, timeout=30)
        except requests.RequestException as e:
            print(f"  연결 오류({type(e).__name__}) {path} 재시도 {i + 1}/{retries}")
            time.sleep(2 * (i + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504):
            print(f"  HTTP {r.status_code} {path} 재시도 {i + 1}/{retries}")
            time.sleep(3 * (i + 1))
            continue
        if r.status_code != 200:
            sys.exit(f"HTTP {r.status_code} {path} — 중단")
        r.encoding = "utf-8"
        text = r.text
        if "<returncode>" in text and "<returncode>00</returncode>" not in text:
            # 오류 응답(키 오류·기간 초과 등): 저장하지 않고 코드만 보고
            code = ET.fromstring(text).findtext(".//returncode")
            msg = ET.fromstring(text).findtext(".//errmsg")
            sys.exit(f"KOPIS 오류 코드 {code}: {msg} ({path})")
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(text, encoding="utf-8")
        return text
    sys.exit(f"재시도 상한 초과: {path}")


def windows(d0: date, d1: date, span=31):
    s = d0
    while s <= d1:
        e = min(s + timedelta(days=span - 1), d1)
        yield s, e
        s = e + timedelta(days=1)


def cmd_facility(a):
    t = get(f"prfplc/{FACILITY}", {}, RAW / f"facility_{FACILITY}.xml")
    root = ET.fromstring(t)
    print("시설:", root.findtext(".//fcltynm"), "공연장 수:", root.findtext(".//mt13cnt"))
    for m in root.iter("mt13"):
        print(" ", m.findtext("mt13id"), m.findtext("prfplcnm"), m.findtext("seatscale"))


def cmd_list(a):
    d0, d1 = date.fromisoformat(a.date_from), date.fromisoformat(a.date_to)
    out = RAW / f"list_{a.tag}"
    n = 0
    for s, e in windows(d0, d1):
        page = 1
        while True:
            p = {"stdate": s.strftime("%Y%m%d"), "eddate": e.strftime("%Y%m%d"), "cpage": page, "rows": 100, "prfplccd": FACILITY}
            t = get("pblprfr", p, out / f"{s:%Y%m%d}_{e:%Y%m%d}_p{page}.xml")
            k = len(ET.fromstring(t).findall(".//db"))
            n += k
            if k < 100:
                break
            page += 1
    print(f"{a.tag}: 공연 목록 {n}행 (중복 포함), 호출 {CALLS['n']}회")


def list_ids(tag):
    ids = {}
    for f in sorted((RAW / f"list_{tag}").glob("*.xml")):
        for db in ET.fromstring(f.read_text(encoding="utf-8")).findall(".//db"):
            ids[db.findtext("mt20id")] = db.findtext("prfnm")
    return ids


def cmd_detail(a):
    ids = list_ids(a.tag)
    for i, mid in enumerate(sorted(ids)):
        get(f"pblprfr/{mid}", {}, RAW / "detail" / f"{mid}.xml")
    print(f"상세 {len(ids)}건 확보, 이번 실행 호출 {CALLS['n']}회")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["facility", "list", "detail"])
    ap.add_argument("--from", dest="date_from", default="2025-01-01")
    ap.add_argument("--to", dest="date_to", default="2025-12-31")
    ap.add_argument("--tag", default="2025")
    a = ap.parse_args()
    {"facility": cmd_facility, "list": cmd_list, "detail": cmd_detail}[a.cmd](a)
