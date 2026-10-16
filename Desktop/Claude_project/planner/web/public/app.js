import { addDays, dailyCounts, stickerKey, streak, summary, weekday, weekStart } from "./stats.js";

const WEEKDAYS = "월화수목금토일";
const KEY_STORE = "familyKey";
const POLL_MS = 30000;
const $app = document.getElementById("app");
const ui = { tab: "today", offline: false, error: "", day: "" };
let data = null;

// ── 유틸 ──────────────────────────────────────────────
const pad = (n) => String(n).padStart(2, "0");
const localToday = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const pct = (r) => `${Math.round(r * 100)}%`;
const md = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;
const daysLabel = (days) => (days.length === 7 ? "매일" : days.map((d) => WEEKDAYS[d]).join("·"));

function readKey() { try { return localStorage.getItem(KEY_STORE); } catch { return null; } }
function writeKey(k) { try { if (k === null) localStorage.removeItem(KEY_STORE); else localStorage.setItem(KEY_STORE, k); } catch { /* 저장 불가 시 메모리에만 */ } }
let familyKey = readKey();

function lock(message = "") {
  familyKey = null;
  writeKey(null);
  data = null;
  ui.error = message;
  render();
}

// ── API ───────────────────────────────────────────────
class Unauthorized extends Error {}

async function api(method, path, body) {
  let res;
  try {
    res = await fetch("/api/" + path, {
      method,
      headers: { "content-type": "application/json", "x-family-key": encodeURIComponent(familyKey ?? "") },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    ui.offline = true;
    throw new Error("offline");
  }
  ui.offline = false;
  if (res.status === 401) throw new Unauthorized();
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(json.error || `HTTP ${res.status}`);
  return json;
}

async function load() {
  try {
    data = await api("GET", "state");
    ui.error = "";
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (!ui.offline) ui.error = "불러오지 못했어요: " + e.message;
  }
  render();
}

async function act(method, path, body) {
  try {
    await api(method, path, body);
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (!ui.offline) ui.error = "저장하지 못했어요: " + e.message;
  }
  await load();
}

async function unlock(key) {
  familyKey = key;
  try {
    data = await api("GET", "state");
    writeKey(key);
    ui.error = "";
  } catch (e) {
    familyKey = null;
    ui.error = e instanceof Unauthorized ? "비밀번호가 맞지 않아요." : ui.offline ? "인터넷 연결이 필요해요." : e.message;
  }
  render();
}

// ── 화면 계산 ─────────────────────────────────────────
function derive() {
  const today = localToday();
  const weekById = new Map(data.weekGoals.map((w) => [w.id, w]));
  const habits = data.habits
    .filter((h) => weekById.has(h.weekGoalId))
    .map((h) => {
      const w = weekById.get(h.weekGoalId);
      return { ...h, weekStart: w.weekStart, weekTitle: w.title, monthGoalId: w.monthGoalId };
    });
  const stickers = new Set(data.stickers.map((s) => stickerKey(s.habitId, s.date)));
  const month = today.slice(0, 7);
  const monthStart = month + "-01";
  const monthEnd = addDays(addDays(monthStart, 32).slice(0, 7) + "-01", -1);
  const weeks = [];
  for (let w = weekStart(monthStart); w <= monthEnd; w = addDays(w, 7)) weeks.push(w);
  return { today, habits, stickers, month, monthStart, monthEnd, weeks };
}

// ── 화면 ──────────────────────────────────────────────
function render() {
  ui.day = localToday();
  if (!familyKey) return renderLock();
  if (!data) {
    $app.innerHTML = `<p class="muted center">${ui.offline ? "인터넷 연결이 필요해요." : esc(ui.error || "불러오는 중…")}</p>`;
    return;
  }
  const ctx = derive();
  const view = { today: viewToday, goals: viewGoals, board: viewBoard }[ui.tab];
  const tabs = [["today", "오늘"], ["goals", "목표 설정"], ["board", "스티커판"]];
  $app.innerHTML = `
    <header><h1>⭐ 칭찬스티커 플래너</h1><button class="link" data-act="logout">잠그기</button></header>
    ${ui.offline ? `<div class="banner warn">인터넷 연결이 필요해요. 연결되면 자동으로 다시 불러옵니다.</div>` : ""}
    ${ui.error ? `<div class="banner err">${esc(ui.error)}</div>` : ""}
    <nav>${tabs.map(([k, l]) => `<button class="tab ${ui.tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`).join("")}</nav>
    <main>${view(ctx)}</main>`;
}

function renderLock() {
  $app.innerHTML = `
    <div class="lock">
      <h1>⭐ 칭찬스티커 플래너</h1>
      <p class="muted">가족 비밀번호를 입력하세요.</p>
      <form data-form="lock"><input type="password" name="key" autocomplete="current-password" aria-label="가족 비밀번호" required><button>열기</button></form>
      ${ui.error ? `<p class="err-text">${esc(ui.error)}</p>` : ""}
    </div>`;
}

function viewToday({ today, habits, stickers, monthStart, monthEnd }) {
  const ws = weekStart(today);
  const wd = weekday(today);
  const stat = (label, start, end) => {
    const r = summary(habits, stickers, start, end, today);
    return `<div class="stat"><div class="label">${label}</div><div class="big">${pct(r.rate)}</div>
      <div class="muted">⭐ ${r.earned}/${r.possible}</div><div class="bar"><i style="width:${pct(r.rate)}"></i></div></div>`;
  };
  const todays = habits.filter((h) => h.weekStart <= today && today < addDays(h.weekStart, 7) && h.days.includes(wd));
  const allDone = todays.length > 0 && todays.every((h) => stickers.has(stickerKey(h.id, today)));
  const item = (h) => {
    const on = stickers.has(stickerKey(h.id, today));
    return `<li><label class="${on ? "done" : ""}">
      <input type="checkbox" data-sticker="${h.id}" ${on ? "checked" : ""} ${ui.offline ? "disabled" : ""}>
      <span class="sticker">${on ? "⭐" : "☆"}</span>
      <span>${esc(h.title)}<small>${esc(h.weekTitle)}</small></span></label></li>`;
  };
  return `
    <section class="stats">
      ${stat("오늘", today, today)}${stat("이번 주", ws, addDays(ws, 6))}${stat("이번 달", monthStart, monthEnd)}
      <div class="stat"><div class="label">연속 달성</div><div class="big">🔥 ${streak(habits, stickers, today)}일</div></div>
    </section>
    <h2>${md(today)} (${WEEKDAYS[wd]}) 할 일</h2>
    ${todays.length
      ? `<ul class="checks">${todays.map(item).join("")}</ul>`
      : `<p class="empty">오늘 할 습관이 없어요. '목표 설정' 탭에서 이번 주 목표와 일일 습관을 추가하세요.</p>`}
    ${allDone ? `<div class="banner ok">오늘 목표를 모두 달성했어요! 정말 잘했어요 👏</div>` : ""}`;
}

function viewGoals({ today, month, weeks }) {
  const dis = ui.offline ? "disabled" : "";
  const dayPicker = [...WEEKDAYS].map((d, i) => `<label class="day"><input type="checkbox" name="days" value="${i}" checked>${d}</label>`).join("");
  const habitRow = (h) => `<li><span>${esc(h.title)} <small>(${daysLabel(h.days)})</small></span>
    <button class="del" data-del="habits/${h.id}" data-confirm="이 습관과 받은 스티커가 지워집니다." ${dis}>삭제</button></li>`;
  const weekBlock = (w) => `
    <div class="week">
      <div class="head"><h4>📅 ${md(w.weekStart)}주 — ${esc(w.title)}</h4>
        <button class="del" data-del="week-goals/${w.id}" data-confirm="주 목표와 그 아래 습관·스티커가 지워집니다." ${dis}>삭제</button></div>
      <ul class="habits">${data.habits.filter((h) => h.weekGoalId === w.id).map(habitRow).join("")}</ul>
      <form data-form="habit" data-week="${w.id}">
        <div class="row"><input name="title" placeholder="일일 습관 (예: 운동 가기)" maxlength="100" aria-label="일일 습관" required><button ${dis}>습관 추가</button></div>
        <div class="days">${dayPicker}</div>
      </form>
    </div>`;
  const monthCard = (m) => `
    <article class="card">
      <div class="head"><h3>🎯 ${esc(m.title)}</h3>
        <button class="del" data-del="month-goals/${m.id}" data-confirm="월 목표와 그 아래 주 목표·습관·스티커가 모두 지워집니다." ${dis}>삭제</button></div>
      ${data.weekGoals.filter((w) => w.monthGoalId === m.id).map(weekBlock).join("")}
      <form data-form="week" data-month="${m.id}" class="row">
        <select name="weekStart" aria-label="주">${weeks.map((w) => `<option value="${w}" ${w === weekStart(today) ? "selected" : ""}>${md(w)}주</option>`).join("")}</select>
        <input name="title" placeholder="주 목표 (예: 운동 3회)" maxlength="100" aria-label="주 목표" required><button ${dis}>주 목표 추가</button>
      </form>
    </article>`;
  return `
    <p class="muted">${month.slice(0, 4)}년 ${Number(month.slice(5))}월 목표</p>
    <form data-form="month" class="row"><input name="title" placeholder="새 월 목표 (예: 체중 2kg 감량)" maxlength="100" aria-label="새 월 목표" required><button ${dis}>월 목표 추가</button></form>
    ${data.monthGoals.filter((m) => m.month === month).map(monthCard).join("")}`;
}

function viewBoard({ today, habits, stickers, month, monthStart, monthEnd, weeks }) {
  const counts = dailyCounts(habits, stickers, monthStart, monthEnd, today);
  const total = summary(habits, stickers, monthStart, monthEnd, today);
  let cells = [...WEEKDAYS].map((d) => `<div class="hd">${d}</div>`).join("") + "<div></div>".repeat(weekday(monthStart));
  for (let d = monthStart; d <= monthEnd; d = addDays(d, 1)) {
    const [e, p] = counts[d] ?? [0, 0];
    cells += `<div class="cell ${p && e === p ? "full" : ""} ${d === today ? "today" : ""}"><b>${Number(d.slice(8))}</b>
      <div>${"⭐".repeat(e)}<span class="empty-star">${"☆".repeat(p - e)}</span></div></div>`;
  }
  const weekRows = weeks.map((w) => ({ w, ...summary(habits, stickers, w, addDays(w, 6), today) })).filter((r) => r.possible);
  const goalRow = (m) => {
    const r = summary(habits.filter((h) => h.monthGoalId === m.id), stickers, monthStart, monthEnd, today);
    return `<div class="goal"><div>🎯 ${esc(m.title)} — ⭐ ${r.earned}/${r.possible}</div><div class="bar"><i style="width:${pct(r.rate)}"></i></div></div>`;
  };
  return `
    <h2>${Number(month.slice(5))}월 스티커판 — ⭐ ${total.earned}장 (${pct(total.rate)})</h2>
    <div class="cal">${cells}</div>
    <h2>주별 달성률</h2>
    ${weekRows.length
      ? weekRows.map((r) => `<div class="hbar"><span>${md(r.w)}주</span><div class="bar"><i style="width:${pct(r.rate)}"></i></div><b>${pct(r.rate)}</b></div>`).join("")
      : `<p class="muted">아직 기록이 없어요.</p>`}
    <h2>월 목표별 달성률</h2>
    ${data.monthGoals.filter((m) => m.month === month).map(goalRow).join("") || `<p class="muted">이번 달 목표가 없어요.</p>`}`;
}

function celebrate() {
  for (let i = 0; i < 14; i++) {
    const s = document.createElement("span");
    s.className = "fly";
    s.textContent = i % 3 ? "⭐" : "🎉";
    s.style.left = Math.random() * 95 + "vw";
    s.style.animationDelay = Math.random() * 0.4 + "s";
    document.body.appendChild(s);
    setTimeout(() => s.remove(), 2400);
  }
}

// ── 이벤트 ────────────────────────────────────────────
$app.addEventListener("click", (e) => {
  const t = e.target.closest("[data-tab],[data-del],[data-act]");
  if (!t) return;
  if (t.dataset.tab) {
    ui.tab = t.dataset.tab;
    render();
  } else if (t.dataset.del) {
    if (confirm(t.dataset.confirm)) act("DELETE", t.dataset.del);
  } else if (t.dataset.act === "logout") {
    if (confirm("이 기기에서 비밀번호를 지우고 잠글까요?")) lock();
  }
});

$app.addEventListener("change", (e) => {
  const cb = e.target.closest("[data-sticker]");
  if (!cb) return;
  if (cb.checked) celebrate();
  act("PUT", "stickers", { habitId: Number(cb.dataset.sticker), date: localToday(), on: cb.checked });
});

$app.addEventListener("submit", (e) => {
  e.preventDefault();
  const f = e.target;
  const fd = new FormData(f);
  const title = String(fd.get("title") ?? "").trim();
  if (f.dataset.form === "lock") return unlock(String(fd.get("key")));
  if (!title) return;
  if (f.dataset.form === "month") act("POST", "month-goals", { month: localToday().slice(0, 7), title });
  if (f.dataset.form === "week") act("POST", "week-goals", { monthGoalId: Number(f.dataset.month), weekStart: fd.get("weekStart"), title });
  if (f.dataset.form === "habit") {
    const days = fd.getAll("days").map(Number);
    if (!days.length) return alert("요일을 하나 이상 골라 주세요.");
    act("POST", "habits", { weekGoalId: Number(f.dataset.week), title, days });
  }
});

// ── 자동 갱신: 30초마다, 화면 복귀·재연결 시. 입력 중이면 건너뜀 ──
function typing() {
  const a = document.activeElement;
  return !!a && ((a.tagName === "INPUT" && a.type !== "checkbox") || a.tagName === "SELECT");
}

async function poll() {
  if (!familyKey || document.hidden || typing()) return;
  const before = JSON.stringify(data);
  const wasOffline = ui.offline;
  try {
    data = await api("GET", "state");
  } catch (e) {
    if (e instanceof Unauthorized) return lock("비밀번호가 바뀌었어요. 다시 입력해 주세요.");
    if (ui.offline !== wasOffline) render();
    return;
  }
  if (JSON.stringify(data) !== before || wasOffline || ui.day !== localToday()) render();
}

setInterval(poll, POLL_MS);
document.addEventListener("visibilitychange", () => { if (!document.hidden) poll(); });
window.addEventListener("online", poll);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
render();
if (familyKey) load();
