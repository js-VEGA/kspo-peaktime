"""공개 파일 4종 교차 확인 (결과는 report/public_crosscheck.md 로 저장).
실행: python -I src/explore_public.py   (프로젝트 루트에서)
"""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
out = []


def emit(s=""):
    print(s)
    out.append(s)


def rd(prefix):
    p = next(RAW.glob(prefix + "_*.csv"))
    return pd.read_csv(p, encoding="cp949", dtype=str)


# 1) 월별주차현황
m = rd("15131671")
m["연도"] = m["연도"].astype(int)
m["월"] = m["월"].str.replace("월", "").astype(int)
m["주차대수"] = m["주차대수"].astype(int)
piv = m.pivot_table(index=["연도", "월"], columns="주차장소", values="주차대수")
emit("## 월별주차현황 (올림픽공원 / 미사경정공원)")
emit(piv.to_markdown())
op = m[m["주차장소"] == "올림픽공원"].pivot(index="월", columns="연도", values="주차대수")
emit("\n올림픽공원 연도별 합계: " + ", ".join(f"{y}={int(op[y].sum()):,}" for y in op.columns))

# 2) 입출차 2024-07
v = rd("15138735")
v["in"] = pd.to_datetime(v["입차일시"])
v["out"] = pd.to_datetime(v["출차일시"])
emit("\n## 입출차 2024-07")
emit(f"- 행 수 {len(v):,} (월별주차현황 2024-07 올림픽공원 = {int(op.loc[7, 2024]):,})")
emit(f"- 완전중복 {v.duplicated().sum():,} 행 ({v.duplicated().mean():.1%}); 분 단위 기록이라 동시 입차 차량일 수 있음")
dur = (v["out"] - v["in"]).dt.total_seconds() / 3600
emit(f"- 주차시간(시간) 분위수: " + ", ".join(f"{q:.0%}={dur.quantile(q):.2f}" for q in (0.01, 0.1, 0.5, 0.9, 0.99)))
emit(f"- 출차<입차(음수) {int((dur < 0).sum())}건, 24시간 초과 {int((dur > 24).sum())}건, 7일 초과 {int((dur > 168).sum())}건")
emit(f"- 입차일(문자열)과 입차일시 날짜 불일치 {int((pd.to_datetime(v['입차일']).dt.date != v['in'].dt.date).sum())}건")
daily = v.groupby(v["in"].dt.date).size()
emit(f"- 일별 입차: 평균 {daily.mean():,.0f}, 최소 {daily.min():,} ({daily.idxmin()}), 최대 {daily.max():,} ({daily.idxmax()})")
emit("- 요일별 평균 일 입차: " + ", ".join(f"{d}={x:,.0f}" for d, x in daily.groupby(pd.to_datetime(daily.index).dayofweek).mean().items()) + "  (0=월)")
hour = v.groupby(v["in"].dt.hour).size() / 31
emit("- 시간대별 평균 입차: " + ", ".join(f"{h}시={x:,.0f}" for h, x in hour.items()))

# 3) 영문 공연정보
p = rd("15149169")
p["d"] = pd.to_datetime(p["공연일자"])
emit("\n## 영문 공연정보")
emit("- 연도별 행 수: " + ", ".join(f"{y}={n}" for y, n in p.groupby(p["d"].dt.year).size().items()))
emit(f"- 2025년 고유 공연일 {p[p['d'].dt.year == 2025]['d'].nunique()}일 / 2024-07 공연일 {p[(p['d'].dt.year == 2024) & (p['d'].dt.month == 7)]['d'].nunique()}일")
dup_title = p["공연제목"].duplicated(keep=False).sum()
emit(f"- 같은 제목 중복 행 {dup_title}건 (다일 공연 가능성), 시작/종료 시각·장소 컬럼 없음")
emit("- 2024-07 공연: " + "; ".join(p[(p['d'].dt.year == 2024) & (p['d'].dt.month == 7)].sort_values('d').apply(lambda r: f"{r['d'].date()} {r['공연제목'][:40]}", axis=1)))

# 4) 혼잡도
c = rd("15164156")
c["ts"] = pd.to_datetime(c["등록일"] + " " + c["등록시간"])
emit("\n## 주차장 혼잡도")
emit(f"- 기간 {c['ts'].min()} ~ {c['ts'].max()}, 기록 {len(c)}건, 기록 있는 날 {c['등록일'].nunique()}일")
emit("- 혼잡도 분포: " + c["혼잡도"].value_counts().to_dict().__repr__())
emit("- 구역별 건수: " + c["주차구역"].value_counts().to_dict().__repr__())
emit("- 연월별 건수: " + c.groupby(c["ts"].dt.to_period("M")).size().to_dict().__repr__())
emit("- 만차 기록 일자: " + ", ".join(sorted(c[c["혼잡도"] == "만차"]["등록일"].unique())[:30]))

# 5) 2024-07 공연일 vs 비공연일 (영문 공연정보 기준, 표본 매우 작음 -> 탐색용)
emit("\n## 2024-07 공연일 vs 같은 요일 비공연일 (탐색용, 인과 아님)")
perf_days = set(p[(p["d"].dt.year == 2024) & (p["d"].dt.month == 7)]["d"].dt.date)
d = daily.copy()
d.index = pd.to_datetime(d.index)
ev = v[v["in"].dt.hour.between(17, 21)].groupby(v["in"].dt.date).size()
ev.index = pd.to_datetime(ev.index)
rows = []
for day in sorted(perf_days):
    same = [x for x in d.index if x.dayofweek == pd.Timestamp(day).dayofweek and x.date() not in perf_days]
    rows.append(
        f"- {day} ({'월화수목금토일'[pd.Timestamp(day).dayofweek]}): 일 입차 {d[pd.Timestamp(day)]:,} vs 같은 요일 비공연일 평균 {d[same].mean():,.0f}; "
        f"17~21시 입차 {ev.get(pd.Timestamp(day), 0):,} vs {ev[same].mean():,.0f}"
    )
for r in rows:
    emit(r)
emit("\n## 공연일자 분포 (2025)")
g = p[p["d"].dt.year == 2025].groupby("d").size()
emit("- 날짜당 공연 행 수 분포: " + g.value_counts().sort_index().to_dict().__repr__())
emit("- 요일 분포: " + g.groupby(g.index.dayofweek).size().to_dict().__repr__() + " (0=월)")

(ROOT / "report" / "public_crosscheck.md").write_text("# 공개 파일 교차 확인 (자동 생성)\n" + "\n".join(out), encoding="utf-8")
