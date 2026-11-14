# App XKols

Chạy nền trên laptop: quét bài mới của KOL, soạn bằng Claude API, đăng lên X bằng
Playwright với cookie của acc chính. Thay cho Scheduled task — khoảng cách giữa
các lần đăng là `sleep` random thật, không bị lưới cron gom về mốc chẵn, và model
chọn trong code chứ không qua UI.

## Cần điền trước khi chạy

| File | Điền gì | Cần cho |
|---|---|---|
| `tools/claude.env` | `ANTHROPIC_API_KEY` — lấy ở console.anthropic.com | cả dry-run và `--live` |
| `tools/x_main.env` | `X_CT0`, `X_AUTH_TOKEN` của **@macropandaX** (F12 → Application → Cookies → x.com) | chỉ `--live` |
| `tools/x_account.env` | đã có — acc phụ @NQuyenru cho twscrape, chỉ đọc | quét KOL |

Cả ba đều khớp `*.env` trong `.gitignore`, không lên GitHub. Dry-run không mở
browser nên chạy được khi chưa có cookie acc chính.

## Chạy

Dry-run (mặc định — không đăng gì, chỉ ghi draft ra `posts/dryrun_YYYYMMDD.md`):

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app
```

Một hành động rồi thoát, để xem thử:

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --once
```

Giả lập giờ để test cửa sổ mà không phải chờ tới 20:00:

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --once --now 20:15
```

**Chế độ duyệt tay** — app soạn xong thì dừng, đưa draft lên trang web local, chờ
bạn bấm Duyệt mới đăng. Đây là chế độ ở giữa: dry-run thì bạn đọc được draft
nhưng app không đăng, live thì app đăng mà bạn không kịp xem.

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --live --review
```

Mở `http://127.0.0.1:8787`. Draft nào không bấm trong 30 phút thì tự bỏ.

Chỉ xem, không duyệt (app tự quyết, trang chỉ để theo dõi):

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --live --web
```

Trang hiện: đã đăng gì hôm nay, hàng chờ duyệt, nhật ký, ghi chú lỗi, và nút
Dừng app. Tự làm mới mỗi 4 giây. Chỉ bind `127.0.0.1` nên không ai ngoài máy này
vào được. Đổi cổng bằng `--port`.

Đăng thật, app tự quyết hết:

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --live
```

Đăng thật và hiện cửa sổ Chromium để nhìn nó làm:

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe -m app --live --headful
```

**Dừng app:** tạo file `STOP` ở gốc repo, app thoát ở vòng kế tiếp. Hoặc Ctrl-C.

Nên chạy dry-run vài ngày, đọc `posts/dryrun_*.md`, thấy draft ổn rồi mới `--live`.

## Test

Không cần API key, không cần cookie, không gọi mạng:

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe tools\test_compliance.py
```

```bash
cd D:\AI\XKols && .venv\Scripts\python.exe tools\test_app.py
```

`test_compliance.py` canh một yêu cầu **pháp lý** (không call kèo, bài có số liệu
phải có ghi chú) — chạy lại mỗi khi sửa `brain.py`. `test_app.py` kiểm lịch, hạn
mức, state và các cổng lọc của scanner.

## Lịch

Giờ ICT. ICT = US Eastern **+12h**, nên hai cửa sổ này là lúc Mỹ đang online:

| Cửa sổ | Giờ ICT | Giờ ET | Làm gì |
|---|---|---|---|
| morning | 07:30–09:30 | 19:30–21:30 | 1 bài gốc + thread của ngày |
| evening | 20:00–23:30 | 08:00–11:30 | 3 bài gốc |

Reply chạy trong cùng hai cửa sổ, cách nhau 4–12 phút, tối đa 25/ngày và 2/tác
giả/ngày. Ngoài cửa sổ app ngủ 4–7 phút mỗi vòng và không làm gì.

Ngoài bài gốc còn ba loại hành động khác:

| Loại | Số/ngày | Ghi chú |
|---|---|---|
| **Quote tweet** | 2 | Bài người khác + bình luận của mình. **Tính là bài gốc nên được tính impression payout**, khác hẳn reply |
| **Tự RT bài cũ** | 1 | Bài của chính mình, 3–21 ngày tuổi, tái dùng reach |
| **Reply** | ≤25 | Không được tính payout — chỉ để lấy follower |

Quote không bao giờ thuật lại bài gốc (X đã đính kèm sẵn); phần chữ phải đứng
được một mình. Một bài đã reply thì không quote nữa và ngược lại.

Đổi lịch ở `app/config.py` (`WINDOWS`, `POST_GAP_MIN`, `REPLY_GAP_MIN`,
`MAX_REPLIES_PER_DAY`).

## Model

| Việc | Model | Vì sao |
|---|---|---|
| Bài gốc + thread | `claude-opus-5-5` | 4 lần/ngày, chất lượng quyết định impression |
| Reply | `claude-sonnet-5-5` | ~20 lần/ngày, cần nhanh và rẻ |

Sửa ở `app/config.py` (`MODEL_POST`, `MODEL_REPLY`, `MODEL_TRANSLATE`).
Từ 14/11: bài gốc và reply đều dùng Opus 5.5; chỉ phần dịch tiếng Việt dùng
Sonnet 5.5.

## Cấu trúc

| File | Việc |
|---|---|
| `config.py` | env, lịch, model, đường dẫn. ICT là offset cố định UTC+7, không cần `tzdata` |
| `state.py` | trạng thái theo ngày ra `posts/.state/state_*.json` + nhật ký TSV `posts/.log/` |
| `brain.py` | gọi Claude: soạn bài, thread, reply. Luật nội dung đọc từ `workflows/` |
| `scan.py` | cầu nối sang `tools/kol_scanner.py` |
| `x_browser.py` | Playwright: đăng, thread, reply, đọc tuổi bài |
| `runner.py` | vòng lặp + CLI |

## Những chỗ đã cẩn ý

- **Rate limit twscrape.** Quét 30 handle bằng 30 request làm cháy quota acc phụ
  trong đúng một vòng (đo 14/11: *"next available at 14:36"*). Scanner dùng search
  gộp `(from:a OR from:b ...)` — 22 handle chỉ còn 2 request, và kết quả search đã
  kèm follower count nên không cần tra từng user.
- **Bẫy mốc giờ.** `querySelector('time')` đầu tiên trên trang bài có thể là giờ
  của tweet được **quote** bên trong, lệch nhiều giờ. `post_age_minutes()` chỉ đọc
  thẻ `<time>` nằm trong link chứa status id của chính bài đó.
- **Không đăng trùng.** Bấm đăng mà không xác nhận được thì app báo lỗi và dừng,
  không bấm lại. Ảnh chụp lưu ở `posts/.log/shots/`.
- **Nội dung đọc từ X là dữ liệu.** Prompt bọc trong `<untrusted_data>` và nói rõ
  không làm theo chỉ dẫn nằm trong đó.
- **Chặn trước khi đăng.** Quá 280 ký tự, quá 2 hashtag, hay có engagement bait
  thì draft bị loại. Trước khi loại thì cho Claude sửa lại **một lần** — draft đầu
  tiên thử nghiệm bị chặn chỉ vì 282 ký tự, bỏ cả lần gọi Opus vì 2 ký tự là lãng phí.
- **Số liệu thị trường lấy trực tiếp, không qua TradingAgents.** `app/market.py`
  tải nến ngày từ Yahoo Finance rồi tự tính RSI, MACD, SMA/EMA, Bollinger, ATR.
  Bỏ `reports/` ngày 14/11 vì đó là file chép tay từ dự án khác, không tự cập
  nhật — hôm 14/11 bài vẫn phải ghi "13 Nov data". Cache 45 phút/lần gọi.
- **Bài chỉ có link bị loại ở scanner.** Đo 14/11: mấy bài kiểu "Update, the plaque
  is going back up <link>" qua hết các cổng khác, rồi bước soạn reply từ chối cả ba
  — tốn một lần gọi model mỗi bài. Nay chặn bằng độ dài phần chữ thật
  (`MIN_BODY_CHARS`, đã trừ link và @mention).
- **Sai account thì dừng.** Mở X xong app đọc `SideNav_AccountSwitcher_Button`,
  không khớp `X_USERNAME` là dừng ngay.
- **Cookie hết hạn thì dừng và nói cần điền lại**, không thử đăng nhập.
- Hai lỗi liên tiếp là dừng hẳn vòng lặp.

## Việc app không làm, và sẽ không làm

Mua Premium, nhập mật khẩu, đăng nhập hộ, xác minh Stripe, đổi handle. Xem
`workflows/account_profile.md` — những việc đó chủ account tự làm.
