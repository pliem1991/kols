"""Hàng đợi việc LÀM TAY — app soạn sẵn, bạn tự bấm trên x.com.

Vì sao có file này: Automation rules của X cấm máy tự like, tự follow, và tự
reply người chưa tương tác với mình. Nhưng rule đó chỉ áp cho hành động máy làm
— "accounts or apps that take repeated actions WITHOUT a person actively
performing them". Bạn tự đọc tự bấm thì là dùng X bình thường.

Nên phần nặng (quét, lọc, soạn, dịch) vẫn để máy, còn mọi thao tác CHẠM vào
x.com thì người làm. Module này KHÔNG mở browser, KHÔNG gọi x.com bằng cookie
acc chính — nó chỉ đọc (qua acc phụ twscrape) và ghi ra file.
"""
from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime

from . import config

LOCK = threading.Lock()

# Mỗi mục gợi ý 4 việc. reply là việc chính, 3 cái kia là tuỳ bạn.
ACTS = ("reply", "like", "follow", "bookmark")

QUEUE_MAX = 5          # số mục giữ trong hàng đợi (chốt 14/11)
REFILL_AT = 3          # còn dưới ngần này thì nạp thêm

# Khoảng cách tối thiểu giữa hai lần TỰ nạp. Không có nó thì vòng lặp nạp lại
# mỗi 6-15 phút (nhịp reply khi không có target) -> acc phụ twscrape dính rate
# limit, gặp 22:00 ngày 14/11: "No account available for queue SearchTimeline.
# Next available at 22:00:37". Nút "Tạo tiếp" bấm tay thì KHÔNG bị chặn bởi
# mốc này — bạn bấm là bạn chấp nhận chờ.
AUTO_REFILL_GAP_MIN = 30
_last_auto: list = [None]


def auto_refill_due() -> bool:
    from datetime import timedelta
    last = _last_auto[0]
    if last is None:
        return True
    return config.now() - last >= timedelta(minutes=AUTO_REFILL_GAP_MIN)


def mark_auto_refill() -> None:
    _last_auto[0] = config.now()


@dataclass
class Item:
    id: str
    author: str
    url: str
    followers: int
    age_min: float
    replies: int
    their_text: str
    draft: str
    draft_vi: str = ""
    done: list[str] = field(default_factory=list)   # việc đã làm
    created_at: str = ""
    closed: bool = False

    @property
    def open(self) -> bool:
        return not self.closed


def _path() -> "config.Path":
    return config.STATE_DIR / f"manual_{config.now():%Y%m%d}.json"


def load() -> list[Item]:
    p = _path()
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    known = set(Item.__dataclass_fields__)
    return [Item(**{k: v for k, v in r.items() if k in known}) for r in raw]


def save(items: list[Item]) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    _path().write_text(
        json.dumps([asdict(i) for i in items], ensure_ascii=False, indent=1),
        encoding="utf-8")


def pending() -> list[Item]:
    return [i for i in load() if i.open]


def mark(item_id: str, act: str) -> bool:
    """Tick một việc đã làm. act="close" thì đóng cả mục."""
    with LOCK:
        items = load()
        for i in items:
            if i.id != item_id:
                continue
            if act == "close":
                i.closed = True
            elif act in ACTS:
                if act in i.done:
                    i.done.remove(act)       # bấm lại = bỏ tick
                else:
                    i.done.append(act)
                # KHÔNG tự đóng mục khi tick reply (sửa 14/11). Trước đây tick
                # "Đã reply" là mục biến mất ngay, nên không tick thêm like hay
                # bookmark cho cùng bài đó được nữa. Bốn nút độc lập; đóng mục
                # là việc riêng, bấm "Xong" hoặc "Bỏ qua".
            else:
                return False
            save(items)
            return True
    return False


async def refill(settings, want: int = QUEUE_MAX) -> dict:
    """Quét KOL, soạn draft, bỏ vào hàng đợi.

    Trả {"added", "cands", "skipped"} chứ không phải mỗi con số: "không soạn
    được mục nào" có hai nguyên nhân rất khác nhau — không có bài nào mới, hay
    có bài nhưng model bỏ qua hết. Gộp lại thành một thông báo thì không sửa
    được gì (gặp 14/11: báo "không có bài mới" trong khi vẫn có @rasbt).

    Đây là nguồn target mà nhánh reply TỰ ĐỘNG không còn được dùng (người ta
    chưa opt-in). Làm tay thì được, nên dữ liệu vẫn có ích — chỉ là người bấm.
    """
    from . import brain, scan, state

    with LOCK:
        items = load()
    have = {i.id for i in items}
    st = state.load()
    room = want - len([i for i in items if i.open])
    if room <= 0:
        return {"added": 0, "cands": 0, "skipped": ["hàng đợi đã đầy"]}

    cands = await scan.find_candidates(window_min=config.MANUAL_WINDOW_MIN, top_n=15)
    fresh = [c for c in cands
             if c["id"] not in have and not st.already_touched(c["id"])]
    if not fresh:
        return {"added": 0, "cands": 0, "skipped": []}

    new: list[Item] = []
    skipped: list[str] = []
    for c in fresh[:room]:
        text, reason = brain.compose_reply(settings, c)
        if text is None:
            skipped.append(f"@{c['handle']}: {reason}")
            continue
        new.append(Item(
            id=c["id"], author=c["handle"], url=c["url"],
            followers=c["followers"], age_min=c["age_min"],
            replies=c["replies"], their_text=c["text"], draft=text,
            created_at=config.now().isoformat(),
        ))
    if not new:
        return {"added": 0, "cands": len(fresh), "skipped": skipped}

    try:
        vi = brain.translate_vi(settings, [i.draft for i in new])
        for i, v in zip(new, vi):
            i.draft_vi = v
    except Exception:
        pass

    with LOCK:
        items = load()
        have = {i.id for i in items}
        items.extend(i for i in new if i.id not in have)
        save(items)
    return {"added": len(new), "cands": len(fresh), "skipped": skipped}


def summary() -> dict:
    items = load()
    done_today = [i for i in items if i.closed]
    acts: dict[str, int] = {a: 0 for a in ACTS}
    for i in items:
        for a in i.done:
            if a in acts:
                acts[a] += 1
    return {"pending": len([i for i in items if i.open]),
            "closed": len(done_today), "acts": acts}
