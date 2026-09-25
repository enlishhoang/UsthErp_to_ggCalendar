#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
timetable_parser.py
Biến payload đã giải mã của ERP thành danh sách buổi học phẳng.
Logic bám theo hàm xử lý thời khóa biểu trong JS của web:
  payload = {items: [ {id, courseName, ..., _calendars: [ {day, weeks|week, date, from, to, place, ...} ]} ],
             startSemesterTime, startSemesterWeek, ...}
- Buổi học lặp hằng tuần: date < 0 hoặc có nhiều tuần -> tính ngày từ tuần bắt đầu kỳ + số tuần + thứ.
- Buổi học có ngày cụ thể: dùng luôn `date` (ms).
Cũng chấp nhận dạng phẳng (mỗi phần tử đã là 1 buổi học có `date`).
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

VN = ZoneInfo("Asia/Ho_Chi_Minh")

PERIOD_START = {
    1: "07:30", 2: "08:25", 3: "09:25", 4: "10:25", 5: "11:20",
    6: "13:00", 7: "13:55", 8: "14:55", 9: "15:50", 10: "16:50",
}
PERIOD_END = {
    1: "08:20", 2: "09:15", 3: "10:15", 4: "11:15", 5: "12:10",
    6: "13:50", 7: "14:45", 8: "15:45", 9: "16:40", 10: "17:40",
}

# Trường `day` của ERP: 2..7 = Thứ 2..Thứ 7, 8 (hoặc 1) = Chủ nhật -> số ngày lệch từ Thứ Hai
DAY_OFFSET = {1: 6, 2: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5, 8: 6}


def _parse_weeks(cal: dict) -> list[int]:
    weeks = list(cal.get("weeks") or [])
    if not weeks and cal.get("week"):
        for part in str(cal["week"]).split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                if a.strip().lstrip("-").isdigit() and b.strip().isdigit():
                    weeks.extend(range(int(a), int(b) + 1))
            elif part.isdigit():
                weeks.append(int(part))
    return weeks


def _ms_to_date(ms):
    return datetime.fromtimestamp(ms / 1000, VN).date()


def extract_sessions(payload, from_ms: int, to_ms: int) -> list[dict]:
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("data") or []
        sem_start = payload.get("startSemesterTime") or 0
        sem_week = payload.get("startSemesterWeek") or 0
    else:
        items, sem_start, sem_week = payload or [], 0, 0

    from_d, to_d = _ms_to_date(from_ms), _ms_to_date(to_ms)  # to_d: loại trừ
    sessions, seen = [], set()

    for it in items:
        cals = it.get("_calendars") or it.get("calendars")
        if cals is None:            # dạng phẳng: chính phần tử là buổi học
            course, cals = {}, [it]
        else:
            course = it

        for cal in cals:
            name = (course.get("courseName") or course.get("name")
                    or cal.get("courseName") or cal.get("name") or "Chưa rõ môn")
            teachers = cal.get("teacherNames") or []
            teacher = ", ".join(teachers) if teachers else (course.get("teacherName") or cal.get("teacherName") or "")
            subject = f"{name} ({teacher})" if teacher else name
            room = cal.get("place") or "Chưa rõ phòng"

            p_from, p_to = cal.get("from"), cal.get("to")
            if p_from not in PERIOD_START or p_to not in PERIOD_END:
                continue

            weeks = _parse_weeks(cal)
            date = cal.get("date")
            start = sem_start or cal.get("_startSemesterDate") or 0
            wk0 = sem_week or cal.get("_startSemesterWeek") or 1

            days = []
            if (date is None or date < 0 or len(weeks) > 1) and start:
                off = DAY_OFFSET.get(cal.get("day"))
                if off is None:
                    continue
                base = _ms_to_date(start)
                monday0 = base - timedelta(days=base.weekday())
                days = [monday0 + timedelta(weeks=w - wk0, days=off) for w in weeks]
            elif date and date > 0:
                days = [_ms_to_date(date)]

            for d in days:
                if not (from_d <= d < to_d):
                    continue
                key = (subject, d, p_from, p_to)
                if key in seen:
                    continue
                seen.add(key)
                sessions.append({
                    "subject": subject,
                    "room": room,
                    "start_time": f"{d.isoformat()}T{PERIOD_START[p_from]}:00+07:00",
                    "end_time": f"{d.isoformat()}T{PERIOD_END[p_to]}:00+07:00",
                })

    sessions.sort(key=lambda e: e["start_time"])
    return sessions
