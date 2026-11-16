# Hướng dẫn thêm acc phụ cho twscrape

## QUAN TRỌNG
- Dùng account **PHỤ / burner**, KHÔNG dùng @macropandaX
- twscrape chỉ **READ** (đọc), không post/reply — không ảnh hưởng account chính
- Mỗi acc phụ thêm vào là **một suất hạn mức nữa**. twscrape tự xoay sang acc
  còn rảnh khi acc đang dùng chạm limit, không cần sửa code gì thêm.

## Vì sao cần acc thứ hai (ghi 15/11)
Một acc phụ không đủ nữa. Danh sách đối tượng đã lên 48 handle = 4 request mỗi
vòng quét, cộng quét following và quét mention. Log ngày 15/11 dính
`No account available for queue "SearchTimeline"` nhiều lần trong một tối, mỗi
lần app phải ngồi chờ 4-5 phút. Thêm acc thứ hai là cách gỡ trực tiếp.

## Bước 1: Đăng nhập X bằng acc phụ MỚI
Mở Chrome (nên dùng cửa sổ ẩn danh hoặc profile khác để không đá văng phiên
của acc phụ cũ), vào https://x.com và đăng nhập.

## Bước 2: Mở DevTools
- Nhấn **F12** (hoặc Ctrl+Shift+I)
- Chọn tab **Application**

## Bước 3: Tìm Cookies
- Panel bên trái: **Cookies** → **https://x.com**
- Tìm 2 cookie này:

| Cookie Name | Ví dụ giá trị |
|-------------|---------------|
| **ct0** | `a1b2c3d4e5f6...` (dài ~160 ký tự) |
| **auth_token** | `abc123def456...` (dài ~40 ký tự) |

## Bước 4: Điền vào file, không gõ vào lệnh
Mở `tools/x_account2.env` (đã tạo sẵn, để trống) và điền ba dòng:

```
X_USERNAME=ten_acc_phu_2
X_CT0=<dán ct0>
X_AUTH_TOKEN=<dán auth_token>
```

Vì sao dùng file chứ không gõ tham số: cookie dán vào dòng lệnh thì nằm lại
trong lịch sử shell (PowerShell ghi ra đĩa), mà cookie là chìa khóa vào thẳng
tài khoản. File `*.env` đã nằm trong .gitignore. **Đừng dán vào chat.**

Acc thứ ba, thứ tư: chép thành `x_account3.env`, `x_account4.env`...

## Bước 5: Nạp vào kho rồi kiểm tra
```
cd D:\AI\XKols
.\.venv\Scripts\python.exe tools\setup_from_env.py
```
Lệnh này đọc mọi file `x_account*.env`, nạp acc mới, bỏ qua acc đã có, rồi in
ra kho hiện có mấy acc và chạy một lệnh đọc thử.

## Bước 6: Khởi động lại app
App đọc kho acc lúc chạy, nên phải khởi động lại mới dùng acc mới.

## Lưu ý
- Cookie hết hạn sau khoảng 1 năm, nhưng **bị huỷ ngay nếu đổi mật khẩu** acc đó.
- Hai acc phụ chạy chung một IP thì X có thể nhận ra là cùng một người. Rủi ro
  là acc phụ bị khoá — không mất gì về nội dung, nhưng phải lấy cookie acc khác.
- File `twscrape_accounts.db` đã nằm trong .gitignore (`*.db`), đừng commit.
- Bị rate limit thì app tự chờ rồi chạy tiếp, không chết.

## Quét thử bằng tay
```
.\.venv\Scripts\python.exe tools\kol_scanner.py --top 10 --minutes 360
```
Mốc tính bằng **phút** (`--minutes`), không phải giờ.
