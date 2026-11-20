"""Smoke test app XKols — kiem tra phan khong can API key."""
import sys
from datetime import datetime, time as dtime
from pathlib import Path

sys.path.insert(0, r"D:\AI\XKols")

from app import config, state, brain
from app.config import Settings

fail = []

def check(name, cond, extra=""):
    print(("  OK   " if cond else "  FAIL ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        fail.append(name)

print("1) cua so lich theo gio ICT")
# Bon cua so tu 15/11: night 00:00-02:30, morning 07:30-09:30,
# midday 11:00-13:00, evening 20:00-23:30.
cases = [("01:00", "night"), ("03:00", None), ("07:00", None),
         ("08:00", "morning"), ("09:30", "morning"), ("10:30", None),
         ("12:00", "midday"), ("14:30", None), ("19:59", None),
         ("20:00", "evening"), ("23:30", "evening"), ("23:31", None)]
for hhmm, want in cases:
    hh, mm = map(int, hhmm.split(":"))
    t = config.now().replace(hour=hh, minute=mm, second=0, microsecond=0)
    got = config.current_window(t)
    name = got.name if got else None
    check(f"{hhmm} -> {name}", name == want, f"(mong {want})")

print("\n2) tong so bai/ngay")
total = sum(w.posts for w in config.WINDOWS)
threads = sum(1 for w in config.WINDOWS if w.thread)
check("7 bai goc", total == 7, f"= {total}")
check("1 thread", threads == 1, f"= {threads}")

print("\n3) validate noi dung")
check("bai thuong dat", brain.validate(
    "The 13 Nov run closed BTC at $68,714.\n\nNot financial advice.")[0])
check("qua dai bi chan", not brain.validate("x" * 281)[0])
check("3 hashtag bi chan", not brain.validate("hi #a #b #c")[0])
check("2 hashtag dat", brain.validate(
    "Model output, 13 Nov: underweight.\n\n"
    "Not financial advice. #Bitcoin #BTC")[0])
check("bait bi chan", not brain.validate("Big move coming. Who agrees?")[0])
check("rong bi chan", not brain.validate("   ")[0])
# Luat moi (14/11): hai mau duoi day truoc kia duoc cho qua, gio phai bi chan.
check("khuyen ty trong bi chan", not brain.validate(
    "The system cut to 60% exposure. Not financial advice.")[0])
check("so lieu thieu ghi chu bi chan", not brain.validate("BTC at $68,400.")[0])

print("\n4) state ghi/doc lai")
st = state.load("29991231")
st.date = "29991231"
st.record_post("evening", "https://x.com/a/status/1", "bai test")
st.record_reply("SomeOne", "123", "https://x.com/b/status/2", "reply test")
st.arm("next_reply_at", (4, 12))
state.save(st)
st2 = state.load("29991231")
check("posts_done luu duoc", st2.posts_in("evening") == 1, f"= {st2.posts_in('evening')}")
check("replies_done luu duoc", st2.replies_done == 1)
check("nho da reply tweet 123", st2.already_replied("123"))
check("chan reply tweet moi khi chua qua han", not st2.due("next_reply_at"))
CAP = config.MAX_REPLIES_PER_AUTHOR_PER_DAY
st2.replied_authors["someone"] = CAP - 1
check(f"con cho khi moi {CAP - 1}/{CAP} lan", st2.can_reply_to("SomeOne"))
st2.replied_authors["someone"] = CAP
check(f"chan reply tac gia qua {CAP} lan", not st2.can_reply_to("SomeOne"))
# Reply TAY phải cộng chung sổ, không thì trần chỉ chặn được một nửa.
st2.replied_authors["mixedguy"] = CAP - 1
st2.manual_authors["mixedguy"] = 1
check("reply tay tinh chung vao tran", not st2.can_reply_to("MixedGuy"))
check("tac gia khac van cho", st2.can_reply_to("Other"))

# Muc lam tay de qua STALE_MIN phut thi tu rung, va khong con chiem suat trong
# tran reply/tac gia nua (chot 17/11).
from app import manual
from datetime import timedelta
now = config.now()
old = manual.Item(id="x1", author="Stale", url="", followers=1, age_min=1,
                  replies=0, their_text="", draft="d",
                  created_at=(now - timedelta(minutes=manual.STALE_MIN + 5)).isoformat())
fresh_i = manual.Item(id="x2", author="Fresh", url="", followers=1, age_min=1,
                      replies=0, their_text="", draft="d",
                      created_at=(now - timedelta(minutes=10)).isoformat())
done_i = manual.Item(id="x3", author="Done", url="", followers=1, age_min=1,
                     replies=0, their_text="", draft="d", done=["reply"],
                     created_at=(now - timedelta(minutes=manual.STALE_MIN + 5)).isoformat())
check("muc qua han bi tinh la rung", manual._stale(old, now))
check("muc moi soan van giu", not manual._stale(fresh_i, now))
check("muc da reply thi khong rung", not manual._stale(done_i, now))
st2.replies_done = config.MAX_REPLIES_PER_DAY
check("chan khi het han muc ngay", not st2.can_reply_to("Other"))
Path(config.STATE_DIR / "state_29991231.json").unlink(missing_ok=True)

print("\n5) scanner nap duoc + doc targets")
from app import scan
ks = scan._scanner()
targets = ks.load_targets()
check("doc reply_targets.txt", len(targets) >= 20, f"= {len(targets)} handle")
check("khong con jam1sm1th", "jam1sm1th" not in targets)
check("loai handle > 600k", all(h not in targets for h in ("tier10k", "Pentosh1")))
ok, why = ks.judge(5, 10, 2_000_000, 60)
check("mega + bai 5 phut -> nhan", ok, why)
ok, _ = ks.judge(30, 10, 2_000_000, 60)
check("mega + bai 30 phut -> loai", not ok)
ok, _ = ks.judge(10, 200, 100_000, 60)
check("200 reply -> loai", not ok)
ok, _ = ks.judge(90, 5, 100_000, 60)
check("bai 90 phut -> loai", not ok)
rows = [{"handle": "a", "likes": 1, "retweets": 0, "replies": 0, "age_min": 1}] * 5
check("diversify cap 2/tac gia", len(ks.diversify(rows)) == 2)

print("\n5b) luan phien chu de bai goc")
from app import runner
st3 = state.DayState(date="29991230")
seen = set()
for _ in range(len(config.POST_PILLARS)):
    p = runner.pick_pillar(st3)
    seen.add(p)
    st3.pillars_used.append(p)
check("dung het cac chu de truoc khi lap", seen == set(config.POST_PILLARS),
      f"= {sorted(seen)}")
check("track_record khong nam trong bai goc",
      "track_record" not in config.POST_PILLARS, "(thread lo phan do)")
check("quay vong khi da dung het", runner.pick_pillar(st3) in config.POST_PILLARS)
check("explainer khong dua report vao prompt",
      "does not need one" in brain._report_block("explainer"))
check("market_read co dua report vao prompt",
      "does not need one" not in brain._report_block("market_read"))

print("\n5b2) chu de co ban (them 18/11)")
for pl in ("term", "ai", "money"):
    check(f"co pillar {pl}", pl in config.POST_PILLARS and pl in brain.PILLAR_BRIEF)
    check(f"{pl} khong doc chi bao", pl in brain.NO_INDICATOR_PILLARS)
check("thread luan phien 2 kieu",
      {config.thread_kind(config.now().replace(day=d)) for d in (1, 2)}
      == set(config.THREAD_KINDS))
# Chi chan dung viec chi cho xuong tien vao mot thu cu the.
ok, why = brain.validate("You should invest in an index fund.",
                         require_disclaimer=False)
check("chan: chi cho xuong tien", not ok, why if not ok else "DA CHO QUA")
# Chu du an chot 18/11: noi chuyen tien bac kieu Rich Dad Poor Dad khong phai
# call keo, dung chan. Bo cu chan ca "build wealth", "financial freedom".
for good in ("Compound interest doubles money in about 24 years at 3% a year.\n\n"
             "Not financial advice.",
             "Rich Dad Poor Dad draws one line that sticks: an asset pays you, "
             "a liability bills you.",
             "Most people are taught to work for money, never taught about money.",
             "Paying yourself first means the saving happens before the spending."):
    ok, why = brain.validate(good, pillar="money")
    check(f"cho qua: {good[:30]}", ok, why if not ok else "")

print("\n5b3) chu de strategy (them 18/11)")
check("co pillar strategy", "strategy" in config.POST_PILLARS
      and "strategy" in brain.PILLAR_BRIEF)
# Khac moi pillar con lai: strategy DUOC goi ten chi bao, vi no day cach doc.
check("strategy duoc doc chi bao", "strategy" not in brain.NO_INDICATOR_PILLARS)
check("strategy khong duoc bang so hom nay",
      "do not quote a live price" in brain._report_block("strategy"))
check("day golden cross thi qua", brain.validate(
    "A golden cross is when the 50-day average rises above the 200-day one.\n\n"
    "Traders read it as a trend turning. It says nothing about why.\n\n"
    "Not financial advice.", pillar="strategy")[0])
ok, why = brain.validate("Golden cross on BTC. You should buy the dip.",
                         pillar="strategy")
check("chan: bien chi bao thanh keo", not ok, why if not ok else "DA CHO QUA")
from app import chart_strategy
check("chon anh theo chu trong bai",
      chart_strategy.card_for.__doc__ is not None)

print("\n5c) chan noi dung meta (viet ve chinh he thong)")
for bad, label in (
    ("More LLM agents in the loop does not mean fewer errors.", "LLM agents in the loop"),
    ("Our pipeline read forty sources to say 'unclear'.", "our pipeline"),
    ("The bear agent was overruled and it was right.", "bear agent"),
    ("A note on prompt design: we stopped letting it see price.", "prompt design"),
):
    ok, why = brain.validate(bad)
    check(f"chan: {label}", not ok, why if not ok else "DA CHO QUA")
check("bai thi truong binh thuong van qua", brain.validate(
    "ETF outflows hit $1.07B this week.\n\nNot financial advice.")[0])
check("thread duoc phep noi la AI tao ra", brain.validate_thread([
    "BTC closed at $68,714 on 13 Nov.",
    "AI-generated analysis from a multi-agent pipeline.\n\nNot financial advice."])[0])

print("\n5d) chi market_read duoc doc chi bao")
IND = "BTC RSI14 hit 23.6 on 14 Nov.\n\nNot financial advice."
for p in brain.NO_INDICATOR_PILLARS:
    ok, why = brain.validate(IND, pillar=p)
    check(f"chan chi bao trong {p}", not ok, why if not ok else "DA CHO QUA")
check("market_read van duoc doc chi bao", brain.validate(IND, pillar="market_read")[0])
check("take khong dua report vao prompt",
      "does not need one" in brain._report_block("take"))
check("take khong co chi bao thi qua", brain.validate(
    "Exchanges earn on volume, not on direction. That is why every outage lands "
    "on the same day.", pillar="take")[0])

print("\n6) Settings -> cookie cho Playwright")
s = Settings(anthropic_key="k", x_username="macropandaX", x_ct0="CT", x_auth_token="AT",
             account_handle="macropandaX")
names = {c["name"]: c for c in s.cookies}
check("co ct0 + auth_token", set(names) == {"ct0", "auth_token"})
check("domain .x.com", all(c["domain"] == ".x.com" for c in names.values()))
check("auth_token httpOnly", names["auth_token"].get("httpOnly") is True)

print("\n7) x_browser nap duoc (Playwright da cai)")
try:
    from app import x_browser
    check("import x_browser", True)
    check("selector dung data-testid", x_browser.SEL_SEND == '[data-testid="tweetButton"]')
except Exception as e:
    check("import x_browser", False, str(e))

print("\n8) runner nap duoc")
try:
    from app import runner
    check("import runner", callable(runner.main))
except Exception as e:
    check("import runner", False, str(e))

print()
if fail:
    print(f"THAT BAI {len(fail)}: " + ", ".join(fail))
    sys.exit(1)
print("TAT CA DAT")
