"""웹 화면용 2025 관측 요약 JSON -> docs/data/peaktime_2025.json

- 단위: 유형(월~일, 공휴일·연휴) × 시각의 주차대수(기관 값) 분포(10/50/90%, 평균)와 입출차 기록 기준 시간당 출차 평균.
- 공연 규모별(금요일·주말): 일 관람객 최대값 구간별 평균. 표본 수(n)를 함께 싣는다.
- 모델 검증 수치는 data/interim/model_preds_rolling_v2.csv 에서 계산한다.
- 공연 규모 증분(+59대/천 명 등)은 report/perf_effect.md 의 결과를 옮긴 값이다.
실행: python -X utf8 -I src/export_site_data_2025.py   (프로젝트 루트에서)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
d = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
d = d[d["valid_day"] == 1].copy()
d["hol_day"] = d.groupby("date")["hol"].transform("max")
d["aud_day"] = d.groupby("date")["aud_daymax"].transform("max")
LABELS = ["월", "화", "수", "목", "금", "토", "일"]
KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def prof(sub, col, q=(0.1, 0.5, 0.9)):
    g = sub.groupby("hour")[col]
    out = {f"p{int(x * 100)}": [int(round(g.quantile(x).get(h, np.nan))) if pd.notna(g.quantile(x).get(h, np.nan)) else None for h in range(24)] for x in q}
    out["mean"] = [int(round(g.mean().get(h, np.nan))) if pd.notna(g.mean().get(h, np.nan)) else None for h in range(24)]
    return out


groups = []
for i, (k, lab) in enumerate(zip(KEYS, LABELS)):
    sub = d[(d["dow"] == i) & (d["hol_day"] == 0)]
    groups.append({"key": k, "label": lab, "n_days": int(sub["date"].nunique()), "cars": prof(sub, "cars"), "out": prof(sub, "outflow"), "inflow": prof(sub, "inflow", q=(0.5,))})
sub = d[d["hol_day"] == 1]
groups.append({"key": "hol", "label": "휴", "name": "공휴일·연휴", "n_days": int(sub["date"].nunique()), "cars": prof(sub, "cars"), "out": prof(sub, "outflow"), "inflow": prof(sub, "inflow", q=(0.5,))})

# 공연 규모 구간 (일 관람객 최대값)
TIERS = [("공연 없음", lambda a: a == 0), ("소규모(8천 명 미만)", lambda a: (a > 0) & (a < 8000)), ("중규모(8천~1.4만)", lambda a: (a >= 8000) & (a < 14000)), ("대규모(1.4만 이상)", lambda a: a >= 14000)]


def tier_block(sub):
    res = []
    for name, f in TIERS:
        s = sub[f(sub["aud_day"])]
        n = int(s["date"].nunique())
        item = {"label": name, "n_days": n}
        if n >= 1:
            item["cars_mean"] = [int(round(v)) if pd.notna(v) else None for v in s.groupby("hour")["cars"].mean().reindex(range(24))]
            item["out_mean"] = [int(round(v)) if pd.notna(v) else None for v in s.groupby("hour")["outflow"].mean().reindex(range(24))]
            item["aud_median"] = int(s.groupby("date")["aud_day"].first().median())
        res.append(item)
    return res


nh = d[d["hol_day"] == 0]
tiers = {"fri": tier_block(nh[nh["dow"] == 4]), "weekend": tier_block(nh[nh["dow"] >= 5])}

# 한산/보통/붐빔 기준: 모든 유형의 8~22시 중앙값 분포의 3분위
def tert(vals):
    v = sorted(x for x in vals if x is not None)
    return [v[len(v) // 3], v[len(v) * 2 // 3]]


cars_t = tert([x for g in groups for x in g["cars"]["p50"][8:23]])
out_t = tert([x for g in groups for x in g["out"]["p50"][8:23]])

# 모델 검증(롤링)
R = pd.read_csv(ROOT / "data/interim/model_preds_rolling_v2.csv")
mae = lambda c: float((R["y"] - R[c]).abs().mean())
val = {
    "eval_hours": int(len(R)), "mean_cars": int(round(R["y"].mean())),
    "mae_dow_hour": round(mae("B1"), 0), "mae_off_hour": round(mae("B2"), 0), "mae_lightgbm_calendar": round(mae("S0"), 0),
    "interval80_coverage": round(float(((R["y"] >= R["S0_lo"]) & (R["y"] <= R["S0_hi"])).mean()), 2),
}
monthly = d.groupby(d["date"].dt.month)["date"].nunique()
meta = {
    "period": "2025-01-01~2025-07-30, 2025-10-01~2025-10-30 (월 말일 제외)",
    "valid_days": int(d["date"].nunique()), "valid_days_by_month": {int(k): int(v) for k, v in monthly.items()},
    "unusable": "2025-07-31~09-30과 11월 이후는 원천 입출차 기록이 거의 없어 제외",
    "cars_thresholds": cars_t, "out_thresholds": out_t,
    "validation": val,
    "uplift": {"eve_cars_per_1k": 59, "eve_cars_ci": [42, 75], "eve_out_per_1k": 69, "eve_out_ci": [38, 100], "n_days": 89,
               "note": "같은 요일 유형(금요일·주말) 안에서 일 관람객 +1천 명당 저녁 17~21시 평균 재차, 18~23시 출차 건수의 증분. 요일·월·기온 편차 통제, 조건부 증분이며 인과가 아님(report/perf_effect.md)."},
}
out = {"meta": meta, "groups": groups, "tiers": tiers}
(ROOT / "docs/data/peaktime_2025.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(json.dumps({"meta": meta, "n_days": {g["key"]: g["n_days"] for g in groups}, "tiers": {k: [(t["label"], t["n_days"]) for t in v] for k, v in tiers.items()}}, ensure_ascii=False, indent=1))
print("size", (ROOT / "docs/data/peaktime_2025.json").stat().st_size)
