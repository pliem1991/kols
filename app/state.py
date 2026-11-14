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
    notes: list[str] = field(default_factory=list)

    # --- truy vấn ----------------------------------------------------------
    def posts_in(self, window: str) -> int:
        return self.posts_done.get(window, 0)

    def can_reply_to(self, author: str) -> bool:
        if self.replies_done >= config.MAX_REPLIES_PER_DAY:
            return False
        a = author.lower()
        return self.replied_authors.get(a, 0) < config.MAX_REPLIES_PER_AUTHOR_PER_DAY

    def already_replied(self, tweet_id: str) -> bool:
        return str(tweet_id) in self.replied_tweet_ids

    def already_touched(self, tweet_id: str) -> bool:
        """Đã reply HOẶC đã quote bài này — đừng đụng vào lần hai."""
        t = str(tweet_id)
        return t in self.replied_tweet_ids or t in self.quoted_tweet_ids

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

    def record_post(self, window: str, url: str, text: str, kind: str = "post") -> None:
        if kind == "thread":
            self.thread_done = True
        else:
            self.posts_done[window] = self.posts_done.get(window, 0) + 1
        self.posted.append({
            "kind": kind, "window": window, "url": url,
            "at": config.now().isoformat(), "text": text[:400],
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
