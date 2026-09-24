#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
sync_auto.py  (phương án gọi trực tiếp API ERP để lấy mã nguồn json)
Cào thời khóa biểu (có thể gồm cả tuần cũ) rồi đẩy lên Google Calendar.

Cách dùng tạm thời:
    Bấm nút run trong VSC:                       Mặc định sync tuần này và tuần sau
    python sync_auto.py                          Trong terminal hoặc command promt
    python sync_auto.py --past-weeks 3 --future-weeks 2 # 3 tuần trước + tuần này và 2 tuần sau,  nên dùng cho lần đầu chạy
"""

import argparse
import asyncio
import logging
import sys
import datetime
import nest_asyncio

from scraper2 import get_schedule, SessionExpiredError
from gcal_manager import sync_to_google_calendar

nest_asyncio.apply()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("usth-sync")

async def main(past_weeks: int, future_weeks: int, headless: bool, calendar_id: str) -> int:
    # 1. Tính toán ranh giới thời gian (từ 0h Thứ Hai của tuần bắt đầu)
    now = datetime.datetime.now()
    start_of_week = now - datetime.timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

    from_time = start_of_week - datetime.timedelta(weeks=past_weeks)
    to_time = start_of_week + datetime.timedelta(weeks=future_weeks + 1)

    from_time_ms = int(from_time.timestamp() * 1000)
    to_time_ms = int(to_time.timestamp() * 1000)

    # 2. Convert sang chuẩn ISO 8601 để Google Calendar API tạo ranh giới xóa lịch
    time_min_iso = from_time.isoformat() + "+07:00"
    time_max_iso = to_time.isoformat() + "+07:00"

    try:
        schedule = await get_schedule(from_time_ms, to_time_ms, headless=headless)
    except SessionExpiredError as e:
        log.error("Phiên đăng nhập hết hạn: %s", e)
        return 1

    log.info("Đã giải mã được %d buổi học từ API ERP.", len(schedule))

    if not schedule:
        log.warning("Không tìm thấy môn học nào trong vùng thời gian này.")
    
    try:
        # Truyền cả ranh giới Min - Max vào hàm đồng bộ
        sync_to_google_calendar(schedule, time_min_iso, time_max_iso, calendar_id=calendar_id)
    except Exception as e:
        log.error("Lỗi giao tiếp với Google Calendar API: %s", e)
        return 1
        
    return 0

if __name__ == "__main__": 
    parser = argparse.ArgumentParser(description="Đồng bộ TKB USTH sang Google Calendar bằng API AES")
    parser.add_argument("--past-weeks", type=int, default=0, help="Số tuần QUÁ KHỨ muốn quét (để lấy lịch cũ)")
    parser.add_argument("--future-weeks", type=int, default=1, help="Số tuần TƯƠNG LAI cần đồng bộ")
    parser.add_argument("--calendar", type=str, default="primary", help="ID Calendar (mặc định: primary)")
    parser.add_argument("--show-browser", action="store_true", help="Hiện cửa sổ Chrome (debug)")
    
    args = parser.parse_args()

    log.info(f"Khởi động: Cào {args.past_weeks} tuần cũ và {args.future_weeks} tuần tới.")
    exit_code = asyncio.run(main(args.past_weeks, args.future_weeks, not args.show_browser, args.calendar))
    sys.exit(exit_code)