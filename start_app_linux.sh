#!/bin/bash

# Đảm bảo script luôn chạy từ thư mục chứa nó (dù bạn gọi nó từ đâu)
cd "$(dirname "$0")"

echo "Đang thiết lập môi trường cho Linux / macOS..."

# Kiểm tra và tạo môi trường ảo nếu chưa có
if [ ! -d "venv" ]; then
    echo "Đang tạo môi trường ảo (venv)..."
    python3 -m venv venv
    
    # Báo lỗi nếu thiếu package venv trên Ubuntu/Pop!_OS
    if [ $? -ne 0 ]; then
        echo "Lỗi: Không thể tạo venv. Hãy chạy lệnh sau trên terminal rồi thử lại:"
        echo "sudo apt install python3-venv"
        exit 1
    fi
fi

# Kích hoạt môi trường ảo
source venv/bin/activate

echo "Đang cài đặt các thư viện Python..."
pip install -r requirements.txt

echo "Đang tải trình duyệt Chromium cho Playwright..."
# Trên Linux/macOS, Playwright tải rất ổn định nên không cần cài thủ công như Windows
playwright install chromium

echo ""
echo "==================================================="
echo "Đang khởi động Web App (Bảng điều khiển)..."
echo "==================================================="
python app.py