"""주차장 혼잡도 정보(data.go.kr 15164156) 탐색: 시각 필드 점검, 2025 시간별 재차(기관 주차대수)와 대조, 만차 기록 분포.
실행: .venv/Scripts/python -X utf8 -I src/probe_congestion.py   (프로젝트 루트에서)
출력: 표준 출력(마크다운 조각). 원본 CSV 는 data/raw(깃 제외)에 있다. API 호출 없음.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data/raw/15164156_한국체육산업개발주식회사_주차장혼잡도정보.csv"
SEV = {"원활": 0, "혼잡": 1, "만차": 2}
LAB = ["월", "화", "수", "목", "금", "토", "일"]

d = pd.read_csv(RAW, encoding="cp949")
d["date"] = pd.to_datetime(d["등록일"])
hms = d["등록시간"].str.split(":", expand=True).astype(int)
d["H"], d["MM"], d["SS"] = hms[0], hms[1], hms[2]
d["sev"] = d["혼잡도"].map(SEV)

print("## 1. 구조")
print(f"- 행 {len(d)}, 컬럼 {list(d.columns[:6])}, 결측 {int(d.iloc[:, :6].isna().sum().sum())}")
print(f"- 등록일 범위 {d.date.min().date()} ~ {d.date.max().date()}, 기록 있는 날 {d.date.nunique()}일")
print(f"- 등록시간의 분 = 등록 월: {(d.MM == d.date.dt.month).mean():.0%}, 초 = 등록 일: {(d.SS == d.date.dt.day).mean():.0%} → 분·초는 날짜가 잘못 들어간 값이며 '시'만 정보로 남는다(시 자체의 정확성은 미확인).")
print(f"- 시 분포: {d.H.value_counts().sort_index().to_dict()}")
print(f"- 주차구역 {d['주차구역'].nunique()}개: {d['주차구역'].value_counts().to_dict()}")
print(f"- 같은 주차구역에 주차장아이디가 둘인 경우: " + ", ".join(f"{k}{sorted(v)}" for k, v in d.groupby('주차구역')['주차장아이디'].unique().items() if len(v) > 1))
b = d.groupby(["등록일", "등록시간"])
print(f"- 같은 등록일·시각 묶음 {b.ngroups}개, 묶음 크기 분포 {b.size().value_counts().sort_index().to_dict()}")
dup = d.duplicated(["등록일", "등록시간", "주차구역"], keep=False).sum()
print(f"- 같은 묶음 안 같은 구역 중복 행 {dup}")
print(f"- 하루 묶음 수 분포 {d.groupby('등록일')['등록시간'].nunique().value_counts().sort_index().to_dict()}")
print(f"- 일련번호 1~{d['일련번호'].max()} 중 빠진 번호 {d['일련번호'].max() - d['일련번호'].nunique()}개")
print(f"- 혼잡도 분포 {d['혼잡도'].value_counts().to_dict()}")
m = d.groupby(d.date.dt.to_period("M")).size()
print("- 월별 건수: " + ", ".join(f"{k}: {v}" for k, v in m.items()))
print("- 판별: 정시 샘플이 아니다(하루 1~8회, 시각 불규칙, 구역 일부만 묶음으로 등록). 운영자가 상황을 게시한 이벤트성 기록으로 보인다(작성 방식은 미확인).")

# ---- 2. 2025 분석일과 대조 ----
H = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
H["hol_day"] = H.groupby("date")["hol"].transform("max")
J = json.loads((ROOT / "docs/data/peaktime_2025.json").read_text(encoding="utf-8"))
t0, t1 = J["meta"]["cars_thresholds"]
lv = lambda v: "한산" if v < t0 else ("보통" if v < t1 else "붐빔")
valid = H[H["valid_day"] == 1]
dd = d[d.date.dt.year == 2025].copy()
key = valid.set_index(["date", "hour"])["cars"]


def attach(df, shift):
    idx = list(zip(df["date"], (df["H"] + shift).clip(0, 23)))
    return pd.Series([key.get(k, np.nan) for k in idx], index=df.index)


dd["cars"] = attach(dd, 0)
v = dd.dropna(subset=["cars"]).copy()
print("\n## 2. 2025 분석일(235일)과 대조")
print(f"- 2025 기록 {len(dd)}행 중 분석일·같은 시에 재차가 있는 행 {len(v)}행, {v.date.nunique()}일, 묶음 {v.groupby(['등록일','등록시간']).ngroups}개")
print("\n행 단위(구역별 상태 → 그 시각 공원 전체 재차):\n")
print("| 상태 | 행 | 재차 10% | 중앙값 | 90% |\n|---|---|---|---|---|")
for s in ["원활", "혼잡", "만차"]:
    x = v.loc[v["혼잡도"] == s, "cars"]
    if len(x):
        print(f"| {s} | {len(x)} | {x.quantile(.1):.0f} | {x.median():.0f} | {x.quantile(.9):.0f} |")
rho = stats.spearmanr(v["sev"], v["cars"])
print(f"\n- 상태 순위(원활<혼잡<만차)와 재차의 스피어먼 상관 {rho.statistic:.2f} (p={rho.pvalue:.2g}, n={len(v)})")
for sh in (-1, 1):
    vv = dd.assign(c=attach(dd, sh)).dropna(subset=["c"])
    print(f"- 시각을 {sh:+d}시간 옮기면 상관 {stats.spearmanr(vv['sev'], vv['c']).statistic:.2f} (n={len(vv)})")
# 묶음 단위: 그 시각 가장 심한 상태
bb = v.groupby(["date", "H"]).agg(sev=("sev", "max"), cars=("cars", "first"), n=("sev", "size")).reset_index()
bb["상태"] = bb["sev"].map({0: "원활", 1: "혼잡", 2: "만차"})
bb["우리"] = bb["cars"].map(lv)
print(f"\n묶음 단위(같은 등록일·시 {len(bb)}개, 묶음 안 가장 심한 상태) × 우리 3분위(임계 {t0}·{t1}대, 그 시각 실제 재차 기준):\n")
ct = pd.crosstab(bb["상태"], bb["우리"]).reindex(index=["원활", "혼잡", "만차"], columns=["한산", "보통", "붐빔"], fill_value=0)
print("| 기관 상태 \\ 우리 구분 | 한산 | 보통 | 붐빔 | 계 |\n|---|---|---|---|---|")
for s, r in ct.iterrows():
    print(f"| {s} | {r['한산']} | {r['보통']} | {r['붐빔']} | {r.sum()} |")
agree = sum(ct.loc[a, b_] for a, b_ in [("원활", "한산"), ("혼잡", "보통"), ("만차", "붐빔")])
print(f"\n- 대각 일치 {agree}/{int(ct.values.sum())} = {agree / ct.values.sum():.0%}; '만차'가 '붐빔'에 든 비율 {ct.loc['만차','붐빔']}/{ct.loc['만차'].sum()}; '원활'이 '한산'에 든 비율 {ct.loc['원활','한산']}/{ct.loc['원활'].sum()}")
kt = stats.kendalltau(bb["sev"], bb["cars"])
print(f"- 묶음 단위 켄달 타우 {kt.statistic:.2f} (p={kt.pvalue:.2g})")
print(f"- 묶음의 요일: {bb.date.dt.dayofweek.map(lambda i: LAB[i]).value_counts().to_dict()}")

# ---- 3. 만차 기록 분포 ----
print("\n## 3. 만차 기록 분포")
dd2 = d.copy()
hol2025 = H.groupby("date")["hol_day"].max()
HOL26 = {"2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01", "2026-03-02", "2026-05-05", "2026-05-24", "2026-05-25",
         "2026-06-03", "2026-06-06", "2026-08-15", "2026-08-17", "2026-09-24", "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-05", "2026-10-09", "2026-12-25"}


def dtype(x):
    if x.year == 2025 and hol2025.get(x, 0) == 1:
        return "공휴일·연휴"
    if x.year == 2026 and x.strftime("%Y-%m-%d") in HOL26:
        return "공휴일·연휴"
    return LAB[x.dayofweek]


dd2["유형"] = dd2["date"].map(dtype)
full = dd2[dd2["혼잡도"] == "만차"].drop_duplicates(["등록일", "H"])
band = pd.cut(full["H"], [-1, 8, 11, 14, 17, 20, 23], labels=["0~8시", "9~11시", "12~14시", "15~17시", "18~20시", "21~23시"])
ct3 = pd.crosstab(full["유형"], band).reindex(["월", "화", "수", "목", "금", "토", "일", "공휴일·연휴"], fill_value=0)
print("\n'만차'가 하나라도 있는 등록일·시 묶음 수(유형 × 시간대, 전 기간):\n")
print("| 유형 | " + " | ".join(ct3.columns.astype(str)) + " | 계 |\n|" + "---|" * (len(ct3.columns) + 2))
for k, r in ct3.iterrows():
    print(f"| {k} | " + " | ".join(str(x) for x in r) + f" | {r.sum()} |")
days_rec = dd2.groupby("유형")["등록일"].nunique().reindex(ct3.index, fill_value=0)
days_full = full.groupby("유형")["등록일"].nunique().reindex(ct3.index, fill_value=0)
print("\n- 기록이 있는 날 대비 만차가 있었던 날: " + ", ".join(f"{k} {days_full[k]}/{days_rec[k]}" for k in ct3.index))
print("- 0시 기록 7행(2026-06-06 00:06:06 등)은 시각이 비정상일 가능성이 있다(공원 심야 만차, 미확인).")
out = dd2[(dd2.date.dt.year == 2026) | dd2.date.dt.month.isin([8, 9, 11, 12])]
print("\n우리 분석에 없는 기간의 기록(2025-08·09·11·12, 2026):\n")
print("| 기간 | 행 | 날 | 상태(원활/혼잡/만차) | 요일 유형별 날 수 |\n|---|---|---|---|---|")
for name, sub in [("2025-08", out[(out.date.dt.year == 2025) & (out.date.dt.month == 8)]), ("2025-09", out[(out.date.dt.year == 2025) & (out.date.dt.month == 9)]),
                  ("2025-11", out[(out.date.dt.year == 2025) & (out.date.dt.month == 11)]), ("2025-12", out[(out.date.dt.year == 2025) & (out.date.dt.month == 12)]),
                  ("2026 전체", out[out.date.dt.year == 2026])]:
    st = sub["혼잡도"].value_counts()
    dt = sub.drop_duplicates("등록일")["유형"].value_counts().to_dict()
    print(f"| {name} | {len(sub)} | {sub.date.nunique()} | {st.get('원활',0)}/{st.get('혼잡',0)}/{st.get('만차',0)} | {dt} |")
s26 = out[out.date.dt.year == 2026]
print(f"\n- 2026 기록 날짜: {sorted(s26['등록일'].unique())}")
