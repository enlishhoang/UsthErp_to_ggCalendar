#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 14 14:27:31 2026

@author: enlishhoang
"""

import asyncio
import nest_asyncio
from playwright.async_api import async_playwright

# Áp dụng patch cho Spyder để không bị lỗi Event loop
nest_asyncio.apply()

async def manual_login_and_save():
    async with async_playwright() as p:
        # headless=False để hiển thị trình duyệt cho bạn tự bấm
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        print("Đang mở trang Thời khóa biểu...")
        # Nhảy thẳng vào link thời khóa biểu. Nếu chưa đăng nhập, ERP sẽ tự điều hướng sang login.
        await page.goto("https://erp.usth.edu.vn/students/learn/timetable")
        
        print("=====================================================")
        print("VUI LÒNG THỰC HIỆN CÁC BƯỚC SAU TRÊN TRÌNH DUYỆT:")
        print("1. Đăng nhập và vượt qua reCAPTCHA.")
        print("2. Nếu bị đẩy ra trang chủ, hãy tự điều hướng lại vào Thời khóa biểu.")
        print("3. QUAN TRỌNG NHẤT: Bấm chuyển sang 'Lịch tuần'.")
        print("=====================================================")
        print("Code đang chờ tín hiệu của Lịch tuần (tối đa 3 phút)...")

        try:
            # Chờ cho đến khi class .day-header xuất hiện (đây là dấu hiệu độc quyền của Lịch tuần)
            await page.wait_for_selector(".day-header", timeout=180000) # Cho bạn 3 phút để thao tác
            
            print("✅ Đã nhận diện được giao diện Lịch tuần!")
            
            # Chờ thêm 3 giây để hệ thống lưu sở thích của bạn vào LocalStorage/Cookie
            await page.wait_for_timeout(3000)
            
            # Lưu lại toàn bộ trạng thái (Cookie, LocalStorage)
            await context.storage_state(path="usth_session.json")
            print("✅ Đã lưu Session (bao gồm cấu hình Lịch tuần) vào file usth_session.json")
            
        except Exception as e:
            print("❌ Hết thời gian chờ 3 phút hoặc có lỗi:", e)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(manual_login_and_save())