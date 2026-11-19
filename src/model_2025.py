"""2025 시간별 주차대수 예측: 기준선 vs LightGBM 분위수, 월 단위 롤링 검증, 변수군 ablation -> report/model_2025.md

- 검증: 월 단위 롤링(Mar~Jul, Oct을 그 이전 유효월로 학습해 예측). 보조로 '한 달 빼고 학습(LOMO)'.
- 변수군: cal(달력) → +wx(기상) → +sched(공연 유무·공연 시간대) → +aud(관람객 수, 사후 관측값).
- 공연 변수의 효과는 '조건부 증분(다른 변수가 같을 때 예측이 얼마나 달라지나)'이지 인과가 아니다.
- SHAP 대신 LightGBM pred_contrib(= TreeSHAP) 평균 절대 기여도.
실행: python -X utf8 -I src/model_2025.py   (프로젝트 루트에서)
"""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
df = df[(df["valid_day"] == 1) & df["cars"].notna()].reset_index(drop=True)
df["y"] = df["cars"]

CAL = ["hour", "dow", "hol", "hol_long"]
WX = ["temp", "hum", "wind", "rain_pos"]
SCHED = ["perf_day", "show_hour"]
AUD = ["aud_hour", "aud_daymax"]
SETS = {"M0 달력": CAL, "M1 +기상": CAL + WX, "M2 +공연 일정": CAL + WX + SCHED, "M3 +관람객 수": CAL + WX + SCHED + AUD}
Q = (0.1, 0.5, 0.9)
FOLD_MONTHS = [3, 4, 5, 6, 7, 10]
PARAMS = dict(n_estimators=300, learning_rate=0.04, num_leaves=15, min_child_samples=25, subsample=0.8, subsample_freq=1, colsample_bytree=0.9, verbose=-1, random_state=7)


def base_dow_hour(tr, te):
    m = tr.groupby(["dow", "hour"])["y"].mean()
    return te.apply(lambda r: m.get((r["dow"], r["hour"]), np.nan), axis=1).values


def base_off_hour(tr, te):  # 휴무일(주말·공휴일)/평일 × 시각 평균
    m = tr.groupby(["is_off", "hour"])["y"].mean()
    return te.apply(lambda r: m.get((r["is_off"], r["hour"]), np.nan), axis=1).values


def base_band(tr, te):
    g = tr.groupby(["is_off", "hour"])["y"]
    lo, hi = g.quantile(0.1), g.quantile(0.9)
    return (te.apply(lambda r: lo.get((r["is_off"], r["hour"]), np.nan), axis=1).values,
            te.apply(lambda r: hi.get((r["is_off"], r["hour"]), np.nan), axis=1).values)


def fit_q(tr, te, feats):
    out = {}
    for q in Q:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, **PARAMS)
        m.fit(tr[feats], tr["y"])
        out[q] = m.predict(te[feats])
    # 분위수 교차 방지
    lo, md, hi = out[0.1], out[0.5], out[0.9]
    out[0.1], out[0.5], out[0.9] = np.minimum(lo, md), md, np.maximum(hi, md)
    return out


def run(split):
    """split: 리스트[(train_idx, test_idx, fold_label)]"""
    P = []
    for tr_i, te_i, lab in split:
        tr, te = df.loc[tr_i], df.loc[te_i]
        p = te[["ts", "date", "y", "hour", "dow", "is_off", "perf_day", "aud_daymax"]].copy()
        p["fold"] = lab
        p["B1"] = base_dow_hour(tr, te)
        p["B2"] = base_off_hour(tr, te)
        p["B2_lo"], p["B2_hi"] = base_band(tr, te)
        for name, feats in SETS.items():
            o = fit_q(tr, te, feats)
            k = name.split()[0]
            p[k], p[k + "_lo"], p[k + "_hi"] = o[0.5], o[0.1], o[0.9]
        P.append(p)
    return pd.concat(P, ignore_index=True)


rolling = [(df.index[df["month"] < m], df.index[df["month"] == m], m) for m in FOLD_MONTHS]
lomo = [(df.index[df["month"] != m], df.index[df["month"] == m], m) for m in sorted(df["month"].unique())]
R, Lo = run(rolling), run(lomo)


def peak_err(S, col):
    e, mg = [], []
    for d, g in S.groupby("date"):
        g = g[g["hour"].between(5, 23)]
        if len(g) < 18:
            continue
        e.append(abs(int(g["hour"].values[np.argmax(g["y"].values)]) - int(g["hour"].values[np.argmax(g[col].values)])))
        mg.append(abs(g["y"].max() - g[col].max()))
    return float(np.mean(e)), float(np.mean(mg)), float(np.mean(np.array(e) == 0)), float(np.mean(np.array(e) <= 1))


def table(S, title):
    L = [f"\n### {title}\n(평가 시간 {len(S):,}개, 평균 주차대수 {S['y'].mean():.0f}대)\n",
         "| 모델 | MAE(대) | MAE 평균주차 대비 | 피크 시각 정확(일치) | 피크 ±1시간 이내 | 피크 크기 오차(대) | 공연일 MAE | 비공연일 MAE | 휴무일 MAE |",
         "|---|---|---|---|---|---|---|---|---|"]
    models = [("B1", "B1 요일×시각 평균"), ("B2", "B2 휴무일×시각 평균(휴일 반영)")] + [(k.split()[0], "LightGBM " + k) for k in SETS]
    res = {}
    for col, name in models:
        e = (S["y"] - S[col]).abs()
        pe = peak_err(S, col)
        res[col] = float(e.mean())
        L.append(f"| {name} | {e.mean():.1f} | {e.mean() / S['y'].mean():.1%} | {pe[2]:.0%} | {pe[3]:.0%} | {pe[1]:.0f} | {e[S['perf_day'] == 1].mean():.1f} | {e[S['perf_day'] == 0].mean():.1f} | {e[S['is_off'] == 1].mean():.1f} |")
    L.append("\n| 80% 구간(q10~q90) | 포괄률(목표 0.80) | 평균 폭(대) |\n|---|---|---|")
    for col, name in [("B2", "B2 휴무일×시각 경험분위수")] + [(k.split()[0], "LightGBM " + k) for k in SETS]:
        lo, hi = S[col + "_lo"], S[col + "_hi"]
        L.append(f"| {name} | {((S['y'] >= lo) & (S['y'] <= hi)).mean():.2f} | {(hi - lo).mean():.0f} |")
    return L, res


out = ["# 2025 시간별 주차대수 예측 결과 (자동 생성)\n",
       "데이터: 유효일 235일(1~7월, 10월; 원천 입출차 공백 구간 제외). 목표는 기관 `주차대수`. 단일 연도라 계절성은 학습하지 못하며, 10월 fold는 1~7월로 학습한 외삽이다.",
       "공연 변수의 효과는 **조건부 증분**(다른 조건이 같을 때 예측의 차이)이며 인과 효과가 아니다. `aud`(관람객 수)는 사후 관측값이라 실제 예측 시점에는 공연 일정(`sched`)까지만 알 수 있다."]
L1, res1 = table(R, "월 단위 롤링 검증 (Mar·Apr·May·Jun·Jul·Oct을 이전 유효월로 학습)")
out += L1
byf = R.groupby("fold").apply(lambda g: pd.Series({"B2": (g["y"] - g["B2"]).abs().mean(), "M0": (g["y"] - g["M0"]).abs().mean(), "M2": (g["y"] - g["M2"]).abs().mean(), "M3": (g["y"] - g["M3"]).abs().mean()}), include_groups=False).round(1)
out += ["\n월별 MAE(대):\n", byf.to_markdown()]
L2, res2 = table(Lo, "보조: 한 달 빼고 학습(LOMO) — 미래 월이 학습에 포함됨, 참고용")
out += L2

# 공연일 증분: M2 − M1 (같은 모델군에서 공연 일정 변수를 넣은 효과) 를 시각별로
dd = R.copy()
dd["inc"] = dd["M2"] - dd["M1"]
inc = dd[dd["perf_day"] == 1].groupby("hour")["inc"].agg(["mean", "count"]).round(0)
out += ["\n### 공연일의 예측 증분(M2 − M1, 롤링 검증 구간의 공연일, 시각별 평균 대수)\n", inc.T.to_markdown()]
# 실제 공연일 - 비공연일(같은 휴무 구분 × 시각)
act = df.groupby(["is_off", "perf_day", "hour"])["y"].mean().unstack("perf_day")
act["diff"] = act[1] - act[0]
a_off = act.loc[1, "diff"].round(0); a_wd = act.loc[0, "diff"].round(0)
out += ["\n### 실측: 공연일 − 비공연일 평균 주차대수(시각별, 요일 외 조건 미보정)\n", "휴무일:\n", a_off.to_frame().T.to_markdown(), "\n평일:\n", a_wd.to_frame().T.to_markdown()]

# 기여도 (전체 유효 데이터로 학습한 M3 q50, pred_contrib)
feats = SETS["M3 +관람객 수"]
m = lgb.LGBMRegressor(objective="quantile", alpha=0.5, **PARAMS).fit(df[feats], df["y"])
c = m.booster_.predict(df[feats], pred_contrib=True)[:, :-1]
imp = pd.Series(np.abs(c).mean(axis=0), index=feats).sort_values(ascending=False).round(1)
out += ["\n### 변수 기여도(평균 |기여|, 대수; LightGBM q50 M3, 전체 학습, TreeSHAP)\n", imp.to_frame("평균|기여|").T.to_markdown()]
mm = lgb.LGBMRegressor(objective="quantile", alpha=0.5, **PARAMS).fit(df[SETS["M2 +공연 일정"]], df["y"])
c2 = mm.booster_.predict(df[SETS["M2 +공연 일정"]], pred_contrib=True)[:, :-1]
cc = pd.DataFrame(c2, columns=SETS["M2 +공연 일정"])
cc["perf"] = cc["perf_day"] + cc["show_hour"]
cc["hour"] = df["hour"].values; cc["perf_flag"] = df["perf_day"].values
out += ["\n공연 일정 변수(perf_day+show_hour) 기여의 시각별 평균(공연일, M2):\n", cc[cc["perf_flag"] == 1].groupby("hour")["perf"].mean().round(0).to_frame().T.to_markdown()]

txt = "\n".join(out)
(ROOT / "report/model_2025.md").write_text(txt, encoding="utf-8")
R.to_csv(ROOT / "data/interim/model_preds_rolling.csv", index=False)
print(txt)
