# USTH ERP → Google Calendar

Tool lấy lịch học từ ERP và tải lên Google Calendar, hiện được đóng gói dưới dạng **extension cho Chrome và Firefox**.

> By **Enlish Hoàng**, Gemini Pro và Claude :>> *(vibe code hết mấy buổi chiều)*

---

## Mô tả

- Tool ra đời bản beta vào chiều thứ Hai, ngày 14/9/2026 tại trọ riêng, nhằm đáp ứng nhu cầu của gen 15 khi muốn sử dụng Google Calendar để xem lịch học như hồi B1 24-25.
- Hướng dẫn cài đặt ở dưới cùng

## Development Timeline 

### V2.0 — chiều 23/9/2026 (trên lớp Kỹ thuật mô :)))
- Chuyển sang đăng nhập ERP bằng Gmail để lưu đăng nhập lâu dài.
- Thêm tính năng chọn thủ công số tuần muốn đồng bộ.
- Sử dụng trình duyệt để xem và lấy lịch qua giao diện ERP.

### V3.0 — chiều 24/9/2026 (trên lớp Công nghệ sinh học y học của BMS :)))))
- Thêm tính năng sync tuần cũ cho người mới.
- Sử dụng giải mã của ERP để lấy lịch trực tiếp từ nguồn ERP, không cần qua giao diện.
- Cấu hình để setup chạy tự động cho bản sau:
  - `sync_auto.py`: có thể cài cho hệ thống chạy tự động mỗi ngày vào một khoảng thời gian.
    - Mặc định sync 2 tuần vào lịch cá nhân mặc định.
    - Điểm trừ: dựa vào tiết học nên có thể lệch giờ thi.
  - `sync.py`: chạy thủ công vì sẽ hỏi thêm thông tin, nhưng chính xác 100% về thời gian sự kiện.

### V4.0 — sáng 25/9/2026
- Thêm giao diện web app host ở local để dễ sử dụng.

### V5.0 — lúc 1 rưỡi sáng 26/9/2026 🤡
- Kết hợp V3 và V4.
- Đã test thành công trên Mac.
- **V5.1 (30/9/2026):** sửa lỗi hiện trình duyệt và tiến trình; sửa lại file chạy cho Windows.

### V6.0 — 12/10/2026
- Chuyển tool thành **extension cho Chrome và Firefox** (đã được Mozilla sign).
- **V6.1 (14/10/2026):** cài đặt cấp quyền qua OAuth duy nhất của nhà phát triển, người dùng không phải tự khai báo OAuth nữa.
- chuyển các phiên bản cũ vào branch Legacy của repo này 

## ⚠️ Hạn chế

- Có thể gây nhầm lẫn lịch thực hành khi một lớp chia ra nhiều nhóm có lịch khác nhau.

---

## 🛠️ Các bước thực hiện cài đặt

### Chuẩn bị

1. Tải về máy: <>Code -> Download ZIP -> giải nén. Hoặc vào mục Releases -> click vào bản tương ứng với trình duyệt đang dùng
2. Có sẵn tài khoản Google (dùng để tải lịch lên Google Calendar) và tài khoản ERP.

### Cài đặt trên Google Chrome (và các trình duyệt nhân Chromium: Edge, Brave, Cốc Cốc...) *temporary

1. Mở Chrome, truy cập địa chỉ `chrome://extensions`.
2. Bật **Chế độ dành cho nhà phát triển** (*Developer mode*) ở góc trên bên phải.
3. Nhấn **Tải tiện ích đã giải nén** (*Load unpacked*).
4. Chọn thư mục `Source code`.
5. Extension xuất hiện trong danh sách. Nhấn biểu tượng 🧩 trên thanh công cụ và **ghim** extension để dễ truy cập.

### Cài đặt trên Mozilla Firefox

1. Tải file `FireFox_ErpCalendarV6.1.xpi` về máy.
2. Mở Firefox, truy cập địa chỉ `about:addons`.
3. Nhấn biểu tượng bánh răng ⚙️ → chọn **Install Add-on From File...** (*Cài đặt tiện ích từ tệp*).
4. Chọn file `FireFox_ErpCalendarV6.1.xpi` vừa tải, nhấn **Add** (*Thêm*) để xác nhận.
5. Nhấn biểu tượng 🧩 trên thanh công cụ và ghim extension nếu cần.

> 💡 Cách nhanh hơn: mở file `.xpi` trực tiếp trong Firefox (kéo thả file vào cửa sổ trình duyệt), Firefox sẽ tự hỏi cài đặt.

### Sử dụng lần đầu

1. Đăng nhập **ERP** bằng Gmail trên trình duyệt như bình thường.
2. Mở extension và chọn số tuần muốn đồng bộ (tuần cũ và tuần sắp tới) và lịch đích (lịch mặc định hoặc lịch khác). 
3. Nhấn **Đồng bộ** -> chọn tài khoản Google muốn tải lịch lên → **Cho phép** (cấp quyền truy cập Google Calendar).
4. Quay lại, kiểm tra kết quả trên [Google Calendar](https://calendar.google.com).

### ❓ Xử lý sự cố thường gặp

| Vấn đề | Cách xử lý |
| --- | --- |
| Chrome báo "Manifest file is missing or unreadable" | Chọn đúng thư mục chứa file `manifest.json`, không phải thư mục cha. |
| Firefox báo extension "chưa được xác minh" | Dùng đúng file `.xpi` đã được Mozilla sign. |
| Không lấy được lịch / hết phiên | Đăng nhập lại ERP rồi thử đồng bộ lại. |
| Không đăng nhập được Google | Kiểm tra trình duyệt không chặn cửa sổ bật lên (pop-up) và thử lại. |