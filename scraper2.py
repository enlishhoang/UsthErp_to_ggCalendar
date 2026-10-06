#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import hashlib
import base64
import json
import datetime
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad, pad
from playwright.async_api import async_playwright
from timetable_parser import extract_sessions

API_URL = "https://erp.usth.edu.vn/student-services/api/v2/timetables/query-student-timetable-in-range"
PROFILE_DIR = "chrome_profile"

APP_KEY = b"304c7f6dff373663d32879ac1c1f1318"
APP_IV = b"069635c0806598e069583aee5440e448"

class SessionExpiredError(Exception): pass

def get_aes_cipher():
    key = hashlib.sha256(APP_KEY).digest()
    iv = hashlib.md5(APP_IV).digest()
    return AES.new(key, AES.MODE_CBC, iv)

def decrypt_payload(encrypted_payload: str) -> list:
    cipher = get_aes_cipher()
    encrypted_data = base64.b64decode(encrypted_payload)
    decrypted_data = unpad(cipher.decrypt(encrypted_data), AES.block_size)
    return json.loads(decrypted_data.decode('utf-8'))

def encrypt_payload(data: dict) -> str:
    cipher = get_aes_cipher()
    json_data = json.dumps(data, separators=(',', ':')).encode('utf-8')
    encrypted = cipher.encrypt(pad(json_data, AES.block_size))
    return base64.b64encode(encrypted).decode('utf-8')

def generate_checksum(payload_dict: dict) -> str:
    """Tạo mã xác thực x-check-sum bắt buộc của ERP"""
    filtered = {k: v for k, v in payload_dict.items() if v is not None and not isinstance(v, (dict, list))}
    sorted_filtered = {k: filtered[k] for k in sorted(filtered.keys())}
    json_str = json.dumps(sorted_filtered, separators=(',', ':'))
    return hashlib.sha256(json_str.encode('utf-8')).hexdigest()

async def get_schedule(from_time_ms: int, to_time_ms: int, headless: bool = True) -> list[dict]:
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(PROFILE_DIR, headless=False)
        
        # 1. Lấy thông tin kỳ học hiện tại
        sem_resp = await context.request.get("https://erp.usth.edu.vn/student-services/api/v1/semesters/current")
        current_semester = None
        if sem_resp.ok:
            sem_data = await sem_resp.json()
            # Web dùng thẳng object trả về (có trường "semester"), không bọc trong "data"
            if isinstance(sem_data, dict):
                current_semester = sem_data.get("semester") or (sem_data.get("data") or {}).get("semester")

        body = {"fromTime": from_time_ms, "toTime": to_time_ms}
        if current_semester:
            body["semester"] = current_semester
            
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-check-sum": generate_checksum(body)
        }
        
        # 2. Bắn Request kèm Payload AES + Header Checksum
        response = await context.request.post(
            API_URL,
            headers=headers,
            data={"payload": encrypt_payload(body)}
        )
        
        if not response.ok:
            text = await response.text()
            await context.close()
            if response.status in (401, 403):
                raise SessionExpiredError(f"HTTP {response.status}: {text[:300]}")
            raise RuntimeError(f"HTTP {response.status} (không phải lỗi session): {text[:300]}")

        raw_response = await response.json()
        await context.close()

        if not isinstance(raw_response, dict) or "payload" not in raw_response:
            raise SessionExpiredError(f"Không có 'payload' trong response: {str(raw_response)[:300]}")
            
        timetable_data = decrypt_payload(raw_response["payload"])

        return extract_sessions(timetable_data, from_time_ms, to_time_ms)
