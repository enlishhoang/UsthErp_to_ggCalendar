import asyncio
import nest_asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
import re
from gcal_manager import sync_to_google_calendar

# Fix lỗi Event Loop cho Spyder
nest_asyncio.apply()

async def get_timetable_data():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state="usth_session.json")
        page = await context.new_page()

        print("Đang truy cập ERP để lấy lịch...")
        await page.goto("https://erp.usth.edu.vn/students/learn/timetable")
        
        all_weeks_html = []
        WEEKS_TO_SCRAPE = 4 # Số tuần bạn muốn cào (tính cả tuần hiện tại)
        
        for i in range(WEEKS_TO_SCRAPE):
            print(f"--- Đang xử lý Tuần {i + 1} ---")
            try:
                # 1. Đợi lưới lịch load xong
                await page.wait_for_selector(".day-header", timeout=15000)
                await page.wait_for_timeout(3000) # Chờ JS đổ dữ liệu môn học
                
                # 2. Cào HTML của tuần hiện tại và lưu vào list
                html_content = await page.content()
                all_weeks_html.append(html_content)
                print(f"Đã lấy xong HTML Tuần {i + 1}.")
                
                # 3. Bấm nút "Next" để sang tuần sau
                if i < WEEKS_TO_SCRAPE - 1:
                    next_btn = page.locator('span[aria-label="right"]')
                    await next_btn.click(force=True)
                    await page.wait_for_timeout(2000) # Đợi web load tuần mới
                    
            except Exception as e:
                print(f"Lỗi ở Tuần {i + 1}: {e}")
                break 

        await browser.close()
        return all_weeks_html

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
    # 1. Lấy danh sách HTML của 4 tuần
    html_sources = await get_timetable_data()
    
    total_schedule = []
    
    # 2. Bóc tách từng tuần và gộp chung vào 1 mảng lớn
    for html in html_sources:
        weekly_schedule = parse_weekly_html(html)
        total_schedule.extend(weekly_schedule)
        
    print(f"Tổng kết: Bóc tách thành công {len(total_schedule)} block môn học cho các tuần tới.")
    
    # 3. Đẩy lên Google Calendar
    if total_schedule:
        sync_to_google_calendar(total_schedule)
    else:
        print("Không tìm thấy môn học nào.")

if __name__ == "__main__":
    asyncio.run(main())