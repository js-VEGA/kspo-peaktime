"""공연 관람객 규모와 주차 수요의 관계(조건부 증분, 인과 아님) -> report/perf_effect.md

배경: 기관 표의 '공연 있는 날'은 주말 65일 전부 + 금요일 23일 + 평일/공휴일 소수라서 '공연일 vs 비공연일' 비교는 요일 효과와 섞인다.
그래서 같은 요일 유형(주말/금요일/휴일) 안에서 일 관람객 수(aud_daymax)가 클수록 주차 지표가 얼마나 달라지는지를 본다.
 - 지표: 일 입차 건수(원천, 규모 보정 불필요), 저녁(17~21시) 평균 재차(기관 표), 퇴장 피크(저녁 18~23시 출차 건수).
 - 통제: 요일 더미, 월 더미, 일평균기온의 월 내 편차. 불확실성: 부트스트랩이 아니라 HC1 강건 표준오차(n 작음 주의).
실행: python -X utf8 -I src/perf_effect.py   (프로젝트 루트에서)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
d = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
d = d[(d["valid_day"] == 1) & d["cars"].notna()]

g = d.groupby("date")
day = pd.DataFrame({
    "month": g["month"].first(), "dow": g["dow"].first(), "off": g["is_off"].max(),
    "aud": g["aud_daymax"].max() / 1000.0, "perf": g["perf_day"].max(),
    "temp": g["temp"].mean(), "inflow": g["inflow"].sum(),
})
day["eve_cars"] = d[d["hour"].between(17, 21)].groupby("date")["cars"].mean()
day["eve_out"] = d[d["hour"].between(18, 23)].groupby("date")["outflow"].sum()
day["temp_dev"] = day["temp"] - day.groupby("month")["temp"].transform("mean")
day["wkgrp"] = np.where(day["off"] == 1, np.where(day["dow"] >= 5, "주말", "공휴일"), np.where(day["dow"] == 4, "금요일", "평일"))

L = ["# 공연 관람객 규모와 주차 지표 (자동 생성, 조건부 증분 — 인과 아님)\n",
     "### 공연일 표시와 요일의 겹침\n", pd.crosstab(day["wkgrp"], day["perf"].rename("공연일")).to_markdown(),
     "\n주말 65일은 전부 '공연일'이라 공연일 더미는 주말 더미와 구분되지 않는다. 그래서 아래는 **같은 요일 유형 안**에서 일 관람객 수의 변동만 쓴다.\n",
     "일 관람객 수(해당일 시간별 관람객 수의 최댓값, 천 명) 분포(공연일):\n",
     day[day["perf"] == 1].groupby("wkgrp")["aud"].describe()[["count", "min", "50%", "max"]].round(1).to_markdown()]


def ols(y, X, names):
    X = np.column_stack([np.ones(len(y)), X]); b = np.linalg.lstsq(X, y, rcond=None)[0]
    r = y - X @ b; XtXi = np.linalg.pinv(X.T @ X)
    meat = (X * r[:, None]).T @ (X * r[:, None]) * len(y) / max(len(y) - X.shape[1], 1)
    se = np.sqrt(np.diag(XtXi @ meat @ XtXi))
    return b, se, 1 - r.var() / y.var()


def fit(sub, ycol, label):
    sub = sub.dropna(subset=[ycol, "temp_dev", "aud"])
    dow = pd.get_dummies(sub["dow"], prefix="d", drop_first=True).astype(float)
    mon = pd.get_dummies(sub["month"], prefix="m", drop_first=True).astype(float)
    X = pd.concat([sub[["aud", "temp_dev"]], dow, mon], axis=1)
    b, se, r2 = ols(sub[ycol].values.astype(float), X.values.astype(float), None)
    return label, len(sub), b[1], se[1], r2


rows = []
for grp_name, sel in (("주말(토·일)", day["wkgrp"] == "주말"), ("금요일", day["wkgrp"] == "금요일"), ("주말+금요일", day["wkgrp"].isin(["주말", "금요일"]))):
    for ycol, yl in (("inflow", "일 입차 건수"), ("eve_cars", "저녁 17~21시 평균 재차"), ("eve_out", "18~23시 출차 건수")):
        sub = day[sel & (day["perf"] == 1)]
        lab, n, b, se, r2 = fit(sub, ycol, f"{grp_name} · {yl}")
        rows.append((lab, n, b, b - 1.96 * se, b + 1.96 * se, r2, float(sub[ycol].mean())))
T = pd.DataFrame(rows, columns=["구분·지표", "일수", "관람객 +1천 명당 증분", "95% 하한", "95% 상한", "R²(통제 포함)", "지표 평균"])
L += ["\n### 일 관람객 +1천 명당 증분 (요일·월 더미, 기온 편차 통제, HC1 강건 CI)\n", T.round(2).to_markdown(index=False)]

# 관람객 구간별 단순 평균(통제 없음, 같은 요일 유형)
bins = pd.cut(day["aud"], [-0.01, 3, 8, 14, 100], labels=["≤3천", "3~8천", "8~14천", ">14천"])
S = day[(day["perf"] == 1) & day["wkgrp"].isin(["주말", "금요일"])].assign(구간=bins).groupby(["wkgrp", "구간"], observed=True).agg(일수=("inflow", "size"), 입차=("inflow", "mean"), 저녁재차=("eve_cars", "mean"), 저녁출차=("eve_out", "mean")).round(0)
L += ["\n### 관람객 규모 구간별 평균(통제 없음, 같은 요일 유형 안)\n", S.to_markdown()]

# 금요일: 공연 있음 vs 없음 (같은 요일)
F = day[day["wkgrp"] == "금요일"].groupby("perf").agg(일수=("inflow", "size"), 입차=("inflow", "mean"), 저녁재차=("eve_cars", "mean"), 저녁출차=("eve_out", "mean")).round(0)
L += ["\n### 금요일: 공연 있는 날 vs 없는 날 (같은 요일, 통제 없음)\n", F.to_markdown()]
txt = "\n".join(L)
(ROOT / "report/perf_effect.md").write_text(txt, encoding="utf-8")
print(txt)
