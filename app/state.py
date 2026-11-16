"""Trạng thái theo ngày: đã đăng gì, reply ai, khi nào tới lượt kế tiếp.

Ghi ra JSON nên app tắt/mở lại không mất mạch, và cũng là nhật ký để soi lại.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from . import config


@dataclass
class DayState:
    date: str
    posts_done: dict[str, int] = field(default_factory=dict)   # window -> số bài
    thread_done: bool = False
    replies_done: int = 0
    replied_authors: dict[str, int] = field(default_factory=dict)
    replied_tweet_ids: list[str] = field(default_factory=list)
    posted: list[dict] = field(default_factory=list)           # {kind, url, at, text}
    images_used: list[str] = field(default_factory=list)
    pillars_used: list[str] = field(default_factory=list)
    quotes_done: int = 0
    quoted_tweet_ids: list[str] = field(default_factory=list)
    reposts_done: int = 0
    next_post_at: str | None = None
    next_reply_at: str | None = None
    # Giãn riêng cho quote: khi thẻ quote không chịu gắn thì nghỉ một lúc chứ
    # không thử lại mỗi vòng (thêm 16/11, xem runner.do_quote).
    next_quote_at: str | None = None
    # Bài bạn tự reply tay từ hàng đợi. Phải ghi lại, nếu không nhánh TỰ ĐỘNG
    # không biết là bạn đã trả lời rồi (và ngược lại) — xem manual.mark.
    manual_tweet_ids: list[str] = field(default_factory=list)
    manual_authors: dict[str, int] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    # --- truy vấn ----------------------------------------------------------
    def posts_in(self, window: str) -> int:
        return self.posts_done.get(window, 0)

    def can_reply_to(self, author: str) -> bool:
        if self.replies_done >= config.MAX_REPLIES_PER_DAY:
            return False
        a = author.lower()
        # Cộng cả reply bạn gửi tay: người ngoài nhìn vào chỉ thấy MỘT tài khoản
        # trả lời, không phân biệt máy hay người. Trần 2 bài/tác giả/ngày là để
        # khỏi trông như bám theo một người, nên reply tay cũng phải tính.
        n = self.replied_authors.get(a, 0) + self.manual_authors.get(a, 0)
        return n < config.MAX_REPLIES_PER_AUTHOR_PER_DAY

    def already_replied(self, tweet_id: str) -> bool:
        return str(tweet_id) in self.replied_tweet_ids

    def already_touched(self, tweet_id: str) -> bool:
        """Đã reply/quote/trả lời tay bài này — đừng đụng lần hai.

        Xét cả NHỮNG NGÀY TRƯỚC. Trước 16/11 chỉ xét trong ngày, nên qua nửa
        đêm là bài cũ quay lại hàng đợi: bài unlock của @DamiDefi
        (2121953369665470503) bạn đã reply tay tối 15/11, sáng 16/11 lại hiện
        ra như việc mới.
        """
        t = str(tweet_id)
        return (t in self.replied_tweet_ids or t in self.quoted_tweet_ids
                or t in self.manual_tweet_ids or t in touched_before())

    def record_quote(self, author: str, tweet_id: str, url: str, text: str) -> None:
        self.quotes_done += 1
        self.quoted_tweet_ids.append(str(tweet_id))
        self.posted.append({
            "kind": "quote", "author": author, "target": tweet_id, "url": url,
            "at": config.now().isoformat(), "text": text[:400],
        })

    def due(self, field_name: str) -> bool:
        """True nếu tới giờ (hoặc chưa đặt giờ)."""
        raw = getattr(self, field_name)
        if not raw:
            return True
        return config.now() >= datetime.fromisoformat(raw)

    def when(self, field_name: str) -> str:
        raw = getattr(self, field_name)
        if not raw:
            return "ngay"
        return datetime.fromisoformat(raw).strftime("%H:%M")

    # --- cập nhật ----------------------------------------------------------
    def arm(self, field_name: str, bounds: tuple[int, int]) -> datetime:
        from datetime import timedelta
        nxt = config.now() + timedelta(seconds=config.rand_gap_sec(bounds))
        setattr(self, field_name, nxt.isoformat())
        return nxt

    def record_post(self, window: str, url: str, text: str, kind: str = "post",
                    pillar: str = "", image: str = "") -> None:
        """Ghi lại bài đã đăng.

        pillar và image được ghi từ 14/11 để sau này đo được: chủ đề nào kéo
        view, bài có ảnh có hơn bài không. Trước đó chỉ lưu text nên không
        ghép ngược lại được — app soạn 6 chủ đề mà không biết cái nào ăn.
        """
        if kind == "thread":
            self.thread_done = True
        else:
            self.posts_done[window] = self.posts_done.get(window, 0) + 1
        self.posted.append({
            "kind": kind, "window": window, "url": url, "pillar": pillar,
            "image": bool(image), "at": config.now().isoformat(),
            "text": text[:400],
        })

    def record_reply(self, author: str, tweet_id: str, url: str, text: str) -> None:
        a = author.lower()
        self.replies_done += 1
        self.replied_authors[a] = self.replied_authors.get(a, 0) + 1
        self.replied_tweet_ids.append(str(tweet_id))
        self.posted.append({
            "kind": "reply", "author": author, "target": tweet_id, "url": url,
            "at": config.now().isoformat(), "text": text[:400],
        })

    def note(self, msg: str) -> None:
        self.notes.append(f"{config.now():%H:%M} {msg}")


def _path_for(day: str) -> Path:
    return config.STATE_DIR / f"state_{day}.json"


# Bài đã đụng trong những ngày TRƯỚC. Ngày cũ không đổi nữa nên đọc một lần rồi
# giữ, mỗi ngày mới dựng lại. 7 ngày là đủ: bài quá một tuần thì cổng tuổi bài
# đã loại từ lâu, giữ thêm chỉ tốn bộ nhớ.
TOUCHED_DAYS = 7
_TOUCHED_CACHE: dict[str, set[str]] = {}

# Nhịp tim: vòng lặp chạm vào mỗi vòng, trang theo dõi đọc ra. Không có nó thì
# trang hiển thị y hệt nhau dù app đang ngủ bình thường hay đang nghỉ dài sau
# lỗi — mà hai chuyện đó khác nhau hoàn toàn.
_BEAT: list = [None, ""]


def beat(what: str = "") -> None:
    _BEAT[0] = config.now()
    if what:
        _BEAT[1] = what


def last_beat() -> tuple[str, str, int]:
    """(giờ, đang làm gì, bao nhiêu giây trước). Chưa đập lần nào -> ('', '', -1)."""
    t = _BEAT[0]
    if t is None:
        return "", "", -1
    return f"{t:%H:%M:%S}", _BEAT[1], int((config.now() - t).total_seconds())


def touched_before(days: int = TOUCHED_DAYS) -> set[str]:
    from datetime import timedelta
    today = config.now().date()
    key = f"{today:%Y%m%d}/{days}"
    hit = _TOUCHED_CACHE.get(key)
    if hit is not None:
        return hit
    ids: set[str] = set()
    for i in range(1, days + 1):
        p = _path_for(f"{today - timedelta(days=i):%Y%m%d}")
        if not p.exists():
            continue
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for fld in ("replied_tweet_ids", "quoted_tweet_ids", "manual_tweet_ids"):
            ids.update(str(x) for x in (raw.get(fld) or []))
    # Những ngày TRƯỚC 16/11 chưa có manual_tweet_ids, nên đọc thẳng sổ làm tay
    # cũ: bài bạn đã bấm "Đã reply" hôm qua vẫn phải tính là đã đụng. Hôm nay
    # thì không đọc ở đây — manual.mark ghi thẳng vào state, khỏi lệch cache.
    for i in range(1, days + 1):
        p = (config.STATE_DIR
             / f"manual_{today - timedelta(days=i):%Y%m%d}.json")
        if not p.exists():
            continue
        try:
            rows = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        ids.update(str(r.get("id")) for r in rows
                   if "reply" in (r.get("done") or []))
    _TOUCHED_CACHE.clear()          # chỉ giữ của hôm nay
    _TOUCHED_CACHE[key] = ids
    return ids


def load(day: str | None = None) -> DayState:
    day = day or f"{config.now():%Y%m%d}"
    p = _path_for(day)
    if p.exists():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            known = {f for f in DayState.__dataclass_fields__}
            return DayState(**{k: v for k, v in raw.items() if k in known})
        except Exception:
            pass
    return DayState(date=day)


def save(st: DayState) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    _path_for(st.date).write_text(
        json.dumps(asdict(st), indent=2, ensure_ascii=False), encoding="utf-8"
    )


REPOSTED_PATH = config.STATE_DIR / "reposted.json"


def reposted_urls() -> set[str]:
    """Sổ RT xuyên ngày — state theo ngày không nhớ được việc này."""
    if REPOSTED_PATH.exists():
        try:
            return set(json.loads(REPOSTED_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return set()


def mark_reposted(url: str) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    seen = reposted_urls() | {url}
    REPOSTED_PATH.write_text(json.dumps(sorted(seen), indent=1), encoding="utf-8")


def own_posts_aged(min_days: int, max_days: int) -> list[dict]:
    """Bài gốc của mình trong khoảng tuổi cho trước, chưa RT lại, có URL thật."""
    if not config.STATE_DIR.exists():
        return []
    from datetime import timedelta
    now = config.now()
    lo, hi = now - timedelta(days=max_days), now - timedelta(days=min_days)
    skip = reposted_urls()
    found: list[dict] = []
    for p in sorted(config.STATE_DIR.glob("state_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("posted", []):
            url = item.get("url", "")
            if item.get("kind") not in ("post", "thread"):
                continue
            if not url.startswith("http") or url in skip:
                continue
            try:
                when = datetime.fromisoformat(item["at"])
            except Exception:
                continue
            if lo <= when <= hi:
                found.append(item)
    return found


def history(days: int = 14) -> list[dict]:
    """Số liệu từng ngày trong `days` ngày gần nhất, cũ trước mới sau.

    Ngày không có file state vẫn được trả về với số 0 — biểu đồ cần đủ cột liên
    tục, thiếu ngày thì nhìn ra "ít" chứ không phải "không có dữ liệu".
    """
    from datetime import timedelta

    today = config.now().date()
    out: list[dict] = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        row = {"date": f"{d:%Y-%m-%d}", "posts": 0, "threads": 0, "replies": 0,
               "quotes": 0, "reposts": 0, "images": 0}
        p = _path_for(f"{d:%Y%m%d}")
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                data = {}
            row["posts"] = sum((data.get("posts_done") or {}).values())
            row["threads"] = 1 if data.get("thread_done") else 0
            row["replies"] = int(data.get("replies_done") or 0)
            row["quotes"] = int(data.get("quotes_done") or 0)
            row["reposts"] = int(data.get("reposts_done") or 0)
            row["images"] = len(data.get("images_used") or [])
        out.append(row)
    return out


def append_log(kind: str, fields: dict) -> None:
    """Một dòng TSV mỗi hành động, để xem lại bằng mắt hoặc Excel."""
    config.LOG_DIR.mkdir(parents=True, exist_ok=True)
    p = config.LOG_DIR / f"{kind}-{config.now():%Y-%m-%d}.tsv"
    cols = [f"{config.now():%H:%M:%S}"] + [
        str(fields.get(k, "")).replace("\t", " ").replace("\n", " ")
        for k in ("url", "target", "author", "chars", "text")
    ]
    with p.open("a", encoding="utf-8") as f:
        f.write("\t".join(cols) + "\n")
