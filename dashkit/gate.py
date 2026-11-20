"""Cổng mật khẩu cho trang theo dõi — không biết gì về X hay Facebook.

Lấy nguyên luật của app/web.py bản 18/11, chỉ bỏ phần cứng tên:

· Token áp cho MỌI request, kể cả từ 127.0.0.1. Không miễn cho localhost vì
  cloudflared chạy ngay trên máy này, nên request qua tunnel cũng hiện ra là
  127.0.0.1 — miễn theo IP là mở toang. Phân biệt bằng header CF-Connecting-IP
  thì phải TIN vào header, hỏng một lần là mất quyền điều khiển tài khoản.
· Vào bằng MẬT KHẨU gõ trong form. Token tụt xuống làm giá trị cookie, tức là
  "đã đăng nhập", không còn là cách vào nữa: token trong URL thì nó nằm lại
  trong lịch sử trình duyệt, trong link chia sẻ, trong ảnh chụp màn hình.
· Đếm sai chung một sổ, không đếm theo IP (xem lý do ở trên), khóa cả cụm.

MỖI app phải dùng tên cookie KHÁC NHAU. Trình duyệt không phân biệt cookie theo
cổng: hai trang cùng ở 127.0.0.1 khác cổng vẫn dùng chung một hũ cookie, nên
trùng tên là đăng nhập trang này làm đăng xuất trang kia.
"""
from __future__ import annotations

import hmac
import secrets as _secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable


@dataclass
class Gate:
    env_file: Path                      # nơi giữ bí mật, nên nằm ngoài thư mục
    token_key: str                      # được phục vụ ra web (vd tools/)
    pass_key: str
    now: Callable[[], datetime]
    cookie: str = "dk"                  # ĐỔI cho từng app, xem docstring
    max_tries: int = 8
    lock_min: int = 5
    _cache: dict[str, str] = field(default_factory=dict)
    _fails: int = 0
    _until: datetime | None = None

    # --- bí mật ------------------------------------------------------------
    def _read(self) -> dict[str, str]:
        out: dict[str, str] = {}
        if self.env_file.exists():
            for line in self.env_file.read_text(encoding="utf-8").splitlines():
                k, _, v = line.partition("=")
                if k.strip() and v.strip():
                    out[k.strip()] = v.strip()
        return out

    def _secret(self, key: str, nbytes: int) -> str:
        """Đọc một bí mật trong file, chưa có thì sinh rồi ghi lại."""
        if not self._cache:
            self._cache = self._read()
        if self._cache.get(key):
            return self._cache[key]
        self._cache[key] = _secrets.token_urlsafe(nbytes)
        self.env_file.parent.mkdir(parents=True, exist_ok=True)
        self.env_file.write_text(
            "".join(f"{k}={v}\n" for k, v in self._cache.items()),
            encoding="utf-8")
        return self._cache[key]

    def token(self) -> str:
        """Giá trị cookie cấp sau khi đăng nhập đúng."""
        return self._secret(self.token_key, 24)

    def password(self) -> str:
        """Mật khẩu vào trang. Đổi bằng cách sửa file env rồi khởi động lại."""
        return self._secret(self.pass_key, 9)

    # --- chặn dò -----------------------------------------------------------
    def locked(self) -> int:
        """Còn bị khóa bao nhiêu giây."""
        if self._until is None:
            return 0
        left = (self._until - self.now()).total_seconds()
        if left <= 0:
            self._fails, self._until = 0, None
            return 0
        return int(left)

    def note_fail(self) -> None:
        self._fails += 1
        if self._fails >= self.max_tries:
            self._until = self.now() + timedelta(minutes=self.lock_min)

    def accept(self, given: str) -> bool:
        """Mật khẩu có đúng không. Đúng thì xóa sổ sai, sai thì ghi một vạch."""
        if given and hmac.compare_digest(given, self.password()):
            self._fails, self._until = 0, None
            return True
        self.note_fail()
        return False

    # --- phiên -------------------------------------------------------------
    def authed(self, cookie_header: str | None) -> bool:
        """Đã đăng nhập chưa — chỉ xét cookie, không nhận token trong URL."""
        for part in (cookie_header or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == self.cookie:
                return hmac.compare_digest(v, self.token())
        return False

    def set_cookie(self) -> str:
        return (f"{self.cookie}={self.token()}; Path=/; HttpOnly; "
                "SameSite=Lax; Max-Age=31536000")
