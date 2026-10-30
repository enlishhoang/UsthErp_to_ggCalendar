@echo off
title Cai dat moi truong Tool ERP USTH (Global) - Python 3.13
echo ========================================================
echo TOOL CAI DAT PYTHON 3.13, PATH VA THU VIEN TU DONG
echo ========================================================
echo.

:: 1. Kiem tra Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [1/3] Khong tim thay Python. Dang tai Python 3.13.0 tu trang chu...
    curl -# -o python_installer.exe https://www.python.org/ftp/python/3.13.0/python-3.13.0-amd64.exe
    
    echo [2/3] Dang cai dat Python va tu dong them vao PATH...
    :: PrependPath=1 tu dong them Python vao bien moi truong PATH
    :: InstallAllUsers=0 de cai truc tiep cho user hien tai, khong can chay as Admin
    start /wait python_installer.exe /quiet InstallAllUsers=0 PrependPath=1 Include_pip=1 Include_test=0
    
    echo Xoa file cai dat rac...
    del python_installer.exe
) else (
    echo [1/3] Python da duoc cai dat san tren may.
    echo [2/3] Bo qua buoc cai dat Python.
)

echo.
echo [3/3] Dang tai va cai dat cac thu vien (Global)...
:: Su dung 'py -m' de luon goi dung ban Python vua cai ma khong bi vuong loi PATH
py -m pip install --upgrade pip
py -m pip install flask requests pycryptodome tzdata google-api-python-client google-auth-httplib2 google-auth-oauthlib

echo.
echo ========================================================
echo CAI DAT HOAN TAT!
echo Bay gio ban co the chay tool bang lenh: py sync_auto.py
echo ========================================================
pause