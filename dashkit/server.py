"""Server của trang theo dõi — http.server của thư viện chuẩn, không phụ thuộc.

Chạy trong thread nền, bind 127.0.0.1 nên không ai ngoài máy này vào được.
App nạp vào một Dash rồi gọi serve(); mọi thứ riêng của app đi qua Dash.
"""
from __future__ import annotations

import json
import mimetypes
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, unquote, urlparse

from .gate import Gate
from .page import Nav, build, login

Query = dict[str, list[str]]


@dataclass
class Dash:
    """Tất cả những gì một app phải nộp để có trang theo dõi."""
    name: str                           # "XKols"
    icon: str                           # một chữ trong ô vuông ở góc
    nav: list[Nav]
    app_js: str                         # các hàm v_<key>(d), head(d), và hành động
    state: Callable[[], dict]           # trả payload cho /api/state
    gate: Gate
    posts: dict[str, Callable[[Query], dict]] = field(default_factory=dict)
    gets: dict[str, Callable[[Query], dict]] = field(default_factory=dict)
    image_root: Path | None = None      # /img chỉ phục vụ file trong đây
    home: str = ""
    poll_ms: int = 4000
    host: str = "127.0.0.1"
    port: int = 8787

    def html(self) -> str:
        return build(self.name, self.icon, self.nav, self.app_js,
                     home=self.home, poll_ms=self.poll_ms)


class Server(ThreadingHTTPServer):
    """HTTPServer mặc định bật SO_REUSEADDR. Trên Windows cờ đó cho hai tiến
    trình bind CÙNG một cổng, không báo lỗi — chạy hai bản app là request đi lung
    tung giữa hai bên (gặp ngày 14/11). Tắt đi để bản thứ hai chết dứt khoát."""
    allow_reuse_address = False


def handler_for(dash: Dash) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):      # im lặng, đừng chen vào log app
            pass

        # --- gửi ------------------------------------------------------------
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            # Không cache: sửa trang xong khởi động lại là thấy ngay, khỏi phải
            # tự nạp lại trình duyệt (gặp ngày 14/11, tưởng code không ăn).
            self.send_header("Cache-Control", "no-store, must-revalidate")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, data: dict, code: int = 200) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                       "application/json; charset=utf-8")

        def _html(self, html: str, code: int = 200) -> None:
            self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

        def _serve_image(self, raw: str) -> None:
            """Chỉ cho xem ảnh trong image_root — đừng mở cả ổ đĩa ra."""
            root = dash.image_root
            if root is None:
                return self._send(404, b"khong phuc vu anh", "text/plain")
            try:
                p = Path(unquote(raw)).resolve()
                p.relative_to(root.resolve())
            except (ValueError, OSError):
                return self._send(403, b"ngoai thu muc cho phep", "text/plain")
            if not p.is_file():
                return self._send(404, b"khong thay anh", "text/plain")
            ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
            self._send(200, p.read_bytes(), ctype)

        # --- cổng -----------------------------------------------------------
        def _deny(self) -> None:
            """Trang thì đưa form đăng nhập, API thì 401 cho JS biết đường."""
            if urlparse(self.path).path in ("/", "/login"):
                return self._html(login(dash.name))
            self._send(401, b"can dang nhap", "text/plain; charset=utf-8")

        def _do_login(self) -> None:
            left = dash.gate.locked()
            if left:
                return self._html(login(
                    dash.name,
                    f"Sai nhiều lần — thử lại sau {left // 60 + 1} phút."), 429)
            n = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(min(n, 4096)).decode("utf-8", "replace")
            if not dash.gate.accept((parse_qs(body).get("p") or [""])[0]):
                return self._html(login(dash.name, "Sai mật khẩu."), 401)
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Set-Cookie", dash.gate.set_cookie())
            self.send_header("Content-Length", "0")
            self.end_headers()

        # --- định tuyến -----------------------------------------------------
        def do_GET(self):                  # noqa: N802
            u = urlparse(self.path)
            if not dash.gate.authed(self.headers.get("Cookie")):
                return self._deny()
            if u.path in ("/", "/login"):
                self._html(dash.html())
            elif u.path == "/api/state":
                self._json(dash.state())
            elif u.path == "/img":
                self._serve_image((parse_qs(u.query).get("p") or [""])[0])
            elif u.path in dash.gets:
                self._json(dash.gets[u.path](parse_qs(u.query)))
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):                 # noqa: N802
            u = urlparse(self.path)
            if u.path == "/login":
                return self._do_login()
            if not dash.gate.authed(self.headers.get("Cookie")):
                return self._deny()
            fn = dash.posts.get(u.path)
            if fn is None:
                return self._send(404, b"not found", "text/plain")
            out = fn(parse_qs(u.query))
            self._json(out, 400 if out.get("ok") is False and out.get("why") else 200)

    return Handler


def serve(dash: Dash) -> str:
    """Bật server trong thread nền. Trả URL."""
    srv = Server((dash.host, dash.port), handler_for(dash))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    dash.gate.password()            # sinh sẵn để in ra log khởi động
    return f"http://{dash.host}:{dash.port}"
