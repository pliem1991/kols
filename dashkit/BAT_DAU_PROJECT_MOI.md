# Brief: dựng màn hình theo dõi cho project mới (Facebook)

Đưa nguyên file này cho session mới là đủ để bắt đầu.

---

## Bối cảnh

Project `XKols` (`D:\AI\XKols`) là app tự động đăng bài lên X cho tài khoản
`@macropandaX`. Nó có một màn hình theo dõi chạy local, và **phần khung của
màn hình đó đã được tách ra thành package `dashkit`** để project khác dùng lại.

Project Facebook sắp làm **chỉ ghi thông tin để giám sát** — không đăng bài,
không chạy vòng lặp tự động. Nên chỉ dùng lại khung màn hình, không dùng lại
bất cứ thứ gì khác của XKols.

## Lấy code ở đâu

```bash
git clone https://github.com/pliem1991/kols.git
```

Trên máy này đã có sẵn bản checkout tại `D:\AI\XKols`, branch `main`,
commit `bd86504`. Không cần clone lại nếu dùng chung máy.

**Đừng đặt project Facebook bên trong `D:\AI\XKols`.** Đó là repo của app X.
Tạo thư mục riêng, ví dụ `D:\AI\FBKols`, với repo git riêng.

## Cài dashkit vào project mới

```bash
pip install -e D:\AI\XKols
```

Cài kiểu `-e` nên sau này sửa `dashkit/` là bên Facebook ăn theo ngay. Lệnh này
cần mạng (pip phải tải `hatchling` để build).

Không có mạng thì thay bằng một file `.pth` trong `site-packages` của venv mới,
nội dung đúng một dòng:

```
D:\AI\XKols
```

Kiểm tra cài được:

```bash
python -c "import dashkit; print(dashkit.__file__)"
```

## Thêm code vào đâu

| Việc | Chỗ |
|---|---|
| Toàn bộ code của project Facebook | thư mục mới, ví dụ `D:\AI\FBKols\app\` |
| Sửa giao diện chung (CSS, khung, JS khung) | `D:\AI\XKols\dashkit\` |
| Code riêng của X | `D:\AI\XKols\app\` — **đừng đụng vào** |

Quy tắc duy nhất không được phá: **`dashkit/` không bao giờ được `import app`.**
Có test chặn bằng cách đọc AST, xem phần dưới.

## Cách dùng

App nộp cho `dashkit` bốn thứ: danh sách mục bên trái, JS riêng, một hàm trả số
liệu, và một cái cổng mật khẩu.

```python
from datetime import datetime
from pathlib import Path

import dashkit

JS = """
function head(d){                      /* tiêu đề + chip + số đếm trên nhãn */
  return {title: d.page, sub: d.mode,
          chips: '<span class="chip"><b>'+d.now+'</b></span>',
          badges: {bai: d.posts.length}};
}
function v_overview(d){                /* một hàm v_<key> cho mỗi mục nav */
  return '<div class="strip">' + cell('var(--acc)', d.reach, 'lượt tiếp cận')
       + '</div>';
}
function v_bai(d){ return '<div class="card">…</div>'; }
"""


def payload():                         # trang gọi hàm này mỗi 4 giây
    return {"page": "FBKols", "mode": "theo dõi", "now": "10:32",
            "reach": 1234, "posts": [...]}


dash = dashkit.Dash(
    name="FBKols", icon="F",
    nav=[dashkit.Nav("overview", "Tổng quan"),
         dashkit.Nav("bai", "Bài đăng", badge=True)],
    app_js=JS,
    state=payload,
    gate=dashkit.Gate(env_file=Path("tools/web.env"),
                      token_key="FBKOLS_WEB_TOKEN",
                      pass_key="FBKOLS_WEB_PASS",
                      now=lambda: datetime.now(),
                      cookie="fb"),      # PHẢI khác "xk" của X
    port=8788,                           # PHẢI khác 8787 của X
)
print(dashkit.serve(dash))
```

Lần chạy đầu `Gate` tự sinh mật khẩu rồi ghi vào `env_file`; in ra log mà dùng.
Đổi mật khẩu thì sửa file đó rồi khởi động lại.

Thêm nút bấm:

```python
dash.posts["/api/lam-moi"] = lambda q: {"ok": True}
```

JS gọi `fetch('/api/lam-moi', {method:'POST'})` rồi `load()`. Hàm nhận query đã
parse (`dict[str, list[str]]`), trả dict là xong; trả `{"ok": False, "why": ...}`
thì server tự trả HTTP 400.

CSS có sẵn: `card` `chead` `sub` `strip` `cell` `duo` `chip` `nav` `bars`
`legend` `danger` `note` `ok` `no` `warn`. Màu lấy qua biến `var(--acc)`
`var(--ok)` `var(--no)` `var(--warn)` `var(--mut)` `var(--line)`.

## Ba chỗ dễ sai

**Tên cookie phải khác.** Trình duyệt không phân biệt cookie theo cổng: hai
trang cùng ở `127.0.0.1` khác cổng vẫn chung một hũ cookie. X dùng `xk`. Trùng
tên là đăng nhập trang Facebook làm đăng xuất trang X, mà triệu chứng nhìn rất
khó đoán.

**Cổng phải khác.** X giữ 8787. `Server` cố ý tắt `SO_REUSEADDR` vì trên Windows
cờ đó cho hai tiến trình bind cùng một cổng mà không báo lỗi, rồi request đi lung
tung giữa hai bên.

**`env_file` đừng nằm trong thư mục phục vụ ra web.** `/img` phục vụ mọi file
trong `image_root`; để file bí mật ở đó là tự đưa chìa khóa qua cửa sổ.

## Test

```bash
python D:\AI\XKols\tools\test_dashkit.py
```

Chạy được một mình, không cần `app/`, không cần API key — đó chính là bằng chứng
`dashkit` độc lập. Nó kiểm cả ranh giới: đọc AST từng file trong `dashkit/`, thấy
`import app` là báo đỏ.

**Nếu sửa `dashkit/` thì phải chạy thêm test của app X**, vì trang X đang dùng
chung khung đó:

```bash
cd D:\AI\XKols && PYTHONIOENCODING=utf-8 .\.venv\Scripts\python.exe tools\test_app.py
```

(Biến `PYTHONIOENCODING=utf-8` là bắt buộc trên máy này — console mặc định cp1252,
không in được tiếng Việt và sẽ `UnicodeEncodeError`.)

## Những thứ KHÔNG dùng lại từ XKols

Đã cân nhắc và loại: `brain.py` (soạn nội dung), `x_browser.py` (Playwright),
`scan.py` / `targets.py` (quét KOL), `payout.py` / `stats.py` (payout của X),
`market.py` / `chart.py` (giá crypto). Project Facebook chỉ giám sát nên không
cần cái nào. Lúc nào Facebook cần đăng bài thật thì mới tính lại.
