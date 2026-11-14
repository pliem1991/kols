"""Today's News + What's happening lấy thẳng từ x.com.

Đây là mục bạn thấy ở cột phải x.com. twscrape có sẵn endpoint này
(`api.trends("news")`) nên không cần mở browser, dùng chung acc phụ read-only.

Khác với app/scan.py:
  - scan.topics()  = chủ đề mà DANH SÁCH KOL của mình đang nói (hẹp, tự đo).
  - xnews.fetch()  = cái X cho là tin/trend của cả nền tảng (rộng, X đo).
Hai nguồn bổ sung nhau, prompt nhận cả hai.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone

from . import config

os.environ.setdefault("TWS_TELEMETRY", "0")

CACHE = config.STATE_DIR / "xnews.json"
CACHE_MAX_AGE_MIN = 25          # trend đổi nhanh, nhưng đừng gọi mỗi vòng lặp

# Chỉ giữ thứ đúng chủ đề của account. Bỏ chính trị, thể thao, drama —
# vừa lạc đề vừa là vùng rủi ro không cần dây vào.
KEEP_DOMAINS = ("business", "finance", "technology", "science", "crypto")
KEEP_WORDS = re.compile(
    r"\b(bitcoin|btc|ethereum|eth|solana|sol|crypto|stablecoin|defi|token|"
    r"altcoin|binance|coinbase|etf|sec\b|cftc|blockchain|onchain|on-chain|"
    r"halving|liquidat|exchange|wallet|nvidia|nvda|openai|anthropic|claude|"
    r"chatgpt|gpt-?\d|llm|\bai\b|artificial intelligence|gpu|datacenter|"
    r"data center|semiconductor|chip|fed\b|inflation|cpi|rate cut|treasury|"
    r"nasdaq|s&p|tsla|tesla|apple|microsoft|google|meta\b|amd\b|tsmc)",
    re.I,
)
# Thấy mấy từ này thì bỏ hẳn, kể cả khi lọt lưới trên.
DROP_WORDS = re.compile(
    r"\b(election|senate|congress|president|shooting|arrest|verdict|nfl|nba|"
    r"premier league|world cup|oscars|grammy|taylor swift)\b", re.I)


@dataclass
class Item:
    kind: str          # "news" = tiêu đề Today's News · "trend" = What's happening
    name: str
    domain: str        # vd "Business & finance · Trending", news thì rỗng
    url: str           # link x.com mở được bằng trình duyệt

    def line(self) -> str:
        tag = "TIN" if self.kind == "news" else "TREND"
        d = f" [{self.domain}]" if self.domain else ""
        return f"- ({tag}) {self.name}{d}"


def _relevant(name: str, domain: str) -> bool:
    if DROP_WORDS.search(name):
        return False
    if KEEP_WORDS.search(name):
        return True
    return any(k in domain.lower() for k in KEEP_DOMAINS)


def _api():
    from twscrape import API
    return API(str(config.TOOLS / "twscrape_accounts.db"))


def _web_url(name: str, raw: str) -> str:
    """trend_url là deep link twitter:// — đổi sang https để bấm được."""
    if "trending/" in raw:
        return "https://x.com/i/trending/" + raw.rsplit("trending/", 1)[1]
    from urllib.parse import quote
    return f"https://x.com/search?q={quote(name)}&src=trend_click"


def _load_cache() -> list[Item] | None:
    if not CACHE.exists():
        return None
    try:
        blob = json.loads(CACHE.read_text(encoding="utf-8"))
        at = datetime.fromisoformat(blob["fetched_at"])
    except Exception:
        return None
    if datetime.now(timezone.utc) - at > timedelta(minutes=CACHE_MAX_AGE_MIN):
        return None
    return [Item(**i) for i in blob["items"]]


async def fetch(limit: int = 20, refresh: bool = False) -> list[Item]:
    """Today's News + trend, đã lọc còn crypto/AI/thị trường."""
    if not refresh:
        cached = _load_cache()
        if cached is not None:
            return cached

    api = _api()
    items: list[Item] = []
    seen: set[str] = set()
    async for t in api.trends("news", limit=limit):
        name = (t.name or "").strip()
        if not name or name.lower() in seen:
            continue
        raw = ""
        meta = getattr(t, "trend_metadata", None)
        domain = (getattr(meta, "domain_context", None) or "") if meta else ""
        tu = getattr(t, "trend_url", None)
        if tu is not None:
            raw = getattr(tu, "url", "") or ""
        if not _relevant(name, domain):
            continue
        seen.add(name.lower())
        items.append(Item(
            kind="news" if "trending/" in raw else "trend",
            name=name, domain=domain, url=_web_url(name, raw)))

    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(
        {"fetched_at": datetime.now(timezone.utc).isoformat(),
         "items": [asdict(i) for i in items]},
        ensure_ascii=False, indent=1), encoding="utf-8")
    return items


def as_prompt_block(items: list[Item] | None) -> str:
    if not items:
        return "(không lấy được tin/trend từ X)"
    return "\n".join(i.line() for i in items[:12])


ACCOUNT_CACHE = config.STATE_DIR / "account.json"
ACCOUNT_MAX_AGE_MIN = 360


async def account_stats(handle: str, refresh: bool = False) -> dict | None:
    """Follower/post count của chính acc mình — để biết còn cách mốc payout bao xa.

    Điều kiện Original Content Rewards: Premium + 500 follower đã xác minh +
    500.000 impression Home Timeline / 90 ngày (reply KHÔNG tính). Impression thì
    chỉ X mới biết, nhưng follower thì đọc được, và đó là mốc chặn đầu tiên.
    """
    if not handle:
        return None
    if not refresh and ACCOUNT_CACHE.exists():
        try:
            blob = json.loads(ACCOUNT_CACHE.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(blob["at"])
            if (datetime.now(timezone.utc) - at
                    <= timedelta(minutes=ACCOUNT_MAX_AGE_MIN)):
                return blob
        except Exception:
            pass
    u = await _api().user_by_login(handle.lstrip("@"))
    if u is None:
        return None
    blob = {"handle": u.username, "followers": u.followersCount,
            "following": u.friendsCount, "posts": u.statusesCount,
            "at": datetime.now(timezone.utc).isoformat()}
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    ACCOUNT_CACHE.write_text(json.dumps(blob, ensure_ascii=False, indent=1),
                             encoding="utf-8")
    return blob


def cached_items() -> list[Item]:
    """Bản cache cho trang web — trang không được tự gọi mạng."""
    return _load_cache() or []


def cached_account() -> dict | None:
    if not ACCOUNT_CACHE.exists():
        return None
    try:
        return json.loads(ACCOUNT_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return None


async def posts_for(name: str, window_min: int, limit: int = 20) -> list[dict]:
    """Bài thật đang nói về một tin/trend — trả đúng shape của kol_scanner.

    Dùng cho hai việc: làm dẫn chứng cho bài viết, và làm target reply khi
    danh sách KOL không có gì mới (ngoài giờ Mỹ thì hay rơi vào trường hợp này).
    """
    from .scan import _scanner
    ks = _scanner()
    api = _api()
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_min)
    rows: list[dict] = []
    async for tw in api.search_trend(name, limit=limit):
        if tw.date < cutoff:
            continue
        age_min = (now - tw.date).total_seconds() / 60
        raw_text = (tw.rawContent or "").strip()
        ok, reason = ks.judge(age_min, tw.replyCount, tw.user.followersCount,
                              window_min, raw_text)
        if not ok:
            continue
        rows.append({
            "handle": tw.user.username,
            "followers": tw.user.followersCount,
            "id": str(tw.id),
            "url": f"https://x.com/{tw.user.username}/status/{tw.id}",
            "text": raw_text[:280],
            "age_min": round(age_min, 1),
            "likes": tw.likeCount,
            "retweets": tw.retweetCount,
            "replies": tw.replyCount,
            "views": tw.viewCount or 0,
            "date": tw.date.isoformat(),
            "tier": f"{reason} · trend:{name[:40]}",
            "topic": name,
        })
    rows.sort(key=ks.rank, reverse=True)
    return ks.diversify(rows, per_author=1)
