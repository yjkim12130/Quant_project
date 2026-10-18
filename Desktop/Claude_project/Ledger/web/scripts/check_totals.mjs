// 실제 시트로 월 합계를 Streamlit 앱 기준값과 대조한다. 사용법: node scripts/check_totals.mjs
import { handle } from "../src/api.js";
import { monthDetail } from "../public/ledger.js";

const EXPECTED = { "2026-04": 10130856, "2026-05": 4178946, "2026-06": 1609026, "2026-07": 2574127 };
const env = { LEDGER_PASSWORD: "check" };
const req = new Request("https://local/api/data", { headers: { "x-ledger-key": "check" } });
const res = await handle(req, env, { fetch, cache: null });
const data = await res.json();
if (!res.ok) throw new Error(JSON.stringify(data));

let failed = 0;
for (const [ym, want] of Object.entries(EXPECTED)) {
  const [y, m] = ym.split("-").map(Number);
  const got = monthDetail(data.rows, y, m).reduce((s, r) => s + r.amount, 0);
  const ok = got === want;
  if (!ok) failed++;
  console.log(`${ym}  ${got.toLocaleString("en-US")}  ${ok ? "OK" : `기대 ${want.toLocaleString("en-US")}`}`);
}
console.log(`rows=${data.rows.length} targets=${data.targets.length}`);
process.exit(failed ? 1 : 0);
