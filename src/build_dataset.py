"""모델링용 시간 단위 데이터셋을 만든다 -> data/interim/model_hourly.csv, report/dataset_check.md

- 기관 연계 표(linked_hourly.csv)의 주차대수(cars)가 목표 변수.
- 입출차 복원(hourly_recon.csv)의 시간별 inflow/outflow, occ_end(= 다음 정시 스냅숏)를 붙인다.
- 유효일(valid_day): 원천 입출차가 존재하는 날. 기준은 '그날 입차 건수 > 0' 이고 아래 공백 구간이 아닐 것.
  * 주차대수 값으로 거르면 설·추석 연휴처럼 실제로 한산한 날이 빠지므로 쓰지 않는다(입차 건수 기준).
  * 원천 공백: 2025-07-31 ~ 09-30, 2025-11-01 이후, 그리고 매월 말일(입차 0건).
실행: python -X utf8 -I src/build_dataset.py   (프로젝트 루트에서)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
inst = pd.read_csv(ROOT / "data/interim/linked_hourly.csv", encoding="utf-8-sig", parse_dates=["ts"], keep_default_na=False, na_values=[""])
rec = pd.read_csv(ROOT / "data/interim/hourly_recon.csv", parse_dates=["ts"])
rec["occ_end"] = rec["occ_start"].shift(-1)

df = rec[["ts", "inflow", "outflow", "occ_end"]].merge(inst[["ts", "cars", "temp", "wind", "rain", "hum", "holiday", "show", "audience"]], on="ts", how="left")
df["date"] = df["ts"].dt.normalize()
day_in = df.groupby("date")["inflow"].transform("sum")
df["day_inflow"] = day_in
df["month"] = df["ts"].dt.month
gap = ((df["ts"] >= "2025-07-31") & (df["ts"] < "2025-10-01")) | (df["ts"] >= "2025-11-01")
df["valid_day"] = ((day_in > 0) & ~gap).astype(int)

# 특징
df["hour"] = df["ts"].dt.hour
df["dow"] = df["ts"].dt.dayofweek
hol = df["holiday"].fillna("")
df["hol"] = (hol != "").astype(int)
df["hol_long"] = hol.str.contains("연휴").astype(int)
df["is_off"] = ((df["dow"] >= 5) | (df["hol"] == 1)).astype(int)
df["rain_pos"] = (df["rain"].fillna(0) > 0).astype(int)
df["show_hour"] = df["show"].notna().astype(int)
df["perf_day"] = df.groupby("date")["show_hour"].transform("max")
df["audience"] = df["audience"].fillna(0)
df["aud_daymax"] = df.groupby("date")["audience"].transform("max")
df = df.rename(columns={"audience": "aud_hour"})
df.to_csv(ROOT / "data/interim/model_hourly.csv", index=False, encoding="utf-8")

v = df[df["valid_day"] == 1]
vd = v.groupby("date").agg(m=("month", "first"), perf=("perf_day", "max"), off=("is_off", "max"), n=("cars", "count"))
L = ["# 모델링 데이터셋 점검 (자동 생성)\n",
     f"- 전체 시간 {len(df):,}, 유효일 {v['date'].nunique()}일({len(v):,}시간), 목표(cars) 결측 {int(v['cars'].isna().sum())}",
     f"- 월별 유효일: {vd.groupby('m').size().to_dict()}",
     f"- 공연일(공연명 있는 날) 유효일 {int(vd['perf'].sum())}일 / 비공연일 {int((vd['perf'] == 0).sum())}일, 휴무일(주말·공휴일) {int(vd['off'].sum())}일",
     f"- 월별 공연일: {vd.groupby('m')['perf'].sum().astype(int).to_dict()}",
     f"- 시간 행 수가 24 미만인 유효일: {int((vd['n'] < 24).sum())}일(기관 표의 누락 시간)",
     f"- 목표 결측이 있는 유효 시간 {int(v['cars'].isna().sum())} → 학습에서 제외",
     f"- 복원 occ_end vs 기관 cars(유효일): 상관 {float(v[['occ_end', 'cars']].dropna().corr().iloc[0, 1]):.3f}",
     "- 정상일 기준 변경 메모: report 15절의 '일 최대 1,500대 이상' 기준은 설·추석 연휴를 잘못 제외한다. 이 데이터셋은 입차 건수 기준을 쓴다."]
(ROOT / "report/dataset_check.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
