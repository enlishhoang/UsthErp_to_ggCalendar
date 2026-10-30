#!/bin/bash
echo "========================================================"
echo "TOOL CAI DAT MOI TRUONG ERP USTH (GLOBAL TREN MACOS)"
echo "========================================================"
echo ""

# Chuyển hướng Terminal về đúng thư mục chứa file chạy
cd "$(dirname "$0")"

# 1. Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "[1/2] Khong tim thay Python3."
    echo "He thong se tu dong yeu cau cai dat Command Line Tools cua Apple."
    echo "-> Vui long nhan 'Install' tren cua so popup hien ra."
    echo "-> Sau khi Apple cai dat xong, hay mo lai file nay!"
    python3 --version
    exit 1
else
    echo "[1/2] Python3 da san sang tren may."
fi

echo ""
echo "[2/2] Dang tai va cai dat thu vien..."
# Dùng || để fallback: Nếu pip bản cũ không hiểu cờ break-system-packages thì chạy lệnh pip bình thường
python3 -m pip install --upgrade pip --break-system-packages 2>/dev/null || python3 -m pip install --upgrade pip
python3 -m pip install -r V4requirements.txt --break-system-packages 2>/dev/null || python3 -m pip install -r V4requirements.txt


echo ""
echo "========================================================"
echo "CAI DAT HOAN TAT!"
echo "Bay gio ban co the chay tool bang lenh: python3 app.py"
echo "========================================================"
echo ""
read -p "Nhan Enter de dong cua so nay..."