// /api/* 처리. env.DB: D1, env.FAMILY_PASSWORD: 가족 비밀번호(Cloudflare secret)
class HttpError extends Error {
  constructor(status, message) {
    super(message);
    this.status = status;
  }
}
const bad = (message) => {
  throw new HttpError(400, message);
};

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

// ── 입력 검증 ─────────────────────────────────────────
function title(v) {
  if (typeof v !== "string" || !v.trim() || v.trim().length > 100) bad("title");
  return v.trim();
}
function id(v) {
  if (!Number.isInteger(v) || v <= 0) bad("id");
  return v;
}
function isoDate(v) {
  const ms = typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) ? Date.parse(v + "T00:00:00Z") : NaN;
  if (Number.isNaN(ms) || new Date(ms).toISOString().slice(0, 10) !== v) bad("date");
  return v;
}
function monday(v) {
  if (new Date(isoDate(v) + "T00:00:00Z").getUTCDay() !== 1) bad("weekStart must be a Monday");
  return v;
}
function month(v) {
  if (typeof v !== "string" || !/^\d{4}-(0[1-9]|1[0-2])$/.test(v)) bad("month");
  return v;
}
function days(v) {
  if (!Array.isArray(v) || !v.length || v.some((d) => !Number.isInteger(d) || d < 0 || d > 6)) bad("days");
  return [...new Set(v)].sort().join("");
}

// ── DB ────────────────────────────────────────────────
async function getState(db) {
  const all = async (sql) => (await db.prepare(sql).all()).results;
  const [m, w, h, s] = await Promise.all([
    all("SELECT * FROM month_goal ORDER BY id"),
    all("SELECT * FROM week_goal ORDER BY week_start, id"),
    all("SELECT * FROM habit ORDER BY id"),
    all("SELECT * FROM sticker ORDER BY date, habit_id"),
  ]);
  return {
    monthGoals: m.map((r) => ({ id: r.id, month: r.month, title: r.title })),
    weekGoals: w.map((r) => ({ id: r.id, monthGoalId: r.month_goal_id, weekStart: r.week_start, title: r.title })),
    habits: h.map((r) => ({ id: r.id, weekGoalId: r.week_goal_id, title: r.title, days: [...r.days].map(Number) })),
    stickers: s.map((r) => ({ habitId: r.habit_id, date: r.date })),
  };
}

async function run(db, sql, ...args) {
  try {
    return await db.prepare(sql).bind(...args).run();
  } catch (e) {
    if (/FOREIGN KEY/i.test(String(e?.message))) bad("parent not found");
    throw e;
  }
}

const TABLES = { "month-goals": "month_goal", "week-goals": "week_goal", habits: "habit" };

export async function handle(request, env) {
  try {
    if (!env.FAMILY_PASSWORD) return json({ error: "server not configured" }, 500);
    const key = request.headers.get("x-family-key") ?? "";
    if (!(await sameSecret(key, encodeURIComponent(env.FAMILY_PASSWORD)))) return json({ error: "unauthorized" }, 401);

    const db = env.DB;
    const [res, rid, extra] = new URL(request.url).pathname.replace(/^\/api\/?/, "").split("/").filter(Boolean);
    const method = request.method;
    let body = null;
    if (method === "POST" || method === "PUT") {
      body = await request.json().catch(() => null);
      if (body === null || typeof body !== "object" || Array.isArray(body)) bad("invalid json body");
    }
    if (extra !== undefined) return json({ error: "not found" }, 404);

    if (method === "GET" && res === "state" && !rid) return json(await getState(db));

    if (method === "POST" && !rid) {
      const insert = async (sql, ...args) => json({ id: (await run(db, sql, ...args)).meta.last_row_id }, 201);
      if (res === "month-goals")
        return await insert("INSERT INTO month_goal (month, title) VALUES (?, ?)", month(body.month), title(body.title));
      if (res === "week-goals")
        return await insert("INSERT INTO week_goal (month_goal_id, week_start, title) VALUES (?, ?, ?)",
          id(body.monthGoalId), monday(body.weekStart), title(body.title));
      if (res === "habits")
        return await insert("INSERT INTO habit (week_goal_id, title, days) VALUES (?, ?, ?)",
          id(body.weekGoalId), title(body.title), days(body.days));
    }

    if (method === "DELETE" && TABLES[res] && rid) {
      await run(db, `DELETE FROM ${TABLES[res]} WHERE id = ?`, id(Number(rid)));
      return json({ ok: true });
    }

    if (method === "PUT" && res === "stickers" && !rid) {
      const habitId = id(body.habitId);
      const date = isoDate(body.date);
      if (typeof body.on !== "boolean") bad("on");
      if (body.on) await run(db, "INSERT OR IGNORE INTO sticker (habit_id, date) VALUES (?, ?)", habitId, date);
      else await run(db, "DELETE FROM sticker WHERE habit_id = ? AND date = ?", habitId, date);
      return json({ ok: true });
    }

    return json({ error: "not found" }, 404);
  } catch (e) {
    if (e instanceof HttpError) return json({ error: e.message }, e.status);
    console.error(e);
    return json({ error: "server error" }, 500);
  }
}
