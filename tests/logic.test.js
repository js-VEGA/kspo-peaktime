// 화면 계산 로직 단위 검증. 실행: node tests/logic.test.js  (프로젝트 루트에서)
// docs/index.html 의 <script id="logic"> 블록을 꺼내 실행하므로 화면과 같은 코드를 검증한다.
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const assert = require("assert");

const root = path.join(__dirname, "..");
const html = fs.readFileSync(path.join(root, "docs", "index.html"), "utf8");
const m = html.match(/<script id="logic">([\s\S]*?)<\/script>/);
assert(m, "logic 스크립트 블록을 찾지 못함");
const sandbox = { module: { exports: {} } };
vm.runInNewContext(m[1], sandbox);
const L = sandbox.module.exports;
const D = JSON.parse(fs.readFileSync(path.join(root, "docs", "data", "peaktime_2025.json"), "utf8"));
const thr = { cars: D.meta.cars_thresholds, out: D.meta.out_thresholds };

let n = 0;
function t(name, fn) { try { fn(); n++; } catch (e) { console.error("FAIL:", name, "\n ", e.message); process.exitCode = 1; } }
const flat = (v) => ({ p10: Array(24).fill(v), p50: Array(24).fill(v), p90: Array(24).fill(v), mean: Array(24).fill(v) });

t("levelOf 경계: 하한 값은 보통, 상한 값은 붐빔", () => {
  const th = [100, 200];
  assert.strictEqual(L.levelOf(99, th), "calm");
  assert.strictEqual(L.levelOf(100, th), "mid");
  assert.strictEqual(L.levelOf(199, th), "mid");
  assert.strictEqual(L.levelOf(200, th), "busy");
  assert.strictEqual(L.levelOf(null, th), null);
  assert.strictEqual(L.levelOf(5, null), null);
});

t("isHour: 5~23 정수만 허용", () => {
  [5, 12, 23].forEach((h) => assert(L.isHour(h)));
  [4, 24, 10.5, NaN, Infinity, "10", null, undefined].forEach((h) => assert(!L.isHour(h), String(h)));
});

t("planVisit 입력 오류: 시각 범위·순서", () => {
  const g = D.groups[5];
  assert.strictEqual(L.planVisit(g, thr, 4, 10).reason, "hour");
  assert.strictEqual(L.planVisit(g, thr, 10, 24).reason, "hour");
  assert.strictEqual(L.planVisit(g, thr, "10", 12).reason, "hour");
  assert.strictEqual(L.planVisit(g, thr, 12, 11).reason, "order");
});

t("도착 5시·출발 5시: 대안 도착 없음(범위가 자기 자신뿐), 결과 정상", () => {
  const r = L.planVisit(D.groups[5], thr, 5, 5);
  assert(r.ok);
  assert.strictEqual(r.altArrive, null);
  if (r.altDepart) assert(r.altDepart.hour >= 5 && r.altDepart.hour <= 7);
});

t("도착 23시·출발 23시: 범위 끝 처리", () => {
  const r = L.planVisit(D.groups[5], thr, 23, 23);
  assert(r.ok);
  if (r.altArrive) assert(r.altArrive.hour >= 21 && r.altArrive.hour <= 23 && r.altArrive.hour !== 23);
  if (r.altDepart) assert(r.altDepart.hour >= 23 - 2 && r.altDepart.hour <= 23);
});

t("도착 5시 ~ 출발 23시 전 그룹에서 오류 없이 계산", () => {
  D.groups.forEach((g) => { const r = L.planVisit(g, thr, 5, 23); assert(r.ok, g.key); });
});

t("모든 시각이 같은 값이면 대안 없음(엄격히 낮을 때만 제안)", () => {
  const g = { cars: flat(1500), out: flat(500) };
  for (let a = 5; a <= 23; a++) for (let d = a; d <= 23; d++) {
    const r = L.planVisit(g, thr, a, d);
    assert(r.ok && r.altArrive === null && r.altDepart === null, `${a}-${d}`);
    assert.strictEqual(r.arrive.level, L.levelOf(1500, thr.cars));
  }
});

t("n이 0인 그룹(값 없음): nodata 로 처리", () => {
  const empty = { cars: { p10: Array(24).fill(null), p50: Array(24).fill(null), p90: Array(24).fill(null) }, out: { p10: Array(24).fill(null), p50: Array(24).fill(null), p90: Array(24).fill(null) } };
  assert.strictEqual(L.planVisit(empty, thr, 10, 12).reason, "nodata");
});

t("한 시각만 값이 없으면 그 시각은 대안에서 건너뜀", () => {
  const cars = flat(2000); cars.p50[11] = null; cars.p50[12] = 1000;
  const r = L.planVisit({ cars, out: flat(500) }, thr, 10, 16);
  assert.strictEqual(r.altArrive.hour, 12);
  assert.strictEqual(r.altArrive.diff, 1000);
});

t("불변식(실제 데이터, 전 그룹 × 모든 도착·출발 조합)", () => {
  let checked = 0;
  D.groups.forEach((g) => {
    for (let a = 5; a <= 23; a++) for (let d = a; d <= 23; d++) {
      const r = L.planVisit(g, thr, a, d, 2);
      assert(r.ok);
      const base = g.cars.p50[a];
      if (r.altArrive) {
        const x = r.altArrive;
        assert(x.hour >= Math.max(5, a - 2) && x.hour <= Math.min(d, a + 2) && x.hour !== a, "대안 도착 범위");
        assert(x.value < base && x.diff === base - x.value && x.value === g.cars.p50[x.hour]);
        for (let h = Math.max(5, a - 2); h <= Math.min(d, a + 2); h++) assert(g.cars.p50[h] >= x.value || h === a, "대안이 범위 최솟값");
      } else {
        for (let h = Math.max(5, a - 2); h <= Math.min(d, a + 2); h++) assert(g.cars.p50[h] >= base, "대안이 없다면 base 가 최소");
      }
      const ob = g.out.p50[d];
      if (r.altDepart) {
        const x = r.altDepart;
        assert(x.hour >= Math.max(a, d - 2) && x.hour <= Math.min(23, d + 2) && x.hour !== d, "대안 출발 범위");
        assert(x.value < ob && x.diff === ob - x.value);
        for (let h = Math.max(a, d - 2); h <= Math.min(23, d + 2); h++) assert(g.out.p50[h] >= x.value || h === d);
      } else {
        for (let h = Math.max(a, d - 2); h <= Math.min(23, d + 2); h++) assert(g.out.p50[h] >= ob);
      }
      checked++;
    }
  });
  assert(checked > 1000);
});

t("실제 데이터 예: 토요일 도착 10시의 중앙값·상태가 JSON 과 일치", () => {
  const g = D.groups[5];
  const r = L.planVisit(g, thr, 10, 16);
  assert.strictEqual(r.arrive.value, g.cars.p50[10]);
  assert.strictEqual(r.arrive.level, L.levelOf(g.cars.p50[10], thr.cars));
  assert.strictEqual(r.depart.value, g.out.p50[16]);
});

// ---------- 관람객 수 시뮬레이터 ----------
const FRI = D.sim.fri, WKE = D.sim.weekend;

t("modelFor: 금→fri, 토·일→weekend, 월~목·휴·모델 없음→null", () => {
  assert.strictEqual(L.modelFor(D.sim, "fri"), FRI);
  assert.strictEqual(L.modelFor(D.sim, "sat"), WKE);
  assert.strictEqual(L.modelFor(D.sim, "sun"), WKE);
  ["mon", "tue", "wed", "thu", "hol", "xxx"].forEach((k) => assert.strictEqual(L.modelFor(D.sim, k), null, k));
  assert.strictEqual(L.modelFor(undefined, "fri"), null);
  assert.strictEqual(L.modelFor({ fri: Object.assign({}, FRI, { n: 2 }) }, "fri"), null, "n<3 은 모델 없음");
  assert.strictEqual(L.modelFor({ fri: Object.assign({}, FRI, { x_max: FRI.x_min }) }, "fri"), null, "범위 0 은 모델 없음");
});

t("sliderBounds: 관측 범위 안쪽, 0.1 단위", () => {
  [FRI, WKE].forEach((mdl) => {
    const b = L.sliderBounds(mdl);
    assert(b.min >= mdl.x_min - 1e-9 && b.max <= mdl.x_max + 1e-9 && b.min <= b.max);
    assert(Math.abs(b.min * 10 - Math.round(b.min * 10)) < 1e-9 && Math.abs(b.max * 10 - Math.round(b.max * 10)) < 1e-9);
    assert.strictEqual(b.step, 0.1);
  });
  assert.strictEqual(JSON.stringify(L.sliderBounds({ x_min: 2.173, x_max: 18.698 })), JSON.stringify({ min: 2.2, max: 18.6, step: 0.1 })); // vm 객체라 deepStrictEqual 대신 값 비교
  assert.strictEqual(L.sliderBounds({ x_min: 2.11, x_max: 2.19 }), null, "0.1 칸이 없으면 null");
  assert.strictEqual(L.sliderBounds(null), null);
});

t("clampToBounds: 최솟값·최댓값 밖은 보정, 숫자가 아니면 null", () => {
  const b = L.sliderBounds(FRI);
  assert.strictEqual(L.clampToBounds(FRI, -5), b.min);
  assert.strictEqual(L.clampToBounds(FRI, 999), b.max);
  assert.strictEqual(L.clampToBounds(FRI, b.min), b.min);
  assert.strictEqual(L.clampToBounds(FRI, b.max), b.max);
  assert.strictEqual(L.clampToBounds(FRI, 9.04), 9.0);
  [NaN, Infinity, "9", null, undefined].forEach((x) => assert.strictEqual(L.clampToBounds(FRI, x), null, String(x)));
});

t("predictEvening: 슬라이더 최솟값·최댓값에서 계산되고 구간이 예측값을 감싼다", () => {
  [FRI, WKE].forEach((mdl) => {
    const b = L.sliderBounds(mdl);
    [b.min, b.max, mdl.xbar].forEach((x) => {
      const r = L.predictEvening(mdl, x);
      assert(r.ok, "x=" + x);
      assert(r.lo < r.yhat && r.yhat < r.hi);
      assert(Math.abs(r.yhat - (mdl.intercept + mdl.slope * x)) < 1e-9);
    });
    // 평균 x 에서 구간 반폭 = t80 · s · sqrt(1 + 1/n)
    const rm = L.predictEvening(mdl, mdl.xbar);
    assert(Math.abs((rm.hi - rm.yhat) - mdl.t80 * mdl.resid_sd * Math.sqrt(1 + 1 / mdl.n)) < 1e-6);
  });
});

t("predictEvening: 관측 범위 밖·숫자 아님·모델 없음은 거부", () => {
  assert.strictEqual(L.predictEvening(FRI, FRI.x_min - 0.5).reason, "range");
  assert.strictEqual(L.predictEvening(FRI, FRI.x_max + 0.5).reason, "range");
  assert.strictEqual(L.predictEvening(FRI, 0).reason, "range", "공연 없음(0)은 범위 밖");
  assert.strictEqual(L.predictEvening(FRI, NaN).reason, "value");
  assert.strictEqual(L.predictEvening(FRI, "9").reason, "value");
  assert.strictEqual(L.predictEvening(null, 9).reason, "model");
  assert.strictEqual(L.predictEvening(Object.assign({}, FRI, { n: 0 }), 9).reason, "model", "n=0");
});

t("predictEvening: 잔차 표준편차 0 이면 구간 폭 0", () => {
  const mdl = { n: 5, slope: 10, intercept: 100, resid_sd: 0, xbar: 5, sxx: 10, t80: 1.5, x_min: 2, x_max: 8 };
  const r = L.predictEvening(mdl, 5);
  assert(r.ok && r.lo === r.yhat && r.hi === r.yhat && r.yhat === 150);
});

t("JSON: 공연일 표본이 없는 유형은 n_perf_days 만 있고 모델이 없다", () => {
  D.groups.forEach((g) => assert(Number.isInteger(g.n_perf_days), g.key));
  ["mon", "tue", "wed", "thu", "hol"].forEach((k) => {
    const g = D.groups.find((x) => x.key === k);
    assert.strictEqual(L.modelFor(D.sim, k), null);
    assert(g.n_perf_days < 10, k);
  });
});

// ---------- 소표본·기본 요일·해시 ----------
t("isSmall: 5일 미만만 참고용(경계 4/5, 0, 비숫자)", () => {
  assert(L.isSmall(0) && L.isSmall(3) && L.isSmall(4));
  assert(!L.isSmall(5) && !L.isSmall(17));
  [null, undefined, NaN, "3"].forEach((x) => assert(L.isSmall(x), String(x)));
  // 실제 데이터: 금요일 대규모(3일)만 소표본, 중규모(9일)는 아님
  assert(L.isSmall(D.tiers.fri[3].n_days) && !L.isSmall(D.tiers.fri[2].n_days));
});

t("groupIndexForDate: 요일·공휴일·대체공휴일·경계", () => {
  const g = (y, mo, d) => L.groupIndexForDate(new Date(y, mo - 1, d, 12, 0, 0));
  assert.strictEqual(g(2026, 11, 21), 5, "토요일");
  assert.strictEqual(g(2026, 11, 22), 6, "일요일");
  assert.strictEqual(g(2026, 11, 23), 0, "월요일");
  assert.strictEqual(g(2026, 12, 31), 3, "목요일");
  assert.strictEqual(g(2026, 1, 1), 7, "신정(목)");
  assert.strictEqual(g(2026, 3, 2), 7, "삼일절 대체공휴일(월)");
  assert.strictEqual(g(2026, 5, 25), 7, "부처님오신날 대체공휴일(월)");
  assert.strictEqual(g(2026, 6, 3), 7, "지방선거일(수)");
  assert.strictEqual(g(2026, 9, 26), 7, "추석 연휴(토)");
  assert.strictEqual(g(2026, 9, 27), 6, "추석 다음 날은 일요일");
  assert.strictEqual(g(2026, 10, 5), 7, "개천절 대체공휴일");
  assert.strictEqual(g(2026, 12, 25), 7, "성탄절(금)");
  assert.strictEqual(g(2026, 7, 17), 4, "제헌절은 상수에 없음 → 금요일");
  assert.strictEqual(g(2025, 1, 1), 2, "2026년 밖은 요일만 판정(수요일)");
  assert.strictEqual(L.groupIndexForDate(new Date(NaN)), null);
  assert.strictEqual(L.groupIndexForDate("2026-11-21"), null);
  assert.strictEqual(L.groupIndexForDate(null), null);
});

t("공휴일 상수: 2026년 날짜만, 중복 없음, 형식 일정", () => {
  const h = L.HOLIDAYS_2026;
  assert.strictEqual(new Set(h).size, h.length);
  h.forEach((x) => assert(/^2026-\d\d-\d\d$/.test(x) && !isNaN(new Date(x).getTime()), x));
});

t("buildHash/parseHash 왕복과 값 범위 검증", () => {
  const s = L.buildHash({ v: "operator", g: 5, m: "out", t: 2, s: 12.55 });
  assert.strictEqual(s, "v=operator&g=5&m=out&t=2&s=12.6".replace("12.6", Number(12.55).toFixed(1)));
  const p = L.parseHash("#" + s, 8);
  assert(p.v === "operator" && p.g === 5 && p.m === "out" && p.t === 2 && Math.abs(p.s - Number(12.55).toFixed(1)) < 1e-9);
  const q = L.parseHash("#v=visitor&g=3&a=10&d=16", 8);
  assert(q.v === "visitor" && q.g === 3 && q.a === 10 && q.d === 16);
  assert.strictEqual(L.buildHash({ v: "visitor", g: 3, t: null, s: undefined, a: 10, d: NaN }), "v=visitor&g=3&a=10");
});

t("parseHash: 범위 밖·형식 오류는 버림, 빈 입력 안전", () => {
  const p = L.parseHash("#v=hack&g=8&m=x&t=4&a=4&d=24&s=-1", 8);
  assert.strictEqual(Object.keys(p).length, 0, JSON.stringify(p));
  assert.strictEqual(Object.keys(L.parseHash("", 8)).length, 0);
  assert.strictEqual(Object.keys(L.parseHash(undefined, 8)).length, 0);
  assert.strictEqual(Object.keys(L.parseHash("#garbage&=&&g", 8)).length, 0);
  assert.strictEqual(L.parseHash("g=7", 8).g, 7);
  assert.strictEqual(L.parseHash("g=8", 8).g, undefined, "그룹 수 밖");
  assert.strictEqual(L.parseHash("a=5&d=23&t=0&s=0", 8).s, 0);
  assert.strictEqual(L.parseHash("s=1e3", 8).s, undefined, "지수 표기 거부");
  assert.strictEqual(L.parseHash("g=1.5&a=10.5", 8).g, undefined);
});

console.log(n + "개 검증 통과" + (process.exitCode ? " (실패 있음)" : ""));
