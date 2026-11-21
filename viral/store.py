"""Kho danh sách video viral — một file JSON, chống trùng theo link bài.

Bên agaubun đọc thẳng file này. Cấu trúc cố ý phẳng và dễ đọc bằng mắt:

    {"updated": "...", "videos": [ {...}, ... ]}

Mỗi video giữ thêm "seen": [[giờ, view], ...] — mỗi lần quét ghi một mốc. Đó là
cách duy nhất đo được TỐC ĐỘ TĂNG thật: lần quét đầu chỉ biết view/giờ tính từ
lúc đăng, lần thứ hai trở đi mới biết nó còn đang lên hay đã nguội.
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent
FILE = ROOT / "videos.json"
LOCK = Lock()

# Trạng thái do bên agaubun bấm trên trang 8788.
STATUSES = ("moi", "da_chon", "da_lam", "bo")
STATUS_VI = {"moi": "mới", "da_chon": "đã chọn", "da_lam": "đã làm", "bo": "bỏ"}

KEEP_SEEN = 12          # giữ 12 mốc gần nhất, đủ vẽ đà tăng mà file không phình


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def load() -> list[dict]:
    if not FILE.exists():
        return []
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data.get("videos", []) if isinstance(data, dict) else []


def save(videos: list[dict]) -> None:
    """Ghi qua file tạm rồi thay — trang 8788 đọc file này mỗi 10 giây, ghi đè
    trực tiếp là có lúc nó đọc trúng file viết dở."""
    FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"updated": _now(), "videos": videos}
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False,
                                     dir=str(FILE.parent), suffix=".tmp") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)
        tmp = Path(f.name)
    tmp.replace(FILE)


def merge(found: list[dict]) -> dict:
    """Nhập mẻ vừa quét vào file. Trả {"them", "capnhat"}.

    Trùng theo url. Bài đã có thì KHÔNG ghi đè trạng thái và mô tả (bên kia có
    thể đã sửa tay), chỉ cập nhật số liệu và thêm một mốc vào "seen".
    """
    with LOCK:
        videos = load()
        by_url = {v["url"]: v for v in videos}
        added = updated = 0
        for v in found:
            old = by_url.get(v["url"])
            if old is None:
                v.setdefault("status", "moi")
                v["found_at"] = _now()
                v["seen"] = [[_now(), v.get("views", 0)]]
                videos.append(v)
                by_url[v["url"]] = v
                added += 1
                continue
            for k in ("views", "likes", "reposts", "replies", "age_min"):
                if k in v:
                    old[k] = v[k]
            seen = old.get("seen") or []
            seen.append([_now(), v.get("views", 0)])
            old["seen"] = seen[-KEEP_SEEN:]
            updated += 1
        videos.sort(key=lambda r: r.get("heat", 0), reverse=True)
        save(videos)
    return {"them": added, "capnhat": updated}


def set_status(url: str, status: str) -> dict:
    """Đổi trạng thái một video. Dùng cho nút bấm trên trang 8788."""
    if status not in STATUSES:
        return {"ok": False, "why": f"trạng thái lạ: {status}"}
    with LOCK:
        videos = load()
        for v in videos:
            if v.get("url") == url:
                v["status"] = status
                v["status_at"] = _now()
                save(videos)
                return {"ok": True, "status": status}
    return {"ok": False, "why": "không có video này trong file"}


def rate(v: dict) -> float:
    """View tăng mỗi giờ, đo giữa hai mốc quét gần nhất.

    Chưa đủ hai mốc thì lấy trung bình từ lúc đăng — kém chính xác hơn nhưng
    còn hơn để trống ở lần quét đầu.
    """
    seen = v.get("seen") or []
    if len(seen) >= 2:
        (t0, v0), (t1, v1) = seen[-2], seen[-1]
        try:
            h = (datetime.strptime(t1, "%Y-%m-%d %H:%M")
                 - datetime.strptime(t0, "%Y-%m-%d %H:%M")).total_seconds() / 3600
        except ValueError:
            h = 0
        if h > 0.05:
            return max(0.0, (v1 - v0) / h)
    age_h = (v.get("age_min") or 0) / 60
    return v.get("views", 0) / age_h if age_h > 0.05 else 0.0


def state() -> dict:
    """Phần dữ liệu cho trang 8788."""
    videos = load()
    for v in videos:
        v["rate"] = round(rate(v))
    return {"videos": videos,
            "updated": (json.loads(FILE.read_text(encoding="utf-8")).get("updated")
                        if FILE.exists() else ""),
            "topics": sorted({v.get("topic", "khác") for v in videos}),
            "file": str(FILE)}
