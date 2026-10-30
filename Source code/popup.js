"use strict";
const api = globalThis.browser ?? globalThis.chrome;
const $ = (id) => document.getElementById(id);
const DEFAULTS = { pastWeeks: 0, futureWeeks: 2, calendarId: "", clientId: "", autoEnabled: true, autoDays: 2 };

function collect() {
  return {
    pastWeeks: parseInt($("past").value) || 0,
    futureWeeks: parseInt($("future").value) || 0,
    calendarId: $("cal").value.trim(),
    clientId: $("cid").value.trim(),
    autoEnabled: $("auto").checked,
    autoDays: parseInt($("days").value) || 2,
  };
}

const save = () => api.storage.local.set({ settings: collect() });

function render(st) {
  st = st || {};
  const pre = $("log"), msg = $("st");
  pre.hidden = !(st.log && st.log.length);
  pre.textContent = (st.log || []).join("\n");
  pre.scrollTop = pre.scrollHeight;
  $("sync").disabled = !!st.running;
  if (st.running) { msg.textContent = "Đang xử lý… vui lòng chờ"; msg.className = ""; }
  else if (st.ok === true) { msg.textContent = "Hoàn tất."; msg.className = "ok"; }
  else if (st.ok === false) { msg.textContent = "Có lỗi, xem log bên dưới."; msg.className = "err"; }
  else { msg.textContent = ""; }
}

async function load() {
  const { settings, syncState, lastSyncAt } = await api.storage.local.get(["settings", "syncState", "lastSyncAt"]);
  const s = { ...DEFAULTS, ...(settings || {}) };
  $("past").value = s.pastWeeks;
  $("future").value = s.futureWeeks;
  $("cal").value = s.calendarId;
  $("cid").value = s.clientId;
  $("auto").checked = s.autoEnabled;
  $("days").value = s.autoDays;
  $("redir").value = api.identity.getRedirectURL();
  if (lastSyncAt) $("last").textContent = "Lần đồng bộ thành công gần nhất: " + new Date(lastSyncAt).toLocaleString("vi-VN");
  render(syncState);
  try { (api.action || api.browserAction).setBadgeText({ text: "" }); } catch (_) {}
}

for (const id of ["past", "future", "cal", "cid", "auto", "days"]) $(id).addEventListener("change", save);
$("redir").addEventListener("focus", (e) => e.target.select());

$("sync").addEventListener("click", async () => {
  await save();
  api.runtime.sendMessage({ type: "sync" });
});

api.storage.onChanged.addListener((ch) => {
  if (ch.syncState) render(ch.syncState.newValue);
  if (ch.lastSyncAt) $("last").textContent = "Lần đồng bộ thành công gần nhất: " + new Date(ch.lastSyncAt.newValue).toLocaleString("vi-VN");
});

load();
