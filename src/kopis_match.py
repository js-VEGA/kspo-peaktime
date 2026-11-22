"""기관 연계 시간표(2025 공연명·관람객)와 KOPIS 2025 올림픽공원 공연 목록의 매칭률, 공연장별 관람객 분포.

입력: data/interim/linked_hourly.csv, data/raw/kopis/{list_2025,detail,facility_FC001247.xml} (src/kopis_fetch.py)
출력: data/interim/kopis_match.json, 표준출력 요약

정규화 규칙
- 괄호 종류 통일(［］〈〉《》「」【】() → 제거), NFKC, 영문 소문자, 공백·기호 제거(한글·영숫자만 남김)
- 연계 시간표 한 행의 여러 공연: 개행이 없으므로 쉼표로 나누고, 정규화 후 4자 미만 조각은 앞 조각에 붙인다
  (공연명 안의 쉼표 대응, 예: "… 주간 3위, 2").
- 이름 일치: 그날이 공연 기간(prfpdfrom~prfpdto)에 드는 KOPIS 공연 중 하나와
  (a) 한쪽 정규화 문자열이 다른 쪽에 포함되거나 (b) 토큰(공백 기준, 소문자·기호 제거) 자카드 0.5 이상.
날짜 매칭: 공연명이 있는 날 중 KOPIS 공연 기간이 하나라도 걸치는 날의 비율(느슨), 이름까지 맞는 날의 비율(엄격).
"""
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kopis"


def norm(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return re.sub(r"[^0-9a-z가-힣]", "", s)


def toks(s):
    s = unicodedata.normalize("NFKC", s or "").lower()
    return {t for t in re.split(r"[^0-9a-z가-힣]+", s) if len(t) >= 2}


def split_row(text):
    parts = [p.strip() for p in text.split(",")]
    out = []
    for p in parts:
        if out and len(norm(p)) < 4:
            out[-1] = out[-1] + "," + p
        elif p:
            out.append(p)
    return out


def same(a, b):
    na, nb = norm(a), norm(b)
    if len(na) >= 4 and len(nb) >= 4 and (na in nb or nb in na):
        return True
    ta, tb = toks(a), toks(b)
    return bool(ta and tb) and len(ta & tb) / len(ta | tb) >= 0.5


def load_kopis():
    halls = {}
    fac = ET.fromstring((RAW / "facility_FC001247.xml").read_text(encoding="utf-8"))
    for m in fac.iter("mt13"):
        halls[m.findtext("mt13id")] = {"name": m.findtext("prfplcnm"), "seats": m.findtext("seatscale")}
    shows = {}
    for f in sorted((RAW / "detail").glob("*.xml")):
        db = ET.fromstring(f.read_text(encoding="utf-8")).find(".//db")
        if db is None:
            continue
        shows[db.findtext("mt20id")] = {
            "id": db.findtext("mt20id"), "name": db.findtext("prfnm"),
            "from": pd.Timestamp(db.findtext("prfpdfrom").replace(".", "-")),
            "to": pd.Timestamp(db.findtext("prfpdto").replace(".", "-")),
            "hall": db.findtext("mt13id"), "place": db.findtext("fcltynm"),
            "genre": db.findtext("genrenm"), "dtguidance": db.findtext("dtguidance"),
        }
    return halls, list(shows.values())


def main():
    halls, shows = load_kopis()
    d = pd.read_csv(ROOT / "data/interim/linked_hourly.csv", encoding="utf-8-sig", keep_default_na=False, na_values=[""], parse_dates=["ts"])
    d["date"] = d["ts"].dt.normalize()
    d["audience"] = pd.to_numeric(d["audience"], errors="coerce").fillna(0)
    aud = d.groupby("date")["audience"].max()
    s = d[d["show"].notna() & (d["show"].str.strip() != "")]
    day_rows = s.groupby("date")["show"].apply(lambda x: sorted(set(x)))
    perf_days = list(day_rows.index)

    loose, strict = 0, 0
    pieces_total, pieces_matched = 0, 0
    hall_days = {}  # hall -> set(date) (이름 일치 기준)
    unmatched = []
    for day in perf_days:
        live = [sh for sh in shows if sh["from"] <= day <= sh["to"]]
        if live:
            loose += 1
        day_hit = False
        for row in day_rows[day]:
            for p in split_row(row):
                pieces_total += 1
                hits = [sh for sh in live if same(p, sh["name"])]
                if hits:
                    pieces_matched += 1
                    day_hit = True
                    for h in {sh["hall"] for sh in hits}:
                        hall_days.setdefault(h, set()).add(day)
                else:
                    unmatched.append((str(day.date()), p))
        strict += day_hit

    dist = []
    for h, days in sorted(hall_days.items(), key=lambda kv: -len(kv[1])):
        v = aud.reindex(sorted(days)).dropna()
        v = v[v > 0]
        # 같은 날 다른 공연장 공연이 함께 있으면 일 최댓값은 섞인 값이다 → 단독일만 따로 센다
        solo = [dd for dd in days if sum(dd in ds for ds in hall_days.values()) == 1]
        vs = aud.reindex(sorted(solo)).dropna()
        vs = vs[vs > 0]
        dist.append({
            "hall": h, "name": halls.get(h, {}).get("name"), "seats": halls.get(h, {}).get("seats"),
            "n_days": int(len(v)), "median": float(v.median()) if len(v) else None,
            "min": float(v.min()) if len(v) else None, "max": float(v.max()) if len(v) else None,
            "n_solo": int(len(vs)), "median_solo": float(vs.median()) if len(vs) else None,
            "min_solo": float(vs.min()) if len(vs) else None, "max_solo": float(vs.max()) if len(vs) else None,
        })
    n = len(perf_days)
    res = {
        "kopis_shows_2025": len(shows), "perf_days": n,
        "date_match_loose": loose, "date_match_loose_rate": round(loose / n, 4),
        "date_match_strict": strict, "date_match_strict_rate": round(strict / n, 4),
        "pieces_total": pieces_total, "pieces_matched": pieces_matched,
        "name_match_rate": round(pieces_matched / pieces_total, 4),
        "halls": dist, "unmatched_sample": unmatched[:40], "n_unmatched": len(unmatched),
        "dtguidance_examples": sorted({sh["dtguidance"] for sh in shows if sh["dtguidance"]})[:15],
    }
    (ROOT / "data/interim/kopis_match.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k not in ("unmatched_sample", "dtguidance_examples")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
