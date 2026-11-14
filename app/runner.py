"""Vòng lặp chính: tới giờ thì soạn và đăng, ngoài giờ thì ngủ.

Khoảng cách giữa các lần đăng là random thật (time.sleep), không phải lưới cron,
nên không bị dồn về các mốc chẵn.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import traceback
from pathlib import Path

from anthropic import AuthenticationError

from . import brain, chart, config, manual, review, scan, state, web, xnews
from .config import ConfigError, load_settings
from .x_browser import LoginExpired, XBrowser, XError

MAX_CONSECUTIVE_FAILS = 2
REPLY_AGE_GRACE_MIN = 90   # bài có thể già thêm chút trong lúc soạn


def log(msg: str) -> None:
    print(f"[{config.now():%m-%d %H:%M:%S}] {msg}", flush=True)


def pick_pillar(st: state.DayState) -> str:
    """Chủ đề cho bài kế tiếp: ưu tiên cái chưa dùng hôm nay, hết thì quay vòng."""
    unused = [p for p in config.POST_PILLARS if p not in st.pillars_used]
    return random.choice(unused or list(config.POST_PILLARS))


def pick_image(st: state.DayState, text: str, pillar: str = "",
               trends: list[dict] | None = None, settings=None) -> str | None:
    """Ảnh cho bài — chỉ khi ảnh MANG thông tin, không bao giờ để trang trí.

    Chủ dự án chốt 14/11: ưu tiên có ảnh, khó quá thì bỏ qua. Nên mọi lỗi vẽ đều
    nuốt và đăng bài không ảnh, chứ không huỷ bài.

    Mỗi chủ đề có loại ảnh riêng, vì mỗi chủ đề mang loại thông tin khác nhau:
      market_read / news  -> đường giá + mốc kỹ thuật
      trend               -> số tài khoản nhắc mỗi chủ đề (mình tự đo)
      take về token AI    -> tương quan với BTC và NVDA
      explainer           -> sơ đồ cơ chế rút từ chính bài
      wry                 -> không có gì để vẽ, và không cố vẽ
    """
    if len(st.images_used) >= config.MAX_IMAGE_POSTS_PER_DAY:
        return None

    low = text.lower()
    wants_corr = ("ai token" in low or "ai tokens" in low
                  or ("correlat" in low and " ai" in low))
    try:
        if pillar == "trend" and trends:
            p = chart.trend_card(trends)
        elif pillar == "explainer" and settings is not None:
            spec = brain.mechanism_steps(settings, text)
            p = chart.flow_card(spec["title"], spec["steps"],
                                loop=spec["loop"]) if spec else None
            if spec is None:
                log("  explainer không phải chuỗi bước -> không vẽ sơ đồ")
        elif wants_corr:
            p = chart.corr_card()
        elif brain.touches_market(text):
            p = chart.latest_card()
        else:
            p = None
    except Exception as e:
        log(f"  vẽ ảnh lỗi, đăng không ảnh: {type(e).__name__}: {e}")
        return None
    if p is None or str(p) in st.images_used:
        return None
    return str(p)


async def gate(kind: str, text: str, target_url: str = "", author: str = "",
               parts: list[str] | None = None, settings=None,
               image: str | None = None) -> bool:
    """Cổng duyệt tay. Không bật --review thì luôn cho qua.

    Bản dịch tiếng Việt chỉ sinh khi thật sự cần hiện lên trang duyệt.
    """
    if not review.enabled():
        return True
    text_vi, parts_vi = "", []
    if settings is not None:
        try:
            if parts:
                parts_vi = brain.translate_vi(settings, parts)
                text_vi = parts_vi[0] if parts_vi else ""
            else:
                text_vi = (brain.translate_vi(settings, [text]) or [""])[0]
        except Exception:
            pass
    log(f"  chờ bạn duyệt ({kind}) trên trang web...")
    ok, why = await review.ask(kind, text, target_url, author, parts,
                               text_vi=text_vi, parts_vi=parts_vi,
                               image=image or "")
    log(f"  {'DUYỆT' if ok else 'BỎ'} — {why}")
    return ok


def dry_file() -> str:
    """Dry-run ghi draft ra file để người duyệt, không mở browser."""
    p = config.POSTS / f"dryrun_{config.now():%Y%m%d}.md"
    if not p.exists():
        p.write_text(f"# Dry run — {config.now():%Y-%m-%d}\n\n"
                     "Draft app định đăng. Không có gì lên X.\n", encoding="utf-8")
    return str(p)


def dry_write(kind: str, text: str, extra: str = "") -> None:
    p = config.POSTS / f"dryrun_{config.now():%Y%m%d}.md"
    dry_file()
    with p.open("a", encoding="utf-8") as f:
        f.write(f"\n## {config.now():%H:%M} — {kind} ({len(text)} ký tự)\n")
        if extra:
            f.write(f"{extra}\n")
        f.write(f"\n> {text}\n")


# --- từng hành động ----------------------------------------------------------
async def do_thread(s, st: state.DayState) -> bool:
    log("soạn thread buổi sáng...")
    try:
        parts = brain.compose_thread(s)
    except brain.StaleReport as e:
        st.note(f"bỏ thread: {e}")
        st.thread_done = True        # không thử lại cả ngày, tránh đốt token
        log(f"  BỎ THREAD: {e}")
        return False
    if not parts:
        st.note("không lấy được dữ liệu thị trường -> bỏ thread hôm nay")
        st.thread_done = True
        log("  không có dữ liệu thị trường -> bỏ thread")
        return False
    ok, why = brain.validate_thread(parts)
    if not ok:
        st.note(f"thread không đạt: {why}")
        log(f"  draft không đạt: {why}")
        return False

    image = pick_image(st, parts[0] + parts[-1])
    if not await gate("thread", parts[0], parts=parts, settings=s, image=image):
        st.note("bạn bỏ thread hôm nay")
        st.thread_done = True
        return False

    if s.dry_run:
        dry_write("THREAD", "\n\n---\n\n".join(parts),
                  f"{len(parts)} bài" + (f" · ảnh: {image}" if image else ""))
        st.record_post("morning", "DRY", parts[0], kind="thread")
        if image:
            st.images_used.append(image)
        log(f"  [dry] thread {len(parts)} bài"
            + (f" + ảnh {Path(image).name}" if image else "") + f" -> {dry_file()}")
        return True

    async with XBrowser(s) as b:
        url = await b.post_thread(parts, image)
    if image:
        st.images_used.append(image)
    st.record_post("morning", url or "?", parts[0], kind="thread")
    state.append_log("post", {"url": url or "?", "chars": len(parts[0]),
                              "text": f"THREAD({len(parts)}) " + parts[0]})
    log(f"  đã đăng thread: {url or '(không bắt được URL)'}")
    return True


async def do_post(s, st: state.DayState, window: config.Window) -> bool:
    pillar = pick_pillar(st)
    log(f"soạn bài gốc ({window.name} {st.posts_in(window.name) + 1}/{window.posts}"
        f", chủ đề: {pillar})...")

    news: list[dict] = []
    trends: list[dict] = []
    xn: list = []
    if pillar in ("news", "trend"):
        # Mục "Today's News" / "What's happening" ở cột phải x.com. Nguồn này
        # biết cả tin mà 22 handle trong reply_targets.txt chưa nhắc tới.
        try:
            xn = await xnews.fetch()
            log("  X đang đẩy: " + (" · ".join(i.name[:40] for i in xn[:4])
                                    or "không lấy được"))
        except Exception as e:
            log(f"  lấy tin X lỗi: {type(e).__name__}: {e}")

    if pillar == "news":
        try:
            news = await scan.find_candidates(window_min=180, top_n=10)
            log(f"  {len(news)} tin nóng từ vòng quét")
        except Exception as e:
            log(f"  quét tin lỗi: {type(e).__name__}: {e}")
        if not news and xn:
            # Timeline KOL im nhưng X vẫn có tin: lấy bài thật dưới tin đầu tiên.
            try:
                news = await xnews.posts_for(xn[0].name, 240, limit=25)
                log(f"  {len(news)} bài quanh tin \"{xn[0].name[:50]}\"")
            except Exception as e:
                log(f"  lấy bài theo tin lỗi: {type(e).__name__}: {e}")
        if not news:
            # Không có tin thì đừng ép, đổi sang chủ đề không cần dữ liệu ngoài.
            pillar = "explainer"
            log(f"  không có tin -> chuyển chủ đề: {pillar}")
    elif pillar == "trend":
        try:
            trends = await scan.find_trends()
            log("  trend: " + (", ".join(
                f"{t['term']}({t['accounts']})" for t in trends[:5]) or "không có"))
        except Exception as e:
            log(f"  dò trend lỗi: {type(e).__name__}: {e}")
        if not trends and not xn:
            pillar = "explainer"
            log(f"  không đo được trend -> chuyển chủ đề: {pillar}")

    drafts = brain.compose_posts(s, window.name, 1, news=news, pillar=pillar,
                                 trends=trends, xnews_items=xn)
    if not drafts:
        st.note(f"Claude không trả bài nào (chủ đề {pillar})")
        return False
    st.pillars_used.append(pillar)
    text = drafts[0]
    ok, why = brain.validate(text)
    if not ok:
        st.note(f"bài không đạt: {why}")
        log(f"  draft không đạt: {why}")
        return False

    image = pick_image(st, text, pillar=pillar, trends=trends, settings=s)
    if not await gate("post", text, settings=s, image=image):
        st.note("bạn bỏ một bài gốc")
        return False

    if s.dry_run:
        dry_write("POST", text, f"ảnh: {image}" if image else "")
        st.record_post(window.name, "DRY", text)
        if image:
            st.images_used.append(image)
        log(f"  [dry] {len(text)} ký tự"
            + (f" + ảnh {Path(image).name}" if image else "") + f" -> {dry_file()}")
        return True

    async with XBrowser(s) as b:
        url = await b.post(text, image)
    if image:
        st.images_used.append(image)
    st.record_post(window.name, url or "?", text)
    state.append_log("post", {"url": url or "?", "chars": len(text), "text": text})
    log(f"  đã đăng: {url or '(không bắt được URL)'}")
    return True


async def do_quote(s, st: state.DayState) -> bool:
    """Quote tweet: bài người khác + bình luận của mình. Tính là bài gốc nên
    được tính impression payout, khác reply."""
    log("tìm bài để quote...")
    cands = await scan.find_candidates(window_min=180, top_n=12)
    fresh = [c for c in cands if not st.already_touched(c["id"])]
    if not fresh:
        log(f"  không có target ({len(cands)} ứng viên, đều đã đụng)")
        return False

    for cand in fresh[:3]:
        text, reason = brain.compose_quote(s, cand)
        if text is None:
            log(f"  bỏ @{cand['handle']}: {reason}")
            continue

        if not await gate("quote", text, cand["url"], cand["handle"], settings=s):
            continue

        if s.dry_run:
            dry_write("QUOTE", text,
                      f"-> @{cand['handle']} ({cand['followers']:,}), "
                      f"{cand['age_min']}m\n{cand['url']}")
            st.record_quote(cand["handle"], cand["id"], "DRY", text)
            log(f"  [dry] quote @{cand['handle']} ({len(text)} ký tự)")
            return True

        async with XBrowser(s) as b:
            url = await b.quote(cand["url"], text)
        st.record_quote(cand["handle"], cand["id"], url or "?", text)
        state.append_log("quote", {"url": url or "?", "target": cand["url"],
                                   "author": cand["handle"], "chars": len(text),
                                   "text": text})
        log(f"  đã quote @{cand['handle']}: {url or '(không bắt được URL)'}")
        return True

    log("  không soạn được bình luận nào đạt")
    return False


async def do_repost(s, st: state.DayState) -> bool:
    """Tự RT một bài cũ của mình. Không gọi Claude, không tốn token."""
    pool = state.own_posts_aged(config.REPOST_MIN_AGE_DAYS, config.REPOST_MAX_AGE_DAYS)
    if not pool:
        st.reposts_done = config.REPOST_PER_DAY   # hết việc, đừng thử lại cả ngày
        log(f"  chưa có bài nào trong khoảng {config.REPOST_MIN_AGE_DAYS}-"
            f"{config.REPOST_MAX_AGE_DAYS} ngày để RT lại")
        return False

    pick = random.choice(pool)
    if not await gate("repost", pick.get("text", "")[:200], pick["url"], settings=s):
        st.note("bạn bỏ lần RT lại")
        st.reposts_done = config.REPOST_PER_DAY
        return False

    if s.dry_run:
        dry_write("REPOST", pick.get("text", "")[:200], f"-> {pick['url']}")
        st.reposts_done += 1
        state.mark_reposted(pick["url"])
        log(f"  [dry] RT lại {pick['url']}")
        return True

    async with XBrowser(s) as b:
        await b.repost(pick["url"])
    st.reposts_done += 1
    state.mark_reposted(pick["url"])
    state.append_log("repost", {"url": pick["url"], "text": pick.get("text", "")[:120]})
    log(f"  đã RT lại {pick['url']}")
    return True


async def do_reply(s, st: state.DayState) -> bool:
    """Chỉ trả lời người đã CHỦ ĐỘNG tương tác với mình.

    Viết lại 14/11. Hai nguồn cũ đều bị Automation rules của X cấm: quét bài
    theo từ khoá/trend, và săn bài của 22 KOL trong reply_targets.txt — cả hai
    đều là "automated replies ... based on keyword searches", người nhận chưa
    hề opt-in. X nói rõ ngay cả việc họ follow mình cũng chưa đủ:
    "a user following your account is not on its own a sufficient indication
    of user intent to receive an automated response".
    """
    log(f"xem ai vừa tương tác với @{s.account_handle} "
        f"(trong {config.MENTION_WINDOW_MIN // 60}h)...")
    try:
        cands = await scan.find_mentions(s.account_handle,
                                         window_min=config.MENTION_WINDOW_MIN)
    except Exception as e:
        log(f"  quét mention lỗi: {type(e).__name__}: {e}")
        return False

    # "you only send one automated reply or mention per user interaction" —
    # already_touched giữ đúng luật đó, mỗi bài chỉ trả lời một lần.
    fresh = [c for c in cands
             if not st.already_touched(c["id"]) and st.can_reply_to(c["handle"])]

    if not fresh:
        log(f"  chưa ai tương tác ({len(cands)} lượt, đều đã trả lời hoặc hết "
            f"hạn mức). Account còn nhỏ thì đây là chuyện bình thường.")
        return False
    log(f"  {len(fresh)} lượt chờ trả lời")

    for cand in fresh[:3]:
        text, reason = brain.compose_reply(s, cand)
        if text is None:
            log(f"  bỏ @{cand['handle']}: {reason}")
            continue

        if not await gate("reply", text, cand["url"], cand["handle"], settings=s):
            continue

        if s.dry_run:
            dry_write("REPLY", text,
                      f"-> @{cand['handle']} ({cand['followers']:,}), "
                      f"{cand['age_min']}m, {cand['replies']} reply\n{cand['url']}")
            st.record_reply(cand["handle"], cand["id"], "DRY", text)
            log(f"  [dry] reply @{cand['handle']} ({len(text)} ký tự) -> {dry_file()}")
            return True

        async with XBrowser(s) as b:
            age = await b.post_age_minutes(cand["url"])
            if age is not None and age > REPLY_AGE_GRACE_MIN:
                log(f"  bỏ @{cand['handle']}: bài đã {age:.0f} phút")
                st.note(f"bỏ {cand['url']} vì {age:.0f}m")
                continue
            url = await b.reply(cand["url"], text)
        st.record_reply(cand["handle"], cand["id"], url or "?", text)
        state.append_log("reply", {"url": url or "?", "target": cand["url"],
                                   "author": cand["handle"], "chars": len(text),
                                   "text": text})
        log(f"  đã reply @{cand['handle']}: {url or '(không bắt được URL)'}")
        return True

    log("  không soạn được reply nào đạt yêu cầu")
    return False


# --- vòng lặp ----------------------------------------------------------------
async def tick(s, st: state.DayState) -> str:
    """Một nhịp. Trả tên hành động đã làm, hoặc lý do nghỉ."""
    w = config.current_window()
    if w is None:
        nxt = ", ".join(f"{x.name} {x.start:%H:%M}" for x in config.WINDOWS)
        return f"ngoài cửa sổ (cửa sổ: {nxt})"

    if w.thread and not st.thread_done:
        if await do_thread(s, st):
            st.arm("next_post_at", config.POST_GAP_MIN)
            return "thread"
        return "thread lỗi"

    if st.posts_in(w.name) < w.posts and st.due("next_post_at"):
        if await do_post(s, st, w):
            st.arm("next_post_at", config.POST_GAP_MIN)
            return "post"
        st.arm("next_post_at", (10, 20))
        return "post lỗi"

    # Quote tweet: sau khi đủ bài gốc của cửa sổ, dùng chung nhịp giãn với bài gốc.
    if (st.posts_in(w.name) >= w.posts and st.quotes_done < config.QUOTES_PER_DAY
            and st.due("next_post_at")):
        if await do_quote(s, st):
            st.arm("next_post_at", config.POST_GAP_MIN)
            return "quote"
        st.arm("next_post_at", (10, 20))
        return "không có bài để quote"

    # RT lại bài cũ: 1 lần/ngày, trong cửa sổ tối, sau khi đã có bài mới hôm đó.
    if (w.name == "evening" and st.reposts_done < config.REPOST_PER_DAY
            and st.posts_in(w.name) >= 1):
        if await do_repost(s, st):
            return "repost"

    if st.replies_done < config.MAX_REPLIES_PER_DAY and st.due("next_reply_at"):
        if await do_reply(s, st):
            st.arm("next_reply_at", config.REPLY_GAP_MIN)
            return "reply"
        st.arm("next_reply_at", (6, 15))
        # Reply tự động không còn target thì nạp hàng đợi LÀM TAY. Chỗ này chỉ
        # đọc và soạn, không chạm vào x.com bằng acc chính.
        if len(manual.pending()) < manual.REFILL_AT and manual.auto_refill_due():
            manual.mark_auto_refill()
            try:
                r = await manual.refill(s)
                if r["added"]:
                    log(f"  soạn thêm {r['added']} mục cho bạn gửi tay (xem trên trang)")
                elif r["skipped"]:
                    log(f"  việc làm tay: {r['cands']} bài nhưng bỏ hết "
                        f"({r['skipped'][0]})")
            except Exception as e:
                log(f"  soạn việc làm tay lỗi: {type(e).__name__}: {e}")
        return "không có target"

    return (f"chờ — bài kế {st.when('next_post_at')}, "
            f"reply kế {st.when('next_reply_at')}")


async def loop(s, once: bool = False) -> None:
    fails = 0
    log(f"khởi động — {'DRY RUN, không đăng gì' if s.dry_run else 'ĐĂNG THẬT'} "
        f"| acc @{s.account_handle} | bài+reply={config.MODEL_REPLY} "
        f"dịch={config.MODEL_TRANSLATE}")
    log(f"cửa sổ: " + " · ".join(
        f"{w.name} {w.start:%H:%M}-{w.end:%H:%M} ({w.posts} bài"
        + (" + thread)" if w.thread else ")") for w in config.WINDOWS))
    log(f"dừng app: tạo file {config.STOP_FILE}")
    # Dọn cờ dừng của lần chạy trước, không thì lần này thoát ngay vòng đầu.
    if config.STOP_FILE.exists():
        config.STOP_FILE.unlink(missing_ok=True)
        log("  (đã xoá cờ STOP còn sót của lần chạy trước)")

    # Nạp sẵn tin X + chỉ số account để trang web có cái hiển thị ngay từ đầu,
    # không phải đợi tới lượt đăng đầu tiên. Lỗi ở đây không được chặn app.
    try:
        items = await xnews.fetch()
        log(f"tin/trend trên X: {len(items)} mục hợp chủ đề")
    except Exception as e:
        log(f"không lấy được tin X: {type(e).__name__}: {e}")
    try:
        acc = await xnews.account_stats(s.account_handle)
        if acc:
            log(f"@{acc['handle']}: {acc['followers']:,} follower "
                f"(mốc payout: 500)")
    except Exception as e:
        log(f"không đọc được chỉ số account: {type(e).__name__}: {e}")

    while True:
        if config.STOP_FILE.exists():
            log("thấy file STOP -> dừng")
            return

        st = state.load()
        try:
            what = await tick(s, st)
            fails = 0
        except LoginExpired as e:
            st.note(f"cookie hết hạn: {e}")
            state.save(st)
            log(f"DỪNG: {e}")
            return
        except AuthenticationError as e:
            st.note(f"API key Claude sai: {e}")
            state.save(st)
            log("DỪNG: API key Claude không hợp lệ. Kiểm tra ANTHROPIC_API_KEY "
                f"trong {config.TOOLS / 'claude.env'}")
            return
        except (XError, Exception) as e:
            fails += 1
            st.note(f"lỗi ({fails}/{MAX_CONSECUTIVE_FAILS}): {type(e).__name__}: {e}")
            log(f"LỖI {fails}/{MAX_CONSECUTIVE_FAILS}: {type(e).__name__}: {e}")
            if not isinstance(e, XError):
                traceback.print_exc()
            state.save(st)
            if fails >= MAX_CONSECUTIVE_FAILS:
                log("DỪNG: lỗi liên tiếp, không thử vòng nữa. Xem posts/.log/shots/")
                return
            what = "lỗi"
        else:
            state.save(st)

        if once:
            log(f"--once: xong ({what})")
            return

        in_window = config.current_window() is not None
        nap = random.randint(60, 150) if in_window else config.rand_gap_sec(
            (config.IDLE_SLEEP_SEC[0] // 60, config.IDLE_SLEEP_SEC[1] // 60))
        log(f"{what} -> ngủ {nap // 60}m{nap % 60:02d}s")
        await asyncio.sleep(nap)


def main() -> int:
    ap = argparse.ArgumentParser(
        prog="python -m app",
        description="XKols — đăng bài và reply trên X bằng Claude API.")
    ap.add_argument("--live", action="store_true",
                    help="ĐĂNG THẬT. Không có cờ này thì chỉ ghi draft ra posts/dryrun_*.md")
    ap.add_argument("--once", action="store_true", help="làm một hành động rồi thoát")
    ap.add_argument("--headful", action="store_true", help="hiện cửa sổ Chromium để xem")
    ap.add_argument("--now", metavar="HH:MM",
                    help="giả lập giờ để test cửa sổ (chỉ dùng với --once)")
    ap.add_argument("--web", action="store_true",
                    help=f"mở trang theo dõi ở http://127.0.0.1:{web.DEFAULT_PORT}")
    ap.add_argument("--port", type=int, default=web.DEFAULT_PORT,
                    help="cổng cho trang theo dõi")
    ap.add_argument("--review", action="store_true",
                    help="chờ bạn duyệt từng draft trên trang web mới đăng (tự bật --web)")
    args = ap.parse_args()

    try:
        s = load_settings(dry_run=not args.live, headful=args.headful)
    except ConfigError as e:
        print(e)
        return 1

    review.set_enabled(args.review)
    if args.web or args.review:
        try:
            url = web.start(s, args.port)
            log(f"trang theo dõi: {url}"
                + ("  (đang chờ bạn duyệt từng bài)" if args.review else ""))
        except OSError as e:
            log(f"không mở được trang theo dõi ở cổng {args.port}: {e}")
            if args.review:
                log("DỪNG: --review mà không có trang thì không duyệt được")
                return 1

    if args.now:
        from datetime import datetime
        hh, mm = (int(x) for x in args.now.split(":"))
        real_now = config.now
        config.now = lambda: real_now().replace(hour=hh, minute=mm)  # type: ignore[assignment]
        log(f"giả lập giờ {args.now}")

    try:
        asyncio.run(loop(s, once=args.once))
    except KeyboardInterrupt:
        log("Ctrl-C -> dừng")
    return 0
