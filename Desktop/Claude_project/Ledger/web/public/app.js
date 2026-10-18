import {
  calendarWeeks, categorySummary, dailyTotals, daysInMonth, kstToday, manwon,
  monthDetail, progress, shiftMonth, won, yearOptions,
} from "./ledger.js";

const KEY_STORE = "ledgerKey";
const DATA_STORE = "ledgerData";
const STALE_MS = 60000;
const WEEKDAYS = ["월", "화", "수", "목", "금", "토", "일"];
const $ = (id) => document.getElementById(id);
const ui = { tab: 0, year: null, month: null, state: "loading" }; // state: loading | ok | failed

// ── 유틸 ──────────────────────────────────────────────
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pad = (n) => String(n).padStart(2, "0");
const clock = (ms) => { const d = new Date(ms); return `${pad(d.getHours())}:${pad(d.getMinutes())}`; };
function ago(ms) {
  const min = Math.floor((Date.now() - ms) / 60000);
  if (min < 1) return "방금";
  if (min < 60) return `${min}분 전`;
  if (min < 1440) return `${Math.floor(min / 60)}시간 전`;
  return `${Math.floor(min / 1440)}일 전`;
}

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { if (v === null) localStorage.removeItem(k); else localStorage.setItem(k, v); } catch { /* 저장 불가 시 메모리에만 */ } },
};
let key = store.get(KEY_STORE);
let data = (() => { try { return JSON.parse(store.get(DATA_STORE)); } catch { return null; } })();
let loading = false;

// ── 로그인 ────────────────────────────────────────────
function showLogin(message = "") {
  $("main").hidden = true;
  $("login").hidden = false;
  $("login-error").textContent = message;
  $("password").focus();
}

function lock(message) {
  key = data = null;
  store.set(KEY_STORE, null);
  store.set(DATA_STORE, null);
  showLogin(message);
}

$("login").addEventListener("submit", (e) => {
  e.preventDefault();
  key = $("password").value;
  $("password").value = "";
  store.set(KEY_STORE, key);
  start();
});

// ── 데이터 ────────────────────────────────────────────
async function load(fresh = false) {
  if (loading) return;
  loading = true;
  ui.state = "loading";
  renderStatus();
  try {
    const res = await fetch("/api/data" + (fresh ? "?fresh=1" : ""), {
      headers: { "x-ledger-key": encodeURIComponent(key ?? "") },
      cache: "no-store",
    });
    if (res.status === 401) return lock("비밀번호가 맞지 않아요.");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    data = { ...(await res.json()), receivedAt: Date.now() };
    store.set(DATA_STORE, JSON.stringify(data));
    ui.state = "ok";
    render();
  } catch {
    ui.state = "failed";
  } finally {
    loading = false;
    renderStatus();
  }
}

// ── 화면 ──────────────────────────────────────────────
function renderStatus() {
  const el = $("status");
  el.classList.toggle("stale", ui.state === "failed");
  if (ui.state === "loading") el.textContent = data ? `${ago(data.fetchedAt)} 데이터 · 갱신 중…` : "불러오는 중…";
  else if (ui.state === "ok") el.textContent = `${clock(data.fetchedAt)} 기준 최신`;
  else el.textContent = data ? `${ago(data.fetchedAt)} 데이터 · 최신 아님 (🔄로 다시 시도)` : "불러오지 못했어요. 🔄로 다시 시도해 주세요.";
}

function renderTabs() {
  document.querySelectorAll("[data-tab]").forEach((b) => b.setAttribute("aria-selected", String(Number(b.dataset.tab) === ui.tab)));
  document.querySelectorAll("[data-panel]").forEach((p) => { p.hidden = Number(p.dataset.panel) !== ui.tab; });
}

// 폼은 주소가 바뀔 때만 다시 넣는다 — 데이터 갱신마다 넣으면 입력 중인 내용이 날아간다.
function renderForm() {
  const form = $("form");
  if (data?.formUrl && form.getAttribute("src") !== data.formUrl) form.setAttribute("src", data.formUrl);
}

function renderDashboard() {
  const t = kstToday();
  const ratio = t.day / daysInMonth(t.year, t.month);
  const summary = categorySummary(data.targets, data.rows, t.year, t.month);
  const max = Math.max(1, ...summary.map((s) => s.actual));
  const total = summary.reduce((sum, s) => sum + s.actual, 0);

  const bars = summary.map((s) => `
    <span class="bar-label">${esc(s.category)}</span>
    <div class="bar-track"><div class="bar-fill" style="width:${(s.actual / max) * 100}%"></div></div>
    <span class="bar-value">${won(s.actual)}</span>`).join("");

  const cards = summary.map((s, i) => {
    const p = progress(s.goal, s.actual, ratio);
    return `
    <div class="cat">
      <div class="cat-title"><b>${i + 1}. ${esc(s.category)}</b> <span class="muted">(전체예산: ${won(s.goal)})</span></div>
      <div class="cat-row">
        <div class="track">
          <div class="green" style="width:${p.green}%"></div>
          <div class="red" style="left:${p.green}%;width:${p.red}%"></div>
          ${p.status === "unset" ? "" : `<div class="marker" style="left:${p.marker}%"></div>`}
        </div>
        <div class="badge ${p.status}">
          <span class="b1">누적: ${won(s.actual)}원</span>
          <span class="b2">계획: ${won(p.plan)}원</span>
          <span class="b3">${p.label}<br>(${p.detail})</span>
        </div>
      </div>
    </div>`;
  }).join("");

  $("dashboard").innerHTML = `
    <h2>📊 카테고리별 사용금액</h2>
    <div class="bars">${bars}</div>
    <hr>
    <h2>🎯 오늘(${t.month}/${t.day}) 기준 소비 성적표</h2>
    ${cards}
    <hr>
    <h2>${t.month}월 총 지출: ${won(total)} 원</h2>`;
}

function renderHistory() {
  const t = kstToday();
  if (ui.year === null) [ui.year, ui.month] = [t.year, t.month];
  const { year, month } = ui;
  const detail = monthDetail(data.rows, year, month);
  const daily = dailyTotals(detail);
  const total = detail.reduce((sum, r) => sum + r.amount, 0);

  const years = yearOptions(data.rows, t.year, year)
    .map((y) => `<option value="${y}"${y === year ? " selected" : ""}>${y}년</option>`).join("");
  const months = Array.from({ length: 12 }, (_, i) => i + 1)
    .map((m) => `<option value="${m}"${m === month ? " selected" : ""}>${m}월</option>`).join("");

  const rows = detail.map((r) => `
    <tr><td>${esc(r.timestamp)}</td><td>${r.date}</td><td>${esc(r.category)}</td><td>${esc(r.small)}</td>
    <td>${esc(r.card)}</td><td class="num">${won(r.amount)}</td><td>${esc(r.payType)}</td><td class="num">${won(r.cumulative)}</td></tr>`).join("");
  const table = detail.length
    ? `<div class="table-wrap"><table>
        <thead><tr><th>Timestamp</th><th>소비 날짜</th><th>소비 내역(분류)</th><th>Category(small)</th>
        <th>사용 카드</th><th class="num">액수</th><th>일시불,할부 여부</th><th class="num">누적 총액</th></tr></thead>
        <tbody>${rows}</tbody></table></div>`
    : `<p class="muted">이 달 내역이 없어요.</p>`;

  const isThisMonth = year === t.year && month === t.month;
  const cells = calendarWeeks(year, month).flat().map((day) => {
    if (day === 0) return "<div></div>";
    const amt = daily.get(day) ?? 0;
    const amtHtml = amt > 0 ? `<span class="amt">${manwon(amt)}</span>` : `<span class="none">-</span>`;
    return `<div class="cal-day${isThisMonth && day === t.day ? " today" : ""}"><span class="day">${day}</span>${amtHtml}</div>`;
  }).join("");

  $("history").innerHTML = `
    <div class="month-nav">
      <button type="button" data-shift="-1" aria-label="이전 달">◀</button>
      <select id="sel-year" aria-label="연도">${years}</select>
      <select id="sel-month" aria-label="월">${months}</select>
      <button type="button" data-shift="1" aria-label="다음 달">▶</button>
    </div>
    <h2>📜 ${year}년 ${month}월 소비 상세 내역</h2>
    ${table}
    <h2>💰 ${year}년 ${month}월 총 지출: ${won(total)} 원</h2>
    <hr>
    <h2>🗓️ ${year}년 ${month}월 소비 캘린더</h2>
    <p class="muted">단위: 만원 (예: 9.3만)</p>
    <div class="cal">${WEEKDAYS.map((d) => `<div class="cal-head">${d}</div>`).join("")}${cells}</div>
    <hr>
    <a class="link-btn" href="${esc(data.sheetUrl)}" target="_blank" rel="noopener">🗑️ 구글 시트에서 수정/삭제하기</a>`;
}

function render() {
  renderTabs();
  renderStatus();
  if (!data) {
    $("dashboard").innerHTML = $("history").innerHTML = `<p class="muted">불러오는 중…</p>`;
    return;
  }
  renderForm();
  renderDashboard();
  renderHistory();
}

// ── 이벤트 ────────────────────────────────────────────
document.querySelector(".tabs").addEventListener("click", (e) => {
  const b = e.target.closest("[data-tab]");
  if (!b) return;
  ui.tab = Number(b.dataset.tab);
  renderTabs();
});

$("refresh").addEventListener("click", () => load(true));

$("history").addEventListener("click", (e) => {
  const b = e.target.closest("[data-shift]");
  if (!b) return;
  ({ year: ui.year, month: ui.month } = shiftMonth(ui.year, ui.month, Number(b.dataset.shift)));
  renderHistory();
});

$("history").addEventListener("change", (e) => {
  if (e.target.id === "sel-year") ui.year = Number(e.target.value);
  else if (e.target.id === "sel-month") ui.month = Number(e.target.value);
  else return;
  renderHistory();
});

// 다시 앱으로 돌아왔을 때 오래된 데이터면 새로 받는다(날짜가 바뀌었을 수도 있으니 다시 그린다).
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState !== "visible" || !key || $("main").hidden) return;
  if (data) render();
  if (!data || Date.now() - data.receivedAt > STALE_MS) load();
});

// ── 시작 ──────────────────────────────────────────────
function start() {
  $("login").hidden = true;
  $("main").hidden = false;
  render();
  load();
}

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
if (key) start();
else showLogin();
