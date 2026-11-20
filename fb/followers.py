"""Số người theo dõi / bạn bè của Facebook agaubun theo thời gian.

Hai nguồn, gộp lại theo thời điểm:
- cheo/followers.jsonl : bot ghi sau mỗi lượt (đang đăng nhập sẵn nên đọc được số trên trang cá nhân)
- data/followers.jsonl : Gấu nhập tay trên trang theo dõi

Mỗi dòng: {"at": "2026-11-20T12:05:00+07:00", "followers": 1234, "friends": 567, "src": "bot"}
followers/friends được phép null nếu lần đó không đọc được.
Không gọi Facebook từ đây: Facebook chặn đọc trang khi chưa đăng nhập.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from . import data

ROOT = Path(__file__).resolve().parent  # XKols/fb
MANUAL = ROOT / "data" / "followers.jsonl"


def _rows(p: Path) -> list[dict]:
    out = []
    try:
        lines = p.read_text(encoding="utf-8-sig").splitlines()
    except OSError:
        return out
    for l in lines:
        try:
            r = json.loads(l)
            at = datetime.fromisoformat(r["at"]).replace(tzinfo=None)
        except (ValueError, KeyError, TypeError):
            continue
        f, fr = r.get("followers"), r.get("friends")
        out.append({"at": at, "followers": f if isinstance(f, int) else None,
                    "friends": fr if isinstance(fr, int) else None,
                    "src": str(r.get("src") or "?")})
    return out


def _num(q: dict, k: str) -> int | None:
    v = (q.get(k) or [""])[0].replace(".", "").replace(",", "").strip()
    return int(v) if v.isdigit() else None


def add_manual(q: dict) -> dict:
    f, fr = _num(q, "followers"), _num(q, "friends")
    if f is None and fr is None:
        return {"ok": False, "why": "Nhập ít nhất một số (follower hoặc bạn bè)."}
    MANUAL.parent.mkdir(exist_ok=True)
    row = {"at": datetime.now().astimezone().isoformat(timespec="seconds"),
           "followers": f, "friends": fr, "src": "tay"}
    with MANUAL.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"ok": True}


def _ago_val(rows: list[dict], key: str, hours: int) -> int | None:
    """Giá trị gần nhất cách đây ít nhất `hours` giờ."""
    cut = datetime.now() - timedelta(hours=hours)
    old = [r[key] for r in rows if r[key] is not None and r["at"] <= cut]
    return old[-1] if old else None


def state() -> dict:
    rows = sorted(_rows(data.CHEO / "followers.jsonl") + _rows(MANUAL), key=lambda r: r["at"])
    out = {}
    for key in ("followers", "friends"):
        pts = [r for r in rows if r[key] is not None]
        last = pts[-1] if pts else None
        cur = last[key] if last else None
        d1, d7 = _ago_val(pts, key, 24), _ago_val(pts, key, 24 * 7)
        out[key] = {
            "now": cur,
            "at": last["at"].strftime("%Y-%m-%d %H:%M") if last else None,
            "src": last["src"] if last else None,
            "d24": cur - d1 if cur is not None and d1 is not None else None,
            "d7": cur - d7 if cur is not None and d7 is not None else None,
            "series": [[r["at"].strftime("%Y-%m-%d %H:%M"), r[key]] for r in pts[-300:]],
        }
    out["points"] = len(rows)
    return out
