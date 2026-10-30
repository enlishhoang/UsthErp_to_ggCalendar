#!/bin/bash
echo "========================================================"
echo "TOOL GO CAI DAT THU VIEN ERP USTH (MACOS / LINUX)"
echo "========================================================"
echo ""

# Chuyển hướng Terminal về đúng thư mục chứa file chạy
cd "$(dirname "$0")"

# 1. Kiểm tra Python
if ! command -v python3 &> /dev/null; then
    echo "Khong tim thay Python3 trên may."
    exit 1
fi

echo "[1/2] Dang gỡ bỏ trình duyệt Chromium của Playwright (nếu có)..."
python3 -m playwright uninstall --all 2>/dev/null

echo ""
echo "[2/2] Dang go cai dat cac thu vien Python..."
# Danh sách thư viện lấy từ requirements.txt và script cài đặt
PACKAGES="flask requests pycryptodome tzdata google-api-python-client google-auth-httplib2 google-auth-oauthlib nest-asyncio playwright beautifulsoup4"

python3 -m pip uninstall -y $PACKAGES --break-system-packages 2>/dev/null || python3 -m pip uninstall -y $PACKAGES

echo ""
echo "========================================================"
echo "GO CAI DAT HOAN TAT!"
echo "========================================================"
echo ""
read -p "Nhan Enter de dong cua so nay..."