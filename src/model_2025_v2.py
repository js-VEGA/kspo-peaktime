"""2차 모델링: 계절 프록시 제거(기온 편차), 관람객 단조 제약, 정규화 격자, 잔차 기반 80% 구간 보정 -> report/model_2025_v2.md

- v1(model_2025.py)에서 기상·공연 변수를 넣은 LightGBM이 달력만 쓴 모델보다 나빠지고 80% 구간 포괄률이 0.55~0.66이었다.
  원인 추정: (1) 기온이 월 구분자로 작동해 월 단위 외삽에서 해롭다 (2) 시간 단위 행이지만 날씨·공연 변수는 일 단위라 유효 표본이 작아 과적합 (3) 분위수 모형의 학습 내 구간이 좁다.
- 대응: temp_dev(일평균기온 − 월평균), 관람객 단조(+) 제약, 규제 격자, 구간은 학습 월에 대한 leave-one-month-out 잔차 분위수로 보정.
- 격자는 롤링 검증 MAE로 고르므로 약간 낙관적이다 → LOMO(참고)로 같은 설정을 다시 평가한다.
실행: python -X utf8 -I src/model_2025_v2.py   (프로젝트 루트에서)
"""
from itertools import product
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
df = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
df = df[(df["valid_day"] == 1) & df["cars"].notna()].reset_index(drop=True)
df["y"] = df["cars"]
df["temp_day"] = df.groupby("date")["temp"].transform("mean")
df["temp_dev"] = df["temp_day"] - df.groupby("month")["temp_day"].transform("mean")
df["hum_day"] = df.groupby("date")["hum"].transform("mean")
df["hblock"] = df["hour"] // 6

CAL = ["hour", "dow", "hol", "hol_long"]
SETS = {
    "S0 달력": CAL,
    "S1 +기온편차": CAL + ["temp_dev"],
    "S2 +관람객": CAL + ["aud_hour", "aud_daymax"],
    "S3 +기온편차+관람객": CAL + ["temp_dev", "aud_hour", "aud_daymax"],
    "S4 +기온편차+관람객+공연일정": CAL + ["temp_dev", "aud_hour", "aud_daymax", "perf_day", "show_hour"],
}
FOLDS = [3, 4, 5, 6, 7, 10]
GRID = list(product([4, 8, 15], [30, 100, 250], [150, 300]))  # num_leaves, min_child_samples, n_estimators


def mono(feats):
    return [1 if f in ("aud_hour", "aud_daymax") else 0 for f in feats]


def fit(tr, feats, leaves, mcs, n, alpha=0.5, objective=None):
    kw = dict(objective="regression") if objective is None else dict(objective=objective)  # L2(평균 예측). quantile·L1은 단조 제약을 지원하지 않아 모든 변수군을 L2로 통일
    m = lgb.LGBMRegressor(n_estimators=n, learning_rate=0.05, num_leaves=leaves, min_child_samples=mcs, subsample=0.8, subsample_freq=1,
                          colsample_bytree=0.9, reg_lambda=5.0, monotone_constraints=mono(feats), verbose=-1, random_state=7, **kw)
    return m.fit(tr[feats], tr["y"])


def mae_rolling(feats, leaves, mcs, n, folds=FOLDS, mode="roll"):
    e, N = 0.0, 0
    for m in folds:
        tr = df[df["month"] < m] if mode == "roll" else df[df["month"] != m]
        te = df[df["month"] == m]
        p = fit(tr, feats, leaves, mcs, n).predict(te[feats])
        e += np.abs(te["y"].values - p).sum(); N += len(te)
    return e / N


# 1) 격자 선택(롤링 검증 MAE)
best = {}
G = []
for name, feats in SETS.items():
    res = [(mae_rolling(feats, *p), p) for p in GRID]
    res.sort(key=lambda t: t[0])
    best[name] = res[0][1]
    G.append((name, res[0][0], res[0][1], np.median([r[0] for r in res])))

# 2) 선택 설정으로 롤링/LOMO 평가 + 잔차 보정 구간
def blocks_key(d):
    return d["is_off"].astype(int) * 4 + d["hblock"].astype(int)


def predict_with_band(tr, te, feats, params):
    mid = fit(tr, feats, *params).predict(te[feats])
    months = sorted(tr["month"].unique())
    res = []
    if len(months) >= 2:
        for t in months:  # 학습 월 내부 leave-one-month-out 잔차
            a, b = tr[tr["month"] != t], tr[tr["month"] == t]
            pb = fit(a, feats, *params).predict(b[feats])
            res.append(pd.DataFrame({"k": blocks_key(b).values, "r": b["y"].values - pb}))
    if res:
        R = pd.concat(res)
        qlo = R.groupby("k")["r"].quantile(0.1); qhi = R.groupby("k")["r"].quantile(0.9)
        k = blocks_key(te).values
        lo = mid + np.array([qlo.get(x, qlo.mean()) for x in k]); hi = mid + np.array([qhi.get(x, qhi.mean()) for x in k])
    else:
        lo = mid * 0.8; hi = mid * 1.2
    return mid, lo, hi


def evaluate(mode):
    out = []
    folds = FOLDS if mode == "roll" else sorted(df["month"].unique())
    for m in folds:
        tr = df[df["month"] < m] if mode == "roll" else df[df["month"] != m]
        te = df[df["month"] == m]
        p = te[["ts", "date", "y", "hour", "dow", "is_off", "perf_day", "aud_daymax", "month"]].copy()
        g = tr.groupby(["is_off", "hour"])["y"].mean()
        p["B2"] = [g.get((a, b), np.nan) for a, b in zip(te["is_off"], te["hour"])]
        gd = tr.groupby(["dow", "hour"])["y"].mean()
        p["B1"] = [gd.get((a, b), np.nan) for a, b in zip(te["dow"], te["hour"])]
        for name, feats in SETS.items():
            mid, lo, hi = predict_with_band(tr, te, feats, best[name])
            k = name.split()[0]
            p[k], p[k + "_lo"], p[k + "_hi"] = mid, np.minimum(lo, mid), np.maximum(hi, mid)
        out.append(p)
    return pd.concat(out, ignore_index=True)


def peak_stats(S, col):
    e = []
    for d, g in S.groupby("date"):
        g = g[g["hour"].between(5, 23)]
        if len(g) >= 18:
            e.append(abs(int(g["hour"].values[np.argmax(g["y"].values)]) - int(g["hour"].values[np.argmax(g[col].values)])))
    e = np.array(e)
    return float((e == 0).mean()), float((e <= 1).mean())


def table(S, title):
    L = [f"\n### {title}\n(평가 시간 {len(S):,}, 평균 주차대수 {S['y'].mean():.0f}대)\n",
         "| 모델 | MAE(대) | 평균 대비 | 피크 시각 일치 | 피크 ±1h | 저녁(17~21시) MAE | 공연 관람객 ≥8천 명 날 저녁 MAE | 80% 구간 포괄률 | 평균 폭(대) |", "|---|---|---|---|---|---|---|---|---|"]
    eve = S["hour"].between(17, 21); big = S["aud_daymax"] >= 8000
    for col, name in [("B1", "B1 요일×시각 평균"), ("B2", "B2 휴무일×시각 평균")] + [(k.split()[0], "LightGBM " + k) for k in SETS]:
        e = (S["y"] - S[col]).abs(); pk = peak_stats(S, col)
        cov = f"{((S['y'] >= S[col + '_lo']) & (S['y'] <= S[col + '_hi'])).mean():.2f}" if col + "_lo" in S else "-"
        w = f"{(S[col + '_hi'] - S[col + '_lo']).mean():.0f}" if col + "_lo" in S else "-"
        L.append(f"| {name} | {e.mean():.1f} | {e.mean() / S['y'].mean():.1%} | {pk[0]:.0%} | {pk[1]:.0%} | {e[eve].mean():.1f} | {e[eve & big].mean():.1f} | {cov} | {w} |")
    return L


R, LO = evaluate("roll"), evaluate("lomo")
out = ["# 2025 시간별 주차대수 예측 2차 결과 (자동 생성)\n",
       "v1 대비 변경: 기온 → 월 내 편차(temp_dev), 관람객 변수 단조(+) 제약, 규제 격자, 80% 구간은 학습 월 내부 leave-one-month-out 잔차 분위수(휴무일×6시간 블록)로 보정. 습도·풍속·강수는 v1에서 이득이 없어 제외했다.\n",
       "### 격자 선택 결과(롤링 검증 MAE 기준, 변수군별 최적)\n", "| 변수군 | 롤링 MAE | (leaves, min_child, trees) | 격자 18개 MAE 중앙값 |", "|---|---|---|---|"]
out += [f"| {n} | {m:.1f} | {p} | {md:.1f} |" for n, m, p, md in G]
out += ["\n격자 선택이 같은 fold로 이뤄져 롤링 수치는 약간 낙관적이다. LOMO 표는 선택과 평가가 더 겹치므로 참고용이다."]
out += table(R, "월 단위 롤링 검증 (3·4·5·6·7·10월)")
out += table(LO, "참고: 한 달 빼고 학습(LOMO)")
byf = R.groupby("month").apply(lambda g: pd.Series({c: (g["y"] - g[c]).abs().mean() for c in ("B2", "S0", "S2", "S3", "S4")}), include_groups=False).round(1)
out += ["\n월별 MAE(대, 롤링):\n", byf.to_markdown()]
txt = "\n".join(out)
(ROOT / "report/model_2025_v2.md").write_text(txt, encoding="utf-8")
R.to_csv(ROOT / "data/interim/model_preds_rolling_v2.csv", index=False)
print(txt)
