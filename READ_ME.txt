Tool python lấy lịch ERP tải lên GG Calendar
By Enlish Hoàng and Gemini Pro and Claude :>> vibe code hết mấy buổi chiều

MÔ TẢ:
    Tool ra đời bản beta vào chiều thứ 2, ngày 14/9/2026 tại trọ riêng nhằm đáp ứng nhu cầu của gen 15 khi muốn sử dụng gg calendar để xem lịch học như hồi B1 24-25
    
    Đã hoàn thành bản 2.0 chiều 23/9/2026 trên lớp kĩ thuật mô :)))
        Chuyển sang đăng nhập ERP bằng gmail để lưu đăng nhập lâu dàimới
        Thêm tính năng chọn thủ công số tuần muốn đồng bộ nguồn
        Sử dụng trình duyệt để xem và lấy lịch qua giao diện Erp
    
    Hoàn thành bản 3.0 chiều 24/09/2026 trên lớp công nghệ sinh học y học của bms :)))))
        Thêm tính năng sync tuần cũ cho người mới
        Sử dụng giải mã hóa của Erp để lấy lịch trực tiếp từ nguồn Erp không cần qua giao diện
        Cấu hình để setup chạy tự động cho bản sau: 
            sync_auto.py có thể cài cho hệ thống chạy tự động mỗi ngày vào 1 khoảng thời gian: 
                mặc định sync 2 tuần vào lịch cá nhân mặc định
                điểm trừ là dựa vào tiết nên có thể lệch giờ thi
            sync.py chạy thủ công vì sẽ hỏi thêm thông tin nhưng chính xác kiện 100% về thời gian sự kiện
        
    Để tối ưu thì mỗi ngành chỉ cần 1 người cài đặt, sau đó tạo lịch chung add mọi người vào rồi chạy code up lên lịch đó là mọi người có thể xem chung
    Hạn chế: có thể gây nhầm lẫn lịch thực hành khi 1 lớp chia ra nhiều nhóm có lịch khác nhau

YÊU CẦU:
    1. Đăng kí API gg calendar trên Google Cloud Console và file credentials.json sau khi đăng kí xong
    2. Trình biên soạn python như VSCode (có cài extension python, python environment) hoặc Spyder
    3. Cài đặt python và pip: https://www.python.org/downloads/
    4. Thêm path python vào environment


CÁC BƯỚC THỰC HIỆN CÀI ĐẶT:
    1. Tải zip và giải nén thư mục vào vị trí mong muốn
    2. Tạo project Google Cloud như hướng dẫn trong 2 ảnh API_ggCloud (dùng mail mà bạn muốn import lịch), sau đó lưu file credentials.json vào cùng thư mục tool này
    3. Mở VSC, open folder -> thư mục đã giải nén -> select folder. New Terminal
    4. Phím window -> search Edit system environment variables -> Environment variables 
        Ở user variables tìm dòng Path -> edit -> new. Paste đường dẫn vào python: C:\Users\TIEN ANH\AppData\Local\Programs\Python\
        Vào terminal VSC chạy lệnh   pip --version   để check thử
    Copy đoạn code sau vào terminal VSC để tải thư viện python:
        Nếu máy chạy linux/mac thì thêm đoạn sau, window thì bỏ qua:
                python3 -m venv .venv
                source .venv/bin/activate
        Window:
        pip install playwright beautifulsoup4 nest-asyncio google-api-python-client google-auth-httplib2 google-auth-oauthlib pycryptodome
        playwright install chromium

    3. Chạy file login_once.py để lấy dữ liệu phiên đăng nhập erp cho 2 file còn lại. Sau khi đăng nhập hãy vào thời khóa biểu -> lịch tuần, cửa sổ sẽ tự đóng sau đó
    4. Lần đầu chạy file sync.py để chọn số tuần muốn đồng bộ và lịch muốn đồng bộ
    5. Cài đặt cho file sync_auto.py chạy tự động hằng ngày: sẽ cập nhật ở phiên bản sau




