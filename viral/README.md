# viral — tìm video đang lên nhanh trên X

Làm cho trang Facebook agaubun: **chỉ tìm và liệt kê**. Không tải video, không
đăng gì, không đụng vào account chính @macropandaX. Phần làm lại bản tiếng Việt
và đăng là việc bên agaubun.

## Chạy một lượt quét

```
cd D:\AI\XKols
.venv\Scripts\python.exe -m viral
```

In ra số video thấy được, thêm mới bao nhiêu, cập nhật bao nhiêu. Mỗi lượt lấy
**5 video mới** (chủ dự án chốt 21/11).

## File danh sách

`D:\AI\XKols\viral\videos.json` — bên agaubun đọc thẳng file này.

```json
{"updated": "2026-11-21 15:00",
 "videos": [
   {"url": "https://x.com/.../status/...",   // khoá chống trùng
    "author": "@ten", "author_followers": 1839266,
    "posted_at": "2026-11-21 04:27", "age_min": 631, "duration_sec": 119,
    "views": 2162351, "likes": 22952, "reposts": 2792, "replies": 674,
    "topic": "công nghệ",
    "desc": "mô tả 1 dòng tiếng Việt",
    "has_speech": true,          // true: cần phụ đề · false: chỉ cần hook
    "thumbnail": "https://pbs.twimg.com/...",
    "heat": 205612,              // điểm nóng để xếp hạng
    "seen": [["2026-11-21 14:56", 2162351]],   // mốc view mỗi lần quét
    "status": "moi",             // moi | da_chon | da_lam | bo
    "status_at": "2026-11-21 15:02"}
 ]}
```

`seen` là cách đo **tốc độ tăng thật**: lần quét đầu chỉ biết view/giờ tính từ
lúc đăng, từ lần thứ hai mới biết video còn đang lên hay đã nguội. Trang 8788
hiển thị số đó ở cột "tăng ... view/giờ".

Video đã có trong file thì lượt quét sau **không ghi đè** `status` và `desc` —
bên agaubun sửa tay được mà không sợ mất.

## Lọc cái gì

Chủ dự án chốt 21/11: **lấy hết**, chỉ chặn bốn nhóm — chính trị, bạo lực,
người lớn, quảng cáo tiền số. Hai lưới lọc chồng lên nhau:

1. **Từ khoá** (`scan.BAN`) — nhanh, nhưng chỉ bắt được tiếng Anh.
2. **Model đọc lại cả mẻ** — lượt quét đầu 21/11 lọt một clip nổ súng ở Mexico
   (chữ tiếng Tây Ban Nha) và một video của @WhiteHouse mà từ khoá không bắt
   được. Model loại cái nào thì lấy bù cái sau, nên mỗi lượt vẫn đủ 5 video
   dùng được.

Thêm một danh sách tài khoản chặn thẳng (`scan.BAN_ACCOUNTS`).

Ngưỡng khác: video dưới 20.000 view hoặc đăng quá 48 giờ thì bỏ.

## Hiển thị

Chỉ trên trang theo dõi Facebook **cổng 8788**, tab **Video viral X**. Trang X
(8787) không có gì thay đổi.

Lọc theo chủ đề và trạng thái, bấm nút đổi trạng thái là ghi ngược vào
`videos.json` ngay. Code tab nằm ở `fb/viral_view.py`.

## Chạy định kỳ

Do **bot Facebook** giữ, không phải bot X: tiến trình `python -m fb` (trang
8788) kiểm mỗi 5 phút, đến giờ thì quét. Hai lượt mỗi ngày, 09:00 và 20:00 —
đổi ở `scan.HOURS`. Không dùng Task Scheduler của Windows, không dùng
scheduler của Claude.

Chủ dự án chốt 21/11: phần video viral thuộc về bên Facebook, nên lịch và logic
đều nằm bên đó. Bot X bật hay tắt không ảnh hưởng.

Quét chạy trong thread riêng (một lượt mất 20-40 giây) và có khoá chống chồng
lượt. Lỗi quét được nuốt tại chỗ, trang 8788 không chết theo.

Mốc lượt cuối ghi ra `viral/.last_scan` chứ không giữ trong bộ nhớ: tiến trình
khởi động lại thì mỗi lần bật lại sẽ quét thêm một lượt thừa.

Chạy tay một lượt bất cứ lúc nào vẫn được bằng `python -m viral` — nó không
xét giờ, quét ngay.

Chạy quá dày không có lợi: acc phụ twscrape có hạn mức request, và video cần
thời gian mới thấy được đà tăng.
