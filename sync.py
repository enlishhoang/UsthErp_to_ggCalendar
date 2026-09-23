#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sync.py
Kịch bản chạy chính: cào N tuần thời khóa biểu rồi đẩy lên Google Calendar.

Cách dùng:
    chay file vaf nhap so tuan muon dong bo
"""

import argparse
import asyncio
import logging
import sys

import nest_asyncio

from scraper import get_schedule
from gcal_manager import sync_to_google_calendar

nest_asyncio.apply()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("usth-sync")


async def main(weeks: int, headless: bool) -> int:
    schedule = await get_schedule(weeks=weeks, headless=headless)
    log.info("Bóc tách thành công %d buổi học cho %d tuần.", len(schedule), weeks)

    if not schedule:
        log.warning("Không tìm thấy môn học nào — có thể ERP đổi giao diện hoặc session hết hạn.")
        return 1
    Destination_calendar = input("Nhập id calendar: Enter để mặc định lịch cá nhân, hoặc vào setting lịch muốn nhập, kéo xuống tìm id lịch và copy paste vào đây: \n") or "primary"

    sync_to_google_calendar(schedule,calendar_id=Destination_calendar)
    return 0


if __name__ == "__main__": 
    num_of_weeks=int(input('Số tuần cần đồng bộ: '))
    parser = argparse.ArgumentParser(description="Đồng bộ thời khóa biểu USTH sang Google Calendar")
    parser.add_argument("--weeks", type=int, default=num_of_weeks, help="Số tuần cần đồng bộ (mặc định: 1)")
    parser.add_argument("--show-browser", action="store_true",
                         help="Hiện cửa sổ trình duyệt khi chạy (mặc định chạy ẩn/headless)")
    args = parser.parse_args()

    exit_code = asyncio.run(main(weeks=args.weeks, headless=not args.show_browser))
    sys.exit(exit_code)
