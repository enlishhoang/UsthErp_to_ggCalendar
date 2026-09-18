#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 14 14:28:13 2026

@author: enlishhoang
"""

import asyncio
import nest_asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from gcal_manager import sync_to_google_calendar # Import hàm từ file gcal_manager.py

nest_asyncio.apply()

async def get_timetable_data():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="usth_session.json")
        page = await context.new_page()

        print("Đang truy cập ERP để lấy lịch...")
        await page.goto("https://erp.usth.edu.vn/students/learn/timetable")
        
        try:
            # Vẫn phải giữ lệnh chờ này để đảm bảo khung lịch tuần đã load lên
            await page.wait_for_selector(".day-header", timeout=15000)
            
            # Đợi thêm 3 giây để JS từ server đổ dữ liệu môn học vào khung
            await page.wait_for_timeout(3000) 
        except Exception as e:
            print("Lỗi khi chờ load trang:", e)

        # Cào HTML
        html_content = await page.content()
        
        # TÍNH NĂNG MỚI: LƯU HTML RA FILE ĐỂ KIỂM TRA
        with open("debug_page.html", "w", encoding="utf-8") as file:
            file.write(html_content)
        print("Đã lưu toàn bộ mã HTML vào file 'debug_page.html'.")

        await page.screenshot(path="debug_timetable.png")
        await browser.close()
        return html_content

def parse_weekly_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    dates = []
    
    # Lấy ngày tháng từ Header
    date_headers = soup.find_all('div', class_='day-header')
    for header in date_headers:
        date_span = header.find('span', class_='day-header-date')
        if date_span:
            d, m, y = date_span.text.strip().split('.')
            dates.append(f"{y}-{m}-{d}")
            
    parsed_events = []
    events = soup.find_all('div', class_='event')
    
    for event in events:
        style = event.get('style', '')
        left_match = re.search(r'--item-left:\s*([\d\.]+)px', style)
        
        if not left_match:
            continue
            
        left_px = float(left_match.group(1))
        col_index = round((left_px - 4) / 206)
        
        if col_index < 0 or col_index >= len(dates):
            continue
            
        event_date = dates[col_index]
        
        subject_tag = event.select_one('.time-detail-item-name')
        subject = subject_tag.get_text(separator=' ', strip=True) if subject_tag else "Chưa rõ môn"
        
        room_tag = event.select_one('.time-detail-item-room')
        room = room_tag.get_text(strip=True) if room_tag else "Chưa rõ phòng"
        
        teacher_tag = event.select_one('.time-detail-item-teacher div')
        teacher = teacher_tag.get_text(strip=True) if teacher_tag else ""
        
        period_tag = event.select_one('.time-detail-item-period')
        if period_tag:
            time_text = period_tag.get_text(separator=' ', strip=True)
            time_match = re.search(r'(\d{2}:\d{2})\s*-\s*(\d{2}:\d{2})', time_text)
            
            if time_match:
                start_time = f"{event_date}T{time_match.group(1)}:00+07:00"
                end_time = f"{event_date}T{time_match.group(2)}:00+07:00"
                
                parsed_events.append({
                    'subject': f"{subject} ({teacher})" if teacher else subject,
                    'room': room,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
    return parsed_events

async def main():
    # 1. Bật trình duyệt ngầm cào HTML
    html_source = await get_timetable_data()
    
    # 2. Đưa HTML vào hàm bóc tách
    my_schedule = parse_weekly_html(html_source)
    print(f"Bóc tách thành công {len(my_schedule)} môn học.")
    
    # 3. Đẩy lên Google Calendar
    if my_schedule:
        sync_to_google_calendar(my_schedule)
    else:
        print("Không tìm thấy môn học nào hoặc lỗi HTML.")

if __name__ == "__main__":
    asyncio.run(main())