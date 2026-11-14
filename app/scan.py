"""Cầu nối sang tools/kol_scanner.py — dùng lại đúng các cổng lọc của workflow."""
from __future__ import annotations

import importlib.util
import sys
from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _scanner():
    """Nạp tools/kol_scanner.py như một module (nó không nằm trong package)."""
    path = config.TOOLS / "kol_scanner.py"
    spec = importlib.util.spec_from_file_location("kol_scanner", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Không nạp được {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["kol_scanner"] = mod
    spec.loader.exec_module(mod)
    return mod


STOPWORDS = set("""
the a an and or but if then than that this these those is are was were be been being
have has had do does did will would can could should may might must of in on at to
for from with by about as into over after before just now new more most very really
it its it's they them their there here what which who whom when where why how all any
both each few other some such no nor not only own same so too s t don should've you
your yours he she his her we our us i me my mine one two three get got going go
""".split())

TICKER_RE = __import__("re").compile(r"\$[A-Za-z]{2,6}\b")
WORD_RE = __import__("re").compile(r"\b[A-Za-z][A-Za-z'\-]{2,}\b")


def topics(posts: list[dict], min_accounts: int = 2, top_n: int = 8) -> list[dict]:
    """Chủ đề đang được nhiều tài khoản nhắc cùng lúc.

    Đếm theo SỐ TÀI KHOẢN nhắc, không theo số lần xuất hiện — một người đăng năm
    bài về cùng một thứ không phải là trend.
    """
    import re
    from collections import defaultdict

    by_term: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[dict]] = defaultdict(list)

    for p in posts:
        author = p["handle"].lower()
        text = p.get("text", "")
        terms = set()
        for t in TICKER_RE.findall(text):
            terms.add(t.upper())
        for w in WORD_RE.findall(text):
            lw = w.lower()
            if lw in STOPWORDS or len(lw) < 4:
                continue
            # Giữ danh từ riêng và từ viết hoa (tên dự án, tổ chức, người).
            if w[0].isupper() or w.isupper():
                terms.add(w if w.isupper() else w.capitalize())
        for term in terms:
            by_term[term].add(author)
            if len(samples[term]) < 3:
                samples[term].append(p)

    rows = [
        {"term": t, "accounts": len(a),
         "engagement": sum(s.get("likes", 0) for s in samples[t]),
         "samples": samples[t]}
        for t, a in by_term.items() if len(a) >= min_accounts
    ]
    rows.sort(key=lambda r: (r["accounts"], r["engagement"]), reverse=True)
    return rows[:top_n]


async def find_trends(window_min: int = 720, top_n: int = 8) -> list[dict]:
    """Chủ đề nóng trên timeline. Quét rộng hơn reply vì trend cần nhiều mẫu."""
    ks = _scanner()
    api = ks.API(str(ks.DB_PATH))
    res = await ks.scan_pool(api, ks.load_targets(), window_min)
    # Lấy cả bài bị loại khỏi danh sách reply: chúng vẫn là tín hiệu chủ đề.
    pool = list(res["candidates"])
    seen = {c["url"] for c in pool}
    for r in res.get("rejected", []):
        if r["url"] not in seen:
            pool.append({"handle": r["handle"], "text": r.get("text", ""),
                         "likes": r.get("likes", 0), "url": r["url"]})
    return topics(pool, top_n=top_n)


async def find_mentions(handle: str, window_min: int = 1440,
                        top_n: int = 15) -> list[dict]:
    """Người đã CHỦ ĐỘNG tương tác với mình: reply bài mình, hoặc @ mình.

    Thêm 14/11. Automation rules của X chỉ cho reply tự động khi người nhận đã
    opt-in — "replying to a post from your account" hoặc mention mình. Đi tìm
    bài người lạ để chen vào thì không được, dù lọc kỹ cỡ nào.

    Cửa sổ ở đây RỘNG (mặc định 24h) chứ không phải 60 phút như lúc đi săn bài
    KOL: người ta hỏi mình thì trả lời muộn còn hơn không, và không có chuyện
    "chen vào sớm để khỏi bị chìm" nữa.
    """
    ks = _scanner()
    h = handle.lstrip("@")
    if not h:
        return []
    api = ks.API(str(ks.DB_PATH))
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_min)
    rows: list[dict] = []
    seen: set[str] = set()
    q = f"(to:{h} OR @{h}) -from:{h} -filter:nativeretweets"
    async for tw in api.search(q, limit=60, kv={"product": "Latest"}):
        if tw.date < cutoff or str(tw.id) in seen:
            continue
        author = tw.user.username or ""
        if author.lower() == h.lower():
            continue
        text = (tw.rawContent or "").strip()
        if not text:
            continue
        seen.add(str(tw.id))
        rows.append({
            "handle": author,
            "followers": tw.user.followersCount,
            "id": str(tw.id),
            "url": f"https://x.com/{author}/status/{tw.id}",
            "text": text[:280],
            "age_min": round((now - tw.date).total_seconds() / 60, 1),
            "likes": tw.likeCount,
            "retweets": tw.retweetCount,
            "replies": tw.replyCount,
            "views": tw.viewCount or 0,
            "date": tw.date.isoformat(),
            "tier": "đã tương tác với mình",
            "is_mention": True,
        })
    # Mới nhất trước: cuộc trò chuyện thì trả lời cái vừa tới, không phải cái nóng.
    rows.sort(key=lambda r: r["age_min"])
    return ks.diversify(rows, per_author=1)[:top_n]


async def find_candidates(window_min: int | None = None, top_n: int = 15) -> list[dict]:
    """Danh sách bài đáng reply, đã sắp theo điểm 'mới + nóng + còn chỗ'.

    Dùng search gộp (2 request cho 30 handle) chứ không phải 1 request/handle —
    acc phụ bị rate limit ngay trong 1 vòng quét nếu làm kiểu cũ.
    """
    ks = _scanner()
    window_min = window_min or ks.DEFAULT_MINUTES
    api = ks.API(str(ks.DB_PATH))
    res = await ks.scan_pool(api, ks.load_targets(), window_min)
    for e in res["errors"]:
        print(f"  scan warning: {e}", flush=True)
    return res["candidates"][:top_n]
