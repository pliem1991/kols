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
# Ký tự đứng trước một từ thì từ đó mở đầu câu -> viết hoa KHÔNG còn là bằng
# chứng danh từ riêng.
SENT_END = set(".!?:;\n\r\"'“”‘’()[]-—…*")


def _cap_terms(text: str) -> list[tuple[str, bool]]:
    """Mọi từ viết hoa trong bài, kèm cờ "nằm giữa câu".

    Hai từ hoa đứng liền nhau thì gộp ("United" + "States" -> "United States"),
    vì tách ra là ra hai chủ đề giả cho cùng một thứ.
    """
    hits: list[tuple[int, int, str, bool]] = []
    for m in WORD_RE.finditer(text):
        w = m.group(0)
        if len(w) < 4 or w.lower() in STOPWORDS:
            continue
        if not (w[0].isupper() or w.isupper()):
            continue
        before = text[:m.start()].rstrip()
        mid = bool(before) and before[-1] not in SENT_END
        hits.append((m.start(), m.end(), w if w.isupper() else w.capitalize(),
                     mid))

    out: list[tuple[str, bool]] = []
    i = 0
    while i < len(hits):
        _, e, w, mid = hits[i]
        if i + 1 < len(hits) and text[e:hits[i + 1][0]].strip() == "":
            nxt = hits[i + 1]
            out.append((f"{w} {nxt[2]}", mid or nxt[3]))
            i += 2
            continue
        out.append((w, mid))
        i += 1
    return out


def topics(posts: list[dict], min_accounts: int = 2, top_n: int = 8) -> list[dict]:
    """Chủ đề đang được nhiều tài khoản nhắc cùng lúc.

    Đếm theo SỐ TÀI KHOẢN nhắc, không theo số lần xuất hiện — một người đăng năm
    bài về cùng một thứ không phải là trend.
    """
    import re
    from collections import defaultdict

    by_term: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[dict]] = defaultdict(list)

    # Lượt 1 — học xem từ nào THẬT SỰ là tên riêng: từ nào từng viết hoa ở GIỮA
    # câu, ở bất kỳ bài nào. Viết hoa đầu câu chỉ là luật chính tả, không phải
    # tín hiệu chủ đề; bài 15/11 ra biểu đồ gồm "Last", "States", "United",
    # "Seems" đúng vì xét chữ hoa mà không xét vị trí. Nhưng chặn thẳng từ đầu
    # câu thì mất luôn tên riêng mở đầu bài ("Anthropic shipped..."), nên học ở
    # mức TOÀN BỘ mẫu rồi mới áp xuống từng bài.
    caps = [(p, _cap_terms(p.get("text", ""))) for p in posts]
    proper = {t for _, ts in caps for t, mid in ts if mid or t.isupper()}

    for p, cap in caps:
        author = p["handle"].lower()
        text = p.get("text", "")
        terms = {t.upper() for t in TICKER_RE.findall(text)}
        terms |= {t for t, _ in cap if t in proper}
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


FOLLOWING_CACHE = config.STATE_DIR / "following.json"
FOLLOWING_MAX_AGE_H = 24

# Tài khoản không đăng tiếng Anh thì gạch hẳn, không quét lại mỗi vòng. Cần
# thấy ít nhất ngần này bài của họ trước khi kết luận.
LANG_MIN_SEEN = 3


def _blob() -> dict:
    import json
    if FOLLOWING_CACHE.exists():
        try:
            return json.loads(FOLLOWING_CACHE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_blob(blob: dict) -> None:
    import json
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    FOLLOWING_CACHE.write_text(json.dumps(blob, ensure_ascii=False, indent=1),
                               encoding="utf-8")


def _learn_langs(per_handle: list[dict]) -> int:
    """Ghi nhớ handle chỉ đăng tiếng không phải Anh. Trả số handle mới gạch.

    Vì sao: danh sách following có 58 tài khoản qua band follower, nhưng phần
    lớn là acc airdrop tiếng Việt từ 2024. Lọc theo band thì chúng vẫn lọt vào
    mọi vòng quét (58 handle = 4 request của acc phụ), rồi mới bị loại ở mức
    từng BÀI vì cờ lang. Acc phụ có hạn mức request, nên loại ở mức TÀI KHOẢN
    rẻ hơn hẳn. Đo 15/11: 69 bài trong 6 giờ, ra đúng 1 ứng viên tiếng Anh.
    """
    blob = _blob()
    skip = set(blob.get("skip") or [])
    before = len(skip)
    for h in per_handle:
        if h["seen"] >= LANG_MIN_SEEN and h.get("en", 0) == 0:
            skip.add(h["handle"].lower())
    if len(skip) != before:
        blob["skip"] = sorted(skip)
        _save_blob(blob)
    return len(skip) - before


async def following_handles(handle: str, refresh: bool = False) -> list[str]:
    """Các tài khoản MÌNH đang follow, đã lọc theo cùng band follower của
    reply_targets.txt.

    Thêm 14/11 theo yêu cầu: reply thêm bài của người mình follow. Lọc band
    ngay ở đây vì danh sách following trả sẵn followersCount — lọc trước thì
    vòng quét sau đỡ được vài request, mà acc phụ đã dính rate limit một lần
    (22:00 ngày 14/11).
    """
    import json
    from datetime import datetime, timedelta, timezone

    skip = {h.lower() for h in (_blob().get("skip") or [])}
    if not refresh and FOLLOWING_CACHE.exists():
        try:
            blob = json.loads(FOLLOWING_CACHE.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(blob["at"])
            if datetime.now(timezone.utc) - at <= timedelta(hours=FOLLOWING_MAX_AGE_H):
                return [h for h in blob["handles"] if h.lower() not in skip]
        except Exception:
            pass

    ks = _scanner()
    api = ks.API(str(ks.DB_PATH))
    who = (handle or "").lstrip("@")
    # Nói rõ đang đọc following của AI: acc CHÍNH là đối tượng, acc phụ chỉ là
    # cái máy đọc. Hai vai này dễ lẫn khi đọc code (chủ dự án hỏi 15/11).
    print(f"  đọc danh sách following của @{who} (acc chính) bằng acc phụ",
          flush=True)
    me = await api.user_by_login(who)
    if me is None:
        print(f"  KHÔNG đọc được @{who} — bỏ qua nguồn following", flush=True)
        return []
    out: list[str] = []
    async for u in api.following(me.id, limit=400):
        n = u.followersCount
        if ks.MIN_FOLLOWERS <= n <= ks.MEGA_FOLLOWERS and u.username:
            out.append(u.username)
    blob = _blob()
    blob.update(at=datetime.now(timezone.utc).isoformat(), handles=out)
    _save_blob(blob)
    return [h for h in out if h.lower() not in skip]


async def find_from_following(handle: str, window_min: int,
                              top_n: int = 15) -> list[dict]:
    """Bài đáng reply trong số những người mình đang follow."""
    handles = await following_handles(handle)
    if not handles:
        return []
    ks = _scanner()
    api = ks.API(str(ks.DB_PATH))
    res = await ks.scan_pool(api, handles, window_min)
    # Gạch hẳn những handle vừa lộ ra là không đăng tiếng Anh, để vòng sau khỏi
    # tốn request cho họ nữa.
    n = _learn_langs(res["per_handle"])
    if n:
        print(f"  gạch {n} tài khoản following không đăng tiếng Anh", flush=True)
    # Chỉ giữ bài tiếng Anh. Reply tiếng Anh dưới bài tiếng Việt không tới được
    # ai trong nhóm mình nhắm, mà vẫn tốn một lượt trong hạn mức ngày.
    out = [c for c in res["candidates"] if (c.get("lang") or "en") == "en"]
    for c in out:
        c["tier"] = (c.get("tier") or "") + " · mình đang follow"
    return out[:top_n]


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
    # Ai đã mở lời với mình thì đáng theo dõi lâu dài — đây là một trong hai
    # nguồn HỢP LỆ để danh sách đối tượng tự lớn lên (xem app/targets.py).
    from . import targets
    for r in rows:
        if not targets.add(r["handle"], r["followers"], "mention"):
            print(f"  thêm @{r['handle']} vào danh sách reply (đã mention mình)",
                  flush=True)

    # Mới nhất trước: cuộc trò chuyện thì trả lời cái vừa tới, không phải cái nóng.
    rows.sort(key=lambda r: r["age_min"])
    return ks.diversify(rows, per_author=1)[:top_n]


async def find_candidates(window_min: int | None = None, top_n: int = 15) -> list[dict]:
    """Danh sách bài đáng reply, đã sắp theo điểm 'mới + nóng + còn chỗ'.

    Dùng search gộp (2 request cho 30 handle) chứ không phải 1 request/handle —
    acc phụ bị rate limit ngay trong 1 vòng quét nếu làm kiểu cũ.
    """
    from . import targets

    ks = _scanner()
    window_min = window_min or ks.DEFAULT_MINUTES
    api = ks.API(str(ks.DB_PATH))
    res = await ks.scan_pool(api, ks.load_targets(), window_min)
    for e in res["errors"]:
        print(f"  scan warning: {e}", flush=True)
    # Ghi lại ai được nhìn tới, ai ra ứng viên — để sau này gỡ được handle chết
    # thay vì cứ tốn request cho nó mãi.
    targets.record_scan(res["per_handle"], res["candidates"])
    return res["candidates"][:top_n]
