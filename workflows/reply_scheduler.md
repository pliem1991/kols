# Workflow: KOL Reply Scheduler

## Overview
Automated system to post replies under big KOL tweets, spaced with random intervals to avoid bot detection.

## Setup
1. Prepare reply schedule in `posts/reply_schedule_YYYYMMDD.md`
2. Each reply needs: KOL handle, post URL, draft reply text
3. All replies must be under 280 characters (X standard Premium limit)

## Execution Flow

### Using Claude Code + Sonnet Agents
```
1. Read reply_schedule file
2. For each reply in queue:
   a. Spawn Sonnet agent to post via Chrome browser
   b. Agent navigates to tweet URL → clicks reply → types text → posts
   c. After posting, schedule next reply with ScheduleWakeup
   d. Random delay: 18-35 minutes between replies
3. Track posted/pending status in schedule file
```

### ScheduleWakeup Pattern
```
ScheduleWakeup({
  delaySeconds: random(1080, 2100),  // 18-35 min
  prompt: "Post next KOL reply from E:\\Kols\\posts\\reply_schedule_YYYYMMDD.md...",
  noop: false,
  reason: "Schedule next KOL reply (@handle) ~N min after previous"
})
```

### Sonnet Agent Prompt Template
```
Post a reply on X via Chrome browser automation.
- Navigate to: <tweet_url>
- Reply text: <draft_text>
- Use javascript_tool to find reply textarea, insert text
- Click Post/Đăng button
- Verify toast confirmation
```

## Rules
- **Random timing**: 18-35 min between replies (never fixed intervals)
- **English only**: All replies to international KOLs
- **Add value**: Insight, counter-point, data — NOT "great post!"
- **No shilling**: Don't mention own tokens or promote anything
- **Verify freshness**: Only reply to posts from the last 12h (scanner default window)
- **Mix strategies**: Combine direct replies with quote tweets for variety

## KOL Tiers
- **Tier 1** (1M+ followers): @elonmusk, @cz_binance, @VitalikButerin, @saylor, @WatcherGuru
- **Tier 2** (300K+): @APompliano, @brian_armstrong, @cobie, @DocumentingBTC, @DrJimFan
- **Tier 3** (AI crossover): @AndrewYNg, @ylecun, @balajis, @emollick

## Scanning for Fresh Posts
Use `tools/kol_scanner.py` with twscrape to find hot posts (default window: last 12h):
```bash
python tools/kol_scanner.py --top 10
```
Override the window if needed: `python tools/kol_scanner.py --top 10 --hours 24`
