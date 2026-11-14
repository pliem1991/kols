"""
KOL Scanner — Find hot posts from target KOLs for reply engagement
Usage: python kol_scanner.py [--top N] [--hours H]
Default window is 12h (per reply_scheduler workflow freshness rule).
"""
import asyncio
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

os.environ["TWS_TELEMETRY"] = "0"

from twscrape import API

DB_PATH = Path(__file__).parent / "twscrape_accounts.db"

TARGET_KOLS = [
    "elonmusk",
    "cz_binance",
    "VitalikButerin",
    "saylor",
    "WatcherGuru",
    "APompliano",
    "brian_armstrong",
    "aantonop",
    "DocumentingBTC",
    "emollick",
    "DrJimFan",
    "MustStopMurad",
    "thedefiedge",
    "Excellion",
    "CryptoWizardd",
    "AndrewYNg",
    "ylecun",
]

DEFAULT_HOURS = 12

async def scan_kol(api: API, username: str, hours_back: int = DEFAULT_HOURS):
    """Get recent tweets from a KOL, sorted by engagement."""
    try:
        user = await api.user_by_login(username)
        tweets = []
        async for tweet in api.user_tweets(user.id, limit=20):
            age = datetime.now(timezone.utc) - tweet.date
            if age > timedelta(hours=hours_back):
                continue
            engagement = tweet.likeCount + tweet.retweetCount * 2 + tweet.replyCount
            tweets.append({
                "id": tweet.id,
                "url": f"https://x.com/{username}/status/{tweet.id}",
                "text": tweet.rawContent[:200],
                "likes": tweet.likeCount,
                "retweets": tweet.retweetCount,
                "replies": tweet.replyCount,
                "engagement": engagement,
                "date": tweet.date.isoformat(),
            })
        tweets.sort(key=lambda t: t["engagement"], reverse=True)
        return {
            "username": username,
            "followers": user.followersCount,
            "top_tweets": tweets[:3],
        }
    except Exception as e:
        return {"username": username, "error": str(e)}

async def main():
    top_n = 5
    if "--top" in sys.argv:
        idx = sys.argv.index("--top")
        top_n = int(sys.argv[idx + 1])

    hours_back = DEFAULT_HOURS
    if "--hours" in sys.argv:
        idx = sys.argv.index("--hours")
        hours_back = int(sys.argv[idx + 1])

    api = API(str(DB_PATH))
    print(f"Scanning {len(TARGET_KOLS)} KOLs for hot posts (last {hours_back}h)...\n")

    results = []
    for kol in TARGET_KOLS:
        print(f"  Scanning @{kol}...", end=" ", flush=True)
        result = await scan_kol(api, kol, hours_back)
        if "error" in result:
            print(f"ERROR: {result['error']}")
        else:
            tweet_count = len(result["top_tweets"])
            print(f"OK — {result['followers']:,} followers, {tweet_count} recent tweets")
        results.append(result)

    all_tweets = []
    for r in results:
        if "error" in r:
            continue
        for t in r.get("top_tweets", []):
            t["kol"] = r["username"]
            t["kol_followers"] = r["followers"]
            all_tweets.append(t)

    all_tweets.sort(key=lambda t: t["engagement"], reverse=True)

    print(f"\n{'='*60}")
    print(f"TOP {top_n} HOTTEST POSTS TO REPLY TO:")
    print(f"{'='*60}\n")

    for i, t in enumerate(all_tweets[:top_n], 1):
        print(f"#{i} @{t['kol']} ({t['kol_followers']:,} followers)")
        print(f"   {t['url']}")
        print(f"   Engagement: {t['likes']:,} likes, {t['retweets']:,} RTs, {t['replies']:,} replies")
        print(f"   \"{t['text']}\"")
        print()

    output_path = Path(__file__).parent.parent / "posts" / f"kol_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"scanned_at": datetime.now().isoformat(), "results": results}, f, indent=2, ensure_ascii=False)
    print(f"Full results saved to: {output_path}")

if __name__ == "__main__":
    asyncio.run(main())
