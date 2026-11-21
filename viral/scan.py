"""Quét X tìm video đang lên nhanh.

Đường đi: twscrape (acc PHỤ, chỉ đọc) -> lọc -> chấm nóng -> lấy 5 cái đầu ->
nhờ Claude viết mô tả tiếng Việt -> ghi vào viral/videos.json.

KHÔNG đụng @macropandaX, KHÔNG tải video, KHÔNG đăng gì.
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from twscrape import API

from . import store

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "tools" / "twscrape_accounts.db"
CLAUDE_ENV = ROOT / "tools" / "claude.env"
MODEL = "claude-sonnet-5-5"

PER_RUN = 5             # chủ dự án chốt 21/11: mỗi lần đưa 5 video
MAX_AGE_H = 48          # cũ hơn thì hết "đang lên"
MIN_VIEWS = 20_000
SEARCH_LIMIT = 60

# Mỗi dòng là một lần gọi search. Nhiều truy vấn nhỏ ra nhiều kiểu video hơn
# một truy vấn to, mà vẫn nằm trong hạn mức của acc phụ.
QUERIES = (
    "filter:native_video min_faves:3000 -filter:replies",
    "filter:native_video min_retweets:1500 -filter:replies",
    "filter:native_video min_faves:1500 -filter:replies lang:en",
)

# --- lọc nội dung -----------------------------------------------------------
# Chủ dự án chốt 21/11: KHÔNG chọn chủ đề nữa, lấy hết, chỉ chặn bốn nhóm này.
BAN = {
    "chính trị": """
        trump biden putin zelensky election vote ballot senate congress parliament
        democrat republican maga antifa protest riot impeach president minister
        communist nazi ukraine gaza israel palestine hamas idf war tariff sanction
        whitehouse potus governor campaign immigration deportation ice border
        politica gobierno presidente elecciones
    """,
    "bạo lực": """
        shooting shooter stabbing killed murder beheaded execution gore blood
        brutal assault corpse dead body torture crash fatal gun rifle minigun
        weapon ammo soldier military navy marines army cartel narco sicario
        balacera tiroteo disparo muerto asesinado ejercito militar arma
    """,
    "người lớn": """
        onlyfans nsfw nude naked porn sex xxx lingerie strip escort fansly
    """,
    "quảng cáo coin": """
        airdrop presale pump memecoin shitcoin degen whitelist giveaway referral
        bonus casino betting crypto token nft
    """,
}
BAN_RE = {k: re.compile(r"(?<![\w$])(" + "|".join(
    re.escape(w) for w in v.split()) + r")(?!\w)", re.I)
    for k, v in BAN.items()}

# Tài khoản chặn thẳng, không cần xét chữ: lượt quét đầu 21/11 lọt một video
# của @WhiteHouse vì câu chữ không có từ nào trong danh sách trên.
BAN_ACCOUNTS = {"whitehouse", "potus", "vp", "statedept", "pentagon", "dod",
                "sechomeland", "ice", "cbp", "kremlin", "mfa_russia"}

# Nhãn chủ đề chỉ để LỌC trên trang cho dễ nhìn, KHÔNG dùng để loại bài: chủ
# dự án chốt 21/11 là lấy hết, nên bài không khớp nhãn nào vẫn vào, nhãn "khác".
TOPICS = {
    "động vật": "dog cat puppy kitten animal bird horse panda monkey elephant "
                "fox shark zoo pet paw rescue cow goat duck",
    "hài": "funny hilarious lol comedy joke prank fail laughing meme humor",
    "cảm động": "wholesome heartwarming emotional cried tears reunion surprise "
                "kindness gift donate helping hero saved",
    "chuyện lạ": "incredible unbelievable rare insane crazy wild amazing weird "
                 "strange unexpected illusion",
    "mẹo vặt": "hack tip trick tutorial diy repair fix recipe cooking cleaning "
               "lifehack",
    "thể thao": "goal dunk touchdown knockout ufc nba nfl fifa match football "
                "soccer basketball olympic skill",
    "công nghệ": "robot drone gadget engineering machine printer tesla spacex "
                 "rocket satellite",
}
TOPIC_RE = {k: re.compile(r"\b(" + "|".join(
    re.escape(w) for w in v.split()) + r")\b", re.I) for k, v in TOPICS.items()}


def banned(text: str) -> str | None:
    """Tên nhóm bị chặn, hoặc None nếu bài sạch."""
    for name, rx in BAN_RE.items():
        if rx.search(text):
            return name
    return None


def topic_of(text: str) -> str:
    best, score = "khác", 0
    for name, rx in TOPIC_RE.items():
        n = len(rx.findall(text))
        if n > score:
            best, score = name, n
    return best


def heat(views: int, likes: int, reposts: int, age_min: float) -> float:
    """Độ nóng: view mỗi giờ, cộng thêm phần tương tác.

    Chia cho tuổi chứ không lấy số tuyệt đối — bài 2 ngày tuổi 1 triệu view đã
    hết cửa lan, bài 3 giờ tuổi 200 nghìn view mới là thứ đáng làm lại.
    """
    age_h = max(age_min / 60, 0.25)
    return (views + likes * 10 + reposts * 30) / age_h


async def fetch(limit_per_query: int = SEARCH_LIMIT) -> tuple[list[dict], list[str]]:
    """Gọi X, trả (video sạch, ghi chú/lỗi). Chưa cắt còn 5."""
    api = API(str(DB_PATH))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=MAX_AGE_H)
    rows: dict[str, dict] = {}
    notes: list[str] = []
    skip = {"không có video": 0, "quá cũ": 0, "ít view": 0, "bị chặn": 0}

    for q in QUERIES:
        try:
            async for tw in api.search(q, limit=limit_per_query,
                                       kv={"product": "Top"}):
                if tw.date < cutoff:
                    skip["quá cũ"] += 1
                    continue
                vids = getattr(getattr(tw, "media", None), "videos", None) or []
                if not vids:
                    skip["không có video"] += 1
                    continue
                views = tw.viewCount or 0
                if views < MIN_VIEWS:
                    skip["ít view"] += 1
                    continue
                text = (tw.rawContent or "").strip()
                if (tw.user.username or "").lower() in BAN_ACCOUNTS:
                    skip["bị chặn"] += 1
                    continue
                if banned(f"{text} {tw.user.username} {tw.user.displayname}"):
                    skip["bị chặn"] += 1
                    continue

                url = f"https://x.com/{tw.user.username}/status/{tw.id}"
                if url in rows:
                    continue
                age_min = (now - tw.date).total_seconds() / 60
                v = vids[0]
                dur = getattr(v, "duration", None) or 0
                rows[url] = {
                    "url": url,
                    "author": f"@{tw.user.username}",
                    "author_followers": tw.user.followersCount,
                    "posted_at": tw.date.astimezone().strftime("%Y-%m-%d %H:%M"),
                    "age_min": round(age_min),
                    "duration_sec": round(dur / 1000) if dur > 1000 else round(dur),
                    "views": views,
                    "likes": tw.likeCount,
                    "reposts": tw.retweetCount,
                    "replies": tw.replyCount,
                    "topic": topic_of(text),
                    "thumbnail": getattr(v, "thumbnailUrl", "") or "",
                    "text": text[:280],
                    "lang": getattr(tw, "lang", "") or "",
                    "heat": round(heat(views, tw.likeCount, tw.retweetCount,
                                       age_min)),
                }
        except Exception as e:
            notes.append(f"{q[:38]}… -> {type(e).__name__}: {e}")

    notes.append("bỏ qua: " + ", ".join(f"{k} {n}" for k, n in skip.items()))
    return sorted(rows.values(), key=lambda r: r["heat"], reverse=True), notes


# --- mô tả tiếng Việt -------------------------------------------------------
def _key() -> str:
    if not CLAUDE_ENV.exists():
        return ""
    for line in CLAUDE_ENV.read_text(encoding="utf-8").splitlines():
        k, _, v = line.partition("=")
        if k.strip() == "ANTHROPIC_API_KEY":
            return v.strip()
    return ""


def describe(rows: list[dict]) -> None:
    """Thêm "desc", "has_speech", "topic" và cờ "drop" cho từng video.

    Đây cũng là LƯỚI LỌC THỨ HAI. Danh sách từ khoá ở trên chỉ bắt được tiếng
    Anh, mà video viral thì đủ thứ tiếng: lượt quét đầu 21/11 lọt một clip nổ
    súng ở Mexico (chữ tiếng Tây Ban Nha) và một video của Nhà Trắng. Model đọc
    được cả câu nên bắt tiếp phần từ khoá bỏ sót.

    Một lần gọi cho cả mẻ. Lỗi thì để trống chứ không chặn cả lượt quét.
    """
    for r in rows:
        r.setdefault("desc", "")
        r.setdefault("has_speech", None)
        r.setdefault("drop", "")
    if not rows:
        return
    key = _key()
    if not key:
        return

    from anthropic import Anthropic

    items = "\n\n".join(
        f'[{i}] {r["author"]} · {r["duration_sec"]}s · {r["views"]:,} view\n'
        f'{r["text"]}' for i, r in enumerate(rows))
    prompt = (
        "Dưới đây là các bài có video trên X, sẽ được làm lại bản tiếng Việt "
        "để đăng lên Facebook. Với MỖI bài, trả đúng một dòng:\n"
        "<số>|<mô tả tiếng Việt 1 câu, tối đa 20 từ>|<speech hoặc nospeech>|"
        "<chủ đề>\n\n"
        "speech = video có người nói, cần phụ đề tiếng Việt.\n"
        "nospeech = chỉ hình ảnh hoặc nhạc nền, chỉ cần hook chữ.\n"
        "Không rõ thì ghi nospeech.\n\n"
        "Chủ đề chọn một trong: hài, động vật, cảm động, chuyện lạ, mẹo vặt, "
        "thể thao, công nghệ, ẩm thực, đời sống, khác.\n"
        "NHƯNG nếu bài thuộc một trong bốn nhóm sau thì chủ đề ghi đúng chữ "
        "BO: chính trị (gồm chính phủ, quân đội, bầu cử), bạo lực (gồm súng "
        "đạn, tai nạn thương vong), người lớn, quảng cáo tiền số.\n"
        "Chỉ trả các dòng đó, không thêm gì.\n\n"
        + items)
    try:
        msg = Anthropic(api_key=key).messages.create(
            model=MODEL, max_tokens=1000,
            messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in msg.content if b.type == "text")
    except Exception as e:
        print(f"  mô tả lỗi, để trống: {type(e).__name__}: {e}", flush=True)
        return

    for line in text.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        num = parts[0].strip("[]")
        if not num.isdigit():
            continue
        i = int(num)
        if not 0 <= i < len(rows):
            continue
        rows[i]["desc"] = parts[1]
        rows[i]["has_speech"] = parts[2].lower().startswith("speech")
        if len(parts) >= 4:
            tp = parts[3].strip().lower()
            if tp.startswith("bo"):
                rows[i]["drop"] = "model loại: thuộc nhóm bị chặn"
            elif tp:
                rows[i]["topic"] = tp


async def run(per_run: int = PER_RUN) -> dict:
    """Một lượt quét đầy đủ. Trả số liệu để in ra log."""
    found, notes = await fetch()
    known = {v["url"] for v in store.load()}
    pool = [r for r in found if r["url"] not in known]

    # Lấy bù: model loại mấy cái thì xét tiếp mấy cái sau, để mỗi lượt vẫn đủ
    # 5 video dùng được chứ không phải 5 cái đem đi xét.
    fresh: list[dict] = []
    dropped = 0
    while pool and len(fresh) < per_run:
        batch = pool[:per_run - len(fresh)]
        pool = pool[len(batch):]
        describe(batch)
        for r in batch:
            if r.get("drop"):
                dropped += 1
            else:
                r.pop("drop", None)
                fresh.append(r)
    if dropped:
        notes.append(f"model loại thêm {dropped} video thuộc nhóm bị chặn")
    # Bài đã có trong file vẫn ghi lại số liệu -> lần sau đo được tốc độ tăng.
    again = [r for r in found if r["url"] in known]
    res = store.merge(fresh + again)
    return {**res, "quet_duoc": len(found), "ghi_chu": notes}


def main() -> None:
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"[{datetime.now():%H:%M:%S}] quét video viral trên X…", flush=True)
    r = asyncio.run(run())
    print(f"  {r['quet_duoc']} video hợp lệ · thêm {r['them']} mới · "
          f"cập nhật {r['capnhat']} cũ -> {store.FILE}", flush=True)
    for e in r["ghi_chu"]:
        print(f"  {e}", flush=True)


if __name__ == "__main__":
    main()
