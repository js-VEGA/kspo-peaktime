"""연계 시간 단위 표(data/interim/linked_hourly.csv) 탐색 분석 -> report/linked_eda.md
실행: python -X utf8 -I src/eda_linked.py   (프로젝트 루트에서)
"""
import glob
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data" / "interim" / "linked_hourly.csv", encoding="utf-8-sig", parse_dates=["ts"], keep_default_na=False, na_values=[""])
df["show"] = df["show"].fillna("")
df["date"] = df["ts"].dt.date
df["hour"] = df["ts"].dt.hour
df["dow"] = df["ts"].dt.dayofweek
L = ["# 연계 시간 단위 표 탐색 (자동 생성)\n"]

# 1) 커버리지
full = pd.date_range("2025-01-01 00:00", "2025-12-31 23:00", freq="h")
miss = full.difference(pd.DatetimeIndex(df["ts"]))
L.append(f"## 커버리지\n- 행 {len(df):,} / 1년 8,760시간 → 누락 {len(miss):,}시간")
L.append(f"- 누락 시간대 분포(시각별): {pd.Series(miss.hour).value_counts().sort_index().to_dict()}")
L.append(f"- 시각별 행 수: {df['hour'].value_counts().sort_index().to_dict()}")
L.append(f"- 마지막 일시 {df['ts'].max()} (이후 2025-12-31 15~23시 누락)")
bymonth = df.groupby(df["ts"].dt.month).size().to_dict()
L.append(f"- 월별 행 수: {bymonth}")

# 2) 방문객 = 주차대수 × 계수?
ratio = (df["visitors"] / df["cars"]).round(2)
L.append("\n## 방문객 / 주차대수 비율")
L.append(f"- 분포(상위): {ratio.value_counts().head(6).to_dict()}")
L.append(f"- 정확히 3.0인 행 비율 {float((ratio == 3.0).mean()):.1%}, 비율의 5/50/95% 분위수 {ratio.quantile([.05, .5, .95]).round(2).tolist()}")

# 3) 주차대수 시각·요일 패턴
L.append("\n## 주차대수 평균(시각별, 전체/주말·평일)")
wd = df[df["dow"] < 5].groupby("hour")["cars"].mean().round(0)
we = df[df["dow"] >= 5].groupby("hour")["cars"].mean().round(0)
L.append("| 시각 | 평일 | 주말 |\n|---|---|---|")
for h in range(24):
    L.append(f"| {h} | {int(wd.get(h, 0))} | {int(we.get(h, 0))} |")
L.append(f"- 최대 {int(df['cars'].max())}대 ({df.loc[df['cars'].idxmax(), 'ts']}), 야간(0~5시) 평균 {df[df['hour'] <= 5]['cars'].mean():.0f}대")

# 4) 2024-07 입출차로 계산한 재차(점유)와 크기 비교 (3개 출입구 한정, 다른 해)
v = pd.read_csv(glob.glob(str(ROOT / "data/raw/15138735_*"))[0], encoding="cp949", dtype=str)
vin, vout = pd.to_datetime(v["입차일시"]), pd.to_datetime(v["출차일시"])
t = pd.date_range("2024-07-02 00:00", "2024-07-30 23:00", freq="h")
a = np.sort(vin.values); b = np.sort(vout.values)
occ = pd.Series(np.searchsorted(a, t.values, side="right") - np.searchsorted(b, t.values, side="right"), index=t)
o = occ.groupby(occ.index.hour).mean().round(0)
j = df[(df["ts"].dt.month == 7)].groupby("hour")["cars"].mean().round(0)
L.append("\n## 크기 비교: 2024-07 입출차로 계산한 점유 대수 vs 2025-07 주차대수 (시각별 평균)")
L.append("| 시각 | 2024-07 점유(3개 출입구) | 2025-07 주차대수 |\n|---|---|---|")
for h in range(24):
    L.append(f"| {h} | {int(o.get(h, 0))} | {int(j.get(h, 0))} |")
L.append(f"- 시각 패턴 상관(24점): {float(np.corrcoef(o.reindex(range(24)).fillna(0), j.reindex(range(24)).fillna(0))[0, 1]):.2f}")

# 5) 월별주차현황과 월 단위 비교 (올림픽공원 2025)
m = pd.read_csv(glob.glob(str(ROOT / "data/raw/15131671_*"))[0], encoding="cp949", dtype=str)
m = m[(m["연도"] == "2025") & (m["주차장소"] == "올림픽공원")].copy()
m["월"] = m["월"].str.replace("월", "").astype(int); m["n"] = m["주차대수"].astype(int)
mm = df.groupby(df["ts"].dt.month)["cars"].agg(["mean", "sum"])
mm["월별주차현황"] = m.set_index("월")["n"]
mm["ratio_sum"] = (mm["월별주차현황"] / mm["sum"]).round(3)
L.append("\n## 월별주차현황(2025, 올림픽공원) vs 시간 단위 주차대수\n" + mm.round(1).to_markdown())
L.append(f"- 월 평균 주차대수와 월별주차현황의 상관 {float(np.corrcoef(mm['mean'], mm['월별주차현황'])[0, 1]):.2f}")

# 6) 공연
sh = df[df["show"] != ""]
L.append("\n## 공연")
L.append(f"- 공연 있는 행 {len(sh):,}, 공연이 있는 날 {sh['date'].nunique()}일, 공연명 고유 {sh['show'].nunique()}")
L.append(f"- 관람객 수>0 인데 공연명 없음: {int(((df['audience'] > 0) & (df['show'] == '')).sum())}행 / 공연명 있는데 관람객 0: {int(((df['audience'] == 0) & (df['show'] != '')).sum())}행")
L.append(f"- 공연일의 시각별 행 수: {sh['hour'].value_counts().sort_index().to_dict()}")
dayaud = sh.groupby("date")["audience"].max()
L.append(f"- 일별 관람객 수(해당일 최대) 분위수 50/90/100%: {dayaud.quantile([.5, .9, 1]).astype(int).tolist()}")
L.append(f"- 한 행에 공연명 여러 개(콤마·개행으로 이어짐)로 보이는 행: {int(sh['show'].str.contains(', ').sum())}")
# 공연일 vs 같은 요일 비공연일 (시각 평균)
pdays = set(sh["date"]); df["perf"] = df["date"].isin(pdays)
g = df.groupby(["perf", "hour"])["cars"].mean().unstack(0).round(0)
L.append("\n## 시각별 평균 주차대수: 공연일 vs 비공연일(요일 구성 미보정, 탐색용)\n" + g.to_markdown())

# 7) 기상
L.append("\n## 기상\n- 기온 결측 1, 강수량 결측 " + str(int(df['rain'].isna().sum())) + f"행(= {df['rain'].isna().mean():.0%}), 강수량>0인 행 {int((df['rain'] > 0).sum())}")
L.append(f"- 강수량 0.0으로 기록된 행 {int((df['rain'] == 0).sum())}")
L.append(f"- 휴일 라벨 종류: {df['holiday'].fillna('').value_counts().head(12).to_dict()}")

txt = "\n".join(L)
(ROOT / "report" / "linked_eda.md").write_text(txt, encoding="utf-8")
print("saved report/linked_eda.md", len(txt))
