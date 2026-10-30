#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
erp_client.py
Client thuần `requests` cho ERP USTH (không cần trình duyệt/Playwright).
- Đăng nhập nội bộ: POST /api/v1/auth/login  {account, password}   (không mã hóa, có x-check-sum)
- Hoặc dán Cookie lấy từ trình duyệt (khi tài khoản chỉ đăng nhập qua Google/SSO hoặc bị reCAPTCHA chặn)
- Lấy TKB: POST /api/v2/timetables/query-student-timetable-in-range (body AES + x-check-sum)
"""
import base64
import hashlib
import json
import os
import time

import requests
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from timetable_parser import extract_sessions

ORIGIN = "https://erp.usth.edu.vn"
BASE = ORIGIN + "/student-services"
COOKIE_FILE = "erp_session.json"

APP_KEY = b"304c7f6dff373663d32879ac1c1f1318"   # key = SHA256(APP_KEY)
APP_IV = b"069635c0806598e069583aee5440e448"    # iv  = MD5(APP_IV)


class ERPError(Exception):
    pass


class LoginError(ERPError):
    pass


class SessionExpiredError(ERPError):
    pass


def _dumps(obj) -> str:
    # Giống JSON.stringify của trình duyệt: gọn, không escape ký tự Unicode
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def _cipher():
    return AES.new(hashlib.sha256(APP_KEY).digest(), AES.MODE_CBC, hashlib.md5(APP_IV).digest())


def encrypt_payload(data: dict) -> str:
    return base64.b64encode(_cipher().encrypt(pad(_dumps(data).encode("utf-8"), AES.block_size))).decode()


def decrypt_payload(payload: str):
    raw = unpad(_cipher().decrypt(base64.b64decode(payload)), AES.block_size)
    return json.loads(raw.decode("utf-8"))


def checksum(body: dict) -> str:
    """x-check-sum: bỏ dict/list lồng nhau (giữ null), sắp key, JSON gọn, SHA256 hex."""
    kept = {k: v for k, v in body.items() if v is None or not isinstance(v, (dict, list))}
    ordered = {k: kept[k] for k in sorted(kept)}
    return hashlib.sha256(_dumps(ordered).encode("utf-8")).hexdigest()


class ERPClient:
    def __init__(self, cookie_file: str = COOKIE_FILE):
        self.cookie_file = cookie_file
        self.s = requests.Session()
        self.s.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": ORIGIN,
            "Referer": ORIGIN + "/students/learn/timetable",
            "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
        })

    # ---------- phiên đăng nhập ----------
    def has_cookies(self) -> bool:
        return len(self.s.cookies) > 0

    def save_cookies(self) -> None:
        with open(self.cookie_file, "w", encoding="utf-8") as f:
            json.dump({c.name: c.value for c in self.s.cookies}, f)
        try:
            os.chmod(self.cookie_file, 0o600)
        except OSError:
            pass

    def load_cookies(self) -> None:
        if not os.path.exists(self.cookie_file):
            return
        try:
            with open(self.cookie_file, encoding="utf-8") as f:
                for k, v in json.load(f).items():
                    self.s.cookies.set(k, v, domain="erp.usth.edu.vn", path="/")
        except (OSError, ValueError):
            pass

    def clear(self) -> None:
        self.s.cookies.clear()
        if os.path.exists(self.cookie_file):
            os.remove(self.cookie_file)

    def set_cookie_header(self, raw: str) -> None:
        raw = raw.strip()
        if raw.lower().startswith("cookie:"):
            raw = raw[7:]
        pairs = []
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                k, v = k.strip(), v.strip()
                if k:
                    pairs.append((k, v))
        if not pairs:
            raise ERPError("Chuỗi Cookie không hợp lệ (cần dạng: tên1=giá trị1; tên2=giá trị2).")

        # HTTP header chỉ chấp nhận ký tự Latin-1. Nếu DevTools/trình duyệt rút gọn một giá
        # trị dài (JWT...) và chèn dấu "…", hoặc bạn copy nhầm dấu nháy/ký tự đặc biệt khác,
        # request sẽ vỡ với lỗi khó hiểu ở tận lúc gọi ERP. Chặn ngay tại đây và nói rõ cookie
        # nào bị lỗi để dễ soi lại chỗ copy thiếu.
        bad = []
        for k, v in pairs:
            try:
                v.encode("latin-1")
            except UnicodeEncodeError as e:
                bad.append(f"{k} (ký tự '{v[e.start:e.end]}' ở vị trí {e.start})")
        if bad:
            raise ERPError(
                "Giá trị cookie chứa ký tự không hợp lệ, có thể do bị rút gọn/cắt bớt lúc copy: "
                + "; ".join(bad)
                + ". Hãy copy lại đúng dòng 'cookie:' trong Request Headers (kéo hết dòng, "
                  "đừng copy phần bị DevTools rút gọn bằng dấu '…')."
            )

        for k, v in pairs:
            self.s.cookies.set(k, v, domain="erp.usth.edu.vn", path="/")
        self.check_session()          # ném SessionExpiredError nếu cookie không dùng được
        self.save_cookies()

    def login(self, account: str, password: str) -> None:
        body = {"account": account, "password": password}
        r = self.s.post(f"{BASE}/api/v1/auth/login", data=_dumps(body).encode("utf-8"),
                        headers={"x-check-sum": checksum(body)}, timeout=20)
        try:
            data = r.json()
        except ValueError:
            data = {}
        code = data.get("code") if isinstance(data, dict) else None
        if code == -1:
            raise LoginError("Sai mã sinh viên hoặc mật khẩu.")
        if code == -2:
            raise LoginError("Tài khoản chưa được xác minh trên ERP.")
        if r.status_code >= 400 or code == 0:
            raise LoginError(f"ERP từ chối đăng nhập (HTTP {r.status_code}, code={code}). "
                             "Nếu bạn thường đăng nhập bằng Google/reCAPTCHA, hãy dùng tab Cookie.")
        try:
            self.check_session()
        except SessionExpiredError:
            raise LoginError("Đăng nhập không tạo được phiên. Hãy dùng tab Cookie.")
        self.save_cookies()

    # ---------- API ----------
    def check_session(self) -> dict:
        """Xác thực phiên bằng /api/v1/auth/session — endpoint web dùng để hỏi 'ai đang đăng
        nhập'. Response được mã hóa AES giống như /timetables. /semesters/current KHÔNG dùng
        được để kiểm tra vì nó có thể trả 200 ngay cả khi chưa đăng nhập, nên trước đây việc
        dán Cookie báo "hợp lệ" dù cookie sai, và lỗi 401 chỉ lộ ra khi lấy thời khóa biểu."""
        # Endpoint "encrypt": ngay cả GET không có tham số cũng phải kèm
        # ?payload=<AES({"requestTime": now_ms})>, nếu không ERP trả 400 "Invalid payload".
        query = encrypt_payload({"requestTime": int(time.time() * 1000)})
        r = self.s.get(f"{BASE}/api/v1/auth/session", params={"payload": query}, timeout=20)
        if r.status_code in (401, 403):
            raise SessionExpiredError(f"HTTP {r.status_code}: chưa đăng nhập hoặc phiên đã hết hạn.")
        if r.status_code >= 400:
            raise ERPError(f"HTTP {r.status_code}: {r.text[:200]}")
        try:
            raw = r.json()
        except ValueError:
            raise SessionExpiredError("ERP không trả JSON (có thể bị chuyển về trang đăng nhập).")
        if os.environ.get("USTH_DEBUG"):
            with open("debug_session_raw.json", "w", encoding="utf-8") as f:
                json.dump(raw, f, ensure_ascii=False, indent=2)
        if not isinstance(raw, dict) or "payload" not in raw:
            raise SessionExpiredError(f"Response /auth/session không có 'payload': {str(raw)[:200]}")
        try:
            data = decrypt_payload(raw["payload"])
        except Exception as e:
            raise SessionExpiredError(f"Không giải mã được /auth/session: {e}")
        if os.environ.get("USTH_DEBUG"):
            with open("debug_session.json", "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        if not isinstance(data, dict) or not data.get("user"):
            raise SessionExpiredError("Cookie/phiên không hợp lệ (không có 'user' trong /auth/session).")
        return data

    def _current_semester(self) -> str | None:
        try:
            r = self.s.get(f"{BASE}/api/v1/semesters/current", timeout=20)
            data = r.json() if r.ok else {}
        except (requests.RequestException, ValueError):
            data = {}
        if not isinstance(data, dict):
            return None
        return data.get("semester") or (data.get("data") or {}).get("semester")

    def get_schedule(self, from_ms: int, to_ms: int) -> list[dict]:
        self.check_session()
        semester = self._current_semester()
        body = {"fromTime": from_ms, "toTime": to_ms}
        if semester:
            body["semester"] = semester

        r = self.s.post(f"{BASE}/api/v2/timetables/query-student-timetable-in-range",
                        data=_dumps({"payload": encrypt_payload(body)}).encode("utf-8"),
                        headers={"x-check-sum": checksum(body)}, timeout=30)
        if r.status_code in (401, 403):
            raise SessionExpiredError(f"HTTP {r.status_code}: {r.text[:200]}")
        if r.status_code >= 400:
            raise ERPError(f"HTTP {r.status_code}: {r.text[:200]}")
        raw = r.json()
        if not isinstance(raw, dict) or "payload" not in raw:
            raise ERPError(f"Response không có 'payload': {str(raw)[:200]}")
        payload = decrypt_payload(raw["payload"])
        if os.environ.get("USTH_DEBUG"):
            with open("debug_timetable.json", "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        return extract_sessions(payload, from_ms, to_ms)