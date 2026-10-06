@echo off
chcp 65001 >nul
title Khởi động Đồng bộ TKB USTH

:: Đảm bảo script luôn chạy từ thư mục chứa file .bat
cd /d "%~dp0"

:: Kiểm tra và tạo môi trường ảo (venv) nếu chưa có
if not exist "venv\Scripts\activate.bat" (
    echo Đang tạo môi trường ảo (venv)...
    python -m venv venv
    if errorlevel 1 (
        echo [Lỗi] Không thể tạo môi trường ảo. Hãy kiểm tra xem máy đã cài Python và tích chọn "Add Python to PATH" chưa.
        pause
        exit /b 1
    )
)

:: Kích hoạt môi trường ảo
call venv\Scripts\activate.bat

echo Đang cài đặt các thư viện Python...
pip install -r requirements.txt

echo.
echo ===================================================
echo Đang tải trình duyệt Chromium cho Playwright...
echo (Nếu báo lỗi "timed out", hãy đóng và chạy lại file này)
echo ===================================================
:: Bắt Playwright cài đặt cục bộ vào thư mục hiện tại để né lỗi khoảng trắng đường dẫn
set PLAYWRIGHT_BROWSERS_PATH=0
playwright install chromium

echo.
echo ===================================================
echo Đang khởi động Web App (Bảng điều khiển)...
echo ===================================================
python app.py

pause