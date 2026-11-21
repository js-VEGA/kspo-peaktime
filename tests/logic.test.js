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

console.log(n + "개 검증 통과" + (process.exitCode ? " (실패 있음)" : ""));
