#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_once.py
Chạy 1 lần (hoặc mỗi khi session hết hạn) để đăng nhập thủ công và lưu session.
"""

import asyncio
import nest_asyncio
from playwright.async_api import async_playwright

from scraper import TIMETABLE_URL, PROFILE_DIR

nest_asyncio.apply()


async def manual_login_and_save(profile_dir: str = PROFILE_DIR) -> bool:
    async with async_playwright() as p:
        # launch_persistent_context giữ nguyên 1 profile Chrome thật (cookie, local
        # storage, cache...) giữa các lần chạy — khác với browser.new_context() cũ,
        # vốn tạo trình duyệt "trắng" mỗi lần nên Google luôn coi là thiết bị lạ.
        context = await p.chromium.launch_persistent_context(profile_dir, headless=False)
        page = context.pages[0] if context.pages else await context.new_page()

        print("Đang mở trang Thời khóa biểu...")
        await page.goto(TIMETABLE_URL)

        print("=====================================================")
        print("VUI LÒNG THỰC HIỆN CÁC BƯỚC SAU TRÊN TRÌNH DUYỆT:")
        print("1. Đăng nhập bằng Google và vượt qua reCAPTCHA (nếu có).")
        print("2. Nếu bị đẩy ra trang chủ, hãy tự điều hướng lại vào Thời khóa biểu.")
        print("3. QUAN TRỌNG NHẤT: Bấm chuyển sang 'Lịch tuần'.")
        print("=====================================================")
        print("Code đang chờ tín hiệu của Lịch tuần (tối đa 3 phút)...")

        success = False
        try:
            await page.wait_for_selector(".day-header", timeout=180000)
            print("✅ Đã nhận diện được giao diện Lịch tuần!")
            await page.wait_for_timeout(3000)
            # Không cần export storage_state nữa — profile_dir đã tự lưu mọi thứ.
            success = True
        except Exception as e:
            print("❌ Hết thời gian chờ 3 phút hoặc có lỗi:", e)

        await context.close()
    return success


if __name__ == "__main__":
    asyncio.run(manual_login_and_save())