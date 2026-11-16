"""Danh sách đối tượng reply tự lớn dần — thêm người đáng, gỡ người chết.

Vì sao có file này: tới 15/11 danh sách đối tượng là một file viết tay
(tools/reply_targets.txt). Nó đứng yên trong khi tài khoản thì đổi: người mình
nhắm đổi chủ đề, có người ngừng đăng, mà người mới đáng reply thì không ai thêm
vào. Hệ quả đo được: nhánh reply tự động hết target liên tục.

Hai luật phải giữ, không được đổi vì tiện:

1. **Chỉ thêm người đã tự tương tác, hoặc người bạn đã chọn tay.** Automation
   rules của X cấm reply tự động dựa trên tìm kiếm từ khoá. Đi quét từ khoá rồi
   nhét tác giả vào danh sách, sau đó reply tự động dưới bài của họ, thực chất
   vẫn là reply theo từ khoá — chỉ là vòng vo hơn. Nên nguồn thêm chỉ có hai:
     · người mention hoặc reply @macropandaX (họ mở lời trước);
     · người bạn tự bấm reply/follow trong hàng đợi làm tay.

2. **File viết tay là của chủ dự án, app không sửa.** Mọi thứ app tự thêm nằm
   trong tools/reply_targets_auto.txt, gỡ cũng chỉ gỡ trong đó.

Ngoài ra có trần: acc phụ twscrape tính request theo batch 15 handle, danh sách
càng dài thì mỗi vòng quét càng tốn — đã chạm rate limit hai lần ngày 15/11.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import config

STATS = config.STATE_DIR / "targets_stats.json"
AUTO_FILE = config.TOOLS / "reply_targets_auto.txt"

MAX_AUTO = 30              # trần cho danh sách app tự thêm
ADD_PER_DAY = 3            # thêm từ từ, để còn đo được cái gì đang hiệu quả
PRUNE_AFTER_DAYS = 14      # chừng này ngày không ra ứng viên nào thì gỡ
MIN_SCANS_BEFORE_PRUNE = 25

HEADER = """# App TỰ thêm. Đừng sửa tay — file này bị ghi đè.
# Người viết tay thì sửa tools/reply_targets.txt.
#
# Nguồn thêm chỉ có hai (xem app/targets.py):
#   mention  — người đã mention hoặc reply @macropandaX trước
#   lam_tay  — người bạn đã tự bấm reply hoặc follow trong hàng đợi làm tay
# Không bao giờ thêm từ tìm kiếm theo từ khoá: X cấm reply tự động kiểu đó.
"""


# --- thống kê ---------------------------------------------------------------
def _load() -> dict:
    if STATS.exists():
        try:
            return json.loads(STATS.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save(d: dict) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATS.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                     encoding="utf-8")


def record_scan(per_handle: list[dict], candidates: list[dict]) -> None:
    """Ghi lại một vòng quét: ai được nhìn tới, ai ra ứng viên."""
    if not per_handle:
        return
    d = _load()
    today = f"{config.now():%Y-%m-%d}"
    passed = {c["handle"].lower() for c in candidates}
    for h in per_handle:
        k = h["handle"].lower()
        row = d.setdefault(k, {"handle": h["handle"], "scans": 0, "seen": 0,
                               "passed": 0, "last_pass": "", "added": "",
                               "source": "tay"})
        row["scans"] += 1
        row["seen"] += h.get("seen", 0)
        if k in passed:
            row["passed"] += 1
            row["last_pass"] = today
    _save(d)


def stats() -> dict:
    return _load()


# --- danh sách app tự thêm --------------------------------------------------
def auto_handles() -> list[str]:
    if not AUTO_FILE.exists():
        return []
    out = []
    for line in AUTO_FILE.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lstrip("@")
        if line:
            out.append(line)
    return out


def _write_auto(handles: list[str], notes: dict[str, str]) -> None:
    body = [HEADER]
    for h in handles:
        body.append(f"{h:<20} # {notes.get(h.lower(), '')}")
    AUTO_FILE.write_text("\n".join(body) + "\n", encoding="utf-8")


def _notes() -> dict[str, str]:
    d = _load()
    return {k: (f"{v.get('followers', 0):,} follower · "
                f"thêm {v.get('added', '?')} · nguồn {v.get('source', '?')}")
            for k, v in d.items() if v.get("added")}


def added_today() -> int:
    d = _load()
    today = f"{config.now():%Y-%m-%d}"
    return sum(1 for v in d.values() if v.get("added") == today)


def add(handle: str, followers: int, source: str) -> str:
    """Thêm một handle vào danh sách tự động. Trả lý do nếu KHÔNG thêm."""
    from .scan import _scanner

    h = (handle or "").lstrip("@")
    if not h:
        return "handle rỗng"
    ks = _scanner()
    if not (ks.MIN_FOLLOWERS <= followers <= ks.MAX_FOLLOWERS):
        return f"{followers:,} follower, ngoài band"
    known = {x.lower() for x in ks.load_targets()}
    if h.lower() in known:
        return "đã có trong danh sách"
    cur = auto_handles()
    if len(cur) >= MAX_AUTO:
        return f"danh sách tự thêm đã đầy ({MAX_AUTO})"
    if added_today() >= ADD_PER_DAY:
        return f"hôm nay đã thêm đủ {ADD_PER_DAY}"

    d = _load()
    row = d.setdefault(h.lower(), {"handle": h, "scans": 0, "seen": 0,
                                   "passed": 0, "last_pass": ""})
    row.update(handle=h, followers=followers, source=source,
               added=f"{config.now():%Y-%m-%d}")
    _save(d)
    _write_auto(cur + [h], _notes())
    return ""


def prune() -> list[str]:
    """Gỡ handle app tự thêm mà lâu rồi không ra ứng viên nào. Trả tên đã gỡ."""
    d = _load()
    cutoff = config.now() - timedelta(days=PRUNE_AFTER_DAYS)
    keep, dropped = [], []
    for h in auto_handles():
        row = d.get(h.lower(), {})
        if row.get("scans", 0) < MIN_SCANS_BEFORE_PRUNE:
            keep.append(h)
            continue
        last = row.get("last_pass") or row.get("added") or ""
        try:
            when = datetime.strptime(last, "%Y-%m-%d")
        except ValueError:
            keep.append(h)
            continue
        if when.date() < cutoff.date():
            dropped.append(h)
        else:
            keep.append(h)
    if dropped:
        _write_auto(keep, _notes())
    return dropped


def summary() -> dict:
    """Cho trang theo dõi: danh sách đang dùng và cái nào đang có ích."""
    from .scan import _scanner

    ks = _scanner()
    d = _load()
    rows = sorted(
        (v for v in d.values() if v.get("scans")),
        key=lambda v: (v.get("passed", 0), v.get("seen", 0)), reverse=True)
    return {
        "total": len(ks.load_targets()),
        "auto": len(auto_handles()),
        "added_today": added_today(),
        "cap_day": ADD_PER_DAY,
        "cap_auto": MAX_AUTO,
        "top": [{"handle": v["handle"], "scans": v.get("scans", 0),
                 "seen": v.get("seen", 0), "passed": v.get("passed", 0),
                 "source": v.get("source", "tay")} for v in rows[:12]],
        "dead": [v["handle"] for v in d.values()
                 if v.get("scans", 0) >= MIN_SCANS_BEFORE_PRUNE
                 and not v.get("passed")],
    }
