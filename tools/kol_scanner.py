"""
KOL Scanner — find FRESH posts worth replying to.

Revised 2026-11-14 per workflows/reply_scheduler.md:
  - window is minutes, not hours (default 60) — a 12h-old post is already buried
  - prefers mid-tier authors, where a new reply actually gets read
  - rejects posts that already have too many replies
  - mega accounts only while the post is very young and thinly replied

Uses X SEARCH, not one timeline request per handle. 30 handles used to cost 30
requests and exhausted the burner account's quota within a single scan (measured
2026-11-14: "No active accounts, next available at 14:36"). Batched as
`(from:a OR from:b OR ...)` it costs 2 requests, and search results already carry
the author's follower count, so no per-user lookups are needed either.

Usage:
    python kol_scanner.py [--top N] [--minutes M] [--json-only] [--quiet]

Target handles come from tools/reply_targets.txt when that file exists
(one handle per line, '#' starts a comment), otherwise from SEED_POOL below.
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["TWS_TELEMETRY"] = "0"

from twscrape import API

HERE = Path(__file__).parent
DB_PATH = HERE / "twscrape_accounts.db"
TARGETS_FILE = HERE / "reply_targets.txt"
OUT_DIR = HERE.parent / "posts"

# --- gates from the workflow -------------------------------------------------
DEFAULT_MINUTES = 60
MIN_FOLLOWERS = 10_000
# Measured 2026-11-14: most handles worth replying to sit at 200k-900k, and the
# real crowding signal is MAX_REPLIES, not follower count. The original 200k
# ceiling rejected 18 of 30 seed handles outright.
MAX_FOLLOWERS = 600_000
MAX_REPLIES = 80            # past this a new reply is invisible
MEGA_FOLLOWERS = 1_500_000
MEGA_MAX_AGE_MIN = 15       # mega accounts only if the post is this fresh
MEGA_MAX_REPLIES = 50
# Measured 2026-11-14: link-only posts ("Update, the plaque is going back up
# <t.co link>") passed every other gate, then the reply step correctly refused
# all of them — one wasted model call each. Gate them here on body text instead.
MIN_BODY_CHARS = 80

BATCH_SIZE = 15             # handles per search query
SEARCH_LIMIT = 60           # tweets per query

SEED_POOL = [
    # crypto / markets
    "thedefiedge", "CryptoWizardd", "MustStopMurad", "0xfoobar", "0xngmi",
    "DefiIgnas", "hosseeb", "eigenphi", "pet3rpan_", "smyyguy",
    "Darrenlautf", "RyanSAdams", "TrustlessState", "StaniKulechov", "sassal0x",
    "milesdeutscher", "CryptoKaleo", "Pentosh1",
    # AI — the crossover audience that actually buys Premium
    "DrJimFan", "hardmaru", "_akhaliq", "swyx", "simonw",
    "rasbt", "giffmana", "emollick", "goodside", "AndrewCurran_",
]


def load_targets() -> list[str]:
    if TARGETS_FILE.exists():
        handles = []
        for line in TARGETS_FILE.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip().lstrip("@")
            if line:
                handles.append(line)
        if handles:
            return handles
    return SEED_POOL


def out(msg: str = "") -> None:
    """Print without dying on emoji under the Windows console codepage."""
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", "replace"))
    sys.stdout.flush()


def body_text(text: str) -> str:
    """The post's own words: links and bare @mentions stripped."""
    t = re.sub(r"https?://\S+", " ", text or "")
    t = re.sub(r"(?:^|\s)@\w+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def judge(age_min: float, replies: int, followers: int, window_min: int,
          text: str = "x" * MIN_BODY_CHARS):
    """Return (ok, reason). Reason explains a rejection, or names the tier."""
    if age_min > window_min:
        return False, f"too old ({age_min:.0f}m)"

    body = body_text(text)
    if len(body) < MIN_BODY_CHARS:
        return False, f"only {len(body)} chars of body text (link-only?)"

    if followers >= MEGA_FOLLOWERS:
        if age_min > MEGA_MAX_AGE_MIN:
            return False, f"mega acct, post {age_min:.0f}m old (need <{MEGA_MAX_AGE_MIN}m)"
        if replies > MEGA_MAX_REPLIES:
            return False, f"mega acct, {replies} replies already"
        return True, "mega-early"

    if followers < MIN_FOLLOWERS:
        return False, f"only {followers:,} followers"
    if followers > MAX_FOLLOWERS:
        return False, f"{followers:,} followers, above band"
    if replies > MAX_REPLIES:
        return False, f"{replies} replies already, buried"
    return True, "mid-tier"


def rank(c: dict) -> float:
    """Prefer young posts that are heating up but not yet crowded."""
    heat = c["likes"] + c["retweets"] * 2
    freshness = max(0.0, 1.0 - c["age_min"] / 60.0)   # 1.0 at 0m -> 0 at 60m
    room = 1.0 / (1 + c["replies"] / 20.0)            # fewer replies = more room
    return heat * (0.3 + freshness) * room


def diversify(rows: list[dict], per_author: int = 2) -> list[dict]:
    """Cap how many candidates one author can occupy.

    Without this, the single most active handle fills the whole shortlist (6 of 8
    on the first run), while the daily limit is 2 replies per author anyway.
    """
    kept: list[dict] = []
    count: dict[str, int] = {}
    for r in rows:
        a = r["handle"].lower()
        if count.get(a, 0) >= per_author:
            continue
        count[a] = count.get(a, 0) + 1
        kept.append(r)
    return kept


def _batches(items: list[str], n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


async def scan_pool(api: API, handles: list[str], window_min: int) -> dict:
    """One search per batch of handles. Returns candidates + per-handle tallies."""
    wanted = {h.lower() for h in handles}
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=window_min)

    candidates: list[dict] = []
    rejected: list[dict] = []
    seen: dict[str, dict] = {h.lower(): {"handle": h, "seen": 0, "kept": 0}
                             for h in handles}
    errors: list[str] = []

    for batch in _batches(handles, BATCH_SIZE):
        q = ("(" + " OR ".join(f"from:{h}" for h in batch) + ")"
             " -filter:replies -filter:nativeretweets")
        try:
            async for tw in api.search(q, limit=SEARCH_LIMIT, kv={"product": "Latest"}):
                author = (tw.user.username or "").lower()
                if author not in wanted:
                    continue
                if tw.date < cutoff - timedelta(minutes=window_min * 3):
                    continue

                seen[author]["seen"] += 1
                age_min = (now - tw.date).total_seconds() / 60
                followers = tw.user.followersCount
                raw_text = (tw.rawContent or "").strip()
                ok, reason = judge(age_min, tw.replyCount, followers, window_min,
                                   raw_text)
                row = {
                    "handle": tw.user.username,
                    "followers": followers,
                    "id": str(tw.id),
                    "url": f"https://x.com/{tw.user.username}/status/{tw.id}",
                    "text": raw_text[:280],
                    "age_min": round(age_min, 1),
                    "likes": tw.likeCount,
                    "retweets": tw.retweetCount,
                    "replies": tw.replyCount,
                    "views": tw.viewCount or 0,
                    "date": tw.date.isoformat(),
                    "tier": reason if ok else None,
                }
                if ok:
                    candidates.append(row)
                    seen[author]["kept"] += 1
                else:
                    # Giữ cả nội dung: bài không hợp để reply vẫn là tín hiệu
                    # chủ đề cho phần dò trend (app/scan.py).
                    rejected.append({"handle": row["handle"], "url": row["url"],
                                     "text": row["text"], "likes": row["likes"],
                                     "why": reason})
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")

    candidates.sort(key=rank, reverse=True)
    candidates = diversify(candidates)
    return {"candidates": candidates, "rejected": rejected,
            "per_handle": list(seen.values()), "errors": errors}


async def main():
    argv = sys.argv
    top_n = int(argv[argv.index("--top") + 1]) if "--top" in argv else 15
    window = int(argv[argv.index("--minutes") + 1]) if "--minutes" in argv else DEFAULT_MINUTES
    json_only = "--json-only" in argv
    quiet = json_only or "--quiet" in argv

    handles = load_targets()
    api = API(str(DB_PATH))

    n_req = (len(handles) + BATCH_SIZE - 1) // BATCH_SIZE
    if not quiet:
        src = TARGETS_FILE.name if TARGETS_FILE.exists() else "SEED_POOL"
        out(f"Searching {len(handles)} handles from {src} in {n_req} request(s), "
            f"posts under {window} min old\n")

    res = await scan_pool(api, handles, window)
    pool = res["candidates"][:top_n]

    ts = datetime.now()
    out_path = OUT_DIR / f"kol_scan_{ts:%Y%m%d_%H%M}.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "scanned_at": ts.isoformat(),
        "window_minutes": window,
        "requests": n_req,
        "gates": {
            "min_followers": MIN_FOLLOWERS, "max_followers": MAX_FOLLOWERS,
            "max_replies": MAX_REPLIES, "mega_followers": MEGA_FOLLOWERS,
            "mega_max_age_min": MEGA_MAX_AGE_MIN,
        },
        "candidates": pool,
        "rejected": res["rejected"],
        "per_handle": res["per_handle"],
        "errors": res["errors"],
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    if json_only:
        out(str(out_path))
        return

    out("=" * 66)
    out(f"{len(pool)} REPLY CANDIDATE(S)   "
        f"(saw {sum(h['seen'] for h in res['per_handle'])} posts, "
        f"rejected {len(res['rejected'])})")
    out("=" * 66)
    for i, c in enumerate(pool, 1):
        out(f"#{i} @{c['handle']} ({c['followers']:,}) — {c['age_min']}m old, "
            f"{c['replies']} replies, {c['likes']} likes  [{c['tier']}]")
        out(f"   {c['url']}")
        out(f"   {c['text'][:150]}")
        out("")

    if res["rejected"] and not pool:
        out("Why the recent posts were rejected:")
        for r in res["rejected"][:12]:
            out(f"   @{r['handle']:<16} {r['why']}")
        out("")

    for e in res["errors"]:
        out(f"SEARCH ERROR: {e}")

    if not pool:
        out("No candidate. Normal outside the posting windows. Sanity-check with")
        out("  --minutes 1440")
    out(f"Saved: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
