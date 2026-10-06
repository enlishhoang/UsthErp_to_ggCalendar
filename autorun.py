#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
autorun.py — tự động chạy sync_auto.py ở lần khởi động máy đầu tiên, mỗi 2 ngày một lần.

Đặt file này cùng thư mục với sync_auto.py, rồi chạy (bằng ĐÚNG môi trường Python
mà bạn dùng cho sync_auto.py, ví dụ conda env của bạn):

    python autorun.py install                 # cài đặt (mặc định: 2 ngày/lần)
    python autorun.py install --days 3 --future-weeks 3 --calendar abc@group.calendar.google.com
    python autorun.py status                  # xem đã cài chưa, lần chạy cuối, log gần nhất
    python autorun.py run --force             # chạy thử ngay, bỏ qua kiểm tra 2 ngày
    python autorun.py uninstall               # gỡ cài đặt

Cách hoạt động:
  * Windows : tạo file .vbs trong thư mục Startup (chạy ẩn, không hiện cửa sổ, không cần quyền admin)
  * Linux   : tạo file .desktop trong ~/.config/autostart (chạy khi đăng nhập vào desktop)
  * macOS   : tạo LaunchAgent (.plist) trong ~/Library/LaunchAgents (RunAtLoad, chạy khi đăng nhập)
  * Mỗi lần khởi động, "autorun.py run" kiểm tra file .last_auto_sync:
      - chưa đủ N ngày kể từ lần đồng bộ thành công gần nhất -> thoát ngay
      - đủ N ngày -> đợi có mạng, chạy sync_auto.py, thành công thì ghi lại ngày chạy
      - thất bại (mất mạng, hết phiên ERP...) -> không ghi ngày, lần khởi động sau sẽ thử lại
  * Log nằm ở autosync.log cùng thư mục.
"""

import argparse
import os
import plistlib
import socket
import subprocess
import sys
import time
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "sync_auto.py"
STAMP = HERE / ".last_auto_sync"
LOG = HERE / "autosync.log"
APP_NAME = "usth-calendar-autosync"
IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"

NETWORK_WAIT_SECONDS = 180   # tối đa đợi mạng sau khi bật máy


# ---------------------------------------------------------------------------
# Tiện ích
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}\n")


def read_last_run():
    try:
        return datetime.fromisoformat(STAMP.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def is_due(days: int) -> bool:
    last = read_last_run()
    if last is None:
        return True
    return (date.today() - last.date()).days >= days


def wait_for_network(max_wait: int) -> bool:
    deadline = time.monotonic() + max_wait
    while True:
        try:
            socket.create_connection(("www.googleapis.com", 443), timeout=3).close()
            return True
        except OSError:
            if time.monotonic() >= deadline:
                return False
            time.sleep(5)


def sync_args(a) -> list:
    return ["--past-weeks", str(a.past_weeks),
            "--future-weeks", str(a.future_weeks),
            "--calendar", a.calendar]


# ---------------------------------------------------------------------------
# Lệnh: run  (được gọi tự động mỗi lần khởi động)
# ---------------------------------------------------------------------------
def cmd_run(a) -> int:
    if not a.force and not is_due(a.days):
        return 0                                   # chưa đến hạn, im lặng thoát

    if not TARGET.exists():
        log(f"LỖI: không tìm thấy {TARGET}")
        return 1

    log(f"Đến hạn đồng bộ (mỗi {a.days} ngày). Đang đợi mạng...")
    if not wait_for_network(NETWORK_WAIT_SECONDS):
        log("Không có mạng sau khi chờ, bỏ qua. Sẽ thử lại ở lần khởi động sau.")
        return 1

    cmd = [sys.executable, str(TARGET)] + sync_args(a)
    log("Chạy: " + " ".join(cmd))
    kwargs = {}
    if IS_WIN:
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    with open(LOG, "a", encoding="utf-8") as lf:
        proc = subprocess.run(cmd, cwd=str(HERE), stdout=lf, stderr=subprocess.STDOUT, **kwargs)

    if proc.returncode == 0:
        STAMP.write_text(datetime.now().isoformat(), encoding="utf-8")
        log("Đồng bộ thành công.")
    else:
        log(f"Đồng bộ thất bại (mã thoát {proc.returncode}). Sẽ thử lại ở lần khởi động sau.")
    return proc.returncode


# ---------------------------------------------------------------------------
# Cài đặt / gỡ cài đặt theo hệ điều hành
# ---------------------------------------------------------------------------
def startup_command(a) -> list:
    exe = Path(sys.executable)
    if IS_WIN:
        pyw = exe.with_name("pythonw.exe")         # không hiện cửa sổ console
        if pyw.exists():
            exe = pyw
    return [str(exe), str(Path(__file__).resolve()), "run", "--days", str(a.days)] + sync_args(a)


def win_entry() -> Path:
    startup = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
    return startup / f"{APP_NAME}.vbs"


def linux_entry() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "autostart" / f"{APP_NAME}.desktop"


def mac_entry() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{APP_NAME}.plist"


def entry_path() -> Path:
    if IS_WIN:
        return win_entry()
    if IS_MAC:
        return mac_entry()
    return linux_entry()


def desktop_quote(arg: str) -> str:
    arg = arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    return f'"{arg}"'


def cmd_install(a) -> int:
    if not TARGET.exists():
        print(f"Không tìm thấy {TARGET.name} cùng thư mục với autorun.py.")
        return 1

    cmd = startup_command(a)
    path = entry_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    if IS_WIN:
        line = subprocess.list2cmdline(cmd).replace('"', '""')    # thoát dấu " trong VBScript
        path.write_text(
            'CreateObject("Wscript.Shell").Run "' + line + '", 0, False\r\n',
            encoding="utf-8",
        )
    elif IS_MAC:
        plist = {
            "Label": APP_NAME,
            "ProgramArguments": cmd,
            "RunAtLoad": True,                 # chạy mỗi khi đăng nhập
            "WorkingDirectory": str(HERE),
            "ProcessType": "Background",
        }
        with open(path, "wb") as f:
            plistlib.dump(plist, f)
    else:
        exec_line = " ".join(desktop_quote(c) for c in cmd)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=USTH Calendar Auto Sync\n"
            f"Exec={exec_line}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Delay=20\n",
            encoding="utf-8",
        )

    print(f"Đã cài đặt: {path}")
    print(f"Python dùng để chạy: {cmd[0]}")
    print(f"Sẽ đồng bộ ở lần khởi động đầu tiên mỗi {a.days} ngày "
          f"(past={a.past_weeks}, future={a.future_weeks}, calendar={a.calendar}).")
    print("Chạy thử ngay:  python autorun.py run --force")
    return 0


def cmd_uninstall(_a) -> int:
    path = entry_path()
    if path.exists():
        path.unlink()
        print(f"Đã gỡ: {path}")
    else:
        print("Chưa cài đặt, không có gì để gỡ.")
    return 0


def cmd_status(a) -> int:
    path = entry_path()
    print("Đã cài đặt:" if path.exists() else "Chưa cài đặt.", path if path.exists() else "")
    last = read_last_run()
    print("Lần đồng bộ thành công gần nhất:", last.strftime("%Y-%m-%d %H:%M") if last else "chưa có")
    print(f"Đến hạn ở lần khởi động tới (mỗi {a.days} ngày):", "có" if is_due(a.days) else "chưa")
    if LOG.exists():
        print("\n--- 15 dòng log gần nhất ---")
        print("\n".join(LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]))
    return 0


# ---------------------------------------------------------------------------
def main() -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--days", type=int, default=2, help="Số ngày giữa hai lần đồng bộ (mặc định 2)")
    common.add_argument("--past-weeks", type=int, default=0)
    common.add_argument("--future-weeks", type=int, default=2)
    common.add_argument("--calendar", type=str, default="primary", help="ID Calendar (mặc định: primary)")

    p = argparse.ArgumentParser(description="Tự động chạy sync_auto.py khi khởi động máy.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("install", parents=[common], help="Cài đặt chạy tự động")
    sub.add_parser("uninstall", help="Gỡ cài đặt")
    sub.add_parser("status", parents=[common], help="Xem trạng thái")
    r = sub.add_parser("run", parents=[common], help="(nội bộ) kiểm tra hạn và đồng bộ")
    r.add_argument("--force", action="store_true", help="Bỏ qua kiểm tra số ngày")

    a = p.parse_args()
    return {"install": cmd_install, "uninstall": cmd_uninstall,
            "status": cmd_status, "run": cmd_run}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())