"use strict";
// Chạy được trên cả Chrome (service worker) và Firefox (event page).
const api = globalThis.browser ?? globalThis.chrome;

const ERP = "https://erp.usth.edu.vn";
const API_URL = ERP + "/student-services/api/v2/timetables/query-student-timetable-in-range";
const SEM_URL = ERP + "/student-services/api/v1/semesters/current";
const GCAL = "https://www.googleapis.com/calendar/v3/calendars";
const SCOPE = "https://www.googleapis.com/auth/calendar.events";
const SYNC_TAG = "[Auto-Synced-ERP]";
const TZ = "Asia/Ho_Chi_Minh";

const APP_KEY = "304c7f6dff373663d32879ac1c1f1318";
const IV_HEX = "21a851e40e72ed93f3a5af3bc92a6bd8"; // = md5("069635c0806598e069583aee5440e448")

// Client ID của bạn (người phát triển), tạo MỘT lần trên Google Cloud. Không phải bí mật, dán thẳng vào đây
// để người dùng khác không phải tự tạo credentials. Họ chỉ cần bấm "Cho phép" khi đăng nhập Google.
const DEFAULT_CLIENT_ID = "598783208697-lq0e06t19lu8594h9thutnhhuumhpto8.apps.googleusercontent.com"; 

const DAY_MS = 86400000;
const VN_MS = 7 * 3600000; // Việt Nam UTC+7, không có giờ mùa hè

const DEFAULTS = { pastWeeks: 0, futureWeeks: 2, calendarId: "primary", clientId: "", autoEnabled: true, autoDays: 2 };

class SessionExpiredError extends Error {}
class AuthRequiredError extends Error {}

// ---------------------------------------------------------------------------
// Mã hóa AES-CBC + checksum (port từ scraper2.py)
// ---------------------------------------------------------------------------
const enc = new TextEncoder();
const dec = new TextDecoder();
const toHex = (buf) => [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
const fromHex = (s) => Uint8Array.from(s.match(/../g), (h) => parseInt(h, 16));
const toB64 = (u8) => btoa(String.fromCharCode(...u8)); // chỉ dùng cho payload nhỏ gửi đi
const fromB64 = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

let _aesKey;
async function aesKey() {
  if (!_aesKey) {
    const k = await crypto.subtle.digest("SHA-256", enc.encode(APP_KEY));
    _aesKey = await crypto.subtle.importKey("raw", k, { name: "AES-CBC" }, false, ["encrypt", "decrypt"]);
  }
  return _aesKey;
}

async function encryptPayload(obj) {
  const ct = await crypto.subtle.encrypt({ name: "AES-CBC", iv: fromHex(IV_HEX) }, await aesKey(), enc.encode(JSON.stringify(obj)));
  return toB64(new Uint8Array(ct));
}

async function decryptPayload(b64) {
  const pt = await crypto.subtle.decrypt({ name: "AES-CBC", iv: fromHex(IV_HEX) }, await aesKey(), fromB64(b64));
  return JSON.parse(dec.decode(pt));
}

async function checksum(body) {
  const o = {};
  for (const k of Object.keys(body).sort()) {
    const v = body[k];
    if (v !== null && v !== undefined && typeof v !== "object") o[k] = v;
  }
  return toHex(await crypto.subtle.digest("SHA-256", enc.encode(JSON.stringify(o))));
}

// ---------------------------------------------------------------------------
// Parser (port từ timetable_parser.py) — ngày được biểu diễn bằng "số ngày kể từ 1970-01-01 theo giờ VN"
// ---------------------------------------------------------------------------
const PERIOD_START = { 1: "07:30", 2: "08:25", 3: "09:25", 4: "10:25", 5: "11:20", 6: "13:00", 7: "13:55", 8: "14:55", 9: "15:50", 10: "16:50" };
const PERIOD_END = { 1: "08:20", 2: "09:15", 3: "10:15", 4: "11:15", 5: "12:10", 6: "13:50", 7: "14:45", 8: "15:45", 9: "16:40", 10: "17:40" };
const DAY_OFFSET = { 1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6 };

const msToDay = (ms) => Math.floor((ms + VN_MS) / DAY_MS);
const dayToIso = (n) => new Date(n * DAY_MS).toISOString().slice(0, 10);
const weekday = (n) => (((n + 3) % 7) + 7) % 7; // Thứ Hai = 0
const vnToday = () => msToDay(Date.now());

function parseWeeks(cal) {
  const weeks = Array.isArray(cal.weeks) ? [...cal.weeks] : [];
  if (!weeks.length && cal.week) {
    for (let part of String(cal.week).split(",")) {
      part = part.trim();
      if (!part) continue;
      if (part.includes("-")) {
        const i = part.indexOf("-");
        const a = part.slice(0, i).trim(), b = part.slice(i + 1).trim();
        if (/^\d+$/.test(a) && /^\d+$/.test(b)) for (let w = +a; w <= +b; w++) weeks.push(w);
      } else if (/^\d+$/.test(part)) weeks.push(+part);
    }
  }
  return weeks;
}

function teacherFullNames(...objs) {
  const names = [];
  for (const o of objs) {
    for (const t of o._teachers || []) {
      const n = t && typeof t === "object" ? t.fullName : null;
      if (n && !names.includes(n)) names.push(n);
    }
  }
  return names.join(", ");
}

function extractSessions(payload, fromMs, toMs) {
  let items, semStart = 0, semWeek = 0;
  if (payload && !Array.isArray(payload) && typeof payload === "object") {
    items = payload.items || payload.data || [];
    semStart = payload.startSemesterTime || 0;
    semWeek = payload.startSemesterWeek || 0;
  } else items = payload || [];

  const fromD = msToDay(fromMs), toD = msToDay(toMs); // toD: loại trừ
  const sessions = [], seen = new Set();

  for (const it of items) {
    let cals = it._calendars || it.calendars, course;
    if (cals == null) { course = {}; cals = [it]; } else course = it;

    for (const cal of cals) {
      const name = course.courseName || course.name || cal.courseName || cal.name || "Chưa rõ môn";
      const tn = cal.teacherNames || [];
      const teacher = tn.length ? tn.join(", ") : (teacherFullNames(cal, course) || course.teacherName || cal.teacherName || "");
      const subject = teacher ? `${name} (${teacher})` : name;
      const room = cal.place || "Chưa rõ phòng";

      const pFrom = cal.from, pTo = cal.to;
      if (!(pFrom in PERIOD_START) || !(pTo in PERIOD_END)) continue;

      const weeks = parseWeeks(cal);
      const date = cal.date;
      const start = semStart || cal._startSemesterDate || 0;
      const wk0 = semWeek || cal._startSemesterWeek || 1;

      let days = [];
      if ((date == null || date < 0 || weeks.length > 1) && start) {
        const off = DAY_OFFSET[cal.day];
        if (off === undefined) continue;
        const base = msToDay(start);
        const monday0 = base - weekday(base);
        days = weeks.map((w) => monday0 + (w - wk0) * 7 + off);
      } else if (date && date > 0) days = [msToDay(date)];

      for (const d of days) {
        if (!(fromD <= d && d < toD)) continue;
        const key = `${subject}|${d}|${pFrom}|${pTo}`;
        if (seen.has(key)) continue;
        seen.add(key);
        sessions.push({
          subject, room,
          start_time: `${dayToIso(d)}T${PERIOD_START[pFrom]}:00+07:00`,
          end_time: `${dayToIso(d)}T${PERIOD_END[pTo]}:00+07:00`,
        });
      }
    }
  }
  sessions.sort((a, b) => (a.start_time < b.start_time ? -1 : a.start_time > b.start_time ? 1 : 0));
  return sessions;
}

// ---------------------------------------------------------------------------
// Lấy dữ liệu từ ERP (dùng cookie đăng nhập sẵn có của trình duyệt)
// ---------------------------------------------------------------------------
async function fetchTimetable(fromMs, toMs) {
  let semester = null;
  const sr = await fetch(SEM_URL, { credentials: "include", headers: { Accept: "application/json" } });
  if (sr.status === 401 || sr.status === 403) throw new SessionExpiredError(`HTTP ${sr.status}`);
  if (sr.ok) {
    const sd = await sr.json();
    if (sd && typeof sd === "object") semester = sd.semester || (sd.data || {}).semester || null;
  }

  const body = { fromTime: fromMs, toTime: toMs };
  if (semester) body.semester = semester;

  const resp = await fetch(API_URL, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json", "x-check-sum": await checksum(body) },
    body: JSON.stringify({ payload: await encryptPayload(body) }),
  });
  if (!resp.ok) {
    const text = (await resp.text()).slice(0, 300);
    if (resp.status === 401 || resp.status === 403) throw new SessionExpiredError(`HTTP ${resp.status}: ${text}`);
    throw new Error(`ERP trả về HTTP ${resp.status}: ${text}`);
  }
  const raw = await resp.json();
  if (!raw || typeof raw !== "object" || !raw.payload) throw new SessionExpiredError("Không có 'payload' trong phản hồi của ERP.");
  return extractSessions(await decryptPayload(raw.payload), fromMs, toMs);
}

// Một số máy chủ kiểm tra Origin/Referer; đặt lại cho request của extension tới API ERP (vô hại nếu không cần).
async function setupHeaderRule() {
  try {
    await api.declarativeNetRequest.updateSessionRules({
      removeRuleIds: [1],
      addRules: [{
        id: 1, priority: 1,
        action: {
          type: "modifyHeaders",
          requestHeaders: [
            { header: "origin", operation: "set", value: ERP },
            { header: "referer", operation: "set", value: ERP + "/students/learn/timetable" },
          ],
        },
        condition: { urlFilter: "||erp.usth.edu.vn/student-services/api/", resourceTypes: ["xmlhttprequest"] },
      }],
    });
  } catch (e) {
    console.warn("Không đặt được rule header:", e);
  }
}

// ---------------------------------------------------------------------------
// Google OAuth (launchWebAuthFlow — dùng được trên cả Chrome và Firefox)
// ---------------------------------------------------------------------------
async function getToken(interactive) {
  const { gToken } = await api.storage.local.get("gToken");
  if (gToken && gToken.exp > Date.now() + 60000) return gToken.token;

  const s = await getSettings();
  const clientId = s.clientId || DEFAULT_CLIENT_ID;
  if (!clientId) throw new AuthRequiredError("Extension chưa có Google Client ID (xem hướng dẫn cho người phát triển).");

  const params = new URLSearchParams({
    client_id: clientId,
    response_type: "token",
    redirect_uri: api.identity.getRedirectURL(),
    scope: SCOPE,
  });
  if (!interactive) params.set("prompt", "none");

  let redirected;
  try {
    redirected = await api.identity.launchWebAuthFlow({ url: "https://accounts.google.com/o/oauth2/v2/auth?" + params, interactive });
  } catch (e) {
    throw new AuthRequiredError("Cần đăng nhập Google: " + (e.message || e));
  }
  const frag = new URLSearchParams(new URL(redirected).hash.slice(1));
  if (frag.get("error")) throw new AuthRequiredError("Google từ chối: " + frag.get("error"));
  const token = frag.get("access_token");
  if (!token) throw new AuthRequiredError("Không nhận được access_token từ Google.");
  await api.storage.local.set({ gToken: { token, exp: Date.now() + Number(frag.get("expires_in") || 3600) * 1000 } });
  return token;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function gfetch(url, opts = {}, interactive = true, attempt = 0) {
  const token = await getToken(interactive);
  const r = await fetch(url, { ...opts, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", ...(opts.headers || {}) } });
  if (r.status === 401 && attempt < 2) {
    await api.storage.local.remove("gToken");
    return gfetch(url, opts, interactive, attempt + 1);
  }
  const retriable = r.status === 429 || r.status >= 500 || (r.status === 403 && /rateLimit|quota/i.test(await r.clone().text()));
  if (retriable && attempt < 4) {
    await sleep(500 * 2 ** attempt);
    return gfetch(url, opts, interactive, attempt + 1);
  }
  if (!r.ok && !(opts.method === "DELETE" && (r.status === 404 || r.status === 410))) {
    throw new Error(`Google Calendar API ${r.status}: ${(await r.text()).slice(0, 200)}`);
  }
  return r;
}

async function pool(items, n, fn) {
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(n, items.length) }, async () => {
    while (i < items.length) await fn(items[i++]);
  }));
}

async function syncToGoogleCalendar(sessions, timeMinIso, timeMaxIso, calendarId, interactive) {
  const cal = encodeURIComponent(calendarId || "primary");
  await log("Đang dọn dẹp lịch cũ trong vùng thời gian chỉ định...");

  const old = [];
  let pageToken;
  do {
    const u = new URL(`${GCAL}/${cal}/events`);
    u.search = new URLSearchParams({ timeMin: timeMinIso, timeMax: timeMaxIso, q: SYNC_TAG, singleEvents: "true", maxResults: "2500", ...(pageToken ? { pageToken } : {}) });
    const j = await (await gfetch(u.toString(), {}, interactive)).json();
    old.push(...(j.items || []));
    pageToken = j.nextPageToken;
  } while (pageToken);

  await pool(old, 4, (ev) => gfetch(`${GCAL}/${cal}/events/${encodeURIComponent(ev.id)}`, { method: "DELETE" }, interactive));
  await log(`Đã xóa ${old.length} sự kiện cũ.`);

  await log("Đang đẩy lịch lên Google Calendar...");
  let added = 0;
  await pool(sessions, 4, async (s) => {
    await gfetch(`${GCAL}/${cal}/events`, {
      method: "POST",
      body: JSON.stringify({
        summary: s.subject,
        location: s.room,
        description: `${SYNC_TAG} Lịch học được tự động đồng bộ từ ERP.`,
        start: { dateTime: s.start_time, timeZone: TZ },
        end: { dateTime: s.end_time, timeZone: TZ },
      }),
    }, interactive);
    added++;
  });
  await log(`Hoàn tất: cập nhật thành công ${added} sự kiện mới.`);
}

// ---------------------------------------------------------------------------
// Điều phối đồng bộ
// ---------------------------------------------------------------------------
async function getSettings() {
  const { settings } = await api.storage.local.get("settings");
  return { ...DEFAULTS, ...(settings || {}) };
}

let state = { running: false, ok: null, log: [] };
const hhmmss = () => new Date().toTimeString().slice(0, 8);
async function saveState() { await api.storage.local.set({ syncState: state }); }
async function log(msg) {
  state.log.push(`${hhmmss()}  ${msg}`);
  if (state.log.length > 100) state.log.shift();
  await saveState();
}

function weekWindow(past, future) {
  const today = vnToday();
  const monday = today - weekday(today);
  const startDay = monday - past * 7, endDay = monday + (future + 1) * 7;
  return {
    startMs: startDay * DAY_MS - VN_MS,
    endMs: endDay * DAY_MS - VN_MS,
    minIso: dayToIso(startDay) + "T00:00:00+07:00",
    maxIso: dayToIso(endDay) + "T00:00:00+07:00",
  };
}

const action = () => api.action || api.browserAction;
const setBadge = (text) => { try { action().setBadgeText({ text }); action().setBadgeBackgroundColor({ color: "#d93025" }); } catch (_) {} };

// Giữ worker sống trong lúc đồng bộ (Chrome tắt service worker sau ~30s không hoạt động)
function keepAlive() {
  const t = setInterval(() => { try { api.runtime.getPlatformInfo(); } catch (_) {} }, 20000);
  return () => clearInterval(t);
}

async function runSync({ interactive = true } = {}) {
  if (state.running) return;
  state = { running: true, ok: null, log: [] };
  await saveState();
  const stop = keepAlive();
  try {
    const s = await getSettings();
    const w = weekWindow(+s.pastWeeks || 0, +s.futureWeeks || 0);

    await log("Đang lấy thời khóa biểu từ ERP...");
    const sessions = await fetchTimetable(w.startMs, w.endMs);
    await log(`Đã giải mã được ${sessions.length} buổi học từ ERP.`);

    if (!sessions.length) {
      await log("Không có buổi học nào trong khoảng thời gian này.");
    } else {
      await syncToGoogleCalendar(sessions, w.minIso, w.maxIso, s.calendarId, interactive);
    }
    await api.storage.local.set({ lastSyncDay: vnToday(), lastSyncAt: new Date().toISOString() });
    state.ok = true;
    setBadge("");
  } catch (e) {
    state.ok = false;
    if (e instanceof SessionExpiredError) await log("LỖI: Phiên ERP hết hạn. Hãy mở erp.usth.edu.vn và đăng nhập lại. (" + e.message + ")");
    else if (e instanceof AuthRequiredError) await log("LỖI: " + e.message);
    else await log("LỖI HỆ THỐNG: " + (e.message || e));
    if (e instanceof SessionExpiredError || e instanceof AuthRequiredError) setBadge("!");
  } finally {
    stop();
    state.running = false;
    await saveState();
  }
}

async function waitOnline(maxMs) {
  const deadline = Date.now() + maxMs;
  for (;;) {
    try { await fetch(ERP + "/", { method: "HEAD", credentials: "omit", cache: "no-store" }); return true; }
    catch (_) { if (Date.now() > deadline) return false; await sleep(5000); }
  }
}

// Lần mở trình duyệt đầu tiên mỗi N ngày
async function autoSync() {
  const s = await getSettings();
  if (!s.autoEnabled) return;
  const { lastSyncDay } = await api.storage.local.get("lastSyncDay");
  if (lastSyncDay != null && vnToday() - lastSyncDay < (+s.autoDays || 2)) return;
  const stop = keepAlive();
  try {
    if (!(await waitOnline(180000))) return;
  } finally { stop(); }
  await runSync({ interactive: false });
}

// ---------------------------------------------------------------------------
// Đăng ký sự kiện (phải ở top-level để Chrome/Firefox đánh thức worker đúng cách)
// ---------------------------------------------------------------------------
api.runtime.onStartup.addListener(() => { autoSync(); });
api.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg && msg.type === "sync") { runSync({ interactive: true }); sendResponse({ started: true }); }
});
setupHeaderRule();

if (typeof module !== "undefined") {
  module.exports = { extractSessions, encryptPayload, decryptPayload, checksum, weekWindow, msToDay, dayToIso };
}
