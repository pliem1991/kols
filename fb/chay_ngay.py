"""Nút "Chạy ngay" trên trang 8788: bật một lượt bot chéo lập tức.

Đây là NGOẠI LỆ DUY NHẤT của luật "chỉ đọc thư mục bot" ở data.py — và cũng chỉ
là bật tiến trình, không ghi file nào vào cheo. Mọi thứ khác (khóa chống chạy
chồng, ghi log, dừng khẩn cấp) vẫn do bot.py tự lo; ở đây chỉ chặn trước mấy
trường hợp chắc chắn bot sẽ bỏ qua, để không tạo một mục log vô ích.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from . import data

PY = data.CHEO / "bot-py" / "Scripts" / "pythonw.exe"

# Tiến trình tách rời hẳn: trang 8788 tắt hay khởi động lại thì lượt bot vẫn chạy.
FLAGS = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
         | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200))


def why_not() -> str | None:
    """Lý do không chạy được, hoặc None nếu chạy được."""
    if data.state_lock():
        return "Bot đang khóa sau cảnh báo của Facebook. Kiểm tra Facebook, xóa file cheo/dung-khan-cap.txt rồi mới chạy lại."
    r = data.run_lock()
    if r:
        return f"Đang có một lượt chạy (pid {r['pid']}, bắt đầu {r['min']} phút trước). Đợi nó xong."
    if data.chrome_open():
        return "Chrome riêng của bot đang mở. Đóng cửa sổ đó rồi chạy lại."
    if not PY.exists():
        return f"Không thấy {PY}"
    return None


def run(q: dict[str, list[str]] | None = None) -> dict:
    """POST /api/cheo/run — bật `pythonw.exe bot.py --now` rồi trả về ngay."""
    why = why_not()
    if why:
        return {"ok": False, "why": why}
    try:
        subprocess.Popen([str(PY), "bot.py", "--now"], cwd=str(data.CHEO),
                         creationflags=FLAGS, close_fds=True,
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except OSError as e:
        return {"ok": False, "why": f"Không bật được: {e}"}
    return {"ok": True, "msg": "Đã bật một lượt. Kết quả xem ở tab Lượt chạy (bot ghi vào log.md khi xong)."}
