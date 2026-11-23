# 19. 기획서 v4 수치 대조표 (자동 생성)

- 대상: `올팍피크타임_기획서_v4.docx` (본문 문단 231개, 숫자 토큰 403개, 고유 값 144개)
- 방법: docx 본문에서 숫자를 모두 뽑아, 서비스 JSON(`docs/data/peaktime_2025.json`)과 화면 로직으로 다시 계산한 값, `plan_assets/README_기획서자료.md`·`report/00_findings_and_direction.md`·`plan_assets/tables/`의 확정값, 안내문 텍스트와 대조했다. 데이터 값이 아닌 숫자(정의·규칙·날짜·번호)는 근거를 따로 적었다.
- 생성 스크립트: 작업 폴더의 `check_v3.py`(저장소 밖, v4에도 같은 스크립트 사용). 수치 계산: `numbers_v3.js`(docs/index.html 의 PeakLogic + peaktime_2025.json + upcoming.json + data/interim/kopis_match.json). KOPIS 값은 report/21과도 대조했다.

## 결과

- 출처에 없는 숫자: **0건**
- 출처 값과 다른 숫자: **0건**
- 링크 해시 5개 중 화면 예시·시나리오와 다른 것: **0건**

## 출처 메모(판단이 필요했던 값)

- **기관 값과 복원값의 크기 관계**: README(fig2, 분석일 235일 기준)는 1.14 × 복원 + 45, report/00 15절(일 최대 1,500대 이상 '정상일' 기준)은 1.13 × 복원 + 51. report/00 214행이 '기획서에는 유효일 기준 값을 쓴다'고 정리했으므로 본문은 '약 1.13~1.14배 + 상수(분석일 기준 1.14 × 복원 + 45)'로 쓰고 그림 캡션은 1.14배 + 45대를 썼다. 상관은 README 확정값 0.983(5,633시간)을 썼다(report/00 15절의 0.981은 다른 날 기준).
- **금요일 소규모 저녁 평균**: `plan_assets/tables/table_tiers.md`는 1,469대, 서비스 JSON(시각별 평균을 정수로 저장한 뒤 17~21시 평균)은 1,470대. 화면과 같게 JSON 값을 썼다(1대 차이는 반올림 순서).
- **토·일 공연일 65일**: JSON에서 토 32일·일 33일이 모두 공연일(n_perf_days = n_days)이다. report/00 16절의 '주말 67일'은 공휴일과 겹친 주말을 포함한 수라 본문에는 쓰지 않았다.
- **예시 입력값**(날짜 2026-12-05, 관람객 12.0천 명·1.2만 명, 14시 도착·19시 출발)은 시나리오 설명용 입력이며, 그 결과 숫자는 모두 화면 로직으로 계산했다. v3의 시나리오 A는 12/5의 실제 KOPIS 일정(KSPO DOME 공연)으로 규모가 '중규모'로 미리 골라지는 상태다.
- **시뮬레이터 관측 범위**: JSON x_max 22.198 → v2는 22.2(반올림), 화면 슬라이더는 22.1(버림). v3는 화면과 같은 22.1을 쓴다.

## 대조표(고유 값별)

| 본문 값 | 분류 | 출처 | 대조 |
|---|---|---|---|
| 0 | 토·일 공연 없는 날 | JSON tiers.weekend[0].n_days | 일치 |
| 1 | 규칙·구조 | 1천 명당·목록 번호 | 일치 |
| 2 | 규칙·구조 | 앞뒤 2시간·연속 2시간 규칙 | 일치 |
| 3 | 표1 관측일 | JSON tiers.fri | 일치 |
| 3 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 4 | 토요일 규모별 관측일 | JSON groups[sat].tiers[1] | 일치 |
| 4 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 5 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 5 | 규모 제안 공연장 최소 표본 | upcoming.json halls | 일치 |
| 6 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 7 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 8 | 표1 관측일 | JSON tiers.fri | 일치 |
| 8 | 표1 관측일 | JSON tiers.weekend | 일치 |
| 9 | 표1 관측일 | JSON tiers.fri | 일치 |
| 9 | 시나리오 A·1-2: 덜 붐빔 시작 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 00 | KOPIS 공연시간 안내 원문 | upcoming.json shows.guidance | 일치 |
| 00 | KOPIS 공연시간 안내 원문 | upcoming.json shows.guidance | 일치 |
| 01 | 규칙·구조 | 12-01(안내문 마감) | 일치 |
| 03 | KOPIS 기준일·범위 | upcoming.json meta.snapshot/range | 일치 |
| 05 | 규칙·구조 | 2026-12-05 예시 날짜(토요일) | 일치 |
| 07 | 규칙·구조 | 2024-07(README) | 일치 |
| 10 | 표1 관측일 | JSON tiers.fri | 일치 |
| 10 | 롤링 검증 달 | JSON meta.validation.fold_months | 일치 |
| 11 | 시나리오 A·1-2: 덜 붐빔 끝 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 11 | KOPIS 기준일·범위 | upcoming.json meta.snapshot/range | 일치 |
| 12 | 시나리오 A·1-2: 대안 도착 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 13 | 토요일 규모별 관측일 | JSON groups[sat].tiers[3] | 일치 |
| 13 | 시나리오 A·1-2: 토 대규모 관측일 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 14 | 시나리오 A·1-2: 도착 입력 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 14 | 시나리오 A·1-2: 대규모 붐빔 시작 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 15 | 토요일 규모별 관측일 | JSON groups[sat].tiers[2] | 일치 |
| 15 | 시나리오 A·1-2: 토 중규모 관측일 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 16 | 표1 퇴장 피크 시각 | JSON tiers.weekend.out_mean 최대 시각 | 일치 |
| 16 | 표1 퇴장 피크 시각 | JSON tiers.weekend.out_mean 최대 시각 | 일치 |
| 17 | 관측일(공휴일·연휴) | JSON groups[hol].n_days | 일치 |
| 17 | 시나리오 A·1-2: 붐빔 끝 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 18 | 표1 퇴장 피크 시각 | JSON tiers.fri.out_mean 최대 시각 | 일치 |
| 18 | 표1 퇴장 피크 시각 | JSON tiers.fri.out_mean 최대 시각 | 일치 |
| 19 | 시나리오 A·1-2: 출발 입력 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 19 | 시나리오 A·1-2: 대규모 붐빔 끝 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 20 | 규칙·구조 | 저녁 17~21시 정의(17·18·19·20·21시 다섯 시각, 화면 로직 mean(a,17,21)) | 일치 |
| 21 | 토·일 대규모 저녁 출차 봉우리 시각 | JSON tiers.weekend[3].out_mean 19~22시 최대 | 일치 |
| 21 | KOPIS: 다가오는 공연 수 | upcoming.json meta (= report/21) | 일치 |
| 22 | 시나리오 A·1-2: 나가기 편한 시각 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 22 | 금요일 시뮬레이터 표본 | JSON sim.fri.n | 일치 |
| 26 | 표1 관측일 | JSON tiers.weekend | 일치 |
| 28 | 관측일(월) | JSON groups[mon].n_days | 일치 |
| 30 | 관측일(화) | JSON groups[tue].n_days | 일치 |
| 30 | 관측일(금) | JSON groups[fri].n_days | 일치 |
| 31 | 표1 관측일 | JSON tiers.weekend | 일치 |
| 31 | KOPIS 기준일·범위 | upcoming.json meta.snapshot/range | 일치 |
| 32 | 관측일(수) | JSON groups[wed].n_days | 일치 |
| 32 | 관측일(토) | JSON groups[sat].n_days | 일치 |
| 33 | 관측일(목) | JSON groups[thu].n_days | 일치 |
| 33 | 관측일(일) | JSON groups[sun].n_days | 일치 |
| 42 | 증분 95% 구간 | JSON meta.uplift.eve_cars_ci (= README 42~75) | 일치 |
| 45 | 확정값 | README §2 | 일치 |
| 59 | 관람객 1천 명당 저녁 증분 | JSON meta.uplift (= README +59) | 일치 |
| 60 | 확정값 | report/00 15절 (심야 약 60대) | 일치 |
| 65 | 토·일 공연일(= 토·일 관측일) | JSON groups sat/sun n_perf_days | 일치 |
| 65 | 시뮬레이터 표본(토·일 공연일) | JSON sim.weekend.n | 일치 |
| 72 | 확정값 | README §1 (월별주차현황 72행) | 일치 |
| 75 | 증분 95% 구간 | JSON meta.uplift.eve_cars_ci (= README 42~75) | 일치 |
| 80 | 규칙·구조 | 80% 예측구간 정의(목표 80%) | 일치 |
| 81 | 80% 구간 포괄률(%) | JSON meta.validation.interval80_coverage = 0.81 | 일치 |
| 86 | 강수량 결측(%) | JSON coverage.rain_missing_rate (= README 약 86%) | 일치 |
| 89 | 증분 분석일 | JSON meta.uplift.n_days (= README n=89) | 일치 |
| 90 | 규칙·구조 | 10~90% 범위 정의 | 일치 |
| 95 | 규칙·구조 | 95% 구간 정의 | 일치 |
| 008 | 규칙·구조 | API_CPM_008(README) | 일치 |
| 009 | 규칙·구조 | API_CPM_009(README) | 일치 |
| 1.2 | 규칙·구조 | 운영자 시나리오 예시 입력(1.2만 명 = 12.0천 명) | 일치 |
| 1.4 | 규칙·구조 | 1.4만 명(규모 구간) 정의 | 일치 |
| 127 | KOPIS: KOPIS 2025 공연 수 | upcoming.json meta (= report/21) | 일치 |
| 131 | KOPIS: 날짜 매칭(엄격) | upcoming.json meta (= report/21) | 일치 |
| 136 | KOPIS: 기관 공연일 | upcoming.json meta (= report/21) | 일치 |
| 2.2 | 금요일 시뮬레이터 슬라이더 범위 | 화면 로직 sliderBounds(JSON sim.fri) | 일치 |
| 2.5 | 관측 범위 하한(천 명) | JSON sim.weekend.x_min | 일치 |
| 2.5 | 토·일 시뮬레이터 슬라이더 범위 | 화면 로직 sliderBounds(JSON sim.weekend) | 일치 |
| 235 | 분석한 날 | JSON meta.valid_days (= README 235일) | 일치 |
| 286 | 확정값 | README §1 | 일치 |
| 293 | 시나리오 A·1-2: 19시 출차 평소 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 322 | 잔차 표준편차 | JSON sim.weekend.resid_sd | 일치 |
| 403 | 시나리오 A·1-2: 대안 도착 차이 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 483 | 확정값 | report/00 15절 (5,000건 × 483페이지) | 일치 |
| 5.4 | 월별 입차(만 건) 11월 | JSON coverage.monthly_inflow (= README) | 일치 |
| 6.0 | 월별 입차(만 건) 12월 | JSON coverage.monthly_inflow (= README) | 일치 |
| 6.2 | 월별 입차(만 건) 8월 | JSON coverage.monthly_inflow (= README) | 일치 |
| 6.6 | 월별 입차(만 건) 9월 | JSON coverage.monthly_inflow (= README) | 일치 |
| 682 | 토·일 대규모 저녁 출차 봉우리 값 | JSON tiers.weekend[3].out_mean | 일치 |
| 699 | 확정값 | README §1·report/18 (혼잡도 699행) | 일치 |
| 724 | 대규모−소규모 저녁 차이 | JSON tiers.weekend 17~21시 평균 차 | 일치 |
| 736 | 표1 피크 출차 | JSON tiers.weekend.out_mean | 일치 |
| 752 | 표1 피크 출차 | JSON tiers.fri.out_mean | 일치 |
| 753 | 표1 피크 출차 | JSON tiers.weekend.out_mean | 일치 |
| 769 | 표1 피크 출차 | JSON tiers.fri.out_mean | 일치 |
| 841 | 표1 피크 출차 | JSON tiers.weekend.out_mean | 일치 |
| 857 | 표1 피크 출차 | JSON tiers.fri.out_mean | 일치 |
| 986 | 표1 피크 출차 | JSON tiers.fri.out_mean | 일치 |
| 986 | 예시 버튼: 금요일 저녁 출차 | 화면 로직 scenarios(JSON) | 일치 |
| 990 | 표1 저녁 평균 | JSON tiers.weekend.cars_mean 17~21시 평균 | 일치 |
| 996 | 시뮬레이터 12.0천 명 결과 | 화면 로직 predictEvening(JSON sim.weekend, 12.0) | 일치 |
| 1.13 | 확정값 | report/00 15절 (1.13 × 복원 + 51) | 일치 |
| 1.14 | 확정값 | README §2 (기관 = 1.14×복원 + 45) | 일치 |
| 12.0 | 규칙·구조 | 시뮬레이터 예시 입력값(관측 범위 안) | 일치 |
| 14.2 | 확정값 | README §2 (원천 중복 14.2%) | 일치 |
| 18.6 | 금요일 시뮬레이터 슬라이더 범위 | 화면 로직 sliderBounds(JSON sim.fri) | 일치 |
| 2024 | 규칙·구조 | 2024-07 입출차(README) | 일치 |
| 2025 | 확정값 | 자료 연도(README) | 일치 |
| 2026 | KOPIS 기준일·범위 | upcoming.json meta.snapshot/range | 일치 |
| 2026 | 확정값 | 대회 연도·날짜(안내문) | 일치 |
| 2027 | KOPIS 기준일·범위 | upcoming.json meta.snapshot/range | 일치 |
| 2028 | 확정값 | 안내문 (2028년까지 운영) | 일치 |
| 22.1 | 토·일 시뮬레이터 슬라이더 범위 | 화면 로직 sliderBounds(JSON sim.weekend) | 일치 |
| 25.4 | 월별 입차(만 건) 10월 | JSON coverage.monthly_inflow (= README) | 일치 |
| 88.8 | KOPIS: 공연명 매칭률(%) | upcoming.json meta (= report/21) | 일치 |
| 96.3 | KOPIS: 날짜 매칭률(%) | upcoming.json meta (= report/21) | 일치 |
| 0.983 | 확정값 | README §2 (fig2) | 일치 |
| 1,278 | 표1 저녁 평균 | JSON tiers.fri.cars_mean 17~21시 평균 | 일치 |
| 1,300 | 평균 주차대수 | JSON meta.validation.mean_cars (= README 평균 1,300대) | 일치 |
| 1,313 | 3분위 경계(주차 중인 차량) | JSON meta.cars_thresholds | 일치 |
| 1,349 | 표1 저녁 평균 | JSON tiers.weekend.cars_mean 17~21시 평균 | 일치 |
| 1,416 | 시뮬레이터 12.0천 명 결과 | 화면 로직 predictEvening(JSON sim.weekend, 12.0) | 일치 |
| 1,470 | 표1 저녁 평균 | JSON tiers.fri.cars_mean 17~21시 평균 | 일치 |
| 1,616 | 시나리오 A·1-2: 대안 도착 값 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 1,714 | 표1 저녁 평균 | JSON tiers.weekend.cars_mean 17~21시 평균 | 일치 |
| 1,748 | 표1 저녁 평균 | JSON tiers.fri.cars_mean 17~21시 평균 | 일치 |
| 1,836 | 시뮬레이터 12.0천 명 결과 | 화면 로직 predictEvening(JSON sim.weekend, 12.0) | 일치 |
| 1,837 | 시나리오 A·1-2: 14시 10% | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 181.0 | 달력 모델 MAE | JSON meta.validation | 일치 |
| 181.0 | 표2 달력 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 190.2 | 표2 휴무일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 192.3 | 표2 달력+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 197.8 | 표2 달력+기온편차+관람객+공연일정 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 198.6 | 표2 달력+기온편차 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 198.6 | 확정값 | README/table_validation (달력+기온편차) | 일치 |
| 2,019 | 시나리오 A·1-2: 14시 평소 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 2,070 | 3분위 경계(주차 중인 차량) | JSON meta.cars_thresholds | 일치 |
| 2,367 | 시나리오 A·1-2: 14시 90% | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 2,527 | 표1 저녁 평균 | JSON tiers.fri.cars_mean 17~21시 평균 | 일치 |
| 2,750 | 공연장 단독일 중앙값 | upcoming.json halls (= report/21) | 일치 |
| 200.2 | 표2 달력+기온편차+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 220.2 | 표2 요일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 237.4 | 표2 달력+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 238.1 | 표2 달력 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 241.4 | 표2 달력+기온편차+관람객+공연일정 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 243.6 | 표2 달력+기온편차+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 260.2 | 표2 달력+기온편차 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 262.0 | 표2 휴무일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 272.2 | 표2 요일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 335.5 | 표2 달력+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 335.5 | 확정값 | table_validation (달력+관람객) | 일치 |
| 361.1 | 표2 달력+기온편차+관람객+공연일정 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 371.2 | 표2 달력+기온편차+관람객 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 397.0 | 표2 요일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 4,271 | 롤링 검증 시간 | JSON meta.validation.eval_hours | 일치 |
| 411.9 | 표2 달력 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 411.9 | 확정값 | table_validation (달력, 관람객 8천 이상) | 일치 |
| 441.9 | 표2 달력+기온편차 LightGBM | JSON validation_table (= tables/table_validation.md) | 일치 |
| 485.7 | 표2 휴무일×시각 평균 | JSON validation_table (= tables/table_validation.md) | 일치 |
| 5,000 | 확정값 | report/00 15절 | 일치 |
| 5,633 | 확정값 | README §2 (fig2) | 일치 |
| 7,803 | 연계 데이터 행 | JSON coverage.linked_rows (= README 7,803행) | 일치 |
| 10,000 | 시나리오 A·1-2: KSPO DOME 단독일 관람객 중앙값 | 화면 로직(showsOn·suggestTier·visitorHeadline·planVisit) + JSON + upcoming.json | 일치 |
| 10,000 | 공연장 단독일 중앙값 | upcoming.json halls (= report/21) | 일치 |
| 215,528 | 확정값 | README §1 | 일치 |
| 15131671 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 15138735 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 15149169 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 15159093 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 15164156 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 15164822 | 규칙·구조 | 데이터셋 번호(README) | 일치 |
| 2,068,143 | 확정값 | README §1·§2 | 일치 |
| 2,411,225 | 확정값 | README §1·§2 | 일치 |

## 링크

- https://js-vega.github.io/kspo-peaktime/
- https://js-vega.github.io/kspo-peaktime/
- https://js-vega.github.io/kspo-peaktime/#v=visitor&g=5&m=cars&p=3&a=9&d=22
- https://js-vega.github.io/kspo-peaktime/#v=visitor&g=0&m=cars&a=16&d=18
- https://js-vega.github.io/kspo-peaktime/#v=operator&g=4&m=out&t=3
- https://github.com/js-VEGA/kspo-peaktime
- https://js-vega.github.io/kspo-peaktime/#v=visitor&g=5&date=2026-12-05&m=cars&a=14&d=19
- https://js-vega.github.io/kspo-peaktime/#v=operator&g=5&m=cars&t=3&s=12.0
