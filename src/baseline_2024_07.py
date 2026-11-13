"""2024-07 입출차(15138735)로 시간대별 입차 대수 예측의 평가 틀과 기준선을 만든다.
한 달뿐이라 '주 단위 롤링 검증'을 쓴다: k번째 주를 그 이전 주들로만 학습해 예측.
공연 플래그는 영문 공연정보(15149169)의 2024-07 공연일(3일, 표본 매우 작음)이며 탐색용이다.
실행: python -X utf8 -I src/baseline_2024_07.py   (프로젝트 루트에서)
"""
import glob
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"

# ---------- 데이터 ----------
v = pd.read_csv(glob.glob(str(RAW / "15138735_*"))[0], encoding="cp949", dtype=str)
v["in"] = pd.to_datetime(v["입차일시"])
idx = pd.date_range("2024-07-01 00:00", "2024-07-31 23:00", freq="h")
y = v.groupby(v["in"].dt.floor("h")).size().reindex(idx, fill_value=0)
df = pd.DataFrame({"y": y.values}, index=idx)
df["hour"] = df.index.hour
df["dow"] = df.index.dayofweek
df["week"] = (df.index.day - 1) // 7  # 0..4 (7/1이 월요일이라 월~일 주와 일치, 5주차는 3일)
e = pd.read_csv(glob.glob(str(RAW / "15149169_*"))[0], encoding="cp949", dtype=str)
perf_days = set(pd.to_datetime(e["공연일자"]).dt.date[(pd.to_datetime(e["공연일자"]).dt.year == 2024) & (pd.to_datetime(e["공연일자"]).dt.month == 7)])
df["perf"] = [int(d in perf_days) for d in df.index.date]
df["perf_eve"] = df["perf"] * df["hour"].between(17, 21).astype(int)

# ---------- 모델 ----------
Q = (0.1, 0.5, 0.9)


def pred_how(train, test):  # 요일×시각 평균 (기준선 B1)
    m = train.groupby(["dow", "hour"])["y"].mean()
    return test.apply(lambda r: m.get((r["dow"], r["hour"]), np.nan), axis=1).values


def pred_hod(train, test):  # 평일/주말 × 시각 평균 (기준선 B0)
    t = train.assign(we=(train["dow"] >= 5).astype(int))
    m = t.groupby(["we", "hour"])["y"].mean()
    return test.apply(lambda r: m.get((int(r["dow"] >= 5), r["hour"]), np.nan), axis=1).values


def band_how(train, test):  # 같은 요일×시각 값들의 10/90% 경험 분위수
    g = train.groupby(["dow", "hour"])["y"]
    lo, hi = g.quantile(0.1), g.quantile(0.9)
    return (test.apply(lambda r: lo.get((r["dow"], r["hour"]), np.nan), axis=1).values,
            test.apply(lambda r: hi.get((r["dow"], r["hour"]), np.nan), axis=1).values)


def lgb_q(train, test, feats):
    out = {}
    for q in Q:
        m = lgb.LGBMRegressor(objective="quantile", alpha=q, n_estimators=150, learning_rate=0.05,
                              num_leaves=8, min_child_samples=5, verbose=-1)
        m.fit(train[feats], train["y"])
        out[q] = m.predict(test[feats])
    return out


def peak_err(test, pred):  # 날짜별 실제 피크 시각과 예측 피크 시각의 차(시간)
    errs = []
    for d, g in test.assign(p=pred).groupby(test.index.date):
        if len(g) == 24:
            errs.append(abs(int(g["hour"].values[np.argmax(g["y"].values)]) - int(g["hour"].values[np.argmax(g["p"].values)])))
    return errs


rows, peak = [], {}
folds = [1, 2, 3, 4]  # 2~5주차 예측
store = {k: [] for k in ("y", "B0", "B1", "L50", "L50_noperf", "lo_B1", "hi_B1", "lo_L", "hi_L", "lo_Ln", "hi_Ln", "fold")}
for k in folds:
    tr, te = df[df["week"] < k], df[df["week"] == k]
    f_full, f_no = ["hour", "dow", "perf", "perf_eve"], ["hour", "dow"]
    lq, ln = lgb_q(tr, te, f_full), lgb_q(tr, te, f_no)
    lo_b, hi_b = band_how(tr, te)
    store["y"] += list(te["y"]); store["fold"] += [k] * len(te)
    store["B0"] += list(pred_hod(tr, te)); store["B1"] += list(pred_how(tr, te))
    store["L50"] += list(lq[0.5]); store["L50_noperf"] += list(ln[0.5])
    store["lo_B1"] += list(lo_b); store["hi_B1"] += list(hi_b)
    store["lo_L"] += list(lq[0.1]); store["hi_L"] += list(lq[0.9])
    store["lo_Ln"] += list(ln[0.1]); store["hi_Ln"] += list(ln[0.9])
    for name, p in (("B0", pred_hod(tr, te)), ("B1", pred_how(tr, te)), ("L50", lq[0.5]), ("L50_noperf", ln[0.5])):
        peak.setdefault(name, []).extend(peak_err(te, p))
S = pd.DataFrame(store)
mae = lambda a, b: float(np.nanmean(np.abs(S[a] - S[b])))
cov = lambda lo, hi: float(((S["y"] >= S[lo]) & (S["y"] <= S[hi])).mean())

L = ["# 2024-07 기준선·평가 틀 결과 (자동 생성, 탐색용)\n",
     "한 달 데이터이고 학습 주가 1~4주뿐이다. 공연일은 3일(영문 공연정보 기준)이라 공연 효과의 검증이 아니라 **평가 틀의 시험**이다. 수치를 기획서에 쓰기 전에 2025 데이터로 다시 계산해야 한다.\n",
     f"- 검증: 주 단위 롤링 (2~5주차를 직전까지의 주로 예측), 평가 시간 수 {len(S)}",
     f"- 시간당 입차 대수 평균(평가 구간): {S['y'].mean():.1f}\n",
     "| 모델 | MAE(대/시간) | 날짜별 피크 시각 오차(시간, 평균) |", "|---|---|---|",
     f"| B0 평일/주말×시각 평균 | {mae('y','B0'):.1f} | {np.mean(peak['B0']):.2f} |",
     f"| B1 요일×시각 평균 | {mae('y','B1'):.1f} | {np.mean(peak['B1']):.2f} |",
     f"| LightGBM q50 (공연 변수 없음) | {mae('y','L50_noperf'):.1f} | {np.mean(peak['L50_noperf']):.2f} |",
     f"| LightGBM q50 (공연 변수 포함) | {mae('y','L50'):.1f} | {np.mean(peak['L50']):.2f} |\n",
     "| 80% 구간 | 포괄률(목표 0.80) |", "|---|---|",
     f"| B1 같은 요일×시각 경험 분위수 | {cov('lo_B1','hi_B1'):.2f} |",
     f"| LightGBM q10~q90 (공연 변수 없음) | {cov('lo_Ln','hi_Ln'):.2f} |",
     f"| LightGBM q10~q90 (공연 변수 포함) | {cov('lo_L','hi_L'):.2f} |\n",
     "공연일(3일)만 따로 본 시간당 MAE:"]
pf = df[df["week"].isin(folds)]["perf"].values
for name in ("B1", "L50_noperf", "L50"):
    L.append(f"- {name}: 공연일 {np.mean(np.abs(S['y'][pf == 1] - S[name][pf == 1])):.1f} / 비공연일 {np.mean(np.abs(S['y'][pf == 0] - S[name][pf == 0])):.1f}")
txt = "\n".join(L)
print(txt)
(ROOT / "report" / "baseline_2024_07.md").write_text(txt, encoding="utf-8")
