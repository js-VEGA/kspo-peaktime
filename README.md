# 올팍 피크타임

올림픽공원 주차장이 **언제 붐비고 언제 빠지는지**, 공연 규모에 따라 **저녁 주차와 퇴장**이 얼마나 달라지는지를
한국체육산업개발(주)의 개방 데이터로 보여 주는 정적 웹 서비스입니다. (2026년 공공데이터 활용 경진대회 출품작)

- 접속 주소: **공개 예정** (GitHub Pages, 예상 주소 `https://js-vega.github.io/kspo-peaktime/` — 공개·배포 후 확인)
- 형태: `docs/index.html` 한 장 + `docs/data/peaktime_2025.json`. 빌드 도구·서버·DB 없이 동작합니다(글꼴만 Google Fonts, 실패해도 기본 글꼴로 표시).

## 화면

| 화면 | 내용 |
|---|---|
| 방문객 | 요일 유형(월~일·공휴일/연휴)별 시간대 주차 차량·출차, 가장 한산한 2시간, 출차가 몰리는 시각, **방문 시각 플래너**(도착·출발 시각을 고르면 같은 유형 날의 상태와 더 한산한 시각을 제안) |
| 운영자 | 금요일·주말의 **공연 규모별** 저녁 주차 차량·퇴장 피크, **관람객 수 시뮬레이터**(관측 범위 안에서 저녁 평균 주차 차량 어림) |
| 데이터 현황 | 월별 입차 기록(원천 공백), 원천 중복, 검증 표, 추가 개방이 필요한 데이터 의견 |

화면 상태는 주소 해시로 공유할 수 있습니다. 예: `#v=operator&g=5&t=3&m=out` (v 화면, g 월0…일6·휴7, t 공연 규모 번호, m cars/out).

## 읽을 때 알아둘 점

- 2025년 1~7월과 10월(235일)의 **관측 분포**입니다. '예측'은 *과거 같은 유형의 날들의 분포 기반 안내*이며 보장이 아닙니다.
- 7월 31일~9월 30일과 11월 이후, 매월 말일은 원천 입출차 기록이 비어 제외했습니다. 단일 연도라 계절성은 배우지 못했습니다.
- 공연이 있는 날과 주차 수요의 관계는 **조건부 비교**이며 공연이 원인이라는 뜻이 아닙니다. 기관 자료에서 주말은 전부 공연일로 표시돼 '공연일 vs 비공연일' 비교가 되지 않아 관람객 규모로만 비교합니다.
- 한산·보통·붐빔은 이 자료 안에서의 상대 구분(3분위)이며 공식 혼잡도가 아닙니다.
- '시간당 출차'는 입출차 기록에 남은 차량만 센 값입니다. 아직 나가지 않은 차량은 원천에 없습니다.
- 자세한 근거와 검증은 `report/00_findings_and_direction.md`, `report/model_2025_v2.md`, `report/perf_effect.md` 를 참고하세요.

## 데이터 출처 (이용허락범위 제한 없음, 공공데이터포털)

한국체육산업개발(주) 공공데이터. 문화포털(culture.go.kr) 오픈API로 받았습니다.

1. **올림픽공원 연계 데이터** (`API_CPM_009`, 공공데이터포털 15164822) — 시간별 주차대수·공연·기상(시간 단위 7,803행)
2. **입출차 정보 전체구역** (`API_CPM_008`, 공공데이터포털 15159093) — 차량 단위 입출차 2,411,225행(원천 중복 제거 후 2,068,143건)

탐색·교차 확인에는 월별주차현황, 영문 공연정보, 입출차 정보(2024-07)를 썼고 최종 화면에는 쓰지 않았습니다. 원본은 저장소에 포함하지 않으며 `data/raw/_manifest.json`에 출처와 해시를 기록합니다.

## 재현

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt   # pandas 2.3.3 고정: 이유는 report/00_findings_and_direction.md 5절
# API 키는 .env(git 제외)에 넣습니다. .env.example 참고. 문화포털 개발계정은 하루 1,000건 제한입니다.
.venv/Scripts/python -X utf8 -I src/fetch_bulk.py allzone --rows 5000   # 입출차 전량(재개 가능)
.venv/Scripts/python -X utf8 -I src/parse_linked.py                      # 연계 시간표 -> data/interim
.venv/Scripts/python -X utf8 -I src/parse_vehicles.py                    # 입출차 파싱·중복 제거
.venv/Scripts/python -X utf8 -I src/reconstruct_occupancy.py             # 재차 복원·검증
.venv/Scripts/python -X utf8 -I src/build_dataset.py                     # 모델링 데이터셋
.venv/Scripts/python -X utf8 -I src/model_2025_v2.py                     # 모델 검증
.venv/Scripts/python -X utf8 -I src/perf_effect.py                       # 공연 관람객 규모 분석
.venv/Scripts/python -X utf8 -I src/export_site_data_2025.py             # 웹용 JSON 생성
```

로컬에서 화면 보기: `cd docs && python -m http.server 8765` 후 http://127.0.0.1:8765 접속(파일을 직접 열면 데이터를 읽지 못합니다).
화면 계산 로직 검증: `node tests/logic.test.js`.

## 배포

GitHub Pages: *Settings → Pages → Deploy from a branch → `main` / `/docs`*. `docs/.nojekyll`은 Jekyll 처리를 끕니다.

## 한계와 이후 과제

`report/00_findings_and_direction.md` 15~17절과 `plan_assets/README_기획서자료.md` 6절(추가 개방이 필요한 데이터 의견)을 참고하세요.
