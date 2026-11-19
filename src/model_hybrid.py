"""하이브리드: 달력 LightGBM(S0) + 시각별 관람객 규모 선형 보정(음수 계수는 0으로) -> report/model_hybrid.md

S0 잔차(학습 월 내부 leave-one-month-out 예측 잔차)를 시각별로 aud_daymax·aud_hour(천 명)에 ridge 회귀하고,
계수 음수는 0으로 잘라 '관람객이 많을수록 같은 시각의 수요가 줄지는 않는다'는 단조 가정을 건다.
최종 예측 = S0 예측 + 시각별 보정. 구간: S0의 LOMO 잔차 분위수(보정 전 기준이라 약간 넓다).
실행: python -X utf8 -I src/model_hybrid.py   (프로젝트 루트에서)
"""
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
df = df[(df["valid_day"] == 1) & df["cars"].notna()].reset_index(drop=True)
df["y"] = df["cars"]
df["hblock"] = df["hour"] // 6
CAL = ["hour", "dow", "hol", "hol_long"]
P = dict(n_estimators=300, learning_rate=0.05, num_leaves=15, min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.9, reg_lambda=5.0, verbose=-1, random_state=7, objective="regression")
FOLDS = [3, 4, 5, 6, 7, 10]
ALPHA = 3.0


def s0(tr):
    return lgb.LGBMRegressor(**P).fit(tr[CAL], tr["y"])


def inner_resid(tr):
    out = []
    for t in sorted(tr["month"].unique()):
        a, b = tr[tr["month"] != t], tr[tr["month"] == t]
        out.append(b.assign(r=b["y"].values - s0(a).predict(b[CAL])))
    return pd.concat(out)


def fit_adj(R):
    """시각별 ridge: r ~ b0 + b1*aud_daymax + b2*aud_hour (천 명). 음수 기울기는 0으로."""
    coef = {}
    for h, g in R.groupby("hour"):
        X = np.column_stack([g["aud_daymax"].values / 1000, g["aud_hour"].values / 1000]); y = g["r"].values
        xm, ym = X.mean(axis=0), y.mean()
        Xc = X - xm
        b = np.linalg.solve(Xc.T @ Xc + ALPHA * np.eye(2) * len(g) / 100, Xc.T @ (y - ym))
        b = np.clip(b, 0, None)
        coef[h] = (b, ym - xm @ b)
    return coef


def apply_adj(te, coef, use_intercept=False):
    adj = np.zeros(len(te))
    for i, (h, ad, ah) in enumerate(zip(te["hour"].values, te["aud_daymax"].values / 1000, te["aud_hour"].values / 1000)):
        b, c = coef.get(h, (np.zeros(2), 0.0))
        adj[i] = b[0] * ad + b[1] * ah + (c if use_intercept else 0.0)
    return adj


def key(d):
    return d["is_off"].astype(int) * 4 + d["hblock"].astype(int)


def run(mode):
    out = []
    folds = FOLDS if mode == "roll" else sorted(df["month"].unique())
    for m in folds:
        tr = df[df["month"] < m] if mode == "roll" else df[df["month"] != m]
        te = df[df["month"] == m]
        mid = s0(tr).predict(te[CAL])
        R = inner_resid(tr) if tr["month"].nunique() >= 2 else None
        coef = fit_adj(R) if R is not None else {}
        adj = apply_adj(te, coef)
        p = te[["date", "y", "hour", "dow", "is_off", "aud_daymax", "month", "perf_day"]].copy()
        p["S0"] = mid; p["H"] = mid + adj
        if R is not None:
            qlo = R.assign(k=key(R)).groupby("k")["r"].quantile(0.1); qhi = R.assign(k=key(R)).groupby("k")["r"].quantile(0.9)
            k = key(te).values
            p["H_lo"] = p["H"] + np.array([qlo.get(x, qlo.mean()) for x in k]); p["H_hi"] = p["H"] + np.array([qhi.get(x, qhi.mean()) for x in k])
        else:
            p["H_lo"], p["H_hi"] = p["H"] * 0.8, p["H"] * 1.2
        out.append(p)
    return pd.concat(out, ignore_index=True)


def tbl(S, title):
    eve = S["hour"].between(17, 21); big = S["aud_daymax"] >= 8000; wk = S["is_off"] == 1
    L = [f"\n### {title}\n(평가 {len(S):,}시간)\n", "| 모델 | 전체 MAE | 저녁(17~21시) MAE | 관람객 ≥8천 날 저녁 MAE | 관람객 ≥8천 날 전체 MAE | 휴무일 MAE | 평일 MAE | 80% 구간 포괄률(H) |", "|---|---|---|---|---|---|---|---|"]
    for c, n in (("S0", "S0 달력 LightGBM"), ("H", "H 하이브리드(S0 + 관람객 보정)")):
        e = (S["y"] - S[c]).abs()
        cov = f"{((S['y'] >= S['H_lo']) & (S['y'] <= S['H_hi'])).mean():.2f}" if c == "H" else "-"
        L.append(f"| {n} | {e.mean():.1f} | {e[eve].mean():.1f} | {e[eve & big].mean():.1f} | {e[big].mean():.1f} | {e[wk].mean():.1f} | {e[~wk].mean():.1f} | {cov} |")
    return L


R, LO = run("roll"), run("lomo")
out = ["# 하이브리드(달력 LightGBM + 관람객 규모 보정) 결과 (자동 생성)\n"] + tbl(R, "월 단위 롤링 검증") + tbl(LO, "참고: LOMO")
f = R.groupby("month").apply(lambda g: pd.Series({"S0": (g["y"] - g["S0"]).abs().mean(), "H": (g["y"] - g["H"]).abs().mean()}), include_groups=False).round(1)
out += ["\n월별 MAE(롤링):\n", f.to_markdown()]
# 전체 학습으로 얻은 시각별 보정 계수(천 명당 대수)
allres = inner_resid(df)
coef = fit_adj(allres)
tab = pd.DataFrame({"일 관람객 +1천 명당(대)": {h: round(b[0], 1) for h, (b, c) in coef.items()}, "해당 시 관람객 +1천 명당(대)": {h: round(b[1], 1) for h, (b, c) in coef.items()}}).T
out += ["\n전체 유효일로 학습한 시각별 보정 계수(음수는 0으로 잘림):\n", tab.to_markdown()]
txt = "\n".join(out)
(ROOT / "report/model_hybrid.md").write_text(txt, encoding="utf-8")
R.to_csv(ROOT / "data/interim/model_preds_rolling_hybrid.csv", index=False)
print(txt)
