# fb — màn hình theo dõi bot Facebook (agaubun)

Chỉ đọc file của bot trong `D:\AI\Facebook\agaubun\cheo` (đổi bằng biến `FB_CHEO`),
không đăng, không điều khiển bot. Dùng chung khung `dashkit/`; không import `app/` của X.

Chạy (trong `D:\AI\XKols`): `.venv\Scripts\python.exe -m fb` -> http://127.0.0.1:8788
Mật khẩu: `fb/fb.env`, khóa `FBKOLS_WEB_PASS` (tự sinh lần đầu, không commit).
Cookie `fbk`, cổng 8788 (X dùng `xk`, 8787).

Mục: Tổng quan, Live follower, Lượt chạy, Chi phí AI, Lỗi, Kết bạn, Group & bài.
Số follower: bot ghi `cheo/followers.jsonl`; nhập tay lưu ở `fb/data/` (không commit).
