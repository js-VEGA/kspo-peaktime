"""data/raw 의 CSV 4종을 프로파일링해 콘솔과 report/raw_profile.md 로 남긴다.
실행: python -I src/profile_raw.py   (프로젝트 루트에서)
"""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "report" / "raw_profile.md"


def read_any(path):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return pd.read_csv(path, encoding=enc, dtype=str), enc
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"인코딩 판별 실패: {path}")


lines = []


def emit(s=""):
    print(s)
    lines.append(s)


for f in sorted(RAW.glob("*.csv")):
    df, enc = read_any(f)
    emit(f"\n## {f.name}")
    emit(f"- 인코딩 {enc}, 행 {len(df):,}, 열 {len(df.columns)}")
    emit(f"- 완전중복 행: {df.duplicated().sum():,}")
    emit("")
    emit("| 컬럼 | 결측 | 결측률 | 고유값 | 예시 |")
    emit("|---|---|---|---|---|")
    for c in df.columns:
        na = df[c].isna().sum() + (df[c].astype(str).str.strip() == "").sum()
        ex = " / ".join(df[c].dropna().astype(str).unique()[:3])
        emit(f"| {c} | {na:,} | {na/len(df):.1%} | {df[c].nunique():,} | {ex[:60]} |")
    # 날짜/시간 형 컬럼 범위
    for c in df.columns:
        if any(k in c for k in ("일시", "일자", "등록일", "입차일", "날짜")):
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().any():
                emit(f"- {c}: {s.min()} ~ {s.max()} (변환실패 {s.isna().sum():,})")
    emit("")

OUT.parent.mkdir(exist_ok=True)
OUT.write_text("# 공개 파일 4종 프로파일 (자동 생성)\n" + "\n".join(lines), encoding="utf-8")
