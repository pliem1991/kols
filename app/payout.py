"""Theo dõi hai con số quyết định payout, ghi lại theo ngày.

Tại sao tách riêng khỏi app/stats.py: stats đọc `viewCount` — tổng lượt xem,
ai xem cũng tính. Còn X chỉ trả tiền theo **verified impression**: người xem
phải có Premium, phải trên Home Timeline, reply không tính. Ngày 14/11 hai con
số chênh nhau rất xa (6 view/bài so với 8 impression trong CẢ 90 ngày), nên gộp
chung là tự lừa mình.

Chỉ số dẫn đường là **verified follower**, không phải view: 29 -> 500 mới là
đường đi, view lên xuống không nói lên điều gì.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta

from . import config

HISTORY = config.STATE_DIR / "payout.json"
CHECK_EVERY_H = 12          # số này nhích theo ngày, quét dày vô ích

NEED_FOLLOWERS = 500
NEED_IMPRESSIONS = 500_000


def load() -> list[dict]:
    if not HISTORY.exists():
        return []
    try:
        return json.loads(HISTORY.read_text(encoding="utf-8"))
    except Exception:
        return []


def latest() -> dict | None:
    rows = load()
    return rows[-1] if rows else None


def due() -> bool:
    last = latest()
    if last is None:
        return True
    try:
        when = datetime.fromisoformat(last["at"])
    except Exception:
        return True
    return config.now() - when >= timedelta(hours=CHECK_EVERY_H)


def record(row: dict) -> list[dict]:
    """Một dòng mỗi lần đo. Cùng ngày đo lại thì ghi đè dòng của ngày đó."""
    rows = load()
    day = row["at"][:10]
    rows = [r for r in rows if r.get("at", "")[:10] != day]
    rows.append(row)
    rows.sort(key=lambda r: r.get("at", ""))
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    HISTORY.write_text(json.dumps(rows, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    return rows


def progress() -> dict:
    """Số mới nhất + thay đổi 7 ngày + ước lượng thời gian tới mốc."""
    rows = load()
    if not rows:
        return {}
    cur = rows[-1]
    f = cur.get("verified_followers") or 0
    i = cur.get("impressions_90d") or 0

    week = None
    cutoff = config.now() - timedelta(days=7)
    older = [r for r in rows[:-1]
             if datetime.fromisoformat(r["at"]) <= cutoff] or rows[:-1]
    if older:
        prev = older[-1]
        days = max(0.5, (datetime.fromisoformat(cur["at"])
                         - datetime.fromisoformat(prev["at"])).total_seconds() / 86400)
        gain = f - (prev.get("verified_followers") or 0)
        week = {"days": round(days, 1), "gain": gain,
                "per_day": round(gain / days, 2)}

    eta = None
    if week and week["per_day"] > 0:
        left = NEED_FOLLOWERS - f
        if left > 0:
            eta = round(left / week["per_day"])

    return {
        "followers": f, "need_followers": NEED_FOLLOWERS,
        "impressions": i, "need_impressions": NEED_IMPRESSIONS,
        "pct": round(min(100.0, f / NEED_FOLLOWERS * 100), 1),
        "at": cur.get("at", ""), "week": week, "eta_days": eta,
        "points": [{"d": r["at"][5:10],
                    "f": r.get("verified_followers") or 0,
                    "i": r.get("impressions_90d") or 0} for r in rows[-30:]],
    }
