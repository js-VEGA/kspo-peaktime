"""차량 단위 입출차(vehicles.csv.gz)로 시간별 입차·출차·재차를 복원하고, 기관 시간 단위 표(linked_hourly.csv)와 대조한다.
- 재차(occupancy): 입차시간 <= t < 출차시간 인 차량 수. 분 단위 누적합으로 시간 평균(occ_mean)과 정시 스냅숏(occ_start)을 만든다.
- 기관 표의 `주차대수`와 시각 정렬(0/+1시간)·크기 비율을 비교한다. 이상 구간은 '정상일'에서만 비교한다.
- 입력이 부분 표본이면 크기(비율)는 의미가 없고 상관만 참고한다.
실행: python -X utf8 -I src/reconstruct_occupancy.py   (프로젝트 루트에서)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
v = pd.read_csv(ROOT / "data" / "interim" / "vehicles.csv.gz", parse_dates=["t_in", "t_out"])
n_raw = len(v)
v = v.drop_duplicates("id")
bad = v["t_out"] < v["t_in"]
n_bad = int(bad.sum())
v = v[~bad & v["t_out"].notna()].copy()

start = pd.Timestamp("2025-01-01 00:00")
end = pd.Timestamp("2026-01-01 00:00")
nmin = int((end - start).total_seconds() // 60)


def minute_idx(s):
    return ((s - start).dt.total_seconds() // 60).astype("int64").values


i_in, i_out = minute_idx(v["t_in"]), minute_idx(v["t_out"])
keep = (i_in >= 0) & (i_in < nmin)
i_in, i_out = i_in[keep], np.clip(i_out[keep], 0, nmin)
delta = np.zeros(nmin + 1, dtype=np.int64)
np.add.at(delta, i_in, 1)
np.add.at(delta, i_out, -1)
occ_min = np.cumsum(delta)[:nmin]
hours = pd.date_range(start, periods=nmin // 60, freq="h")
H = pd.DataFrame({
    "ts": hours,
    "occ_start": occ_min[::60],
    "occ_mean": occ_min.reshape(-1, 60).mean(axis=1),
    "inflow": np.bincount(i_in // 60, minlength=nmin // 60)[: nmin // 60],
    "outflow": np.bincount(i_out[i_out < nmin] // 60, minlength=nmin // 60)[: nmin // 60],
})
H.to_csv(ROOT / "data" / "interim" / "hourly_recon.csv", index=False)

inst = pd.read_csv(ROOT / "data" / "interim" / "linked_hourly.csv", encoding="utf-8-sig", parse_dates=["ts"], keep_default_na=False, na_values=[""])
inst["date"] = inst["ts"].dt.normalize()
dd = inst.groupby("date").agg(n=("cars", "size"), mx=("cars", "max"))
normal_days = set(dd[(dd["n"] >= 23) & (dd["mx"] >= 1500)].index)  # 기관 표의 정상일(휴일 포함 일 최대 1,500대 이상)
inst_n = inst[inst["date"].isin(normal_days)].set_index("ts")["cars"]

L = ["# 재차 복원 점검 (자동 생성)\n",
     f"- 차량 행 {n_raw:,} → 중복 ID 제거·출차<입차 제외({n_bad:,}건) 후 {len(v):,}행 사용",
     f"- 기관 표의 정상일 {len(normal_days)}일, 비교 시각 {len(inst_n):,}개\n",
     "| 정렬 | 상관 | 기관/복원 비율 중앙값 |", "|---|---|---|"]
best = None
for name, col, shift in (("occ_start(정시)", "occ_start", 0), ("occ_mean(해당 시 평균)", "occ_mean", 0), ("occ_start(+1h)", "occ_start", -1), ("occ_mean(이전 시 평균)", "occ_mean", 1)):
    r = H.set_index("ts")[col].shift(shift).reindex(inst_n.index)
    ok = r.notna() & (r > 0)
    if ok.sum() < 10:
        continue
    corr = float(np.corrcoef(r[ok], inst_n[ok])[0, 1])
    ratio = float((inst_n[ok] / r[ok]).median())
    L.append(f"| {name} | {corr:.3f} | {ratio:.2f} |")
    if best is None or corr > best[0]:
        best = (corr, col, shift)
L.append("")
if best:
    r = H.set_index("ts")[best[1]].shift(best[2]).reindex(inst_n.index)
    ok = r.notna() & (r > 0)
    err = (inst_n[ok] - r[ok])
    L.append(f"- 최상 정렬: {best[1]} (shift {best[2]}), 상관 {best[0]:.3f}")
    L.append(f"- 기관 표 − 복원값: 평균 {err.mean():.1f}, 절대오차 중앙값 {err.abs().median():.1f}, 기관 표 평균 {inst_n[ok].mean():.0f}")
    mon = pd.DataFrame({"inst": inst_n[ok], "recon": r[ok]}).groupby(lambda t: t.month).mean().round(0)
    L.append("\n월별 평균(정상일): 기관 표 vs 복원\n" + mon.to_markdown())
bad_days = inst.groupby("date").agg(n=("cars", "size"), mx=("cars", "max"))
bad_days = bad_days[~bad_days.index.isin(normal_days)]
rec_day = H.assign(date=H["ts"].dt.normalize()).groupby("date")["occ_mean"].max()
L.append(f"\n- 기관 표의 이상일 {len(bad_days)}일 중 복원값 일 최대 중앙값: {float(rec_day.reindex(bad_days.index).median()):.0f} (기관 표 일 최대 중앙값 {float(bad_days['mx'].median()):.0f})")
(ROOT / "report" / "recon_check.md").write_text("\n".join(L), encoding="utf-8")
print("\n".join(L))
