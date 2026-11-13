"""data/raw/kcisa 의 공연(perf)·대관(rental) XML 페이지를 표로 만들어 data/interim 에 저장하고 요약한다.
날짜는 구조화 필드가 없어 description 본문에서 정규식으로 추출한 '후보'이다(검증 전).
실행: python -X utf8 -I src/parse_kcisa.py   (프로젝트 루트에서)
"""
import html
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "kcisa"
INT = ROOT / "data" / "interim"
INT.mkdir(exist_ok=True)
TAG = re.compile(r"<[^>]+>")
FIELDS = ["title", "regDate", "collectionDb", "subjectKeyword", "extent", "spatial", "spatialCoverage", "temporalCoverage", "temporal", "url", "description"]


def load(dirname):
    rows = []
    for p in sorted((RAW / dirname).glob("page_*.txt")):
        for it in ET.parse(p).getroot().findall(".//item"):
            rows.append({f: (it.findtext(f) or "").strip() for f in FIELDS})
    return pd.DataFrame(rows)


def plain(s):
    return " ".join(html.unescape(TAG.sub(" ", html.unescape(s))).split())


# 'YYYY.MM.DD' / 'YYYY-MM-DD' / 'YYYY년 M월 D일' (연도가 명시된 것만 신뢰)
DATE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def dates_in(text):
    out = []
    for y, m, d in DATE.findall(text):
        try:
            out.append(pd.Timestamp(int(y), int(m), int(d)).date())
        except ValueError:
            pass
    return sorted(set(out))


perf = load("perf_rows100")
perf["text"] = perf["description"].map(plain)
perf["dates"] = (perf["title"] + " " + perf["text"]).map(dates_in)
perf["n_dates"] = perf["dates"].map(len)
perf["first_date"] = perf["dates"].map(lambda d: d[0] if d else None)
perf["has_time"] = perf["temporalCoverage"].str.contains(r"\d{1,2}:\d{2}")
perf.drop(columns=["description"]).to_csv(INT / "perf_parsed.csv", index=False, encoding="utf-8-sig")

rental = load("rental_rows100")
rental["year_in_title"] = rental["title"].str.extract(r"(20\d{2})")[0]
rental.drop(columns=["description"]).to_csv(INT / "rental_parsed.csv", index=False, encoding="utf-8-sig")

L = []
L.append("# KCISA 공연·대관 파싱 요약 (자동 생성)\n")
L.append(f"## 공연정보 {len(perf):,}행")
L.append(f"- regDate 분포: {perf['regDate'].str[:10].value_counts().head(5).to_dict()}")
L.append(f"- 장소(spatial) 상위: {perf['spatial'].value_counts().head(8).to_dict()}")
L.append(f"- 시설분류(subjectKeyword) 상위: {perf['subjectKeyword'].value_counts().head(8).to_dict()}")
L.append(f"- temporalCoverage 에 시각(HH:MM) 있음: {int(perf['has_time'].sum()):,}행")
L.append(f"- extent(공연시간) 값 있음: {int((~perf['extent'].isin(['', '.'])).sum()):,}행")
L.append(f"- 본문/제목에서 연도 포함 날짜 추출 성공: {int((perf['n_dates'] > 0).sum()):,}행")
fd = pd.to_datetime(perf["first_date"], errors="coerce")
L.append(f"- 추출 첫 날짜의 연도 분포: {fd.dt.year.value_counts().sort_index().to_dict()}")
L.append(f"- 2025년 날짜 후보가 있는 행: {int(perf['dates'].map(lambda d: any(x.year == 2025 for x in d)).sum()):,}")
L.append(f"- 제목 중복: {int(perf['title'].duplicated().sum())}행")
L.append(f"\n## 대관정보 {len(rental):,}행")
L.append(f"- 제목 속 연도 분포: {rental['year_in_title'].value_counts().sort_index().to_dict()}")
L.append(f"- 장소(spatial) 상위: {rental['spatial'].value_counts().head(8).to_dict()}")
L.append(f"- 날짜 필드(temporalCoverage) 값 있음: {int((rental['temporalCoverage'] != '').sum())}행, description 값 있음: {int((rental['description'] != '').sum())}행")
txt = "\n".join(L)
print(txt)
(ROOT / "report" / "kcisa_parse_summary.md").write_text(txt, encoding="utf-8")
