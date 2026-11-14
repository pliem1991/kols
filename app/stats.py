"""Đọc lại kết quả THẬT của những bài đã đăng.

Vì sao có file này: cho tới 14/11 app soạn 6 chủ đề, luân phiên đều nhau, rồi
không bao giờ nhìn lại. Mọi quyết định về nội dung đều là đoán — kể cả quyết
định chủ đề nào đáng có ảnh. Mà payout của X tính theo IMPRESSION, nên không đo
impression thì không biết mình đang đi đâu.

Nguồn số: twscrape đọc timeline của chính account (acc phụ, read-only). X trả
viewCount cho bài của bất kỳ ai, nên không cần đăng nhập bằng acc chính.

Hạn chế phải biết: viewCount ở đây là TỔNG lượt xem, còn payout chỉ tính
impression trên Home Timeline của người có Premium. Con số này luôn CAO HƠN số
X dùng để trả tiền. Nó dùng để so sánh bài với bài, không dùng để đoán tiền.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone

from . import config

os.environ.setdefault("TWS_TELEMETRY", "0")

CACHE = config.STATE_DIR / "stats.json"
MAX_AGE_MIN = 180          # bài mới cần thời gian tích view, quét dày vô ích
LOOKBACK = 60              # số bài gần nhất lấy về


def _own_posts() -> dict[str, dict]:
    """Bản đồ status_id -> thông tin bài do app ghi lại (chủ đề, ảnh, ngày)."""
    out: dict[str, dict] = {}
    if not config.STATE_DIR.exists():
        return out
    for p in sorted(config.STATE_DIR.glob("state_*.json")):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in data.get("posted", []):
            url = item.get("url", "")
            m = re.search(r"/status/(\d+)", url)
            if not m or item.get("kind") not in ("post", "thread", "quote"):
                continue
            out[m.group(1)] = {
                "pillar": item.get("pillar", ""),
                "image": bool(item.get("image")),
                "kind": item.get("kind", "post"),
                "at": item.get("at", ""),
                "text": item.get("text", "")[:160],
                "url": url,
            }
    return out


async def collect(handle: str, refresh: bool = False) -> dict:
    """Ghép số liệu thật vào từng bài, rồi tổng hợp theo chủ đề.

    Trả {"rows": [...], "by_pillar": {...}, "by_image": {...}, "at": iso}.
    """
    if not refresh and CACHE.exists():
        try:
            blob = json.loads(CACHE.read_text(encoding="utf-8"))
            at = datetime.fromisoformat(blob["at"])
            if (datetime.now(timezone.utc) - at).total_seconds() / 60 <= MAX_AGE_MIN:
                return blob
        except Exception:
            pass

    from twscrape import API
    api = API(str(config.TOOLS / "twscrape_accounts.db"))
    h = (handle or "").lstrip("@")
    if not h:
        return {"rows": [], "by_pillar": {}, "by_image": {}, "at": "", "why": "chưa có handle"}

    user = await api.user_by_login(h)
    if user is None:
        return {"rows": [], "by_pillar": {}, "by_image": {}, "at": "",
                "why": f"không đọc được @{h}"}

    mine = _own_posts()
    rows: list[dict] = []
    async for tw in api.user_tweets(user.id, limit=LOOKBACK):
        sid = str(tw.id)
        meta = mine.get(sid)
        if meta is None:
            continue           # bài đăng tay trước khi có app — không có chủ đề
        rows.append({
            "id": sid, "url": meta["url"], "pillar": meta["pillar"] or "?",
            "image": meta["image"], "kind": meta["kind"],
            "at": meta["at"][:16].replace("T", " "),
            "text": meta["text"],
            "views": tw.viewCount or 0, "likes": tw.likeCount,
            "replies": tw.replyCount, "reposts": tw.retweetCount,
            "age_h": round((datetime.now(timezone.utc) - tw.date).total_seconds() / 3600, 1),
        })

    rows.sort(key=lambda r: r["at"], reverse=True)
    blob = {"rows": rows, "by_pillar": _group(rows, lambda r: r["pillar"]),
            "by_image": _group(rows, lambda r: "có ảnh" if r["image"] else "không ảnh"),
            "at": datetime.now(timezone.utc).isoformat()}
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
    return blob


def _group(rows: list[dict], key) -> dict:
    """Trung bình view/like theo nhóm.

    Chỉ tính bài đã đủ 6 giờ: bài vừa đăng còn đang tích view, gộp chung vào
    sẽ kéo trung bình của chủ đề nào vừa tới lượt xuống thấp một cách giả tạo.
    """
    buckets: dict[str, list[dict]] = {}
    for r in rows:
        if r["age_h"] < 6:
            continue
        buckets.setdefault(key(r), []).append(r)
    out = {}
    for k, rs in buckets.items():
        n = len(rs)
        out[k] = {
            "n": n,
            "views": round(sum(r["views"] for r in rs) / n, 1),
            "likes": round(sum(r["likes"] for r in rs) / n, 2),
            "best": max(r["views"] for r in rs),
        }
    return dict(sorted(out.items(), key=lambda kv: kv[1]["views"], reverse=True))


def cached() -> dict:
    """Bản cache cho trang web — trang không được tự gọi mạng."""
    if not CACHE.exists():
        return {"rows": [], "by_pillar": {}, "by_image": {}, "at": ""}
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {"rows": [], "by_pillar": {}, "by_image": {}, "at": ""}
