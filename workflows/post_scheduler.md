# Workflow: Post Scheduler

## Overview
Schedule and post original content tweets spaced 2-4 hours apart across the day.

## Content Pillars (daily mix)
| Pillar | Share | Examples |
|--------|-------|---------|
| News Reactions | 40% | Market moves, protocol updates, regulatory news |
| AI x Crypto | 20% | AI agents, DePIN, compute tokens |
| Memes | 20% | Gemini-generated images, quote cards |
| Quote Tweets | 10% | Repost KOL posts with commentary |
| Deep Analysis | 10% | Thread-style takes on trends |

## Daily Target: 4-6 posts

### Schedule Template
- Post 1: ~9:00 AM (news reaction to overnight moves)
- Post 2: ~12:00 PM (AI x Crypto or meme)
- Post 3: ~3:00 PM (market commentary or quote tweet)
- Post 4: ~6:00 PM (wisdom/motivation or deep take)
- Post 5: ~9:00 PM (meme or engagement bait)
- Post 6: ~11:00 PM (overnight recap or quote tweet)

## Post Creation Workflow

### Text-only Posts
1. Draft content in `posts/batch_YYYYMMDD.md`
2. Post via Chrome browser automation (Sonnet agent)

### Posts with Gemini Images
1. Open gemini.google.com → prompt for meme image
2. Download image → crop Gemini watermark
3. Compose tweet on X → attach image → post
4. See `workflows/post_with_gemini_image.md` for details

### Quote Tweets
1. Find KOL post to quote (via kol_scanner.py or manual)
2. Navigate to post → click Repost → Quote
3. Add commentary text → post

## Rules
- **Spacing**: 2-4 hours between own posts (never back-to-back)
- **Language**: English only
- **Hashtags**: 2-4 per post, natural placement
- **Character limit**: 280 chars (standard Premium)
- **No financial advice disclaimer**: Bio says "Not financial advice"
- **Images boost engagement**: Use Gemini images when possible
