# dashkit — khung màn hình theo dõi

Tách ra khỏi `app/web.py` ngày 20/11 để project Facebook dùng chung. Trong
`dashkit/` **không có một dòng nào biết X hay Facebook là gì**.

| Phần | Ở đâu |
|---|---|
| Server HTTP (thread nền, bind 127.0.0.1), định tuyến, phục vụ ảnh | `server.py` |
| Cổng mật khẩu, cookie phiên, chặn dò mật khẩu | `gate.py` |
| CSS, trang đăng nhập, khung trang, JS chung | `page.py` |

JS chung gồm: đổi mục không tải lại trang, tự nạp lại mỗi 4 giây, mở/đóng từng
mục, chép draft, và ba hàm vẽ `cell()` / `bars()` / `legend()`.

## Cài vào project khác

```bash
pip install -e D:\AI\XKols
```

Cài kiểu `-e` nên sửa `dashkit/` là bên kia ăn theo ngay, không phải cài lại.
Không muốn cài thì thêm `sys.path.insert(0, r"D:\AI\XKols")` trước khi import,
nhưng cách đó dễ quên khi đổi máy.

## Dùng

App phải nộp bốn thứ: danh sách mục bên trái, JS riêng, một hàm trả số liệu, và
một cái cổng.

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


def payload():                         # gọi mỗi 4 giây
    return {"page": "Trang ABC", "mode": "theo dõi", "now": "10:32",
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
                      cookie="fb"),
    port=8788,
)
print(dashkit.serve(dash))             # -> http://127.0.0.1:8788
```

Lần chạy đầu `gate` tự sinh mật khẩu rồi ghi vào `env_file`; in ra log mà dùng.
Đổi mật khẩu thì sửa file đó rồi khởi động lại.

### Ba chỗ dễ sai

**Tên cookie phải khác nhau.** Trình duyệt không phân biệt cookie theo cổng:
hai trang cùng ở `127.0.0.1` khác cổng vẫn chung một hũ cookie. X đang dùng
`xk`, nên Facebook phải dùng tên khác — trùng là đăng nhập trang này làm đăng
xuất trang kia.

**Cổng phải khác nhau.** X giữ 8787. `Server` cố ý tắt `SO_REUSEADDR`: trùng
cổng thì bản thứ hai chết ngay chứ không âm thầm tranh request.

**`env_file` đừng để trong thư mục phục vụ ra web.** `/img` phục vụ mọi file
trong `image_root`; để file bí mật ở đó là tự đưa chìa khóa qua cửa sổ.

### Thêm nút bấm

```python
dash.posts["/api/lam-moi"] = lambda q: {"ok": True}
```

JS gọi `fetch('/api/lam-moi', {method:'POST'})` rồi `load()`. Hàm nhận query đã
parse (`dict[str, list[str]]`), trả dict là xong — `{"ok": False, "why": "..."}`
thì server trả 400.

### CSS có sẵn

`card` `chead` `sub` `strip` `cell` `duo` `chip` `nav` `bars` `legend` `danger`
`note` `ok` `no` `warn`. Màu lấy qua biến: `var(--acc)` `var(--ok)` `var(--no)`
`var(--warn)` `var(--mut)` `var(--line)`.

Sửa giao diện thì sửa trong `page.py`, cả hai trang ăn theo. `CSS` và trang
đăng nhập trong đó cắt nguyên văn từ `app/web.py` bản 18/11.
