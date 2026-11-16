"""연계 API(API_CPM_009) 페이지에서 시간 단위 행('입출차정보(추가정보)')을 모아 data/interim/linked_hourly.csv 로 저장한다.
같은 응답에 차량 단위 행(입출차정보)이 섞여 있어 DESCRIPTION 에 '주차대수'가 있는 행만 쓴다.
실행: python -X utf8 -I src/parse_linked.py   (프로젝트 루트에서)
"""
import glob
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
rows = {}
for f in sorted(glob.glob(str(ROOT / "data" / "raw" / "kcisa" / "linked_rows*" / "page_*.txt"))):
    for it in ET.parse(f).getroot().findall(".//item"):
        d = it.findtext("DESCRIPTION") or ""
        if "주차대수" not in d:
            continue
        m = re.match(
            r"\s*주차대수:(?P<cars>[^,]*),\s*방문객:(?P<visitors>[^,]*),\s*기온:(?P<temp>[^,]*),\s*풍향:(?P<wind>[^,]*),"
            r"\s*강수량:(?P<rain>[^,]*),\s*습도:(?P<hum>[^,]*),\s*휴일:(?P<holiday>[^,]*),\s*공연명:(?P<show>.*),\s*공연관람객수:(?P<audience>[^,]*)\s*$",
            d, flags=re.S)
        if not m:
            print("파싱 실패:", it.findtext("LOCAL_ID"), d[:80])
            continue
        r = m.groupdict()
        r["show"] = " ".join(r["show"].split())
        r["local_id"] = int(it.findtext("LOCAL_ID"))
        r["ts"] = it.findtext("ISSUED_DATE")
        rows[r["local_id"]] = r
df = pd.DataFrame(rows.values()).sort_values("ts")
for c in ("cars", "visitors", "temp", "wind", "rain", "hum", "audience"):
    df[c] = pd.to_numeric(df[c].replace("", None), errors="coerce")
df["ts"] = pd.to_datetime(df["ts"])
out = ROOT / "data" / "interim" / "linked_hourly.csv"
df.to_csv(out, index=False, encoding="utf-8-sig")
print(f"{len(df):,}행 -> {out.relative_to(ROOT)}  기간 {df['ts'].min()} ~ {df['ts'].max()}")
print("고유 일시", df["ts"].nunique(), "| 공연 있는 행", int((df["show"] != "").sum()), "| 공연명 고유", df.loc[df['show'] != '', 'show'].nunique())
print("결측:", df[["cars", "visitors", "temp", "wind", "rain", "hum", "audience"]].isna().sum().to_dict())
print(df[["cars", "visitors", "temp", "audience"]].describe().round(1).to_string())
print("휴일 값:", df["holiday"].value_counts().head(5).to_dict())
