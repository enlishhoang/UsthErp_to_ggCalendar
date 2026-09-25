#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py — Local Web App: đồng bộ TKB USTH -> Google Calendar (không Playwright/Chromium).
Chạy:  python app.py   (tự mở trình duyệt mặc định tại http://127.0.0.1:5077)
"""
import logging
import os
import threading
import webbrowser
from datetime import datetime, timedelta

from flask import Flask, abort, jsonify, request

from erp_client import ERPClient, ERPError, LoginError, SessionExpiredError
from timetable_parser import VN

PORT = int(os.environ.get("PORT", "5077"))
app = Flask(__name__)
client = ERPClient()
client.load_cookies()
sync_lock = threading.Lock()


@app.before_request
def guard():
    # Chặn DNS-rebinding và CSRF từ trang web khác: chỉ nhận Host local + POST dạng JSON.
    if request.host.split(":")[0] not in ("127.0.0.1", "localhost"):
        abort(403)
    if request.method == "POST" and not request.is_json:
        abort(415)


def _window(past: int, future: int):
    now = datetime.now(VN)
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return monday - timedelta(weeks=past), monday + timedelta(weeks=future + 1)


def _weeks(data: dict, key: str, default: int) -> int:
    try:
        return max(0, min(26, int(data.get(key, default))))
    except (TypeError, ValueError):
        return default


def _err(msg: str, code: int = 400):
    return jsonify(ok=False, error=msg), code


def _fetch(data: dict):
    start, end = _window(_weeks(data, "past_weeks", 0), _weeks(data, "future_weeks", 2))
    sessions = client.get_schedule(int(start.timestamp() * 1000), int(end.timestamp() * 1000))
    return sessions, start, end


@app.get("/")
def index():
    return PAGE


@app.get("/api/status")
def status():
    if not client.has_cookies():
        return jsonify(logged_in=False)
    try:
        client.check_session()
        return jsonify(logged_in=True, semester=client._current_semester())
    except Exception:
        return jsonify(logged_in=False)


@app.post("/api/login")
def login():
    d = request.get_json(silent=True) or {}
    account, password = str(d.get("account", "")).strip(), str(d.get("password", ""))
    if not account or not password:
        return _err("Nhập mã sinh viên và mật khẩu.")
    try:
        client.login(account, password)
    except ERPError as e:
        return _err(str(e), 401)
    except Exception as e:
        return _err(f"Không kết nối được ERP: {e}", 502)
    return jsonify(ok=True)


@app.post("/api/cookie")
def cookie():
    d = request.get_json(silent=True) or {}
    try:
        client.set_cookie_header(str(d.get("cookie", "")))
    except SessionExpiredError:
        client.clear()
        return _err("Cookie không dùng được (hết hạn hoặc thiếu cookie phiên).", 401)
    except ERPError as e:
        return _err(str(e))
    except Exception as e:
        return _err(f"Không kết nối được ERP: {e}", 502)
    return jsonify(ok=True)


@app.post("/api/logout")
def logout():
    client.clear()
    return jsonify(ok=True)


@app.post("/api/schedule")
def schedule():
    try:
        sessions, _, _ = _fetch(request.get_json(silent=True) or {})
    except SessionExpiredError as e:
        return _err(str(e), 401)
    except Exception as e:
        return _err(f"Lỗi khi lấy TKB: {e}", 502)
    return jsonify(ok=True, sessions=sessions)


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
        return _err("Đang có một lần đồng bộ khác chạy.", 409)
    handler = _ListHandler()
    glog = logging.getLogger("usth-sync.gcal")
    glog.setLevel(logging.INFO)
    glog.addHandler(handler)
    try:
        try:
            from gcal_manager import sync_to_google_calendar
        except ImportError as e:
            return _err(f"Thiếu thư viện Google: {e}. Chạy: pip install -r requirements.txt", 500)
        try:
            sessions, start, end = _fetch(d)
        except SessionExpiredError as e:
            return _err(str(e), 401)
        except Exception as e:
            return _err(f"Lỗi khi lấy TKB: {e}", 502)
        if not sessions:
            # Không đồng bộ khi rỗng: gcal_manager sẽ xóa lịch cũ trong khoảng này.
            return _err("Không có buổi học nào trong khoảng này — đã dừng để không xóa lịch trên Google.")
        try:
            sync_to_google_calendar(sessions, start.isoformat(), end.isoformat(), calendar_id=calendar_id)
        except FileNotFoundError:
            return _err("Không thấy credentials.json (khóa OAuth của Google Calendar) trong thư mục chạy.", 500)
        except Exception as e:
            return _err(f"Lỗi Google Calendar: {e}", 502)
        return jsonify(ok=True, count=len(sessions), log=handler.lines)
    finally:
        glog.removeHandler(handler)
        sync_lock.release()


PAGE = r"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Đồng bộ TKB ERP → Google Calendar</title>
<style>
:root{--bg:#fff;--fg:#1c1e21;--muted:#65676b;--card:#f5f6f7;--line:#dddfe2;--accent:#1a73e8;--err:#c5221f;--ok:#188038;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#18191a;--fg:#e4e6eb;--muted:#a8abb0;--card:#242526;--line:#3a3b3c;--accent:#8ab4f8;--err:#f28b82;--ok:#81c995}}
body{font:15px/1.5 system-ui,sans-serif;background:var(--bg);color:var(--fg);max-width:760px;margin:2rem auto;padding:0 1rem}
h1{font-size:1.4rem;margin-bottom:1.2rem}
h2{font-size:1.1rem;margin:0 0 .8rem}
section{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:1.2rem;margin:1.2rem 0}
ol{margin:.4rem 0 1rem;padding-left:1.2rem;color:var(--muted);font-size:.9rem}
ol li{margin-bottom:.3rem}
label{display:block;margin:.5rem 0 .2rem;color:var(--muted);font-size:.9rem}
input,textarea{width:100%;box-sizing:border-box;padding:.5rem;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--fg);font:inherit}
textarea{min-height:90px;resize:vertical}
.row{display:flex;gap:.75rem;flex-wrap:wrap}.row>div{flex:1;min-width:140px}
button{padding:.5rem .9rem;border:0;border-radius:6px;background:var(--accent);color:#fff;font:inherit;cursor:pointer;margin:.6rem .4rem 0 0}
button.sec{background:transparent;color:var(--accent);border:1px solid var(--accent)}
button:disabled{opacity:.5;cursor:wait}
.msg{margin-top:.6rem;min-height:1.3em}.err{color:var(--err)}.ok{color:var(--ok)}
table{width:100%;border-collapse:collapse;margin-top:.6rem;font-size:.9rem}td,th{text-align:left;padding:.25rem .4rem;border-bottom:1px solid var(--line)}
pre{white-space:pre-wrap;color:var(--muted);font-size:.85rem;margin-top:.6rem}
small{color:var(--muted);display:block;margin-top:.5rem}
</style></head><body>

<h1>Đồng Bộ TKB ERP → Google Calendar</h1>

<section>
  <h2>1. Đăng nhập ERP <small id="st" style="display:inline"></small></h2>
  
  <h2>2. Lấy Cookie:</h2>
  <ol>
    <li>Bấm F12 → Network → Reload nếu chưa có gì</li>
    <li>Chọn 1 mục bất kỳ → Headers → Kéo xuống Request Headers</li>
    <li>Kéo xuống Cookie: chuột phải copy value</li>
    <li>Paste vào ô dưới đây</li>
  </ol>
  
  <textarea id="cookie" placeholder="Dán chuỗi Cookie vào đây..." autocomplete="off"></textarea>
  
  <div>
    <button id="bc">Dùng Cookie này</button>
    <button class="sec" id="bo">Đăng xuất</button>
  </div>
  <div id="m1" class="msg"></div>
</section>

<section>
  <h2>3. Đồng bộ</h2>
  <div class="row">
    <div>
      <label>Số tuần cũ</label>
      <input id="past" type="number" min="0" max="26" value="0">
    </div>
    <div>
      <label>Số tuần tới (ngoài tuần này)</label>
      <input id="future" type="number" min="0" max="26" value="2">
    </div>
  </div>
  
  <label>ID Calendar (để trống = lịch chính)</label>
  <input id="cal" autocomplete="off" placeholder="Để trống nếu dùng lịch mặc định">
  
  <div>
    <button id="bs">Đồng bộ lên Google Calendar</button>
    <button class="sec" id="bp">Xem trước</button>
  </div>
  <div id="m2" class="msg"></div>
  <div id="out"></div>
</section>

<script>
const $=id=>document.getElementById(id);
async function api(p,b){try{const r=await fetch(p,{method:b?'POST':'GET',headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});
 return await r.json()}catch(e){return{ok:false,error:'Không kết nối được máy chủ local.'}}}
function msg(id,t,k){const e=$(id);e.textContent=t;e.className='msg '+(k||'')}
async function refresh(){const s=await api('/api/status');$('st').textContent=s.logged_in?'— đã đăng nhập'+(s.semester?' (kỳ '+s.semester+')':''):'— chưa đăng nhập'}

async function run(btn,m,fn){btn.disabled=true;msg(m,'Đang xử lý…');try{await fn()}finally{btn.disabled=false}}

$('bc').onclick=()=>run($('bc'),'m1',async()=>{const r=await api('/api/cookie',{cookie:$('cookie').value});
 if(r.ok)$('cookie').value='';msg('m1',r.ok?'Cookie hợp lệ, đăng nhập thành công.':r.error,r.ok?'ok':'err');refresh()});

$('bo').onclick=async()=>{await api('/api/logout',{});msg('m1','Đã đăng xuất.');refresh()};

const opts=()=>({past_weeks:+$('past').value||0,future_weeks:+$('future').value||0,calendar_id:$('cal').value});

function table(rows){const t=document.createElement('table');t.innerHTML='<tr><th>Ngày</th><th>Giờ</th><th>Môn</th><th>Phòng</th></tr>';
 rows.forEach(s=>{const tr=t.insertRow();[s.start_time.slice(0,10),s.start_time.slice(11,16)+'–'+s.end_time.slice(11,16),s.subject,s.room].forEach(v=>tr.insertCell().textContent=v)});return t}

$('bp').onclick=()=>run($('bp'),'m2',async()=>{const r=await api('/api/schedule',opts());$('out').replaceChildren();
 if(!r.ok)return msg('m2',r.error,'err');msg('m2','Tìm thấy '+r.sessions.length+' buổi học.','ok');$('out').append(table(r.sessions))});

$('bs').onclick=()=>run($('bs'),'m2',async()=>{$('out').replaceChildren();const r=await api('/api/sync',opts());
 if(!r.ok)return msg('m2',r.error,'err');msg('m2','Đã đồng bộ '+r.count+' buổi học.','ok');const p=document.createElement('pre');p.textContent=r.log.join('\n');$('out').append(p)});

refresh();
</script></body></html>"""


if __name__ == "__main__":
    threading.Timer(1.0, lambda: webbrowser.open(f"http://127.0.0.1:{PORT}")).start()
    app.run(host="127.0.0.1", port=PORT, debug=False)