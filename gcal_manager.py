#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Sep 14 14:45:50 2026

@author: enlishhoang
"""

import os.path
import datetime
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Quyền truy cập: Cho phép đọc và ghi vào Lịch
SCOPES = ['https://www.googleapis.com/auth/calendar']
TIMEZONE = 'Asia/Ho_Chi_Minh'

def get_calendar_service():
    creds = None
    # Token.json lưu trữ thông tin xác thực sau lần đăng nhập đầu tiên
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    # Nếu chưa có token hoặc token hết hạn, mở trình duyệt để xác thực lại
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # File này bạn vừa tải từ Google Cloud
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Lưu lại để lần sau chạy ngầm không cần trình duyệt
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return build('calendar', 'v3', credentials=creds)

def sync_to_google_calendar(schedule_data):
    service = get_calendar_service()
    
    # Lấy mốc thời gian hiện tại
    now_utc_str = datetime.datetime.utcnow().isoformat() + 'Z' 
    now_timestamp = datetime.datetime.now().timestamp()
    
    print("Đang dọn dẹp lịch cũ do tool tạo (từ thời điểm hiện tại)...")
    events_result = service.events().list(
        calendarId='primary', timeMin=now_utc_str, 
        q='[Auto-Synced-ERP]', 
        singleEvents=True).execute()
    events = events_result.get('items', [])

    for event in events:
        service.events().delete(calendarId='primary', eventId=event['id']).execute()
        print(f"Đã xóa lịch cũ: {event.get('summary')}")

    print("Đang lọc và đẩy lịch tương lai lên...")
    for item in schedule_data:
        # Chuyển chuỗi thời gian của môn học thành timestamp Unix để đối chiếu
        event_time = datetime.datetime.fromisoformat(item['start_time'])
        
        # Chỉ đẩy dữ liệu lên API nếu thời gian bắt đầu lớn hơn hiện tại
        if event_time.timestamp() > now_timestamp:
            event = {
              'summary': item['subject'],
              'location': item['room'],
              'description': '[Auto-Synced-ERP] Lịch học được tự động đồng bộ từ ERP.',
              'start': {
                'dateTime': item['start_time'],
                'timeZone': TIMEZONE,
              },
              'end': {
                'dateTime': item['end_time'],
                'timeZone': TIMEZONE,
              },
            }
            service.events().insert(calendarId='primary', body=event).execute()
            print(f"Đã thêm mới: {item['subject']}")
        else:
            print(f"Bỏ qua lịch quá khứ: {item['subject']}")
