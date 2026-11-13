# 올팍 피크타임 (작업 중)

한국체육산업개발 개방 데이터로 올림픽공원 주차 수요에서 공연이 만드는 몫을 분리·예측하고,
방문자에게 출발 시각을, 운영자에게 공연·대관 겹침 위험을 알려주는 정적 웹 서비스.
2026년 공공데이터 활용 경진대회 출품 준비 중이며 아직 완성되지 않았다.

## 재현

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # pandas 2.3.3 고정: 이유는 report/00_findings_and_direction.md 5절
.venv/Scripts/python -I src/download_public.py             # data.go.kr 파일데이터 -> data/raw
.venv/Scripts/python -I src/profile_raw.py                 # report/raw_profile.md
.venv/Scripts/python -I src/explore_public.py              # report/public_crosscheck.md
```

API 2종(연계 데이터, 입출차 전체구역)은 문화포털 서비스키가 필요하다. 키는 `.env`(git 제외)에 넣는다. `.env.example` 참고.

## 데이터 출처

한국체육산업개발(주) 공공데이터(공공데이터포털, 이용허락범위 제한 없음). 원본 CSV는 저장소에 포함하지 않고 `data/raw/_manifest.json`에 출처와 해시를 기록한다.

## 한계

`report/00_findings_and_direction.md` 참고.
