"""Đăng bài / reply trên X bằng Playwright + cookie của acc chính.

Chỉ dùng data-testid để chọn element, không dùng text, nên không phụ thuộc
ngôn ngữ giao diện X (Việt hay Anh đều chạy).
"""
from __future__ import annotations

import asyncio
import re
from pathlib import Path

from playwright.async_api import Page, TimeoutError as PWTimeout, async_playwright

from . import config

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")

COMPOSE_URL = "https://x.com/compose/post"
HOME_URL = "https://x.com/home"

SEL_BOX = '[data-testid="tweetTextarea_0"]'
SEL_BOX_N = '[data-testid="tweetTextarea_{n}"]'
SEL_SEND = '[data-testid="tweetButton"]'
SEL_SEND_INLINE = '[data-testid="tweetButtonInline"]'
SEL_ADD = '[data-testid="addButton"]'
SEL_WHOAMI = '[data-testid="SideNav_AccountSwitcher_Button"]'
SEL_TOAST = '[data-testid="toast"]'


class XError(RuntimeError):
    pass


class LoginExpired(XError):
    pass


class SoftLocked(XError):
    """X nghi là bot: hiện captcha / "This request looks like it might be
    automated" / bắt xác minh. Gặp cái này là DỪNG HẲN, không thử lại — thử lại
    chính là thứ biến cảnh báo thành khoá tài khoản."""


class XBrowser:
    def __init__(self, settings):
        self.s = settings
        self._pw = None
        self._browser = None
        self._ctx = None
        self.page: Page | None = None

    # --- vòng đời ----------------------------------------------------------
    async def __aenter__(self) -> "XBrowser":
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=not self.s.headful)
        self._ctx = await self._browser.new_context(
            user_agent=UA, viewport={"width": 1280, "height": 900}, locale="en-US"
        )
        await self._ctx.add_cookies(self.s.cookies)
        self.page = await self._ctx.new_page()
        await self._verify_login()
        return self

    async def __aexit__(self, *exc) -> None:
        for closer in (self._ctx, self._browser):
            try:
                if closer:
                    await closer.close()
            except Exception:
                pass
        try:
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    async def _verify_login(self) -> None:
        assert self.page
        await self.page.goto(HOME_URL, wait_until="domcontentloaded", timeout=45_000)
        try:
            el = await self.page.wait_for_selector(SEL_WHOAMI, timeout=20_000)
        except PWTimeout:
            await self._shot("login-failed")
            raise LoginExpired(
                "Không vào được X bằng cookie. Mở tools/x_main.env và điền lại "
                "ct0 + auth_token (cookie hết hạn khi đổi mật khẩu hoặc log out "
                "all sessions)."
            )
        who = (await el.inner_text()) or ""
        want = self.s.account_handle.lower()
        if want and want not in who.lower():
            await self._shot("wrong-account")
            raise XError(f"Đang đăng nhập account khác: {who.strip()!r}, cần @{want}")

    async def _shot(self, tag: str) -> Path | None:
        if not self.page:
            return None
        d = config.LOG_DIR / "shots"
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{config.now():%Y%m%d-%H%M%S}-{tag}.png"
        try:
            await self.page.screenshot(path=str(p), full_page=False)
            return p
        except Exception:
            return None

    # --- thao tác cơ bản ---------------------------------------------------
    async def _type_into(self, selector: str, text: str) -> None:
        """Ô soạn của X là contenteditable (DraftJS) — phải click rồi gõ."""
        assert self.page
        box = await self.page.wait_for_selector(selector, timeout=30_000)
        await box.click()
        await self.page.keyboard.insert_text(text)
        await asyncio.sleep(0.4)

    async def _click_send(self) -> None:
        assert self.page
        for sel in (SEL_SEND, SEL_SEND_INLINE):
            btn = await self.page.query_selector(sel)
            if btn and await btn.is_enabled():
                await btn.click()
                return
        await self._shot("no-send-button")
        raise XError("Không tìm thấy nút đăng đang bật")

    async def _url_from_toast(self) -> str | None:
        """Toast sau khi đăng có link 'View' trỏ tới bài vừa lên."""
        assert self.page
        try:
            toast = await self.page.wait_for_selector(SEL_TOAST, timeout=15_000)
        except PWTimeout:
            return None
        for _ in range(10):
            html = await toast.inner_html()
            m = re.search(r'href="(/[^"]+/status/\d+)"', html)
            if m:
                return "https://x.com" + m.group(1)
            await asyncio.sleep(0.5)
        return None

    async def _confirm_sent(self) -> bool:
        """Ô soạn trống lại = X đã nhận. Dùng khi không bắt được toast."""
        assert self.page
        for _ in range(16):
            await asyncio.sleep(0.5)
            box = await self.page.query_selector(SEL_BOX)
            if box is None:
                return True
            txt = (await box.inner_text()).strip()
            if not txt:
                return True
        return False

    # Dấu hiệu X nghi bot. Kiểm sau mỗi thao tác tương tác, không chỉ lúc đăng.
    LOCK_MARKS = (
        "this request looks like it might be automated",
        "verify you're human", "verify you are human",
        "unusual activity", "your account has been locked",
        "we've temporarily limited", "arkoselabs",
    )

    async def _check_soft_lock(self) -> None:
        assert self.page
        try:
            body = (await self.page.inner_text("body"))[:4000].lower()
        except Exception:
            return
        for mark in self.LOCK_MARKS:
            if mark in body:
                await self._shot("soft-locked")
                raise SoftLocked(
                    f"X chặn mềm (thấy {mark!r}). DỪNG app. Vào x.com bằng tay, "
                    "giải xác minh, nghỉ vài tiếng rồi hẵng chạy lại.")

    # --- hành động ---------------------------------------------------------
    async def _attach(self, image: str | Path) -> None:
        """Đính ảnh qua input file ẩn — không phải mở hộp thoại chọn file."""
        assert self.page
        p = Path(image)
        if not p.exists():
            raise XError(f"Không thấy ảnh để đính: {p}")
        inp = await self.page.wait_for_selector(
            'input[data-testid="fileInput"]', state="attached", timeout=20_000)
        await inp.set_input_files(str(p))
        try:
            await self.page.wait_for_selector(
                '[data-testid="attachments"]', timeout=30_000)
        except PWTimeout:
            await self._shot("attach-failed")
            raise XError("Ảnh không lên được — huỷ để khỏi đăng bài thiếu ảnh")
        await asyncio.sleep(1.0)

    async def post(self, text: str, image: str | Path | None = None) -> str | None:
        """Đăng 1 bài gốc. Trả URL nếu bắt được, None nếu đăng rồi mà không rõ URL."""
        assert self.page
        await self.page.goto(COMPOSE_URL, wait_until="domcontentloaded", timeout=45_000)
        await self._type_into(SEL_BOX, text)
        if image:
            await self._attach(image)
        await self._click_send()
        url = await self._url_from_toast()
        if url:
            return url
        if await self._confirm_sent():
            return None
        await self._shot("post-unconfirmed")
        raise XError("Bấm đăng rồi nhưng không xác nhận được — KIỂM TAY, "
                     "đừng đăng lại kẻo trùng")

    async def post_thread(self, parts: list[str],
                          image: str | Path | None = None) -> str | None:
        """Đăng thread trong 1 lần: gõ từng ô rồi bấm đăng một lần.

        Ảnh (nếu có) gắn vào bài ĐẦU — đó là bài được nhìn thấy nhiều nhất.
        """
        assert self.page
        if not parts:
            raise XError("thread rỗng")
        await self.page.goto(COMPOSE_URL, wait_until="domcontentloaded", timeout=45_000)
        await self._type_into(SEL_BOX, parts[0])
        if image:
            await self._attach(image)
        for i, part in enumerate(parts[1:], start=1):
            add = await self.page.wait_for_selector(SEL_ADD, timeout=15_000)
            await add.click()
            await asyncio.sleep(0.5)
            await self._type_into(SEL_BOX_N.format(n=i), part)
        await self._click_send()
        url = await self._url_from_toast()
        if url:
            return url
        if await self._confirm_sent():
            return None
        await self._shot("thread-unconfirmed")
        raise XError("Thread: bấm đăng rồi nhưng không xác nhận được — KIỂM TAY")

    async def reply(self, target_url: str, text: str) -> str | None:
        """Reply dưới 1 bài. Kiểm lại tuổi bài ngay trước khi gõ."""
        assert self.page
        await self.page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
        await asyncio.sleep(1.0)
        await self._type_into(SEL_BOX, text)
        await self._click_send()
        url = await self._url_from_toast()
        if url:
            return url
        if await self._confirm_sent():
            return None
        await self._shot("reply-unconfirmed")
        raise XError("Reply: bấm đăng rồi nhưng không xác nhận được — KIỂM TAY")

    async def quote(self, target_url: str, text: str) -> str | None:
        """Quote tweet: bình luận của mình + bài gốc đính kèm.

        Không đi qua menu Repost > Quote (mục Quote không có data-testid ổn định).
        Dán URL bài gốc vào cuối ô soạn thì X tự gắn thành thẻ quote — đường này
        bền hơn nhiều và không phụ thuộc ngôn ngữ giao diện.
        """
        assert self.page
        await self.page.goto(COMPOSE_URL, wait_until="domcontentloaded", timeout=45_000)
        await self._type_into(SEL_BOX, f"{text}\n\n{target_url}")
        # Chờ thẻ quote hiện ra; không có thì bài sẽ thành bài thường kèm link.
        try:
            await self.page.wait_for_selector(
                '[data-testid="attachments"], [role="blockquote"]', timeout=12_000)
        except PWTimeout:
            await self._shot("quote-card-missing")
            raise XError("Không thấy thẻ quote gắn vào — huỷ để khỏi đăng thành "
                         "bài thường kèm link trần")
        await self._click_send()
        url = await self._url_from_toast()
        if url:
            return url
        if await self._confirm_sent():
            return None
        await self._shot("quote-unconfirmed")
        raise XError("Quote: bấm đăng rồi nhưng không xác nhận được — KIỂM TAY")

    async def repost(self, target_url: str) -> bool:
        """Tự RT lại bài cũ của mình để tái dùng reach (tactic đo được ở
        @Crypto_bn: 8/40 bài gần nhất là tự RT)."""
        assert self.page
        await self.page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
        btn = await self.page.wait_for_selector('[data-testid="retweet"]', timeout=20_000)
        await btn.click()
        try:
            confirm = await self.page.wait_for_selector(
                '[data-testid="retweetConfirm"]', timeout=10_000)
        except PWTimeout:
            await self._shot("repost-no-confirm")
            raise XError("Không thấy menu xác nhận Repost")
        await confirm.click()
        await asyncio.sleep(2.0)
        # Đã RT thì nút đổi thành unretweet.
        done = await self.page.query_selector('[data-testid="unretweet"]')
        if done is None:
            await self._shot("repost-unconfirmed")
            raise XError("Repost không xác nhận được — kiểm tay")
        return True

    async def post_age_minutes(self, target_url: str) -> float | None:
        """Tuổi thật của bài, tính từ thẻ <time> NẰM TRONG link chứa status id.

        Bẫy gặp 14/11/2026: querySelector('time') đầu tiên có thể là mốc giờ của
        tweet được QUOTE bên trong, lệch nhiều giờ.
        """
        assert self.page
        m = re.search(r"(/[^/]+/status/\d+)", target_url)
        if not m:
            return None
        path = m.group(1)
        if self.page.url.rstrip("/") != target_url.rstrip("/"):
            await self.page.goto(target_url, wait_until="domcontentloaded", timeout=45_000)
        iso = await self.page.evaluate(
            """(p) => {
                const a = document.querySelector(`a[href*="${p}"] time`);
                return a ? a.getAttribute('datetime') : null;
            }""",
            path,
        )
        if not iso:
            return None
        from datetime import datetime, timezone
        when = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - when).total_seconds() / 60
