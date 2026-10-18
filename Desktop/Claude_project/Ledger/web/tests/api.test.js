import test from "node:test";
import assert from "node:assert/strict";
import { handle, parseCsv, toAmount, toIsoDate } from "../src/api.js";

const KEY = "우리집 가계부";
const DATA_CSV = [
  '"Timestamp","소비 날짜","소비 내역(분류)","Category(small)","사용 카드","액수","일시불,할부 여부"',
  '"4/6/2026 20:47:53","4/6/2026"," 외식비(배달 포함) ","후토마끼, 김밥","그 외","10000","일시불"',
  '"10/10/2026 22:25:02","10/9/2026","외식비(배달 포함)","20000","영준 현대카드","","무이자 할부 3개월"',
  '"10/10/2026 22:26:17","","교통비","택시","그 외","abc","일시불"',
].join("\n");
const TARGET_CSV = '"Category","Monthly_Goal"\n"외식비(배달 포함)","300000"\n"교통비","100000"';

function fakeFetch(sheets = { Data: DATA_CSV, Target: TARGET_CSV }) {
  const calls = [];
  const fn = async (url) => {
    calls.push(url);
    const name = decodeURIComponent(new URL(url).searchParams.get("sheet"));
    if (!(name in sheets)) return new Response("nope", { status: 500 });
    return new Response(sheets[name], { status: 200 });
  };
  fn.calls = calls;
  return fn;
}
function fakeCache() {
  const store = new Map();
  return {
    store,
    match: async (url) => store.get(String(url))?.clone(),
    put: async (url, res) => void store.set(String(url), res),
  };
}
function setup({ env = { LEDGER_PASSWORD: KEY }, fetch = fakeFetch(), cache = fakeCache() } = {}) {
  const call = async (path = "data", key = KEY) => {
    const headers = key === null ? {} : { "x-ledger-key": encodeURIComponent(key) };
    const res = await handle(new Request("https://ledger.test/api/" + path, { headers }), env, { fetch, cache });
    return { status: res.status, data: await res.json() };
  };
  return { call, fetch, cache };
}

test("parseCsv handles quotes, commas, escaped quotes, CRLF", () => {
  assert.deepEqual(parseCsv('"a","b,c"\r\n"d ""e""",\n'), [["a", "b,c"], ['d "e"', ""]]);
});

test("toIsoDate parses M/D/YYYY and rejects junk", () => {
  assert.equal(toIsoDate("4/6/2026"), "2026-04-06");
  assert.equal(toIsoDate("10/10/2026 22:25:02"), "2026-10-10");
  assert.equal(toIsoDate("2/30/2026"), null);
  assert.equal(toIsoDate(""), null);
});

test("toAmount: numbers pass, junk and blanks become 0", () => {
  assert.equal(toAmount("73000"), 73000);
  assert.equal(toAmount(""), 0);
  assert.equal(toAmount("abc"), 0);
});

test("rejects missing or wrong password, 500 when not configured", async () => {
  assert.equal((await setup().call("data", null)).status, 401);
  assert.equal((await setup().call("data", "틀림")).status, 401);
  assert.equal((await setup({ env: {} }).call()).status, 500);
});

test("unknown path is 404", async () => {
  assert.equal((await setup().call("other")).status, 404);
});

test("returns cleaned rows and targets", async () => {
  const { status, data } = await setup().call();
  assert.equal(status, 200);
  assert.deepEqual(data.targets, [
    { category: "외식비(배달 포함)", goal: 300000 },
    { category: "교통비", goal: 100000 },
  ]);
  assert.deepEqual(data.rows[0], {
    timestamp: "4/6/2026 20:47:53", date: "2026-04-06", category: "외식비(배달 포함)",
    small: "후토마끼, 김밥", card: "그 외", amount: 10000, payType: "일시불",
  });
  assert.equal(data.rows[1].amount, 0);
  assert.equal(data.rows[2].date, null);
  assert.equal(data.rows[2].amount, 0);
  assert.match(data.formUrl, /^https:\/\/docs\.google\.com\/forms\//);
  assert.match(data.sheetUrl, /\/edit$/);
  assert.equal(typeof data.fetchedAt, "number");
});

test("second call is served from cache; fresh=1 bypasses it", async () => {
  const s = setup();
  await s.call();
  await s.call();
  assert.equal(s.fetch.calls.length, 2);
  await s.call("data?fresh=1");
  assert.equal(s.fetch.calls.length, 4);
});

test("google failure or unexpected sheet is 502", async () => {
  assert.equal((await setup({ fetch: fakeFetch({ Target: TARGET_CSV }) }).call()).status, 502);
  const html = fakeFetch({ Data: "<html>login</html>", Target: TARGET_CSV });
  assert.equal((await setup({ fetch: html }).call()).status, 502);
});
