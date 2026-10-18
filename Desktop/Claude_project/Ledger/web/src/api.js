// /api/data 처리. env.LEDGER_PASSWORD: 가계부 비밀번호(Cloudflare secret)
// 공개 구글 시트를 gviz CSV로 읽어 JSON으로 준다. 시트·폼 주소는 서버에만 둔다.
const SHEET_ID = "19wGTMH2bt6SZPQ5tbbwcOPVoCZYti1QTc7uYsPjty2w";
const FORM_URL = "https://docs.google.com/forms/d/e/1FAIpQLScygQkv9LyeZmUMSE3kKdW1Nba2GvZ3UM3QlxKaHnO-wc8NFw/viewform?embedded=true";
const SHEET_URL = `https://docs.google.com/spreadsheets/d/${SHEET_ID}/edit`;
const CACHE_SECONDS = 60;
const csvUrl = (name) => `https://docs.google.com/spreadsheets/d/${SHEET_ID}/gviz/tq?tqx=out:csv&sheet=${encodeURIComponent(name)}`;

class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}

const json = (data, status = 200) =>
  new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });

async function sameSecret(a, b) {
  const digest = async (s) => new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s)));
  const [x, y] = await Promise.all([digest(a), digest(b)]);
  let diff = 0;
  for (let i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
  return diff === 0;
}

// ── CSV ───────────────────────────────────────────────
export function parseCsv(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c !== '"') field += c;
      else if (text[i + 1] === '"') { field += '"'; i++; }
      else quoted = false;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  return rows;
}

function records(text, required) {
  const [header = [], ...rows] = parseCsv(text);
  const names = header.map((h) => h.trim());
  if (!required.every((c) => names.includes(c))) throw new HttpError(502, "unexpected sheet format");
  return rows
    .filter((r) => r.some((v) => v.trim() !== ""))
    .map((r) => Object.fromEntries(names.map((n, i) => [n, r[i] ?? ""])));
}

// 시트 날짜는 M/D/YYYY(구글 폼 기본). 해석 못 하면 null — pandas errors="coerce"와 같다.
export function toIsoDate(s) {
  const m = /^\s*(\d{1,2})\/(\d{1,2})\/(\d{4})(\s|$)/.exec(s);
  if (!m) return null;
  const [y, mo, d] = [Number(m[3]), Number(m[1]), Number(m[2])];
  const dt = new Date(Date.UTC(y, mo - 1, d));
  if (dt.getUTCMonth() !== mo - 1 || dt.getUTCDate() !== d) return null;
  return dt.toISOString().slice(0, 10);
}

// 숫자가 아니면 0 — pandas to_numeric(errors="coerce").fillna(0)과 같다.
export function toAmount(s) {
  const t = String(s).trim();
  const n = t === "" ? 0 : Number(t);
  return Number.isFinite(n) ? n : 0;
}

// ── 시트 읽기(60초 캐시) ───────────────────────────────
async function readSheet(name, { fetch, cache, fresh }) {
  const url = csvUrl(name);
  if (!fresh && cache) {
    const hit = await cache.match(url);
    if (hit) return { text: await hit.text(), fetchedAt: Number(hit.headers.get("x-fetched-at")) };
  }
  let res;
  try {
    res = await fetch(url);
  } catch {
    throw new HttpError(502, "sheet fetch failed");
  }
  if (!res.ok) throw new HttpError(502, "sheet fetch failed");
  const text = await res.text();
  const fetchedAt = Date.now();
  if (cache) {
    const headers = { "cache-control": `max-age=${CACHE_SECONDS}`, "x-fetched-at": String(fetchedAt) };
    await cache.put(url, new Response(text, { headers }));
  }
  return { text, fetchedAt };
}

export async function handle(request, env, deps = {}) {
  const fetch = deps.fetch ?? globalThis.fetch;
  const cache = deps.cache === undefined ? globalThis.caches?.default : deps.cache;
  try {
    if (!env.LEDGER_PASSWORD) return json({ error: "server not configured" }, 500);
    const key = request.headers.get("x-ledger-key") ?? "";
    if (!(await sameSecret(key, encodeURIComponent(env.LEDGER_PASSWORD)))) return json({ error: "unauthorized" }, 401);

    const url = new URL(request.url);
    if (request.method !== "GET" || url.pathname.replace(/\/+$/, "") !== "/api/data") return json({ error: "not found" }, 404);

    const opts = { fetch, cache, fresh: url.searchParams.get("fresh") === "1" };
    const [data, target] = await Promise.all([readSheet("Data", opts), readSheet("Target", opts)]);
    const targets = records(target.text, ["Category", "Monthly_Goal"]).map((r) => ({
      category: r.Category.trim(),
      goal: toAmount(r.Monthly_Goal),
    }));
    const rows = records(data.text, ["소비 날짜", "소비 내역(분류)", "액수"]).map((r) => ({
      timestamp: r["Timestamp"] ?? "",
      date: toIsoDate(r["소비 날짜"]),
      category: r["소비 내역(분류)"].trim(),
      small: r["Category(small)"] ?? "",
      card: r["사용 카드"] ?? "",
      amount: toAmount(r["액수"]),
      payType: r["일시불,할부 여부"] ?? "",
    }));
    return json({ fetchedAt: Math.min(data.fetchedAt, target.fetchedAt), formUrl: FORM_URL, sheetUrl: SHEET_URL, targets, rows });
  } catch (e) {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    console.error(e);
    return json({ error: "server error" }, 500);
  }
}
