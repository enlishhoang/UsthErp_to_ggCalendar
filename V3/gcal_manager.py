#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gcal_manager.py
Quản lý kết nối Google Calendar API (OAuth2) và logic đồng bộ sự kiện.
"""

import datetime
import logging
import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]
TIMEZONE = "Asia/Ho_Chi_Minh"
SYNC_TAG = "[Auto-Synced-ERP]"

log = logging.getLogger("usth-sync.gcal")

def get_calendar_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    return build("calendar", "v3", credentials=creds)

def sync_to_google_calendar(schedule_data: list[dict], time_min_iso: str, time_max_iso: str, calendar_id: str = 'primary') -> None:
    service = get_calendar_service()

    log.info("Đang dọn dẹp lịch cũ trong VÙNG THỜI GIAN CHỈ ĐỊNH...")
    # Chỉ khoanh vùng xóa sự kiện trong khoảng thời gian đã tính toán
    events_result = service.events().list(
        calendarId=calendar_id,
        timeMin=time_min_iso,
        timeMax=time_max_iso,
        q=SYNC_TAG,
        singleEvents=True,
    ).execute()

    for event in events_result.get("items", []):
        service.events().delete(calendarId=calendar_id, eventId=event["id"]).execute()
        log.info("Đã xóa lịch cũ: %s", event.get("summary"))

    log.info("Đang đẩy lịch lên (bao gồm cả lịch quá khứ nếu có trong vùng quét)...")
    added = 0
    for item in schedule_data:
        event = {
            "summary": item["subject"],
            "location": item["room"],
            "description": f"{SYNC_TAG} Lịch học được tự động đồng bộ từ ERP.",
            "start": {"dateTime": item["start_time"], "timeZone": TIMEZONE},
            "end": {"dateTime": item["end_time"], "timeZone": TIMEZONE},
        }
        service.events().insert(calendarId=calendar_id, body=event).execute()
        added += 1

    log.info("Hoàn tất: Cập nhật thành công %d sự kiện mới.", added)