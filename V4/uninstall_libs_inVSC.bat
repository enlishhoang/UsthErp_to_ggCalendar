@echo off
title GO CAI DAT THU VIEN ERP USTH

echo ========================================================
echo TOOL GO CAI DAT THU VIEN ERP USTH (WINDOWS)
echo ========================================================
echo.

cd /d "%~dp0"

echo [1/2] Dang gỡ bỏ trình duyệt Chromium của Playwright (nếu có)...
python -m playwright uninstall --all 2>NUL

echo.
echo [2/2] Dang go cai dat cac thu vien Python...
python -m pip uninstall -y flask requests pycryptodome tzdata google-api-python-client google-auth-httplib2 google-auth-oauthlib nest-asyncio playwright beautifulsoup4

echo.
echo ========================================================
echo GO CAI DAT HOAN TAT!
echo ========================================================
echo.
pause