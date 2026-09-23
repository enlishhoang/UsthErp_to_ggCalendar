#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper.py
Cào và bóc tách thời khóa biểu từ ERP USTH.
Dùng chung cho mọi kịch bản sync (1 tuần, N tuần, chạy nền, ...).
"""

import re
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

TIMETABLE_URL = "https://erp.usth.edu.vn/students/learn/timetable"

# Thư mục profile Chrome dùng chung giữa login_once.py và các lần sync tự động.
# Giữ nguyên profile (cookie, local storage, cache...) giúp Google nhận diện
# đây là thiết bị quen, giảm khả năng bị bắt xác minh lại mỗi lần.
PROFILE_DIR = "chrome_profile"

# Khoảng cách giữa các cột ngày trong lưới lịch tuần (px)
COLUMN_WIDTH_PX = 206
COLUMN_OFFSET_PX = 4


class SessionExpiredError(Exception):
    """Profile Chrome (chrome_profile/) không còn phiên đăng nhập hợp lệ."""


async def fetch_weeks_html(weeks: int = 1, headless: bool = True,
                            profile_dir: str = PROFILE_DIR) -> list[str]:
    """
    Mở lại profile Chrome đã đăng nhập từ login_once.py, cào HTML của
    `weeks` tuần liên tiếp bằng cách bấm nút "Next" giữa mỗi tuần.
    Trả về danh sách chuỗi HTML, mỗi phần tử là 1 tuần.
    Raise SessionExpiredError nếu không vào được lưới lịch tuần ngay từ đầu.
    """
    htmls = []
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(profile_dir, headless=headless)
        page = context.pages[0] if context.pages else await context.new_page()

        print("Đang truy cập ERP để lấy lịch...")
        await page.goto(TIMETABLE_URL)

        try:
            await page.wait_for_selector(".day-header", timeout=15000)
        except Exception:
            await context.close()
            raise SessionExpiredError(
                f"Không thấy lưới lịch tuần sau khi vào {TIMETABLE_URL} "
                f"(URL hiện tại: {page.url}). Session có thể đã hết hạn."
            )

        for i in range(weeks):
            print(f"--- Đang xử lý tuần {i + 1}/{weeks} ---")
            try:
                if i > 0:
                    await page.wait_for_selector(".day-header", timeout=15000)
                await page.wait_for_timeout(3000)  # chờ JS đổ dữ liệu môn học

                htmls.append(await page.content())

                if i < weeks - 1:
                    await page.locator('span[aria-label="right"]').click(force=True)
                    await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"Lỗi ở tuần {i + 1}: {e}")
                break

        await context.close()
    return htmls


def parse_weekly_html(html_content: str) -> list[dict]:
    """Bóc tách 1 chuỗi HTML tuần thành danh sách sự kiện (subject/room/start/end)."""
    soup = BeautifulSoup(html_content, "html.parser")

    dates = []
    for header in soup.find_all("div", class_="day-header"):
        date_span = header.find("span", class_="day-header-date")
        if date_span:
            d, m, y = date_span.text.strip().split(".")
            dates.append(f"{y}-{m}-{d}")

    parsed_events = []
    for event in soup.find_all("div", class_="event"):
        style = event.get("style", "")
        left_match = re.search(r"--item-left:\s*([\d.]+)px", style)
        if not left_match:
            continue

        left_px = float(left_match.group(1))
        col_index = round((left_px - COLUMN_OFFSET_PX) / COLUMN_WIDTH_PX)
        if col_index < 0 or col_index >= len(dates):
            continue
        event_date = dates[col_index]

        subject_tag = event.select_one(".time-detail-item-name")
        subject = subject_tag.get_text(separator=" ", strip=True) if subject_tag else "Chưa rõ môn"

        room_tag = event.select_one(".time-detail-item-room")
        room = room_tag.get_text(strip=True) if room_tag else "Chưa rõ phòng"

        teacher_tag = event.select_one(".time-detail-item-teacher div")
        teacher = teacher_tag.get_text(strip=True) if teacher_tag else ""

        period_tag = event.select_one(".time-detail-item-period")
        if not period_tag:
            continue

        time_text = period_tag.get_text(separator=" ", strip=True)
        time_match = re.search(r"(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})", time_text)
        if not time_match:
            continue

        parsed_events.append({
            "subject": f"{subject} ({teacher})" if teacher else subject,
            "room": room,
            "start_time": f"{event_date}T{time_match.group(1)}:00+07:00",
            "end_time": f"{event_date}T{time_match.group(2)}:00+07:00",
        })

    return parsed_events


async def get_schedule(weeks: int = 1, headless: bool = True) -> list[dict]:
    """Tiện ích gộp: cào N tuần rồi bóc tách luôn thành 1 danh sách sự kiện phẳng."""
    htmls = await fetch_weeks_html(weeks=weeks, headless=headless)
    schedule = []
    for html in htmls:
        schedule.extend(parse_weekly_html(html))
    return schedule