#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import logging
import os
import queue
import threading
import time
import webbrowser
from datetime import datetime, timedelta

from flask import Flask, Response, abort, jsonify, request

from login_once import manual_login_and_save
from scraper2 import get_schedule as get_schedule_api, SessionExpiredError, PROFILE_DIR

# Import thêm logic scraper HTML nếu có dùng
try:
    from scraper import get_schedule as get_schedule_html
    HAS_HTML_SCRAPER = True
except ImportError:
    HAS_HTML_SCRAPER = False

PORT = int(os.environ.get("PORT", "5077"))
SHUTDOWN_GRACE = 5      # giây chờ sau khi tab đóng (để F5 / reload không làm tắt app)
STARTUP_GRACE = 60      # giây chờ tab đầu tiên kết nối, nếu không có thì tự tắt

app = Flask(__name__)
sync_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Phát hiện tab đóng bằng kết nối SSE (/api/alive)
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
_streams = 0            # số tab đang giữ kết nối /api/alive
_exit_timer = None


def _schedule_exit_check(delay):
    """Hẹn giờ kiểm tra xem có nên tắt app không (huỷ hẹn giờ cũ nếu có)."""
    global _exit_timer
    with _state_lock:
        if _exit_timer:
            _exit_timer.cancel()
        _exit_timer = threading.Timer(delay, _maybe_exit)
        _exit_timer.daemon = True
        _exit_timer.start()


def _maybe_exit():
    with _state_lock:
        if _streams > 0:
            return                      # có tab kết nối lại rồi, không tắt
    if sync_lock.locked():              # đang đồng bộ -> không tắt giữa chừng
        _schedule_exit_check(SHUTDOWN_GRACE)
        return
    print("Trình duyệt đã đóng, tự động tắt ứng dụng...")
    os._exit(0)


@app.get("/api/alive")
def alive():
    global _streams, _exit_timer

    def gen():
        global _streams
        try:
            while True:
                yield ": keepalive\n\n"
                time.sleep(2)           # ghi thất bại = trình duyệt đã ngắt kết nối
        finally:
            with _state_lock:
                _streams -= 1
                remaining = _streams
            if remaining == 0:
                _schedule_exit_check(SHUTDOWN_GRACE)

    with _state_lock:
        _streams += 1
        if _exit_timer:                 # tab (mới) đã kết nối -> huỷ lệnh tắt
            _exit_timer.cancel()
            _exit_timer = None

    resp = Response(gen(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    return resp


# ---------------------------------------------------------------------------
@app.before_request
def guard():
    if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
        abort(403)
    if request.method == "POST" and not request.is_json:
        abort(415)


def _window(past: int, future: int):
    from timetable_parser import VN
    now = datetime.now(VN)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - timedelta(weeks=past), monday + timedelta(weeks=future + 1)


def run_async(coro):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@app.get("/")
def index():
    return PAGE


@app.get("/api/status")
def status():
    logged_in = os.path.exists(PROFILE_DIR) and len(os.listdir(PROFILE_DIR)) > 0
    return jsonify(logged_in=logged_in)


@app.post("/api/login")
def login():
    try:
        success = run_async(manual_login_and_save(PROFILE_DIR))
        if success:
            return jsonify(ok=True)
        return jsonify(ok=False, error="Đăng nhập không thành công hoặc hết thời gian chờ."), 400
    except Exception as e:
        return jsonify(ok=False, error=f"Lỗi khởi chạy trình duyệt: {e}"), 502


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lines = []

    def emit(self, record):
        self.lines.append(record.getMessage())


@app.post("/api/sync")
def sync():
    d = request.get_json(silent=True) or {}
    calendar_id = str(d.get("calendar_id", "")).strip() or "primary"

    if not sync_lock.acquire(blocking=False):
        return "Đang có một tiến trình khác chạy.\n", 409

    log_queue = queue.Queue()

    class QueueHandler(logging.Handler):
        def emit(self, record):
            log_queue.put(record.getMessage() + "\n")

    def run_sync():
        glog = logging.getLogger("usth-sync.gcal")
        glog.setLevel(logging.INFO)
        handler = QueueHandler()
        glog.addHandler(handler)
        try:
            from gcal_manager import sync_to_google_calendar
            past_w = int(d.get("past_weeks", 0))
            future_w = int(d.get("future_weeks", 2))
            start, end = _window(past_w, future_w)

            sessions = run_async(get_schedule_api(int(start.timestamp() * 1000), int(end.timestamp() * 1000), headless=True))

            if not sessions:
                log_queue.put("Không có buổi học nào trong khoảng thời gian này.\n")
            else:
                sync_to_google_calendar(sessions, start.isoformat(), end.isoformat(), calendar_id=calendar_id)
        except SessionExpiredError:
            log_queue.put("LỖI: Phiên đăng nhập hết hạn. Hãy đăng nhập lại.\n")
        except Exception as e:
            log_queue.put(f"LỖI HỆ THỐNG: {e}\n")
        finally:
            glog.removeHandler(handler)
            sync_lock.release()
            log_queue.put(None)  # Tín hiệu kết thúc stream

    # Chạy tiến trình đồng bộ ở một luồng (thread) riêng để không chặn response
    threading.Thread(target=run_sync).start()

    def stream():
        while True:
            msg = log_queue.get()
            if msg is None:
                break
            yield msg

    return app.response_class(stream(), mimetype='text/plain')


@app.post("/api/sync_html")
def sync_html():
    if not HAS_HTML_SCRAPER:
        return jsonify(ok=False, error="File scraper.py không tồn tại hoặc bị lỗi.")

    d = request.get_json(silent=True) or {}
    calendar_id = str(d.get("calendar_id", "")).strip() or "primary"
    if not sync_lock.acquire(blocking=False):
        return jsonify(ok=False, error="Đang có một tiến trình khác chạy."), 409

    handler = _ListHandler()
    glog = logging.getLogger("usth-sync.gcal")
    glog.setLevel(logging.INFO)
    glog.addHandler(handler)

    try:
        from gcal_manager import sync_to_google_calendar
        past_w = int(d.get("past_weeks", 0))
        future_w = int(d.get("future_weeks", 2))

        sessions = run_async(get_schedule_html(past_weeks=past_w, weeks=future_w + 1, headless=True))

        if not sessions:
            return jsonify(ok=False, error="Không cào được qua giao diện HTML.")

        start, end = _window(past_w, future_w)
        sync_to_google_calendar(sessions, start.isoformat(), end.isoformat(), calendar_id=calendar_id)
        return jsonify(ok=True, count=len(sessions), log=handler.lines)
    except Exception as e:
        return jsonify(ok=False, error=f"Lỗi khi cào HTML: {e}"), 502
    finally:
        glog.removeHandler(handler)
        sync_lock.release()


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bảng Điều Khiển TKB ERP V5</title>
<style>
:root{--bg:#fff;--fg:#1c1e21;--muted:#65676b;--card:#f5f6f7;--line:#dddfe2;--accent:#1a73e8;--err:#c5221f;--ok:#188038;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#18191a;--fg:#e4e6eb;--muted:#a8abb0;--card:#242526;--line:#3a3b3c;--accent:#8ab4f8;--err:#f28b82;--ok:#81c995}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:760px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.4rem;margin-bottom:1.2rem}
h2{font-size:1.1rem;margin:0 0 .8rem}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1.2rem;margin:1.2rem 0}
label{display:block;margin:.5rem 0 .2rem;color:var(--muted);font-size:.9rem}
input{width:100%;box-sizing:border-box;padding:.5rem;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
.row{display:flex;gap:.75rem;flex-wrap:wrap}.row>div{flex:1;min-width:140px}
button{padding:.5rem .9rem;border:0;border-radius:6px;background:var(--accent);color:#fff;font:inherit;cursor:pointer;margin:.6rem .4rem 0 0}
button.sec{background:transparent;color:var(--accent);border:1px solid var(--accent)}
button.warn{background:#d93025;color:#fff;}
button:disabled{opacity:.5;cursor:wait;filter:brightness(0.8)}
.msg{margin-top:.6rem;min-height:1.3em;font-weight:500}.err{color:var(--err)}.ok{color:var(--ok)}
table{width:100%;border-collapse:collapse;margin-top:.6rem;font-size:.9rem}td,th{text-align:left;padding:.25rem .4rem;border-bottom:1px solid var(--line)}
pre{white-space:pre-wrap;color:var(--muted);font-size:.85rem;margin-top:.6rem;background:var(--bg);padding:10px;border-radius:6px}
small{color:var(--muted);display:block;margin-top:.5rem}
</style></head><body>

<h1>Bảng Điều Khiển TKB ERP → Google Calendar</h1>

<section>
  <h2>1. Quản lý Phiên Đăng nhập <small id="st" style="display:inline"></small></h2>
  <div><button id="bl">Mở trình duyệt để Đăng nhập ERP bằng Gmail</button></div>
  <div id="m1" class="msg"></div>
</section>

<section>
  <h2>2. Đồng bộ Thủ công</h2>
  <div class="row">
    <div><label>Số tuần cũ</label><input id="past" type="number" min="0" max="26" value="0"></div>
    <div><label>Số tuần tới</label><input id="future" type="number" min="0" max="26" value="2"></div>
  </div>
  <label>ID Calendar (để trống = lịch chính)</label>
  <input id="cal" autocomplete="off" placeholder="VD: abc@group.calendar.google.com">
  
  <div>
    <button id="bs">Đồng bộ Nhanh (API)</button>
    <button class="warn" id="bh">Đồng bộ Lịch thi (HTML - chậm hơn)</button>
  </div>
  <div id="m2" class="msg"></div>
  <div id="out"></div>
</section>

<script>
// Giữ một kết nối SSE mở suốt thời gian tab còn sống.
// Tab đóng -> trình duyệt ngắt kết nối -> Python tự tắt sau vài giây.
// EventSource tự kết nối lại khi reload trang, nên không cần ping thủ công.
window.aliveSource = new EventSource('/api/alive');

window.onload = function() {
    function getEl(id) { return document.getElementById(id); }
    
    async function api(path, bodyData) {
        try {
            const res = await fetch(path, {
                method: bodyData ? 'POST' : 'GET',
                headers: { 'Content-Type': 'application/json' },
                body: bodyData ? JSON.stringify(bodyData) : undefined
            });
            if (!res.ok) {
                const text = await res.text();
                return { ok: false, error: 'HTTP Lỗi ' + res.status + ': ' + text.substring(0, 50) };
            }
            return await res.json();
        } catch (err) {
            return { ok: false, error: 'Lỗi mạng hoặc server bị sập: ' + err.message };
        }
    }

    function setMsg(id, txt, cls) {
        const e = getEl(id);
        if(!e) return;
        e.textContent = txt;
        e.className = 'msg ' + (cls || '');
    }

    async function refreshStatus() {
        const s = await api('/api/status');
        const st = getEl('st');
        if(st) st.textContent = (s && s.logged_in) ? '— Đã lưu phiên' : '— Chưa đăng nhập';
    }

    async function runAction(btnId, msgId, fn) {
        const btn = getEl(btnId);
        if (!btn) { alert('Không tìm thấy nút ' + btnId); return; }
        
        btn.disabled = true;
        setMsg(msgId, 'Đang xử lý… vui lòng chờ hệ thống');
        
        try {
            await fn();
        } catch (e) {
            alert('Lỗi Javascipt nội bộ: ' + e);
            setMsg(msgId, 'Lỗi bất ngờ: ' + e, 'err');
        } finally {
            btn.disabled = false;
        }
    }

    // Gắn sự kiện cho các nút
    getEl('bl').onclick = () => runAction('bl', 'm1', async () => {
        const r = await api('/api/login', {});
        setMsg('m1', r.ok ? 'Lưu phiên đăng nhập thành công!' : r.error, r.ok ? 'ok' : 'err');
        refreshStatus();
    });

    const getOpts = () => ({
        past_weeks: parseInt(getEl('past').value) || 0,
        future_weeks: parseInt(getEl('future').value) || 0,
        calendar_id: getEl('cal').value
    });

    getEl('bs').onclick = () => runAction('bs', 'm2', async () => {
        getEl('out').innerHTML = '<pre id="log_pre"></pre>';
        const pre = getEl('log_pre');
        
        try {
            const res = await fetch('/api/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(getOpts())
            });
            
            if (res.status === 409) {
                setMsg('m2', await res.text(), 'err');
                return;
            }

            // Đọc stream từng dòng log bắn về
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                pre.textContent += decoder.decode(value);
                // Tự động cuộn xuống dưới cùng
                pre.scrollTop = pre.scrollHeight; 
            }
            setMsg('m2', 'Hoàn tất.', 'ok');
        } catch(e) {
            setMsg('m2', 'Lỗi: ' + e.message, 'err');
        }
    });

    getEl('bh').onclick = () => runAction('bh', 'm2', async () => {
        getEl('out').innerHTML = '';
        const r = await api('/api/sync_html', getOpts());
        if (!r.ok) return setMsg('m2', r.error, 'err');
        setMsg('m2', 'HTML: Đã đồng bộ ' + r.count + ' buổi học.', 'ok');
        
        const p = document.createElement('pre');
        p.textContent = (r.log || []).join('\n');
        getEl('out').appendChild(p);
    });

    // Khởi chạy khi load trang
    refreshStatus();
};
</script></body></html>"""

if __name__ == "__main__":
    # Nếu không có tab nào kết nối trong STARTUP_GRACE giây (mở trình duyệt thất bại), tự tắt
    _schedule_exit_check(STARTUP_GRACE)
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    # threaded=True là bắt buộc: mỗi tab giữ 1 kết nối SSE mở liên tục
    app.run(host="127.0.0.1", port=PORT, debug=False, threaded=True)