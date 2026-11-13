# Hướng dẫn lấy Cookies X (Twitter) cho twscrape

## QUAN TRỌNG
- Dùng account PHỤ / burner, KHÔNG dùng @L_gaucuhanh
- twscrape chỉ READ (đọc), không post/reply — không ảnh hưởng account chính

## Bước 1: Đăng nhập X bằng account phụ
Mở Chrome, vào https://x.com và đăng nhập bằng account phụ

## Bước 2: Mở DevTools
- Nhấn **F12** (hoặc Ctrl+Shift+I)
- Chọn tab **Application** (hoặc **Storage** trên Firefox)

## Bước 3: Tìm Cookies
- Ở panel bên trái, mở **Cookies** → **https://x.com**
- Tìm 2 cookies này:

| Cookie Name | Ví dụ giá trị |
|-------------|---------------|
| **ct0** | `a1b2c3d4e5f6...` (dài ~160 ký tự) |
| **auth_token** | `abc123def456...` (dài ~40 ký tự) |

## Bước 4: Copy giá trị
- Click vào cookie **ct0** → copy giá trị ở dưới
- Click vào cookie **auth_token** → copy giá trị ở dưới

## Bước 5: Setup twscrape
Mở terminal, chạy:

```
cd E:\Kols\tools
python setup_twscrape.py add <username_acc_phu> <ct0_value> <auth_token_value>
```

Ví dụ:
```
python setup_twscrape.py add myburner123 a1b2c3d4e5f6abc123 xyz789abc456def
```

## Bước 6: Test
```
python setup_twscrape.py test
```
Nếu hiện "Test OK! Found @elonmusk — xxx followers" là thành công.

## Bước 7: Scan KOL posts
```
python kol_scanner.py --top 10
```
Sẽ scan 17 KOLs và hiện top 10 bài hot nhất trong 48h qua.

## Lưu ý
- Cookies hết hạn sau ~1 năm, nhưng có thể bị revoke nếu đổi password
- Nếu bị rate limit, chờ 15 phút rồi thử lại
- Có thể add nhiều account phụ để tăng rate limit
