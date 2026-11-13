"""KCISA(문화포털) API 2종을 소량 호출해 응답 형식·페이지 한도를 확인한다. 키는 출력하지 않는다.
실행: python -I src/kcisa_probe.py   (프로젝트 루트에서)
"""
import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
OUT = ROOT / "data" / "raw"
K = "https://api.kcisa.kr/openapi/"
APIS = {
    "linked": (K + "API_CPM_009/request", "KCISA_SERVICE_KEY_LINKED"),
    "allzone": (K + "API_CPM_008/request", "KCISA_SERVICE_KEY_ALLZONE"),
    "perf": (K + "service/rest/meta/KSCperf", "KCISA_SERVICE_KEY_PERF"),
    "rental": (K + "service/rest/meta12/getKSCD0803", "KCISA_SERVICE_KEY_RENTAL"),
    "ops": (K + "service/rest/meta12/getKSCD0801", "KCISA_SERVICE_KEY_OPS"),
}


def call(api, key, accept=None, timeout=120, **params):
    p = {"serviceKey": key, **params}
    headers = {"Accept": accept} if accept else {}
    return requests.get(api, params=p, timeout=timeout, headers=headers)


def redact(text, key):
    return text.replace(key, "<KEY>")


only = sys.argv[3:] or list(APIS)
for name, (api, env) in APIS.items():
    if name not in only:
        continue
    key = os.getenv(env, "").strip()
    print(f"\n=== {name} ({api}) key set: {bool(key)} len={len(key)}")
    if not key:
        continue
    accept = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] != "none" else None
    rows = int(sys.argv[2]) if len(sys.argv) > 2 else 1
    try:
        r = call(api, key, accept=accept, numOfRows=rows, pageNo=1)
    except requests.RequestException as e:  # 예외 문구에 URL(키)이 섞이지 않도록 종류만 출력
        print("request failed:", type(e).__name__)
        continue
    print("status", r.status_code, "| content-type", r.headers.get("content-type"), "| bytes", len(r.content))
    body = redact(r.text, key)
    (OUT / f"_probe_{name}.txt").write_text(body, encoding="utf-8")
    print(body[:1800])
