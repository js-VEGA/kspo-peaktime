"""data.go.kr 파일데이터 4종을 data/raw 로 내려받는다 (표준 라이브러리만 사용).

포털 '다운로드' 버튼과 같은 순서로 요청한다:
  1) 상세 페이지에서 버튼 인자 추출 -> 2) selectFileDataDownload.do 로 파일 ID 조회
  -> 3) check-limit.json 으로 한도 확인 -> 4) fileDownload.do 로 파일 수신.
캡차(needCaptcha)가 요구되면 우회하지 않고 중단한다.
실행: python -I src/download_public.py   (프로젝트 루트에서)
"""
import hashlib
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from http.cookiejar import CookieJar
from pathlib import Path

BASE = "https://www.data.go.kr"
DATASETS = {
    "15138735": "올림픽공원 입출차 정보 (2024-07)",
    "15131671": "월별주차현황",
    "15149169": "영문 공연정보",
    "15164156": "주차장 혼잡도 정보",
    "15147873": "공공데이터 개방목록 (기관 전체 목록)",
}
UA = "Mozilla/5.0 (research; KSPO contest data collection)"
RAW = Path(__file__).resolve().parent.parent / "data" / "raw"

opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
opener.addheaders = [("User-Agent", UA)]


def post(path, data, referer):
    req = urllib.request.Request(
        BASE + path,
        data=urllib.parse.urlencode(data).encode(),
        headers={"Referer": referer, "X-Requested-With": "XMLHttpRequest"},
    )
    with opener.open(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_one(pk, label):
    page_url = f"{BASE}/data/{pk}/fileData.do"
    html = opener.open(page_url, timeout=60).read().decode("utf-8", errors="replace")
    buttons = re.findall(
        r"fn_fileDataDown\('(\d+)',\s*'([^']+)',\s*'([^']*)',\s*'(\d+)',\s*'(\d+)'\)", html
    )
    if not buttons:
        raise RuntimeError(f"{pk}: 다운로드 버튼을 찾지 못함")
    results = []
    for pub_pk, detail_pk, _atch, sn, hist in buttons:
        meta = json.loads(
            post(
                "/tcs/dss/selectFileDataDownload.do",
                {
                    "publicDataDetailPk": detail_pk,
                    "publicDataPk": pub_pk,
                    "atchFileId": "",
                    "fileDetailSn": sn,
                    "publicDataTyCode": "PR0051",
                },
                page_url,
            )
        )
        if not meta.get("status"):
            raise RuntimeError(f"{pk}: 파일 ID 조회 실패 {meta.get('error')}")
        info = meta["fileDataRegistVO"]
        atch_id, orig = meta["atchFileId"], info.get("orginlFileNm") or f"{pk}.csv"
        data_nm = info.get("dataNm") or pk
        limit = json.loads(post("/cmm/cmm/check-limit.json", {"atchFileId": atch_id, "fileDetailSn": sn}, page_url))
        if limit.get("needCaptcha"):
            raise RuntimeError(f"{pk}: 포털이 캡차를 요구함 -> 브라우저에서 직접 내려받아 data/raw 에 넣어 주세요")
        url = f"{BASE}/cmm/cmm/fileDownload.do?atchFileId={atch_id}&fileDetailSn={sn}&dataNm={urllib.parse.quote(data_nm)}"
        req = urllib.request.Request(url, headers={"Referer": page_url})
        with opener.open(req, timeout=300) as r:
            body = r.read()
        out = RAW / f"{pk}_{orig}"
        out.write_bytes(body)
        results.append(
            {
                "dataset_id": pk,
                "label": label,
                "saved_as": out.name,
                "original_name": orig,
                "portal_data_name": data_nm,
                "portal_declared_rows": info.get("atchFileCo"),
                "bytes": len(body),
                "sha256": hashlib.sha256(body).hexdigest(),
                "source_page": page_url,
                "downloaded_at": datetime.now().isoformat(timespec="seconds"),
            }
        )
        print(f"OK {out.name}  {len(body):,} bytes")
        time.sleep(1.5)  # 포털 부하·한도 고려
    return results


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    targets = sys.argv[1:] or list(DATASETS)  # 인자로 ID를 주면 그것만 받는다
    mpath = RAW / "_manifest.json"
    old = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else []
    merged = {m["saved_as"]: m for m in old}
    failed = []
    for pk in targets:
        try:
            for m in fetch_one(pk, DATASETS[pk]):
                merged[m["saved_as"]] = m
        except Exception as e:  # noqa: BLE001
            failed.append((pk, str(e)))
            print(f"FAIL {pk}: {e}", file=sys.stderr)
    manifest = list(merged.values())
    mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {len(targets) - len(failed)} ok, {len(failed)} failed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
