"""Cấu hình app XKols — đọc env, hằng số lịch, đường dẫn."""
from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from datetime import datetime, time as dtime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
POSTS = ROOT / "posts"
# reports/ (TradingAgents) không còn được dùng từ 14/11 — số liệu lấy trực tiếp
# trong app/market.py. Thư mục cũ giữ lại làm tư liệu, app không đọc nữa.
WORKFLOWS = ROOT / "workflows"
STATE_DIR = POSTS / ".state"
LOG_DIR = POSTS / ".log"
STOP_FILE = ROOT / "STOP"          # tạo file này là app dừng ở vòng kế tiếp

# ICT = UTC+7 quanh năm, không có DST -> offset cố định, không cần tzdata.
# ICT = US Eastern + 12h.
TZ = timezone(timedelta(hours=7), "ICT")

# --- model ------------------------------------------------------------------
MODEL_POST = "claude-opus-5-5"     # bài gốc + thread: chất lượng quan trọng nhất
# Reply đổi sang Opus ngày 14/11. Lý do cũ (reply nhiều nên chọn model rẻ) không
# còn đúng: reply tự động giờ chỉ phục vụ người đã tương tác với mình (0 lượt
# trong 30 ngày), còn hàng đợi làm tay tối đa 8 draft/ngày — nhỏ hơn hàng chục
# lần so với mức 25/ngày lúc thiết kế. Thêm nữa Sonnet trả sai định dạng 3 lần
# liên tiếp tối 14/11 (viết thẳng reply thay vì bọc JSON) nên draft bị bỏ phí.
MODEL_REPLY = "claude-opus-5-5"
# Dịch tiếng Việt thì Sonnet thừa sức, và mỗi mẻ chỉ gọi một lần.
MODEL_TRANSLATE = "claude-sonnet-5-5"

# --- lịch (giờ ICT, theo workflows/post_scheduler.md) -----------------------
@dataclass(frozen=True)
class Window:
    name: str
    start: dtime
    end: dtime
    posts: int                     # số bài gốc trong cửa sổ
    thread: bool = False

    def contains(self, t: dtime) -> bool:
        return self.start <= t <= self.end


# Bốn cửa sổ, xếp theo giờ tăng dần (next_window() dựa vào thứ tự này).
#
# Hai cửa sổ cũ (morning, evening) chọn theo giả định "ICT = ET + 12, ngoài hai
# khung đó là đêm ở Mỹ". Đo thật ngày 15/11 — 282 bài trong 7 ngày của 22 KOL
# đang theo dõi, chia theo giờ ICT — cho thấy giả định đó sai ở hai chỗ:
#   · 11-18h ICT median 22.300 view, không hề chết (đó là sáng ở châu Âu);
#   · 20-23h ICT median 15.300 view, THẤP NHẤT trong bốn khung, mà lại đang
#     gánh 3 trong 4 bài mỗi ngày.
#   · 00-06h ICT là chỗ KOL tập trung nhất (148/282 bài) — giờ Mỹ hoạt động
#     thật, 13:00-19:00 ET.
# Chủ dự án chốt 15/11: không dời khung cũ, thêm khung mới và tăng số bài.
#
# Hạ hai lần trong ngày 21/11 theo yêu cầu chủ dự án: 7 bài/ngày -> 5 -> 3.
# Cắt theo số đo ở trên, không cắt đều:
#   · evening 20-23h là khung view THẤP NHẤT: 3 -> 1, nhưng phải còn >= 1 vì
#     nhánh tự RT bài cũ trong runner.py đòi "đã có bài mới trong evening".
#   · night 00-02:30h bỏ hẳn khỏi danh sách, không để posts=0: cổng quote là
#     "đã đủ bài gốc của cửa sổ" nên posts=0 làm night thành cửa sổ chỉ quote,
#     tức là vẫn đăng. Bỏ cửa sổ thì khung đó app ngủ thật. Reply không mất gì:
#     ngoài cửa sổ vẫn quét, chỉ thưa hơn (REPLY_GAP_OFF_WINDOW_MIN).
#   · giữ morning (bài + thread, khung chất lượng nhất) và midday (11-18h ICT
#     median 22.300 view, cao nhất).
# Còn 3 bài gốc + 1 thread, cộng tối đa 2 quote và 1 RT.
WINDOWS: tuple[Window, ...] = (
    Window("morning", dtime(7, 30), dtime(9, 30), posts=1, thread=True),
    Window("midday", dtime(11, 0), dtime(13, 0), posts=1),
    Window("evening", dtime(20, 0), dtime(23, 30), posts=1),
)

POST_GAP_MIN = (45, 90)            # phút, giãn cách giữa 2 bài gốc
REPLY_GAP_MIN = (4, 12)            # phút, giãn cách giữa 2 reply
# Tuổi tối đa của bài để còn đáng reply. 60 phút là luật trong
# workflows/reply_scheduler.md — bài cũ hơn đã có hàng trăm reply, vào là chìm.
# Ngoài hai cửa sổ đăng thì thường không có target nào, đó là đúng chứ không lỗi.
# Chỉnh tạm bằng biến môi trường XKOLS_REPLY_WINDOW để xem thử.
REPLY_FRESH_MIN = int(os.environ.get("XKOLS_REPLY_WINDOW", "60"))

# Từ 14/11 reply chỉ dành cho người đã tương tác với mình, nên cửa sổ rộng hẳn:
# ai hỏi mình thì trả lời muộn vẫn hơn bỏ qua, và không còn chuyện phải chen vào
# sớm kẻo chìm. 1440 phút = 24 giờ.
MENTION_WINDOW_MIN = int(os.environ.get("XKOLS_MENTION_WINDOW", "1440"))

# Hàng đợi LÀM TAY dùng cửa sổ riêng, rộng hơn 60 phút. Luật 60 phút sinh ra cho
# reply tự động (vào sớm kẻo chìm); bạn tự chọn tay thì thà có vài bài để cân
# nhắc còn hơn hàng đợi trống. Đo 14/11 lúc 21:35 ICT: 60 phút ra 0 ứng viên,
# 240 phút ra 1.
# Nới 180 -> 360 ngày 15/11: đo lúc 08:3x, cửa sổ 180 phút ra đúng 3 ứng viên và
# cả 3 đều đã bị nhánh reply TỰ ĐỘNG lấy mất trước đó -> hàng đợi làm tay rỗng.
MANUAL_WINDOW_MIN = int(os.environ.get("XKOLS_MANUAL_WINDOW", "360"))

# Hạ 35 -> 20 -> 10 trong ngày 21/11 theo yêu cầu chủ dự án. Ngày 17/11 chạm
# 32/35, tức là trần cũ gần như chính là mức chạy thật, nên đây là giảm thật
# chứ không phải con số trang trí. Reply tay cũng tính chung vào trần này, nên
# ở mức 10 thì nên để dành phần lớn cho tay.
MAX_REPLIES_PER_DAY = 10
# Trần reply cho MỘT tác giả trong một ngày, tính CẢ máy lẫn tay. Người ngoài
# nhìn vào chỉ thấy một tài khoản trả lời, không phân biệt ai bấm nút. Chủ dự
# án chốt 3 ngày 16/11 sau khi thấy hàng đợi ra hai mục @CrewWatcherX, rồi hạ
# xuống 2 ngày 17/11 — bám một người quá hai lần trong ngày là nhìn ra ngay.
MAX_REPLIES_PER_AUTHOR_PER_DAY = 2

# Ngoài cửa sổ đăng thì VẪN quét reply, chỉ thưa hơn (15-30 phút/lần thay vì
# 4-12). Thêm 15/11: trước đó cả vòng lặp nghỉ ngoài cửa sổ, nên từ 13:00 tới
# 20:00 ICT ai mention mình cũng phải đợi. Thưa là vì acc phụ twscrape có hạn
# mức request — đã dính một lần lúc 09:04 ngày 15/11.
REPLY_GAP_OFF_WINDOW_MIN = (15, 30)

# Tự RT bài cũ của chính mình: 1 lần/ngày, chỉ bài đã đủ cũ để vòng người xem
# khác hẳn lần đăng đầu.
# Quote tweet: bài của người khác + bình luận của mình. Tính là bài gốc của
# mình nên ĐƯỢC tính impression payout, khác hẳn reply.
QUOTES_PER_DAY = 2

# Ảnh: ưu tiên có, nhưng chỉ khi ảnh MANG thông tin (biểu đồ từ số của pipeline).
# Đính cùng một ảnh vào mọi bài thì thành nhiễu, nên giới hạn mỗi ngày.
# 15/11: 2 -> 4 theo số bài mỗi ngày (4 -> 7 + thread). Vẫn ít hơn số bài, nên
# ảnh vẫn phải "đáng vẽ" mới được chọn.
MAX_IMAGE_POSTS_PER_DAY = 4

# Luân phiên chủ đề cho BÀI GỐC, mỗi bài đúng một chủ đề, dùng hết mới quay vòng.
#
# Sửa 14/11 lần hai: bộ cũ (how_it_works, self_deprecating...) viết về CHÍNH CÁI
# HỆ THỐNG — "agent của tôi cãi nhau", "pipeline của tôi tính sai". Đó là nội dung
# meta, không ai theo dõi một account thị trường để đọc chuyện công cụ của nó.
# Ba account tham khảo đều viết về thị trường và tin tức. Bộ mới bám theo đó.
# track_record cố ý KHÔNG nằm đây: thread buổi sáng đã lo phần đó.
POST_PILLARS = ("news", "trend", "market_read", "explainer", "take", "wry",
                "term", "ai", "money", "strategy")

# Thread buổi sáng luân phiên hai kiểu, theo ngày chẵn/lẻ. Trước 18/11 thread
# luôn là thread thị trường; chủ dự án muốn thêm loại hướng dẫn cơ bản cho
# người mới. Luân phiên chứ không thay hẳn: thread thị trường là chỗ duy nhất
# ghi lại track record theo ngày. Thêm một cái lợi: thread "basics" không cần
# dữ liệu thị trường, nên hôm nào không lấy được giá vẫn có thread để đăng.
THREAD_KINDS = ("market", "basics")


def thread_kind(t: datetime | None = None) -> str:
    return THREAD_KINDS[(t or now()).timetuple().tm_yday % len(THREAD_KINDS)]

REPOST_PER_DAY = 1
REPOST_MIN_AGE_DAYS = 3
REPOST_MAX_AGE_DAYS = 21
IDLE_SLEEP_SEC = (240, 420)        # ngoài cửa sổ thì ngủ dài, có nhiễu

MAX_POST_CHARS = 280               # giữ 280 cho tới khi có Premium (post dài)
MAX_HASHTAGS = 2


def rand_gap_sec(bounds: tuple[int, int]) -> int:
    lo, hi = bounds
    return random.randint(lo * 60, hi * 60)


def now() -> datetime:
    return datetime.now(TZ)


def current_window(t: datetime | None = None) -> Window | None:
    t = t or now()
    for w in WINDOWS:
        if w.contains(t.timetz().replace(tzinfo=None)):
            return w
    return None


def next_window(t: datetime | None = None) -> tuple[Window, str]:
    """Cửa sổ mở kế tiếp và giờ mở, dạng "HH:MM" (hôm nay hoặc mai).

    Trang theo dõi cần cái này: ngoài cửa sổ thì "bài kế 10:22" là giờ đã hẹn
    rồi bị cổng cửa sổ chặn lại — hiện lên thành giờ quá khứ, nhìn như app
    chết (chủ dự án hỏi 10:27 ngày 15/11).
    """
    t = t or now()
    hm = t.timetz().replace(tzinfo=None)
    for w in WINDOWS:
        if hm < w.start:
            return w, f"{w.start:%H:%M}"
    return WINDOWS[0], f"{WINDOWS[0].start:%H:%M}"


# --- env --------------------------------------------------------------------
def _read_env_file(path: Path) -> dict[str, str]:
    cfg: dict[str, str] = {}
    if not path.exists():
        return cfg
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k.strip()] = v.strip()
    return cfg


class ConfigError(RuntimeError):
    pass


@dataclass
class Settings:
    anthropic_key: str
    x_username: str
    x_ct0: str
    x_auth_token: str
    dry_run: bool = True
    headful: bool = False
    account_handle: str = field(default="")

    @property
    def cookies(self) -> list[dict]:
        base = {"domain": ".x.com", "path": "/", "secure": True}
        return [
            {"name": "ct0", "value": self.x_ct0, **base},
            {"name": "auth_token", "value": self.x_auth_token, "httpOnly": True, **base},
        ]


def load_settings(dry_run: bool = True, headful: bool = False) -> Settings:
    claude = _read_env_file(TOOLS / "claude.env")
    main_acc = _read_env_file(TOOLS / "x_main.env")

    # Biến môi trường thắng file, để test được mà không phải sửa file thật.
    def pick(name: str, src: dict[str, str]) -> str:
        return os.environ.get(name) or src.get(name, "")

    key = pick("ANTHROPIC_API_KEY", claude)
    ct0 = pick("X_CT0", main_acc)
    auth = pick("X_AUTH_TOKEN", main_acc)

    missing = []
    if not key:
        missing.append(f"ANTHROPIC_API_KEY trong {TOOLS / 'claude.env'}")
    # Dry-run không mở browser nên không cần cookie — chỉ --live mới bắt buộc.
    if not dry_run:
        if not ct0:
            missing.append(f"X_CT0 trong {TOOLS / 'x_main.env'}")
        if not auth:
            missing.append(f"X_AUTH_TOKEN trong {TOOLS / 'x_main.env'}")
    if missing:
        raise ConfigError("Thiếu cấu hình:\n  - " + "\n  - ".join(missing))

    handle = pick("X_USERNAME", main_acc).lstrip("@")
    return Settings(
        anthropic_key=key,
        x_username=handle,
        x_ct0=ct0,
        x_auth_token=auth,
        dry_run=dry_run,
        headful=headful,
        account_handle=handle,
    )
