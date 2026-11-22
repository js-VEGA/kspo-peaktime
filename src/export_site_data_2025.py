"""웹 화면용 2025 관측 요약 JSON -> docs/data/peaktime_2025.json

- 단위: 유형(월~일, 공휴일·연휴) × 시각의 주차대수(기관 값) 분포(10/50/90%, 평균)와 입출차 기록 기준 시간당 출차 평균.
- 공연 규모별(금요일·주말): 일 관람객 최대값 구간별 평균. 표본 수(n)를 함께 싣는다.
- 모델 검증 수치는 data/interim/model_preds_rolling_v2.csv 에서 계산한다.
- 공연 규모 증분(+59대/천 명 등)은 report/perf_effect.md 의 결과를 옮긴 값이다.
실행: python -X utf8 -I src/export_site_data_2025.py   (프로젝트 루트에서)
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

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


# 방문객 화면의 공연 규모 선택용: 금·토·일(비공휴일) 각 유형 안에서 규모별 시간대 분포(아래 TIERS 와 같은 구간)
def group_tiers(sub):
    res = []
    for name, f in TIERS:
        s = sub[f(sub["aud_day"])]
        n = int(s["date"].nunique())
        item = {"label": name, "n_days": n}
        if n >= 1:
            item["cars"] = prof(s, "cars")
            item["out"] = prof(s, "outflow")
        res.append(item)
    return res


# 공연 규모 구간 (일 관람객 최대값)
TIERS = [("공연 없음", lambda a: a == 0), ("소규모(8천 명 미만)", lambda a: (a > 0) & (a < 8000)), ("중규모(8천~1.4만)", lambda a: (a >= 8000) & (a < 14000)), ("대규모(1.4만 이상)", lambda a: a >= 14000)]


groups = []
for i, (k, lab) in enumerate(zip(KEYS, LABELS)):
    sub = d[(d["dow"] == i) & (d["hol_day"] == 0)]
    groups.append({"key": k, "label": lab, "n_days": int(sub["date"].nunique()), "n_perf_days": int(sub.loc[sub["aud_day"] > 0, "date"].nunique()), "cars": prof(sub, "cars"), "out": prof(sub, "outflow"), "inflow": prof(sub, "inflow", q=(0.5,))})
for g in groups:
    if g["key"] in ("fri", "sat", "sun"):
        i = KEYS.index(g["key"])
        g["tiers"] = group_tiers(d[(d["dow"] == i) & (d["hol_day"] == 0)])
sub = d[d["hol_day"] == 1]
groups.append({"key": "hol", "label": "휴", "name": "공휴일·연휴", "n_days": int(sub["date"].nunique()), "n_perf_days": int(sub.loc[sub["aud_day"] > 0, "date"].nunique()), "cars": prof(sub, "cars"), "out": prof(sub, "outflow"), "inflow": prof(sub, "inflow", q=(0.5,))})



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


def sim_model(sub):
    """공연일(일 관람객 최댓값 > 0)만 대상으로 '일 관람객(천 명) → 저녁 17~21시 평균 주차대수'의 단순 OLS.
    요일·월·기온을 통제하지 않는다(통제 추정은 report/perf_effect.md, meta.uplift). 예측구간 계산에 필요한 값을 함께 싣는다."""
    g = sub.groupby("date").agg(aud=("aud_day", "first"))
    g["eve"] = sub[sub["hour"].between(17, 21)].groupby("date")["cars"].mean()
    g = g[g["aud"] > 0].dropna()
    x, y = g["aud"].values / 1000.0, g["eve"].values
    n = len(x)
    xbar, sxx = x.mean(), ((x - x.mean()) ** 2).sum()
    b = ((x - xbar) * (y - y.mean())).sum() / sxx
    a = y.mean() - b * xbar
    sd = float(np.sqrt(((y - (a + b * x)) ** 2).sum() / (n - 2)))
    se_b = sd / float(np.sqrt(sxx))
    t95, t80 = float(stats.t.ppf(0.975, n - 2)), float(stats.t.ppf(0.9, n - 2))
    return {"n": int(n), "slope": round(float(b), 4), "slope_ci95": [round(float(b - t95 * se_b), 2), round(float(b + t95 * se_b), 2)],
            "intercept": round(float(a), 2), "resid_sd": round(sd, 2), "xbar": round(float(xbar), 4), "sxx": round(float(sxx), 4),
            "t80": round(t80, 4), "x_min": round(float(x.min()), 4), "x_max": round(float(x.max()), 4)}


sim = {"fri": sim_model(nh[nh["dow"] == 4]), "weekend": sim_model(nh[nh["dow"] >= 5])}

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
    "fold_months": sorted(int(x) for x in R["month"].unique()),
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
meta["group_tiers_note"] = "groups[금·토·일].tiers: 해당 요일(비공휴일) 분석일을 그날 관람객 수(시간별 최댓값) 구간(없음 0, 소 <8천, 중 8천~1.4만 미만, 대 1.4만 이상)으로 나눠 시각별 주차대수·출차의 10/50/90% 분위수와 평균을 계산. 표본 수 n_days 를 함께 싣는다."
meta["scenarios_note"] = "첫 화면 예시 3개는 화면에서 이 JSON 값만으로 고른다: (1) 토요일 대규모 공연일 분포(groups[sat].tiers[3])의 평소(50%) 주차대수 최대 시각과 값, (2) 월~목 각 유형의 9~18시 중 평소 주차대수 연속 2시간 합이 가장 작은 유형·시간대, (3) 금요일 대규모 공연일 평균 출차(tiers.fri[3].out_mean)의 최대 시각과 값."
meta["sim_note"] = "금요일·주말(비공휴일) 공연일의 일 관람객 최댓값(천 명) → 저녁 17~21시 평균 주차대수 단순 OLS. 요일·월·기온 통제 없음. 구간은 예측구간(80%, t 분포)."
# ---- 데이터 현황 탭용: 월별 입차 기록, 원천 중복, 검증 표, 결측 ----
veh = pd.read_csv(ROOT / "data/interim/vehicles.csv.gz", usecols=["t_in"], parse_dates=["t_in"])
mcount = veh.groupby(veh["t_in"].dt.month).size().reindex(range(1, 13), fill_value=0)
chk = (ROOT / "report/vehicles_check.md").read_text(encoding="utf-8")
mm = re.search(r"파싱된 행 ([\d,]+), ID 중복 제거 후 ([\d,]+)", chk)
raw_rows, uniq_rows = (int(x.replace(",", "")) for x in mm.groups())
assert len(veh) == uniq_rows, f"vehicles.csv.gz({len(veh)})와 report/vehicles_check.md({uniq_rows}) 불일치"
linked = pd.read_csv(ROOT / "data/interim/linked_hourly.csv", encoding="utf-8-sig", usecols=["rain"], keep_default_na=False, na_values=[""])
vt = pd.read_csv(ROOT / "plan_assets/tables/table_validation.csv", encoding="utf-8-sig")
coverage = {
    "monthly_inflow": {str(int(k)): int(v) for k, v in mcount.items()},
    "raw_rows": raw_rows, "unique_rows": uniq_rows, "dup_rate": round(1 - uniq_rows / raw_rows, 4),
    "first_in": veh["t_in"].min().strftime("%Y-%m-%d %H:%M"), "last_in": veh["t_in"].max().strftime("%Y-%m-%d %H:%M"),
    "rain_missing_rate": round(float(linked["rain"].isna().mean()), 4), "linked_rows": int(len(linked)),
}
validation_table = [{"model": r["모델"], "mae_all": float(r["전체 MAE(대)"]), "mae_eve": float(r["저녁 17~21시 MAE(대)"]), "mae_big_eve": float(r["관람객 8천 이상 날 저녁 MAE(대)"])} for _, r in vt.iterrows()]
out = {"meta": meta, "groups": groups, "tiers": tiers, "sim": sim, "coverage": coverage, "validation_table": validation_table}
(ROOT / "docs/data/peaktime_2025.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
print(json.dumps({"meta": meta, "n_days": {g["key"]: g["n_days"] for g in groups}, "tiers": {k: [(t["label"], t["n_days"]) for t in v] for k, v in tiers.items()}}, ensure_ascii=False, indent=1))
print("size", (ROOT / "docs/data/peaktime_2025.json").stat().st_size)
