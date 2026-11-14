# Account & Profile Checklist — @macropandaX

Things only the account owner can do. The app cannot and must not do any of
these: they need the password, a payment method, or identity verification.

## Baseline, 2026-11-14

| | |
|---|---|
| Handle | @macropandaX — đổi 14/11, trước là @L_gaucuhanh |
| Name | Macro Panda — đổi 14/11, trước là "Liem Pham" |
| Followers | 762 |
| Following | 93 |
| Posts | 4,804 |
| Created | 2021-02-20 |
| Premium | **no** |
| Bio | "Crypto & AI markets, read daily. Structure, flows, and what the numbers don't say. No calls, no signals. Not financial advice." — đổi 14/11 |
| Reach | 6 posts on 11-13 drew 9-65 views each, ~193 total |

## Monetization gate (Original Content Rewards)

Creator Revenue Sharing was retired 2026-09-07. The current program needs:

Số thật, đọc từ chính trang eligibility của X ngày 14/11
(`x.com/i/jf/creators/original_content_rewards`):

- [ ] Active **Premium, Premium+ or Premium Business** — Basic does not qualify
- [ ] 500 **verified** followers — **đang có 29**, KHÔNG phải 762
- [ ] **500,000 verified Home Timeline impressions / 90 days** — **đang có 8**

**Sửa lỗi 14/11:** trước đó ghi "762 follower, đã qua mốc 500". Sai. X đếm
**verified follower** (người có Premium), không đếm tổng follower. 762 tổng thì
chỉ 29 là verified. Mốc 500 chưa qua, còn xa.

Con số 8 impression/90 ngày cũng là số X dùng để trả tiền — khác hẳn `viewCount`
mà `app/stats.py` đọc được (tổng lượt xem, ai xem cũng tính). Khoảng cách tới
500.000 không phải chuyện tinh chỉnh nội dung.
- [ ] Stripe payout account + identity verification (Vietnam is a supported
      payout country)

Only impressions from Premium-subscribing viewers, on the Home Timeline, with at
least half the post visible, count. Search and Explore views do not.

Reported payout rate from creators' own figures: ~$1.0-1.2 per 1,000 verified
impressions. So the 500k threshold is worth roughly **$500-600 per 90 days**.
Treat ad revenue as proof of reach, not as the business. Real revenue at this
size comes from paid subscriptions, sponsorships, and selling the report itself.

## To do, in order

1. **Subscribe to Premium.** Nothing else matters until this exists. Check the
   in-app price for Vietnam; global Premium is around $8/month.
2. **Check Settings → Account status** right after subscribing. 4,804 posts
   averaging ~10 views suggests the account may already be reach-limited. Find
   out before investing three months of content.
3. ~~**Change the handle.**~~ Xong 14/11: @L_gaucuhanh → **@macropandaX**, chủ
   tài khoản tự đổi. @macropanda, @macro_panda, @PandaMacro đều đã có người giữ.
4. ~~**Change the display name.**~~ Xong 14/11: **Macro Panda**.
5. ~~**Rewrite the bio.**~~ Xong 14/11. Bỏ cụm **"Market alpha"** — đó là lời hứa
   lợi nhuận, đúng loại nội dung mà `app/brain.py` chặn bằng cổng cứng, và là vùng
   khuyến nghị đầu tư không phép theo `workflows/compliance.md`. Câu
   *"No calls, no signals"* lọc đúng người đọc: ai tìm kèo sẽ bỏ qua.
   (Bản nháp cũ *"Multi-agent AI reads the market daily"* đã bỏ — chủ dự án bác
   ngày 14/11: chủ đề là thị trường, không phải công cụ.)
6. **Pin the track-record thread.** This is the single highest-leverage item
   after Premium: it decides whether a visitor follows.
7. **Set up Stripe payout** once impressions are within reach of the threshold.

## Known drag

The existing 762 followers were largely acquired through Vietnamese
airdrop/giveaway activity in 2024 (see the retweet history). They do not read
English market content and will not engage with it, which suppresses initial
distribution of every new post. Expect low reach for several weeks regardless of
content quality. Keeping the account is still right — the 500-follower gate is
already cleared and account age from 2021 counts for something.

## Never automate

Password entry, login, Premium purchase, Stripe/identity verification, handle
changes. The owner does these by hand.

## Theo dõi tự động (app/payout.py, thêm 14/11)

`XBrowser.eligibility()` mở `x.com/i/jf/creators/original_content_rewards` bằng
cookie acc chính và đọc đúng hai con số X dùng để xét. Chạy tối đa 12 giờ một
lần, ghi một dòng mỗi ngày vào `posts/.state/payout.json`, hiện trên dashboard
ở mục "Đường tới payout" kèm thanh tiến độ và tốc độ 7 ngày.

Chỉ số DẪN ĐƯỜNG là **verified follower**, không phải view. 29 → 500 mới là
đường đi; view lên xuống không nói lên điều gì vì người xem không có Premium
thì không tính một impression nào.

Đo lần đầu 14/11: 29 verified follower, 8 impression / 90 ngày.
