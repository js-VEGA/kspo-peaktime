"""다가오는 공연(KOPIS) → docs/data/upcoming.json

입력: data/raw/kopis/list_upcoming/*.xml, data/raw/kopis/detail/*.xml, data/raw/kopis/facility_FC001247.xml,
      data/interim/kopis_match.json (src/kopis_match.py)
갱신: python -I src/kopis_fetch.py list --from <오늘> --to <약 4개월 뒤> --tag upcoming  (기존 list_upcoming 폴더를 비운 뒤)
      python -I src/kopis_fetch.py detail --tag upcoming
      python -I src/kopis_match.py ; python -I src/export_upcoming.py --snapshot <수집한 날>

- 회차별 날짜는 KOPIS에 없다. 공연시간 안내(dtguidance)의 '○요일', '○요일 ~ ○요일' 만 읽어 공연 요일로 쓰고,
  그 밖의 글자가 남으면(해석 불가) days=null 로 두어 화면에서 '공연 기간'으로만 표시한다. HOL(공휴일) 표기는 요일 판정에 쓰지 않는다.
- 공연장별 규모 제안: 2025년 이름까지 일치한 공연일 중 다른 공연장 공연이 없던 날(단독일)의 일 관람객(시간별 최댓값) 중앙값을
  화면의 공연 규모 경계(8천 명, 1.4만 명)에 넣는다. 단독일이 5일 미만인 공연장은 제안하지 않는다(p=null).
"""
import argparse
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kopis"
DOW = "월화수목금토일"
MIN_N = 5
EDGES = (8000, 14000)  # src/export_site_data_2025.py TIERS 와 같은 경계


def parse_days(g):
    if not g:
        return None
    days = set()
    pat = re.compile(r"([월화수목금토일])요일(?:\s*~\s*([월화수목금토일])요일)?\s*\(([^)]*)\)")
    for m in pat.finditer(g):
        a = DOW.index(m.group(1))
        b = DOW.index(m.group(2)) if m.group(2) else a
        if b < a:
            return None
        days.update(range(a, b + 1))
    rest = pat.sub("", g)
    rest = re.sub(r"HOL\s*\([^)]*\)", "", rest)
    if re.sub(r"[\s,]", "", rest) or not days:
        return None
    return sorted(days)


def tier_of(v):
    return 1 if v < EDGES[0] else 2 if v < EDGES[1] else 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=date.today().isoformat())
    ap.add_argument("--from", dest="d0", default=None)
    ap.add_argument("--to", dest="d1", default=None)
    a = ap.parse_args()

    fac = ET.fromstring((RAW / "facility_FC001247.xml").read_text(encoding="utf-8"))
    hall_name = {m.findtext("mt13id"): m.findtext("prfplcnm") for m in fac.iter("mt13")}
    hall_name = {k: ("올림픽공원 " + v if v == "일대" else v) for k, v in hall_name.items()}  # KOPIS 공연장명 '일대' = 공원 일대 행사
    match = json.loads((ROOT / "data/interim/kopis_match.json").read_text(encoding="utf-8"))
    halls = {}
    for h in match["halls"]:
        n = h["n_solo"]
        ok = n >= MIN_N and h["median_solo"] is not None
        halls[h["hall"]] = {"name": hall_name.get(h["hall"], h["name"]), "n": n,
                            "median": round(h["median_solo"]) if h["median_solo"] is not None else None,
                            "min": round(h["min_solo"]) if h["min_solo"] is not None else None,
                            "max": round(h["max_solo"]) if h["max_solo"] is not None else None,
                            "p": tier_of(h["median_solo"]) if ok else None}

    ids, windows = set(), []
    for f in sorted((RAW / "list_upcoming").glob("*.xml")):
        s, e = f.stem.split("_")[:2]
        windows.append((s, e))
        for db in ET.fromstring(f.read_text(encoding="utf-8")).findall(".//db"):
            ids.add(db.findtext("mt20id"))
    d0 = a.d0 or min(w[0] for w in windows)
    d1 = a.d1 or max(w[1] for w in windows)
    fmt = lambda s: f"{s[:4]}-{s[4:6]}-{s[6:]}" if "-" not in s else s
    d0, d1 = fmt(d0), fmt(d1)

    shows, unparsed = [], 0
    for i in sorted(ids):
        db = ET.fromstring((RAW / "detail" / f"{i}.xml").read_text(encoding="utf-8")).find(".//db")
        hall = db.findtext("mt13id")
        g = (db.findtext("dtguidance") or "").strip()
        days = parse_days(g)
        unparsed += days is None
        shows.append({"name": db.findtext("prfnm").strip(), "hall": hall,
                      "hall_name": hall_name.get(hall) or db.findtext("fcltynm"),
                      "from": db.findtext("prfpdfrom").replace(".", "-"), "to": db.findtext("prfpdto").replace(".", "-"),
                      "days": days, "guidance": g})
    shows.sort(key=lambda s: (s["from"], s["name"]))
    out = {
        "meta": {
            "source": "(재)예술경영지원센터 공연예술통합전산망(www.kopis.or.kr)",
            "snapshot": a.snapshot, "range": [d0, d1], "facility": "올림픽공원(KOPIS 공연시설 FC001247)",
            "days_rule": "회차별 날짜는 KOPIS에 없어 공연시간 안내(dtguidance)의 '○요일', '○요일 ~ ○요일' 표기만 공연 요일로 읽는다. 다른 표기가 섞여 해석할 수 없으면 days=null(공연 기간으로만 표시). HOL 표기는 쓰지 않는다.",
            "tier_rule": "2025년 같은 공연장 단독 공연일(이름 일치, 다른 공연장 공연 없음)의 일 관람객(시간별 최댓값) 중앙값을 공연 규모 경계(8천·1.4만 명)에 넣어 제안한다. 단독일 5일 미만 공연장은 제안하지 않는다. 같은 날 여러 공연이면 가장 큰 제안을 쓴다.",
            "match_2025": {k: match[k] for k in ("perf_days", "date_match_strict", "date_match_strict_rate", "date_match_loose", "date_match_loose_rate", "pieces_total", "pieces_matched", "name_match_rate", "kopis_shows_2025")},
            "n_shows": len(shows), "n_days_unparsed": unparsed,
        },
        "halls": halls,
        "shows": shows,
    }
    p = ROOT / "docs/data/upcoming.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"upcoming.json: 공연 {len(shows)}건(요일 해석 불가 {unparsed}), 범위 {d0}~{d1}, 기준일 {a.snapshot}")


if __name__ == "__main__":
    main()
