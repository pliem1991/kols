"""Hàng chờ duyệt — chế độ thứ ba giữa dry-run và live.

Dry-run thì bạn đọc được draft nhưng app không đăng. Live thì app đăng nhưng bạn
không kịp xem. Chế độ duyệt: app soạn xong thì dừng lại, đưa draft lên trang web
local, chờ bạn bấm Duyệt mới đăng.

Hàng chờ nằm trong bộ nhớ của tiến trình, dùng chung giữa vòng lặp (asyncio) và
server web (thread riêng) nên phải có khoá.
"""
from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import asdict, dataclass, field

from . import config

# Quá hạn mà không ai bấm thì tự bỏ — đừng treo vòng lặp cả đêm.
TIMEOUT_SEC = 30 * 60
POLL_SEC = 1.0

_LOCK = threading.Lock()


@dataclass
class Pending:
    id: str
    kind: str                       # post | thread | quote | reply | repost
    text: str
    target_url: str = ""
    target_author: str = ""
    created_at: str = ""
    decision: str = "pending"       # pending | approved | rejected | expired
    decided_at: str = ""
    note: str = ""
    parts: list[str] = field(default_factory=list)
    text_vi: str = ""                # bản dịch để đọc, KHÔNG phải bản đăng
    parts_vi: list[str] = field(default_factory=list)
    image: str = ""                  # đường dẫn ảnh sẽ đính kèm, nếu có


_QUEUE: dict[str, Pending] = {}
_HISTORY: list[Pending] = []


def enabled() -> bool:
    return _ENABLED


_ENABLED = False


def set_enabled(on: bool) -> None:
    global _ENABLED
    _ENABLED = on


def snapshot() -> dict:
    with _LOCK:
        return {
            "pending": [asdict(p) for p in _QUEUE.values()],
            "recent": [asdict(p) for p in _HISTORY[-15:]][::-1],
        }


def decide(pid: str, decision: str, note: str = "") -> bool:
    with _LOCK:
        p = _QUEUE.get(pid)
        if p is None or p.decision != "pending":
            return False
        p.decision = decision
        p.note = note
        p.decided_at = config.now().isoformat()
        return True


def _submit(kind: str, text: str, target_url: str = "", target_author: str = "",
            parts: list[str] | None = None, text_vi: str = "",
            parts_vi: list[str] | None = None, image: str = "") -> Pending:
    p = Pending(
        id=uuid.uuid4().hex[:8], kind=kind, text=text, target_url=target_url,
        target_author=target_author, created_at=config.now().isoformat(),
        parts=parts or [], text_vi=text_vi, parts_vi=parts_vi or [], image=image,
    )
    with _LOCK:
        _QUEUE[p.id] = p
    return p


def _retire(p: Pending) -> None:
    with _LOCK:
        _QUEUE.pop(p.id, None)
        _HISTORY.append(p)


async def ask(kind: str, text: str, target_url: str = "", target_author: str = "",
              parts: list[str] | None = None, text_vi: str = "",
              parts_vi: list[str] | None = None, image: str = "") -> tuple[bool, str]:
    """Đưa draft lên trang duyệt rồi chờ. Trả (được đăng không, lý do)."""
    if not _ENABLED:
        return True, "không bật chế độ duyệt"

    p = _submit(kind, text, target_url, target_author, parts, text_vi, parts_vi, image)
    waited = 0.0
    while waited < TIMEOUT_SEC:
        if not _ENABLED:
            # Bạn vừa chuyển sang chế độ tự động giữa lúc chờ -> cho qua luôn,
            # đừng bắt draft nằm đó đến hết 30 phút.
            with _LOCK:
                _QUEUE[p.id].decision = "approved"
            _retire(p)
            return True, "bạn chuyển sang chế độ tự động"
        with _LOCK:
            decision = _QUEUE[p.id].decision
        if decision != "pending":
            _retire(p)
            return decision == "approved", f"bạn bấm {decision}"
        await asyncio.sleep(POLL_SEC)
        waited += POLL_SEC

    with _LOCK:
        _QUEUE[p.id].decision = "expired"
    _retire(p)
    return False, f"hết {TIMEOUT_SEC // 60} phút không ai duyệt"
