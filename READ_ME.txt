Tool python lấy lịch ERP tải lên GG Calendar
By Enlish Hoàng and Gemini Pro :))) vibe code hết mẹ buổi chiều

MÔ TẢ:
    Tool ra đời bản beta vào chiều thứ 2, ngày 14/9/2026 tại trọ riêng nhằm đáp ứng nhu cầu của gen 15 khi muốn sử dụng gg calendar để xem lịch học như hồi B1 24-25
    Đã hoàn thành bản 2.0 chiều 23/9/2026 trên lớp kĩ thuật mô :)))
    Để tối ưu thì mỗi ngành chỉ cần 1 người cài đặt, sau đó tạo lịch chung add mọi người vào rồi chạy code up lên lịch đó là mọi người có thể xem chung
    Hạn chế: có thể gây nhầm lẫn lịch thực hành khi 1 lớp chia ra nhiều nhóm có lịch khác nhau

YÊU CẦU:
    1. Đăng kí API gg calendar trên Google Cloud Console và file credentials.json sau khi đăng kí xong
    2. Trình biên soạn python như VSC hoặc Spyder


CÁC BƯỚC THỰC HIỆN:
    1. Tạo project Google Cloud như ảnh API_ggCloud (dùng mail trường, vào được trang chủ thì vào console chứ ko phải start for free), sau đó lưu file credentials.json vào cùng thư mục tool này
    2. Copy đoạn code sau vào terminal VSC để tải thư viện python:
        
        pip install playwright beautifulsoup4 nest-asyncio google-api-python-client google-auth-httplib2 google-auth-oauthlib
        playwright install chromium
    3. Chạy file login_once.py để lấy dữ liệu phiên đăng nhập erp cho 2 file còn lại. Sau khi đăng nhập hãy vào thời khóa biểu -> lịch tuần, cửa sổ sẽ tự đóng sau đó
    4. Chạy file daily-sync.py hàng ngày để update tuần đó, hoặc weekly-sync.py để update 1 tháng sau đó




