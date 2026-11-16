# Workflow: Post Scheduler

Revised 2026-11-14. Supersedes the 6-posts-across-the-day version.

## Goal

Build **verified Home Timeline impressions**, because that is the only thing X's
Original Content Rewards pays for. Replies earn nothing. Only original posts do.

Threshold to clear: **500,000 verified impressions / 90 days ≈ 5,600 per day.**
Baseline on 2026-11-13: ~193 total views/day across 6 posts. The gap is the whole
job.

## Positioning

**Dropped 2026-11-14:** the `TradingAgents` reports in `reports/` are no longer
used. They were a hand-copied snapshot from another project that never refreshed,
so on 14 Nov the app was still posting "13 Nov data". Market figures now come from
`app/market.py` — Yahoo Finance daily candles with RSI, MACD, moving averages and
Bollinger bands computed in-process, dated today, every run.

The old positioning below is kept only as a record of what was tried:

> **An AI agent system that reads the market every day, with every call published
> — wins and losses.**

Target reader: English-speaking developers, quants and semi-pro traders in the
US and EU. That audience buys X Premium at a high rate, and only Premium viewers'
impressions count toward payout, so it is the right audience twice over.

A public, dated track record is the one thing on crypto X that cannot be faked.
After 60-90 days it becomes the reason to follow.

## Daily target: 7 posts + 1 thread

Raised from 4 on 2026-11-15 by the project owner, together with two new windows.
The earlier "fewer, better" argument (six thin posts teach the ranker that this
account does not hold attention) still holds for *quality*: every gate in
`app/brain.py` stays. What changed is coverage — 4 posts all sat inside two
windows, one of which measures worst (see below).

## Timing

ICT = US Eastern **+ 12h**.

| Window (ICT) | US ET | Content |
|---|---|---|
| 00:00 – 02:30 | 12:00 – 14:30 (prev. day) | 2 posts |
| 07:30 – 09:30 | 19:30 – 21:30 (prev. day) | 1 post + the daily thread |
| 11:00 – 13:00 | 23:00 – 01:00 | 1 post |
| 20:00 – 23:30 | 08:00 – 11:30 | 3 posts |

Spacing inside a window: 45-90 min, randomized. Never back-to-back.

### What the hours actually measure

Measured 2026-11-15: 282 posts over 7 days from the 22 handles in
`tools/reply_targets.txt`, bucketed by ICT hour, median views per bucket.

| ICT block | posts | median views |
|---|---|---|
| 00 – 06 | 148 | 22,500 |
| 07 – 09 | 27 | **29,600** |
| 11 – 18 | 22 | 22,300 |
| 20 – 23 | 74 | **15,300** |

Two things the previous version of this file asserted turned out to be wrong:

- "Never post 11:00-18:00 ICT, it is dead" — it is not. That block is European
  morning and measures the same as the overnight hours.
- The evening window was treated as the main slot (3 of 4 posts) while it is the
  **weakest** of the four blocks.

Keep the caveat in view: this measures when *other accounts'* audiences are
awake, which is a proxy. At 6-17 views per post the binding constraint is
distribution, not hour-of-day. Timing is a second-order lever; it is worth not
choosing the worst block, and not worth more than that.

## Replies run outside the windows too

Changed 2026-11-15. The windows gate POSTS only. The reply branch runs all day
on a slower cadence (`REPLY_GAP_OFF_WINDOW_MIN`, 15-30 min, versus 4-12 inside a
window), because someone who mentions the account at 14:00 ICT should not wait
until 20:00. The slower cadence is a rate-limit concession to the read-only
twscrape account, which has hit its quota once (09:04, 2026-11-15).

## The subject is the market, not the tooling

Corrected 2026-11-14, twice, by the project owner. Two earlier versions of this
file made the analysis pipeline the topic — "our agents disagreed", "our model
rated BTC underweight", "prompt design notes". Nobody follows a markets account to
read about its software. None of the three reference accounts does it.

The pipeline is a **source** for claims about the market. It is never the subject.
`app/brain.py` → `is_meta()` now rejects a post that slips back into it; the rule
is off only inside a thread, whose closing post must disclose that the analysis is
AI-generated.

## Content pillars

One pillar per post, enforced in code — each post is told which pillar to write,
and all five are used before any repeats (`config.POST_PILLARS`). The earlier
version passed percentages and let the model choose; it chose the pipeline report
nearly every time, because that was the strongest block of data in the prompt.

| Pillar | What it is | Data it gets |
|---|---|---|
| `news` | One thing that just happened, from the scan, with the number | scan, last 3h |
| `trend` | What the timeline is collectively on about, **counted by how many separate accounts touched it** in 12h — measured, not guessed | trend table |
| `market_read` | What price is doing now, with real figures | market table |
| `explainer` | One mechanism explained: liquidation cascades, ETF flows, funding | none |
| `take` | Opinionated take on a current discussion, with a claim of its own | market table |
| `wry` | Dry humour about markets, from a trader's chair | none |

A pillar that needs outside data and finds none falls back to `explainer` rather
than inventing something.

Trend counts accounts, not mentions — one person posting five times about a thing
is not a trend. Measured 14 Nov: Jensen (4 accounts), Anthropic (3), NVDA (2).
Related terms do not merge yet, so one story can appear as several rows.

`track_record` is deliberately not a post pillar — the morning thread covers it.

Dropped: memes, generic "wisdom/HODL", and anything about the account's own stack.

## Compliance — read `workflows/compliance.md`

No trade calls, ever, in any form. Any post carrying a figure, level, indicator or
model rating must contain "Not financial advice."; in a thread the last post
carries it. These are enforced by a hard check in `app/brain.py` → `validate()`,
not merely requested in a prompt. Unlicensed buy/sell recommendations are a legal
violation in Vietnam and a disclaimer does not cure one.

## Format (measured against reference accounts, 2026-11-14)

Compared @Crypto_bn (35k followers), @josnhathuy (23.5k) and @AshCrypto (2.15M).
What their best posts share, and what this account now copies:

- **100-200 characters.** Not a 250-character wall of figures.
- **Opinion or finding in the first line.** Never build to a conclusion.
- **A blank line between thoughts.** Two or three short lines, never one paragraph.
- **One idea per post.**
- Self-RT of an older post, 1/day, for posts 3-21 days old. @Crypto_bn does this
  on 8 of his last 40 posts; it costs nothing and recycles reach.

Not copied: their market calls, hopium ("I will become a millionaire"), crude
language, and any invented personal life — this account is a system and says so.

## Images

Measured on @AshCrypto's last 30 posts: **mean 121.8k views with media vs 113.8k
text-only — about 7% apart.** Images are not a reach lever by themselves. What his
top posts share is being early on a big number, not having a picture.

So: an image earns its place only when it **is** the information — a chart, a
table, a screenshot of the data. Decorative memes are not part of the mix.

The high-value image for this account is its own output: a chart with the model's
dated call marked on it, an indicator table, or a scorecard of past calls against
outcomes. Rendered from the pipeline's own numbers, deterministic, no watermark to
crop. That artifact is also the track record made visible, which is the thing
worth sharing. **Not built yet.**

## The daily thread

One thread per day, posted in the morning ICT window. Thread = the top
impression driver available, and Premium allows long posts.

Shape: hook with the verdict and a number → bear case → bull case → levels →
what would change the picture. Source every figure from `app/market.py`, dated by
the candle date.

## Rules

- **English only.** No Vietnamese on this account.
- **Every claim carries a number or a source.** No "smart money is rotating".
- **Hashtags: 0-2.** Three or more reads as reach-farming and is being
  down-ranked. The old 2-4 rule is withdrawn.
- **No financial advice.** State the system's position, never tell anyone to buy.
- **Score the previous call openly**, including when it was wrong. That is the
  product.
- **No engagement bait** ("drop a 🚀", "who agrees"). Payout review flags it.
- Image only when it carries information (a chart, a table). Generated memes are
  no longer part of the mix.

## Volume discipline

4 posts + ~20 replies/day is a human-plausible load. Do not raise it to chase the
impression threshold; getting demonetized for platform manipulation costs more
than the impressions are worth.

## Source: X's own news and trend panel (added 2026-11-14)

`app/xnews.py` reads the **Today's News** and **What's happening** panels from
x.com through twscrape (`api.trends("news")`, read-only, burner account). No
browser needed, cached 25 minutes in `posts/.state/xnews.json`.

Why it matters: `scan.topics()` only sees what the 22 handles in
`tools/reply_targets.txt` are saying. X's panel sees the whole platform — it
carries stories those 22 have not reached yet.

Filtering: keep anything matching the crypto / AI / markets vocabulary or tagged
`Business & finance`, `Technology`, `Science`. Hard-drop politics, elections,
sport and celebrity — off-topic and needless risk.

Two pillars consume it:

- **news** — X headlines for the subject, plus real scanned posts for the claims
  and figures. If the KOL scan is empty, `xnews.posts_for()` pulls actual posts
  under the top headline instead.
- **trend** — both lists side by side: what X says the platform is on, and the
  measured per-account count from the KOL timeline. The brief asks for a topic
  in both, or one X has that the niche has not caught up to.

**A headline is not a verified fact.** The pillar brief requires attribution
("X is surfacing…"), never assertion. Headline text is untrusted data and is
wrapped in `<untrusted_data>` in the prompt like every other scanned input.

## Only market_read may read indicators (added 2026-11-14)

Observed when sampling all six pillars in one batch: `market_read` and `take`
produced the same post — both "RSI oversold, below the lower Bollinger band".
Both had been handed the same market table and nothing else to work with.

Rule now enforced in code, not in prompt text:

- `_report_block()` gives the market table to **`market_read` only**.
- `validate(text, pillar=...)` rejects any post from `take`, `explainer`, `wry`
  or `trend` that mentions RSI, MACD, Bollinger, SMA/EMA, ATR, overbought,
  oversold, golden/death cross. `repair()` is told to rewrite without indicators
  rather than swap one for another.

The division: `market_read` reads today's candles. `take` argues about how the
market or the industry works — incentives, structure, positioning — and must
still make sense next week. Prompt wording alone had already failed twice at
keeping pillars apart (TradingAgents, then the meta-content episode), so this
is a hard gate.

## Ảnh theo từng chủ đề (mở rộng 14/11)

Trước đó chỉ `market_read`/`news` có ảnh, vì luật đính ảnh là "bài phải mang số
liệu thị trường". Hai bài tối 14/11 rơi trúng `wry` và `explainer` — hai chủ đề
cố ý KHÔNG nhận bảng chỉ báo — nên cả hai ra bài không ảnh.

Giờ mỗi chủ đề có loại ảnh riêng, vì mỗi chủ đề mang loại thông tin khác nhau:

| chủ đề | ảnh | hàm |
|---|---|---|
| market_read, news | đường giá 90 phiên + mốc kỹ thuật | `chart.latest_card()` |
| trend | số tài khoản riêng biệt nhắc mỗi chủ đề | `chart.trend_card()` |
| take (về token AI) | tương quan với BTC vs NVDA | `chart.corr_card()` |
| explainer | sơ đồ cơ chế 3-5 bước, có thể nối vòng | `chart.flow_card()` |
| wry | không có | — |

`explainer` lấy các bước bằng `brain.mechanism_steps()`: đưa chính bài vừa soạn
cho model, hỏi lại chuỗi bước. Nếu bài là quan sát/định nghĩa chứ không phải một
chuỗi nhân quả thì trả `{"ok": false}` và KHÔNG vẽ — ép mọi bài explainer thành
sơ đồ sẽ ra hình vô nghĩa, tệ hơn không có hình.

`wry` cố ý không có ảnh: nó là một câu quan sát, không có gì để đo. Thà bài chữ
hay còn hơn ảnh trang trí.

Trần vẫn là `MAX_IMAGE_POSTS_PER_DAY = 2`.
