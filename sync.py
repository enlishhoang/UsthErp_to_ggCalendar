#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py  (phương án cào HTML — dùng khi cần lịch thi chính xác)
Cào thời khóa biểu (có thể gồm cả tuần cũ) rồi đẩy lên Google Calendar.

Cách dùng:
    python sync.py                              # sẽ hỏi số tuần cũ / tuần tới / calendar
    python sync.py --past-weeks 3 --weeks 2     # 3 tuần trước + tuần này và 1 tuần sau vào lịch cá nhân mặc định    #khuyên dùng lần đầu
    python sync.py --past-weeks 3 --weeks 2 --calendar <id lịch bạn muốn nhập vào ex: abc@group.calendar.google.com>>

Quy ước: --weeks là số tuần tính từ TUẦN NÀY trở đi (gồm cả tuần này).
         --calendar <link của lịch mà bạn muốn thêm vào thay vì lịch cá nhân mặc định>
"""

import argparse
import asyncio
import datetime
import inspect
import logging
import sys

import nest_asyncio

from scraper import get_schedule  # scraper.py = bản cào HTML (bản gọi API là scraper2.py)
from gcal_manager import sync_to_google_calendar

nest_asyncio.apply()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("usth-sync")


def ask_int(prompt: str, default: int) -> int:
    raw = input(f"{prompt} (Enter = {default}): ").strip()
    return int(raw) if raw else default


def compute_window(past_weeks: int, weeks: int) -> tuple[str, str]:
    """Ranh giới xóa/ghi trên Google Calendar: 0h Thứ Hai (past_weeks tuần trước) -> 0h Thứ Hai sau `weeks` tuần."""
    now = datetime.datetime.now()
    monday = (now - datetime.timedelta(days=now.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    start = monday - datetime.timedelta(weeks=past_weeks)
    end = monday + datetime.timedelta(weeks=weeks)
    return start.isoformat() + "+07:00", end.isoformat() + "+07:00"


async def main(past_weeks: int, weeks: int, headless: bool, calendar_id: str) -> int:
    params = inspect.signature(get_schedule).parameters
    if past_weeks and "past_weeks" not in params:
        log.error("get_schedule() trong scraper_html chưa hỗ trợ tham số past_weeks.")
        return 1

    kwargs = {"weeks": weeks, "headless": headless}
    if "past_weeks" in params:
        kwargs["past_weeks"] = past_weeks

    schedule = await get_schedule(**kwargs)
    log.info("Bóc tách thành công %d buổi học (%d tuần cũ + %d tuần từ tuần này).",
             len(schedule), past_weeks, weeks)

    if not schedule:
        # Dừng ở đây để không xóa sạch lịch trên Google khi cào hỏng.
        log.warning("Không tìm thấy môn học nào — có thể ERP đổi giao diện hoặc session hết hạn.")
        return 1

    time_min_iso, time_max_iso = compute_window(past_weeks, weeks)
    sync_to_google_calendar(schedule, time_min_iso, time_max_iso, calendar_id=calendar_id)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đồng bộ thời khóa biểu USTH sang Google Calendar (cào HTML)")
    parser.add_argument("--past-weeks", type=int, default=None, help="Số tuần QUÁ KHỨ cần lấy lại")
    parser.add_argument("--weeks", type=int, default=None, help="Số tuần từ tuần này trở đi (gồm tuần này)")
    parser.add_argument("--calendar", type=str, default=None, help="ID Calendar (mặc định: primary)")
    parser.add_argument("--show-browser", action="store_true",
                        help="Hiện cửa sổ trình duyệt khi chạy (mặc định chạy ẩn/headless)")
    args = parser.parse_args()

    past_weeks = args.past_weeks if args.past_weeks is not None else ask_int("Số tuần cũ cần lấy lại", 0)
    weeks = args.weeks if args.weeks is not None else ask_int("Số tuần cần đồng bộ (từ tuần này)", 1)
    calendar_id = args.calendar or input(
        "Nhập id calendar (Enter = lịch cá nhân; id nằm trong Cài đặt và chia sẻ lịch/Setting and sharing > Tích hợp lịch/Integrated > Calendar ID): "
    ).strip() or "primary"

    exit_code = asyncio.run(main(past_weeks, weeks, not args.show_browser, calendar_id))
    sys.exit(exit_code)
