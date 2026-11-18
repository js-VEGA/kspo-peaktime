"""입출차 전체구역(API_CPM_008) 차량 단위 행을 data/interim/vehicles.csv.gz 로 모으고 품질을 점검한다.
수집이 끝나지 않았어도 받은 페이지만으로 실행할 수 있다(그 경우 '부분 표본'이다).
실행: python -X utf8 -I src/parse_vehicles.py   (프로젝트 루트에서)
"""
import glob
import gzip
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
PAGES = sorted(glob.glob(str(ROOT / "data" / "raw" / "kcisa" / "allzone_bulk*" / "page_*.xml.gz")))
PAT = re.compile(r"입구:(?P<gate_in>[^,]*),\s*입차시간:(?P<t_in>[^,]*),\s*출구:(?P<gate_out>[^,]*),\s*출차시간:(?P<t_out>.*)$", re.S)

recs, bad, titles = [], 0, 0
for f in PAGES:
    with gzip.open(f, "rt", encoding="utf-8") as g:
        root = ET.fromstring(g.read())
    for it in root.findall(".//item"):
        d = (it.findtext("DESCRIPTION") or "").strip()
        m = PAT.match(d)
        if not m:
            bad += 1
            continue
        r = m.groupdict()
        r["id"] = it.findtext("LOCAL_ID")
        r["issued"] = it.findtext("ISSUED_DATE")
        r["title"] = it.findtext("TITLE")
        recs.append(r)
df = pd.DataFrame(recs)
n0 = len(df)
df = df.drop_duplicates("id")
for c in ("t_in", "t_out", "issued"):
    df[c] = pd.to_datetime(df[c].str.strip().replace("", None), errors="coerce")
df["gate_in"] = df["gate_in"].str.strip()
df["gate_out"] = df["gate_out"].str.strip()
out = ROOT / "data" / "interim" / "vehicles.csv.gz"
df.to_csv(out, index=False, encoding="utf-8")

L = ["# 입출차 전체구역 차량 단위 행 점검 (자동 생성)\n"]
L.append(f"- 읽은 페이지 {len(PAGES)}개, 파싱된 행 {n0:,}, ID 중복 제거 후 {len(df):,}, 파싱 실패 {bad}")
L.append("- **완전한 전량이 아니면 부분 표본이다.** 서버 순서가 날짜순이 아니라서 일부 페이지만으로는 일별·시간별 재차를 계산할 수 없다.")
L.append(f"- 입차시간 범위 {df['t_in'].min()} ~ {df['t_in'].max()}, 입차시간 변환 실패 {int(df['t_in'].isna().sum())}")
L.append(f"- 출차시간 없음(미출차·장기주차 추정) {int(df['t_out'].isna().sum()):,}행 ({df['t_out'].isna().mean():.1%})")
L.append(f"- ISSUED_DATE == 입차시간 인 행 {float((df['issued'] == df['t_in']).mean()):.1%}")
dur = (df["t_out"] - df["t_in"]).dt.total_seconds() / 3600
L.append(f"- 주차시간(시간) 분위수 1/10/50/90/99%: {[round(float(dur.quantile(q)), 2) for q in (.01, .1, .5, .9, .99)]}")
L.append(f"- 출차<입차 {int((dur < 0).sum())}건, 24시간 초과 {int((dur > 24).sum())}건, 7일 초과 {int((dur > 168).sum())}건, 30일 초과 {int((dur > 720).sum())}건")
L.append(f"- 입구 종류: {df['gate_in'].value_counts().to_dict()}")
L.append(f"- 출구 종류: {df['gate_out'].value_counts().head(12).to_dict()}")
L.append(f"- 입차 월별 행 수: {df.groupby(df['t_in'].dt.to_period('M')).size().astype(int).to_dict()}")
L.append(f"- 같은 시각 같은 입구 중복 입차 기록(분·초 동일): {int(df.duplicated(['t_in', 'gate_in']).sum()):,}")
txt = "\n".join(L)
(ROOT / "report" / "vehicles_check.md").write_text(txt, encoding="utf-8")
print(txt)
