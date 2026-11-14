"""2024-07 입출차(15138735)를 사이트용 JSON(docs/data/profile_2024_07.json)으로 내보낸다.
요일별로 '공연이 없던 날'의 시간대별 평균·최소·최대 입차 대수를 만들고, 공연일은 실제 관측값을 따로 싣는다.
예측값이 아니라 관측 요약이다(분위수는 요일당 표본이 4~5일이라 쓰지 않고 최소~최대를 쓴다).
실행: python -X utf8 -I src/export_site_data.py   (프로젝트 루트에서)
"""
import glob
import json
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "docs" / "data" / "profile_2024_07.json"
LABELS = "월화수목금토일"

v = pd.read_csv(glob.glob(str(RAW / "15138735_*"))[0], encoding="cp949", dtype=str)
v["in"] = pd.to_datetime(v["입차일시"])
day = v["in"].dt.floor("D")
hour = v["in"].dt.hour
tab = pd.crosstab(day, hour).reindex(columns=range(24), fill_value=0)
tab = tab.reindex(pd.date_range("2024-07-01", "2024-07-31"), fill_value=0)

e = pd.read_csv(glob.glob(str(RAW / "15149169_*"))[0], encoding="cp949", dtype=str)
e["d"] = pd.to_datetime(e["공연일자"])
e = e[(e["d"].dt.year == 2024) & (e["d"].dt.month == 7)]
perf = {d.date(): list(g["공연제목"]) for d, g in e.groupby("d")}

dows = []
for dow in range(7):
    days = [d for d in tab.index if d.dayofweek == dow]
    normal = [d for d in days if d.date() not in perf]
    arr = tab.loc[normal].values
    dows.append({
        "dow": dow,
        "label": LABELS[dow],
        "n_days": len(days),
        "n_normal_days": len(normal),
        "mean": [round(float(x), 1) for x in arr.mean(axis=0)],
        "min": [int(x) for x in arr.min(axis=0)],
        "max": [int(x) for x in arr.max(axis=0)],
        "perf_days": [
            {"date": d.date().isoformat(), "events": perf[d.date()], "values": [int(x) for x in tab.loc[d].values]}
            for d in days if d.date() in perf
        ],
    })

data = {
    "meta": {
        "title": "올팍 피크타임 시험판",
        "source": "한국체육산업개발(주) 올림픽공원 입출차 정보(공공데이터포털 15138735), 영문 공연정보(15149169)",
        "period": "2024-07-01 ~ 2024-07-31",
        "scope": "동2문·남2문·북2문 주차구역의 입차 건수(시간대별)",
        "kind": "관측 요약(예측 아님)",
        "total_rows": int(len(v)),
        "generated": datetime.now().strftime("%Y-%m-%d"),
    },
    "days": dows,
}
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)")
for d in dows:
    print(d["label"], f"일수 {d['n_days']} (공연 제외 {d['n_normal_days']})", "공연일", [p["date"] for p in d["perf_days"]], "피크시각", int(np.argmax(d["mean"])))
