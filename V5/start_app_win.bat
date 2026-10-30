@echo off
chcp 65001 >nul
title Khoi đong dong bo TKB USTH

:: Đảm bảo script luôn chạy từ thư mục chứa file .bat
cd /d "%~dp0"

:: Kiểm tra và tạo môi trường ảo (venv) nếu chưa có
if not exist ".venv\Scripts\activate.bat" (
    echo Dang tao moi truong ao 
    python -m venv .venv
    if errorlevel 1 (
        echo [Lỗi] Khong the tao moi truong ao. Hay kiem tra xem may da cai Python va tich chon "Add Python to PATH" chua.
        pause
        exit /b 1
    )
)

:: Kích hoạt môi trường ảo
call .venv\Scripts\activate.bat

echo Đang cai đat cac thu vien Python
pip install -r requirements.txt

echo.
echo ===================================================
echo Dang tai trinh duyet Chromium cho Playwright
echo Neu bao loi "timed out", hay đong va chay lai file nay
echo ===================================================
:: Bắt Playwright cài đặt cục bộ vào thư mục hiện tại để né lỗi khoảng trắng đường dẫn
set PLAYWRIGHT_BROWSERS_PATH=0
playwright install chromium

echo.
echo ===================================================
echo Dang khoi đong Bang dieu khien
echo ===================================================
python app.py

pause