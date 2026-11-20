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

QUEUE_MAX = 10         # đủ 10 mục/ngày để reply tay (chốt 14/11)
REFILL_AT = 5          # còn dưới ngần này thì nạp thêm

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
    # Đóng vì quá hạn, KHÔNG phải vì bạn làm xong. Tách ra để thống kê khỏi
    # tính nhầm thành việc đã làm.
    expired: bool = False

    @property
    def open(self) -> bool:
        return not self.closed


def _unescape(s: str) -> str:
    import html
    return html.unescape(s or "")


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


# Mục soạn xong mà để quá lâu thì tự bỏ. Lý do: draft bám vào một bài cụ thể —
# qua 3 tiếng thì bài đó đã có thêm hàng chục reply, vào lúc này là chìm, mà
# chỗ nó giữ trong trần reply/tác giả vẫn bị tính. Chủ dự án chốt 17/11.
STALE_MIN = 180


def _stale(i: "Item", now) -> bool:
    """Quá hạn = mở, chưa reply, và soạn đã quá STALE_MIN phút."""
    if not i.open or "reply" in i.done or not i.created_at:
        return False
    try:
        born = datetime.fromisoformat(i.created_at)
    except ValueError:
        return False
    return (now - born).total_seconds() > STALE_MIN * 60


def expire() -> int:
    """Đóng các mục quá hạn. Trả về số mục vừa đóng."""
    with LOCK:
        items = load()
        now = config.now()
        gone = [i for i in items if _stale(i, now)]
        for i in gone:
            i.closed = True
            i.expired = True
        if gone:
            save(items)
    return len(gone)


def pending() -> list[Item]:
    expire()
    return [i for i in load() if i.open]


def _sync_reply(item: "Item", ticked: bool) -> None:
    """Chép việc reply TAY sang sổ chung, để nhánh tự động biết mà tránh.

    Hai nhánh trước đây ghi vào hai chỗ khác nhau: nhánh tự động ghi vào
    state_*.json, nhánh làm tay chỉ ghi vào manual_*.json. Không bên nào đọc
    của bên kia, nên cùng một bài có thể được trả lời hai lần, và cùng một tác
    giả có thể bị trả lời quá trần ngày (gặp 15/11 với @DamiDefi).
    """
    from . import state
    st = state.load()
    tid, author = str(item.id), item.author.lower()
    if ticked:
        if tid not in st.manual_tweet_ids:
            st.manual_tweet_ids.append(tid)
            st.manual_authors[author] = st.manual_authors.get(author, 0) + 1
    else:
        if tid in st.manual_tweet_ids:
            st.manual_tweet_ids.remove(tid)
            st.manual_authors[author] = max(
                0, st.manual_authors.get(author, 0) - 1)
    state.save(st)


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
                    # Bạn tự bấm reply/follow dưới bài của ai thì người đó đáng
                    # theo dõi tiếp — nguồn HỢP LỆ thứ hai để danh sách đối
                    # tượng tự lớn lên (xem app/targets.py).
                    if act in ("reply", "follow"):
                        from . import targets
                        targets.add(i.author, i.followers, "lam_tay")
                if act == "reply":
                    _sync_reply(i, ticked=act in i.done)
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

    expire()      # trước khi đếm chỗ trống và trần reply/tác giả
    with LOCK:
        items = load()
    have = {i.id for i in items}
    st = state.load()
    room = want - len([i for i in items if i.open])
    if room <= 0:
        return {"added": 0, "cands": 0, "dupes": 0,
                "skipped": ["hàng đợi đã đầy"]}

    # Hai nguồn, không phải một. Nhánh reply TỰ ĐỘNG cũng ăn từ danh sách KOL và
    # nó chạy trước (6-15 phút một lần), nên tới lượt hàng đợi làm tay thì bài
    # nào ngon đã bị "touched" rồi — đo 15/11 lúc 08:3x: 3 ứng viên, cả 3 đều đã
    # reply tự động hoặc đã nằm sẵn trong hàng đợi. Người mình follow là nguồn
    # riêng, nhánh tự động chỉ dùng tới khi không còn mention nào.
    cands = await scan.find_candidates(window_min=config.MANUAL_WINDOW_MIN, top_n=15)
    seen_ids = {c["id"] for c in cands}
    try:
        more = await scan.find_from_following(
            getattr(settings, "account_handle", ""),
            window_min=config.MANUAL_WINDOW_MIN, top_n=15)
        cands += [c for c in more if c["id"] not in seen_ids]
    except Exception as e:
        skipped_src = f"không đọc được danh sách following: {type(e).__name__}"
    else:
        skipped_src = ""

    # Trần reply theo TÁC GIẢ. Trước 16/11 hàng đợi không đếm gì cả, nên cùng
    # một ngày ra hai mục @CrewWatcherX. Đếm gộp ba nguồn vì cả ba đều kết
    # thúc bằng một reply dưới tên @macropandaX:
    #   - reply máy đã gửi      (st.replied_authors)
    #   - reply tay bạn đã bấm  (st.manual_authors)
    #   - mục còn treo trong hàng đợi — chỗ đã đặt trước, chưa dùng
    used: dict[str, int] = {}
    for src in (st.replied_authors, st.manual_authors):
        for a, n in src.items():
            used[a] = used.get(a, 0) + n
    for i in items:
        if i.open and "reply" not in i.done:
            a = i.author.lower()
            used[a] = used.get(a, 0) + 1

    dupes = 0
    over_cap: set[str] = set()
    fresh = []
    for c in cands:
        if c["id"] in have or st.already_touched(c["id"]):
            dupes += 1
            continue
        a = c["handle"].lower()
        if used.get(a, 0) >= config.MAX_REPLIES_PER_AUTHOR_PER_DAY:
            over_cap.add(c["handle"])
            continue
        used[a] = used.get(a, 0) + 1
        fresh.append(c)
    cap_note = (f"đủ trần {config.MAX_REPLIES_PER_AUTHOR_PER_DAY} reply/ngày: "
                + ", ".join("@" + h for h in sorted(over_cap))) if over_cap else ""
    if not fresh:
        return {"added": 0, "cands": len(cands), "dupes": dupes,
                "skipped": [x for x in (skipped_src, cap_note) if x]}

    new: list[Item] = []
    skipped: list[str] = [cap_note] if cap_note else []
    for c in fresh[:room]:
        text, reason = brain.compose_reply(settings, c)
        if text is None:
            skipped.append(f"@{c['handle']}: {reason}")
            continue
        new.append(Item(
            id=c["id"], author=c["handle"], url=c["url"],
            followers=c["followers"], age_min=c["age_min"],
            # X trả rawContent còn nguyên entity HTML ("&amp;"), đưa thẳng lên
            # trang là hiện ra chữ "&amp;" chứ không phải "&".
            replies=c["replies"], their_text=_unescape(c["text"]), draft=text,
            created_at=config.now().isoformat(),
        ))
    if not new:
        return {"added": 0, "cands": len(fresh), "dupes": dupes,
                "skipped": skipped}

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
    return {"added": len(new), "cands": len(fresh), "dupes": dupes,
            "skipped": skipped}


def summary() -> dict:
    expire()
    items = [i for i in load() if not i.expired]
    done_today = [i for i in items if i.closed]
    acts: dict[str, int] = {a: 0 for a in ACTS}
    for i in items:
        for a in i.done:
            if a in acts:
                acts[a] += 1
    return {"pending": len([i for i in items if i.open]),
            "closed": len(done_today), "acts": acts,
            # Mục tự rụng vì để quá STALE_MIN phút. Hiện lên trang chứ không
            # im lặng: để quá nhiều nghĩa là app soạn nhiều hơn bạn bấm nổi.
            "expired": len([i for i in load() if i.expired]),
            "stale_min": STALE_MIN,
            # Tổng số mục app đã soạn hôm nay — mẫu số cho biểu đồ trên trang:
            # "3 lần like" không nói lên gì, "3 trên 7 mục" thì có.
            "total": len(items), "target": QUEUE_MAX}
