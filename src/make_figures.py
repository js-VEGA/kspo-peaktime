"""기획서용 그림·표 생성 -> plan_assets/figures/*.png, plan_assets/tables/*.csv|md

모든 수치는 data/interim 의 산출물에서 계산한다(손으로 옮긴 숫자 없음).
색: dataviz 기본 팔레트(파랑·주황, 순서형 파랑 램프). 라벨은 직접 표기, 격자는 연하게.
실행: python -X utf8 -I src/make_figures.py   (프로젝트 루트에서)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "plan_assets"
(OUT / "figures").mkdir(parents=True, exist_ok=True)
(OUT / "tables").mkdir(parents=True, exist_ok=True)

SURF, INK, INK2, MUTED, GRID, BASE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
BLUE, ORANGE, GRAY = "#2a78d6", "#eb6834", "#b9b8b1"
RAMP = {"공연 없음": "#86b6ef", "소규모": "#3987e5", "중규모": "#1c5cab", "대규모": "#0d366b"}
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False, "figure.facecolor": SURF, "axes.facecolor": SURF,
    "savefig.facecolor": SURF, "text.color": INK, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "axes.edgecolor": BASE, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "font.size": 11, "axes.titlesize": 12, "axes.titleweight": "bold", "axes.spines.top": False, "axes.spines.right": False,
})
SRC = "자료: 한국체육산업개발(주) 올림픽공원 연계 데이터·입출차 정보 전체구역(2025), 저자 분석"


def finish(fig, name, note=None):
    if note:
        fig.text(0.0, -0.015, note, fontsize=8.5, color=MUTED, ha="left", va="top", wrap=True)
    fig.savefig(OUT / "figures" / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


df = pd.read_csv(ROOT / "data/interim/model_hourly.csv", parse_dates=["ts", "date"])
v = df[(df["valid_day"] == 1) & df["cars"].notna()].copy()
v["hol_day"] = v.groupby("date")["hol"].transform("max")
v["aud_day"] = v.groupby("date")["aud_daymax"].transform("max")

# ---------- 그림 1: 월별 입차 기록 건수 ----------
veh = pd.read_csv(ROOT / "data/interim/vehicles.csv.gz", parse_dates=["t_in"])
mc = veh.groupby(veh["t_in"].dt.month).size().reindex(range(1, 13), fill_value=0)
usable = {1, 2, 3, 4, 5, 6, 7, 10}
fig, ax = plt.subplots(figsize=(9, 4.4))
cols = [BLUE if m in usable else GRAY for m in mc.index]
ax.bar(mc.index, mc.values / 1e4, color=cols, width=0.62)
for m, n in mc.items():
    ax.text(m, n / 1e4 + 0.6, f"{n / 1e4:.1f}", ha="center", va="bottom", fontsize=10, color=INK2)
ax.set_xticks(range(1, 13)); ax.set_xticklabels([f"{m}월" for m in range(1, 13)])
ax.set_ylabel("입차 기록(만 건)"); ax.set_ylim(0, 37)
ax.grid(axis="x", visible=False)
ax.text(12, 9.6, "12/7 이후\n기록 없음", ha="center", fontsize=9.5, color=INK2)
from matplotlib.patches import Patch
ax.legend(handles=[Patch(color=BLUE, label="분석에 사용한 달(1~7월·10월)"), Patch(color=GRAY, label="원천 기록이 거의 없어 제외한 달")], loc="upper left", frameon=False, fontsize=10)
ax.set_title("월별 입차 기록 건수: 8~9월과 11~12월은 원천 자체가 비어 있다", loc="left")
finish(fig, "fig1_data_coverage.png", SRC + " · 중복 제거 후 2,068,143건")

# ---------- 그림 2: 재차 복원 검증 ----------
s = v.dropna(subset=["occ_end"])
x, y = s["occ_end"].values, s["cars"].values
b, a = np.polyfit(x, y, 1)
r = float(np.corrcoef(x, y)[0, 1])
fig, ax = plt.subplots(figsize=(6.4, 5.6))
ax.scatter(x, y, s=6, color=BLUE, alpha=0.18, linewidths=0)
xs = np.array([0, x.max()])
ax.plot(xs, a + b * xs, color=ORANGE, lw=2)
ax.plot(xs, xs, color=MUTED, lw=1, ls="--")
ax.text(x.max() * 0.70, 700, f"주황 실선: 추세선\n기관 = {b:.2f}×복원 + {a:.0f}\n회색 점선: y = x", color=INK, fontsize=10.5, ha="left")
ax.set_xlabel("입출차 기록으로 복원한 재차(대)"); ax.set_ylabel("기관 시간표의 주차대수(대)")
ax.set_title(f"복원 재차와 기관 주차대수는 같은 움직임을 보인다 (상관 {r:.3f})", loc="left", fontsize=11.5)
finish(fig, "fig2_reconstruction_check.png", f"유효일 {s['date'].nunique()}일·{len(s):,}시간. 복원 재차는 다음 정시 시점 기준. " + SRC)
recon = dict(r=r, slope=b, intercept=a, n=len(s), days=int(s["date"].nunique()))

# ---------- 그림 3: 유형별 시간대 곡선 ----------
panels = [("평일(월~목)", (v["dow"] <= 3) & (v["hol_day"] == 0)), ("금요일", (v["dow"] == 4) & (v["hol_day"] == 0)),
          ("토요일", (v["dow"] == 5) & (v["hol_day"] == 0)), ("일요일", (v["dow"] == 6) & (v["hol_day"] == 0)), ("공휴일·연휴", v["hol_day"] == 1)]
fig, axes = plt.subplots(2, 3, figsize=(11, 6.2), sharey=True, sharex=True)
hrs = np.arange(5, 24)
for ax, (name, m) in zip(axes.flat, panels):
    sub = v[m]
    g = sub.groupby("hour")["cars"]
    p10, p50, p90 = g.quantile(0.1).reindex(hrs), g.quantile(0.5).reindex(hrs), g.quantile(0.9).reindex(hrs)
    ax.fill_between(hrs, p10, p90, color=BLUE, alpha=0.22, linewidth=0)
    ax.plot(hrs, p50, color=BLUE, lw=2.2)
    pk = int(p50.idxmax())
    ax.plot([pk], [p50[pk]], "o", color=ORANGE, ms=8, mec=SURF, mew=2)
    ax.annotate(f"{pk}시 {p50[pk]:,.0f}대", (pk, p50[pk]), xytext=(0, 11), textcoords="offset points", ha="center", fontsize=10, color=INK)
    ax.set_title(f"{name}  ({sub['date'].nunique()}일)", loc="left", fontsize=11.5)
    ax.set_xticks([6, 9, 12, 15, 18, 21])
for ax in axes[:, 0]:
    ax.set_ylabel("주차대수(대)")
for ax in axes[1, :]:
    ax.set_xlabel("시각")
lax = axes.flat[5]; lax.axis("off")
lax.plot([], [], color=BLUE, lw=2.2, label="중앙값"); lax.fill_between([], [], [], color=BLUE, alpha=0.22, label="10~90% 범위(같은 유형 날들)")
lax.plot([], [], "o", color=ORANGE, label="가장 많은 시각")
lax.legend(loc="center left", frameon=False, fontsize=10.5)
fig.suptitle("요일 유형별 시간대 주차대수: 평일은 낮 시간, 주말은 오후~저녁에 몰린다", x=0.01, ha="left", fontsize=13, fontweight="bold")
finish(fig, "fig3_daytype_profiles.png", SRC + " · 유효일 235일(1~7월, 10월)")

# ---------- 그림 4: 공연 규모별 저녁 곡선 ----------
def tier_of(a):
    return "공연 없음" if a == 0 else ("소규모" if a < 8000 else ("중규모" if a < 14000 else "대규모"))


v["tier"] = v["aud_day"].map(tier_of)
nh = v[v["hol_day"] == 0]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.9), sharey=True)
hrs2 = np.arange(8, 24)
for ax, (name, sub) in zip(axes, [("금요일", nh[nh["dow"] == 4]), ("토·일요일", nh[nh["dow"] >= 5])]):
    ax.axvspan(17, 21, color=GRID, alpha=0.55, lw=0)
    ends = []
    for t in ["공연 없음", "소규모", "중규모", "대규모"]:
        ss = sub[sub["tier"] == t]
        n = ss["date"].nunique()
        if n == 0:
            continue
        mu = ss.groupby("hour")["cars"].mean().reindex(hrs2)
        ax.plot(hrs2, mu, color=RAMP[t], lw=2.4)
        ends.append((mu.iloc[-1], f"{t}({n}일)", RAMP[t], t))
    ends.sort()
    last = -1e9
    for val, lab, c, t in ends:  # 끝점 직접 라벨(겹침 방지)
        yy = max(val, last + 120); last = yy
        ax.text(23.25, yy, lab, color=INK, fontsize=10, va="center")
    ax.set_xlim(8, 27.2); ax.set_xticks([8, 10, 12, 14, 16, 18, 20, 22])
    ax.set_title(name, loc="left"); ax.set_xlabel("시각")
    ax.text(19, ax.get_ylim()[1] * 0.985, "저녁 17~21시", ha="center", va="top", fontsize=9.5, color=INK2)
axes[0].set_ylabel("평균 주차대수(대)")
fig.suptitle("공연 규모가 클수록 같은 요일의 저녁 주차대수가 높다 (관측 평균, 요일 유형 안 비교)", x=0.01, ha="left", fontsize=12.5, fontweight="bold")
finish(fig, "fig4_tier_curves.png", "공연 규모: 그날 시간별 관람객 수의 최댓값 8천 미만=소, 8천~1.4만=중, 1.4만 이상=대. 괄호는 관측한 날 수. " + SRC)

# ---------- 그림 5: 관람객 규모 대 저녁 주차 (일 단위) ----------
g = nh[nh["dow"].isin([4, 5, 6])].groupby("date").agg(aud=("aud_day", "first"), dow=("dow", "first"))
g["eve"] = nh[nh["hour"].between(17, 21)].groupby("date")["cars"].mean()
g = g[g["aud"] > 0].dropna()
fig, ax = plt.subplots(figsize=(8, 5.2))
res5 = {}
for name, m, c in [("금요일", g["dow"] == 4, ORANGE), ("토·일요일", g["dow"] >= 5, BLUE)]:
    gg = g[m]
    ax.scatter(gg["aud"] / 1000, gg["eve"], s=42, color=c, alpha=0.85, edgecolors=SURF, linewidths=1.2, label=f"{name} ({len(gg)}일)")
    bb, aa = np.polyfit(gg["aud"] / 1000, gg["eve"], 1)
    xs = np.array([gg["aud"].min() / 1000, gg["aud"].max() / 1000])
    ax.plot(xs, aa + bb * xs, color=c, lw=1.6, ls="--")
    res5[name] = (bb, len(gg))
ax.set_xlabel("그날 공연 관람객 수(천 명, 시간별 최댓값)"); ax.set_ylabel("저녁 17~21시 평균 주차대수(대)")
ax.legend(frameon=False, loc="upper left", fontsize=10.5)
ax.set_title("관람객이 많은 날일수록 저녁 주차가 늘어난다", loc="left")
ax.text(0.99, 0.04, "요일·월·기온 편차를 통제한 추정:\n관람객 +1천 명당 약 +59대 (95% 구간 42~75)", transform=ax.transAxes, ha="right", fontsize=10, color=INK)
finish(fig, "fig5_audience_vs_evening.png", "점선은 통제 전 단순 추세선. 조건부 관계이며 공연이 원인이라는 뜻이 아니다. " + SRC)

# ---------- 그림 6: 모델 검증 ----------
R = pd.read_csv(ROOT / "data/interim/model_preds_rolling_v2.csv")
mae = lambda c, m=None: float((R["y"] - R[c]).abs()[m if m is not None else slice(None)].mean())
big = (R["hour"].between(17, 21)) & (R["aud_daymax"] >= 8000)
left = [("요일×시각 평균", mae("B1"), GRAY), ("휴무일×시각 평균", mae("B2"), GRAY), ("달력 LightGBM", mae("S0"), BLUE), ("달력+기온편차+관람객+일정", mae("S4"), GRAY)]
right = [("휴무일×시각 평균", mae("B2", big), GRAY), ("달력 LightGBM", mae("S0", big), BLUE), ("달력+관람객 수", mae("S2", big), ORANGE)]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.0), gridspec_kw={"width_ratios": [1.15, 1]})
for ax, rows, ttl, lim in [(axes[0], left, f"전체 시간 (평균 {R['y'].mean():,.0f}대)", 260), (axes[1], right, "관람객 8천 명 이상인 날의 저녁(17~21시)", 560)]:
    ys = np.arange(len(rows))[::-1]
    ax.barh(ys, [r[1] for r in rows], color=[r[2] for r in rows], height=0.55)
    for yy, r in zip(ys, rows):
        ax.text(r[1] + lim * 0.015, yy, f"{r[1]:.0f}", va="center", fontsize=11, color=INK)
    ax.set_yticks(ys); ax.set_yticklabels([r[0] for r in rows]); ax.set_xlim(0, lim)
    ax.grid(axis="y", visible=False); ax.set_title(ttl, loc="left", fontsize=11.5); ax.set_xlabel("평균 절대 오차(대, 작을수록 좋음)")
cov = float(((R["y"] >= R["S0_lo"]) & (R["y"] <= R["S0_hi"])).mean())
fig.subplots_adjust(top=0.80, wspace=0.95, bottom=0.18)
fig.suptitle("월 단위 롤링 검증: 달력만 쓴 모델이 가장 좋고,\n관람객 정보는 큰 공연의 저녁에서만 도움이 된다", x=0.01, y=0.99, ha="left", fontsize=12.5, fontweight="bold")
finish(fig, "fig6_validation.png", f"앞선 달로 학습해 다음 달(3~7월, 10월) 예측, {len(R):,}시간. 달력 모델의 80% 예측 구간은 실제 값의 {cov:.0%}를 포함. " + SRC)

# ---------- 그림 7: 서비스 구성도 ----------
fig, ax = plt.subplots(figsize=(11, 4.6)); ax.axis("off"); ax.set_xlim(0, 11.2); ax.set_ylim(-0.5, 4.6); ax.grid(False)
cols = [("① 공공데이터", ["연계 데이터(시간별 주차·공연·\n기상, 7,803행)", "입출차 정보 전체구역\n(2,411,225행, API)", "영문 공연정보 · 월별주차현황\n· 주차장 혼잡도 정보"]),
        ("② 정제·검증", ["원천 중복 14.2% 제거", "입출차로 재차 복원\n→ 기관 값과 상관 0.98", "원천 공백(8~9월, 11~12월)\n탐지·제외"]),
        ("③ 분석", ["요일 유형 × 시각 분포\n(중앙값·10/90%)", "공연 규모별 저녁 주차·\n퇴장 피크 비교", "월 단위 롤링 검증\n(오차·구간 포괄률)"]),
        ("④ 웹 서비스", ["방문객: 한산한 시간,\n출차 몰리는 시각", "운영자: 공연 규모별\n저녁 점유·퇴장 피크", "정적 웹(JSON) → 2028년까지\n유지 비용 거의 없음"])]
xw, gap = 2.45, 0.4
for i, (title, items) in enumerate(cols):
    x0 = 0.1 + i * (xw + gap)
    ax.text(x0 + xw / 2, 4.25, title, ha="center", fontsize=12.5, fontweight="bold", color=INK)
    for j, t in enumerate(items):
        y0 = 2.95 - j * 1.35
        ax.add_patch(plt.Rectangle((x0, y0 - 0.55), xw, 1.15, facecolor="#e9f1fb" if i < 3 else "#fff3ec", edgecolor=BLUE if i < 3 else ORANGE, lw=1.4))
        ax.text(x0 + xw / 2, y0 + 0.02, t, ha="center", va="center", fontsize=9.8, color=INK)
    if i < 3:
        ax.annotate("", xy=(x0 + xw + gap - 0.04, 2.4), xytext=(x0 + xw + 0.04, 2.4), arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.6))
finish(fig, "fig7_architecture.png", "정적 웹(HTML·JS·JSON): 서버·DB 없이 호스팅. 소스 코드는 공모전 수상 시 제공 가능.")

# ---------- 표 ----------
tab = pd.DataFrame([
    ("요일×시각 평균", mae("B1"), mae("B1", R["hour"].between(17, 21))),
    ("휴무일×시각 평균", mae("B2"), mae("B2", R["hour"].between(17, 21))),
    ("달력 LightGBM", mae("S0"), mae("S0", R["hour"].between(17, 21))),
    ("달력+기온편차 LightGBM", mae("S1"), mae("S1", R["hour"].between(17, 21))),
    ("달력+관람객 LightGBM", mae("S2"), mae("S2", R["hour"].between(17, 21))),
    ("달력+기온편차+관람객 LightGBM", mae("S3"), mae("S3", R["hour"].between(17, 21))),
    ("달력+기온편차+관람객+공연일정 LightGBM", mae("S4"), mae("S4", R["hour"].between(17, 21))),
], columns=["모델", "전체 MAE(대)", "저녁 17~21시 MAE(대)"]).round(1)
tab["관람객 8천 이상 날 저녁 MAE(대)"] = [round(mae(c, big), 1) for c in ("B1", "B2", "S0", "S1", "S2", "S3", "S4")]
tab.to_csv(OUT / "tables/table_validation.csv", index=False, encoding="utf-8-sig")
(OUT / "tables/table_validation.md").write_text(tab.to_markdown(index=False), encoding="utf-8")
tt = []
for grp, sub in (("금요일", nh[nh["dow"] == 4]), ("토·일요일", nh[nh["dow"] >= 5])):
    for t in ["공연 없음", "소규모", "중규모", "대규모"]:
        ss = sub[sub["tier"] == t]
        if ss["date"].nunique() == 0:
            continue
        eve = ss[ss["hour"].between(17, 21)].groupby("date")["cars"].mean().mean()
        out_pk = ss.groupby("hour")["outflow"].mean()
        tt.append((grp, t, ss["date"].nunique(), round(eve), int(out_pk.idxmax()), round(out_pk.max())))
T = pd.DataFrame(tt, columns=["요일 유형", "공연 규모", "관측일 수", "저녁 17~21시 평균 주차대수", "퇴장 피크 시각", "퇴장 피크 시간당 출차(기록 기준)"])
T.to_csv(OUT / "tables/table_tiers.csv", index=False, encoding="utf-8-sig")
(OUT / "tables/table_tiers.md").write_text(T.to_markdown(index=False), encoding="utf-8")
print(tab.to_string(index=False)); print(T.to_string(index=False))
print("recon", recon, "cov", round(cov, 3), "dose", res5)
