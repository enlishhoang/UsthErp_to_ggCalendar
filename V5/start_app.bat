@echo off
chcp 65001 >nul
title Khởi động Đồng bộ TKB USTH

echo Đang cài đặt các thư viện Python...
pip install -r requirements.txt

echo.
echo ===================================================
echo Đang tải trình duyệt Chromium cho Playwright...
echo (Nếu báo lỗi "timed out", hãy đóng và chạy lại file này)
echo ===================================================
:: Bắt Playwright cài đặt cục bộ vào thư mục hiện tại để né lỗi khoảng trắng ở C:\Users\TIEN ANH\
set PLAYWRIGHT_BROWSERS_PATH=0
playwright install chromium

echo.
echo Đang khởi động Web App (Bảng điều khiển)...
python app.py

pause