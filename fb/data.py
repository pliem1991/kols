"""Đọc số liệu bot comment chéo / kết bạn Facebook. CHỈ ĐỌC, không ghi gì vào thư mục bot.

Nguồn (thư mục cheo của project agaubun):
- state.json      : group, câu kế tiếp, số comment hôm nay (daily), bài đã comment
- ket-ban.json    : lời mời kết bạn đã gửi (date, mutual...)
- log.md          : mỗi lượt chạy một mục "## ..." (cả lượt task cũ lẫn bot browser-use)
- dung-khan-cap.txt: có file này = bot đã tự khóa sau cảnh báo của Facebook
- bot.py          : đọc hằng số hạn mức để trang luôn khớp với code bot
- .env            : chỉ đọc khóa TT_MODEL, không bao giờ đọc/gửi khóa khác
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

CHEO = Path(os.environ.get("FB_CHEO", r"D:\AI\Facebook\agaubun\cheo"))
DEFAULT_MODEL = "claude-sonnet-5-5"

ERR = re.compile(r"[Ll]ỗi|CẢNH BÁO|DỪNG|Dừng sớm|không kết nối|bị khóa|checkpoint", re.I)
NOT_ERR = re.compile(r"Không có cảnh báo", re.I)


def _json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:  # noqa: BLE001
        return default


def _const(src: str, name: str, default):
    m = re.search(rf"^{name}\s*=\s*(\d+)", src, re.M)
    return int(m.group(1)) if m else default


def limits() -> dict:
    try:
        src = (CHEO / "bot.py").read_text(encoding="utf-8")
    except OSError:
        src = ""
    m = re.search(r"^RUN_MIN,\s*RUN_MAX\s*=\s*(\d+),\s*(\d+)", src, re.M)
    return {
        "comments": _const(src, "DAILY_MAX_COMMENTS", 50),
        "friends": _const(src, "FRIEND_DAILY_MAX", 4),
        "mutual": _const(src, "MIN_MUTUAL", 16),
        "run_min": int(m.group(1)) if m else 3,
        "run_max": int(m.group(2)) if m else 8,
        "groups_per_run": _const(src, "GROUPS_PER_RUN", 2),
        "posts_per_group": _const(src, "POSTS_PER_GROUP", 4),
    }


def model() -> str:
    if os.environ.get("TT_MODEL"):
        return os.environ["TT_MODEL"]
    try:
        for line in (CHEO / ".env").read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() == "TT_MODEL" and v.strip():
                return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return DEFAULT_MODEL + " (mặc định)"


def chrome_open() -> bool:
    """Giống profile_in_use() của bot: lockfile của Chrome bot đang bị giữ."""
    lock = CHEO / "chrome-profile" / "lockfile"
    if not lock.exists():
        return False
    try:
        with open(lock, "r+b"):
            return False
    except OSError:
        return True


TASK = "TT cheo bot"
_NEXT: dict = {"t": 0.0, "v": None}


def next_run() -> dict | None:
    """Giờ chạy kế của tác vụ Windows chạy bot (bot tự lệch thêm 0-5 phút). Cache 60 giây."""
    if time.time() - _NEXT["t"] < 60:
        return _NEXT["v"]
    v = None
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"$t=Get-ScheduledTask -TaskName '{TASK}' -ErrorAction Stop;"
             f"$i=$t|Get-ScheduledTaskInfo;"
             "\"$($t.State)|$(if($i.NextRunTime){$i.NextRunTime.ToString('yyyy-MM-dd HH:mm')})\""],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        state, _, at = out.stdout.strip().partition("|")
        if state:
            v = {"state": state, "at": at or None}
    except Exception:  # noqa: BLE001
        v = None
    _NEXT.update(t=time.time(), v=v)
    return v


def parse_log() -> list[dict]:
    try:
        text = (CHEO / "log.md").read_text(encoding="utf-8")
    except OSError:
        return []
    runs = []
    for block in re.split(r"^## ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        lines = [l[2:].strip() if l.startswith("- ") else l.strip()
                 for l in body.splitlines() if l.strip()]
        md = re.search(r"(\d{2})/(\d{2})/(\d{4})", head)
        if not md:
            continue
        mt = re.search(r"(\d{1,2}):(\d{2})", head) or re.search(r"~(\d{1,2})h", head)
        hh, mm = (int(mt.group(1)), int(mt.group(2)) if mt.lastindex == 2 else 0) if mt else (0, 0)
        when = datetime(int(md.group(3)), int(md.group(2)), int(md.group(1)), hh, mm)
        low = head.lower()
        kind = "dry" if "dry" in low else "bot" if "browser-use" in low else "task"
        tongs = re.findall(r"Tổng \d+ comment[^\n]*", body)
        tong = tongs[-1] if tongs else ""
        mc = re.search(r"Tổng (\d+) comment", tong)
        mf = re.search(r"(\d+) lời mời", tong)
        mcost = re.search(r"~\$([\d.]+)", tong)
        mreq = re.search(r"(\d+) request", tong)
        min_ = re.search(r"(\d+) token vào", tong)
        mout = re.search(r"(\d+) token ra", tong)
        mmod = re.search(r"\((claude-[\w.-]+)\)", tong)
        friends = int(mf.group(1)) if mf else sum(
            1 for l in lines if re.match(r"(\[dry\] )?kết bạn: .+\(\d+ bạn chung\)", l))
        errs = [l for l in lines if ERR.search(l) and not NOT_ERR.search(l)]
        runs.append({
            "at": when.strftime("%Y-%m-%d %H:%M"), "date": when.strftime("%Y-%m-%d"),
            "kind": kind, "title": head.strip(),
            "comments": int(mc.group(1)) if mc else 0,
            "friends": friends,
            "cost": float(mcost.group(1)) if mcost else 0.0,
            "requests": int(mreq.group(1)) if mreq else 0,
            "tin": int(min_.group(1)) if min_ else 0,
            "tout": int(mout.group(1)) if mout else 0,
            "model": mmod.group(1) if mmod else "",
            "errors": errs, "lines": lines[:40],
        })
    runs.sort(key=lambda r: r["at"])
    return runs


def costs(runs: list[dict], now: datetime) -> dict:
    """Tiền AI: tính cả lượt chạy thử vì vẫn gọi API thật. Lượt --test3 không ghi log nên không có ở đây."""
    ai = [r for r in runs if r["requests"] or r["cost"]]
    days = []
    for i in range(29, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        rs = [r for r in ai if r["date"] == d]
        days.append({"date": d, "runs": len(rs), "requests": sum(r["requests"] for r in rs),
                     "tin": sum(r["tin"] for r in rs), "tout": sum(r["tout"] for r in rs),
                     "cost": round(sum(r["cost"] for r in rs), 4),
                     "comments": sum(r["comments"] for r in rs)})

    def tot(n: int | None) -> dict:
        cut = (now - timedelta(days=n - 1)).strftime("%Y-%m-%d") if n else ""
        rs = [r for r in ai if r["date"] >= cut]
        c = sum(r["cost"] for r in rs)
        cm = sum(r["comments"] for r in rs)
        return {"runs": len(rs), "cost": round(c, 4), "tin": sum(r["tin"] for r in rs),
                "tout": sum(r["tout"] for r in rs), "per_comment": round(c / cm, 4) if cm else None}

    return {"days": days, "today": tot(1), "d7": tot(7), "d30": tot(30), "all": tot(None),
            "avg_run": round(sum(r["cost"] for r in ai) / len(ai), 4) if ai else None}


def state() -> dict:
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    lim = limits()
    st = _json(CHEO / "state.json", {})
    fs = _json(CHEO / "ket-ban.json", {"sent": []})
    sent = fs.get("sent", [])
    runs = parse_log()
    real = [r for r in runs if r["kind"] != "dry"]

    daily = st.get("daily") or {}
    # bot browser-use cộng vào state.daily (kể cả --test3 không ghi log); lượt task cũ thì không
    task_today = sum(r["comments"] for r in real if r["date"] == today and r["kind"] == "task")
    c_today = (daily.get("comments", 0) if daily.get("date") == today else 0) + task_today
    f_today = sum(1 for x in sent if x.get("date") == today)

    # lịch sử 14 ngày
    by = defaultdict(lambda: {"comments": 0, "friends": 0, "runs": 0, "errors": 0, "cost": 0.0})
    for r in real:
        b = by[r["date"]]
        b["comments"] += r["comments"]
        b["runs"] += 1
        b["errors"] += len(r["errors"])
        b["cost"] += r["cost"]
    for x in sent:
        if x.get("date"):
            by[x["date"]]["friends"] += 1
    by[today]["comments"] = c_today
    # theo ngày cho biểu đồ: ít nhất 1 năm, xa hơn nếu dữ liệu cũ hơn
    first = min([k for k, b in by.items() if b["runs"] or b["friends"] or b["comments"]] or [today])
    start = min(datetime.strptime(first, "%Y-%m-%d"), now - timedelta(days=365))
    daily_s = []
    for i in range((now.date() - start.date()).days, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        b = by[d]
        daily_s.append([d, b["comments"], b["friends"], b["runs"], b["errors"], round(b["cost"], 4)])
    hist = [{"date": r[0], "comments": r[1], "friends": r[2], "runs": r[3], "errors": r[4], "cost": r[5]}
            for r in daily_s[-14:]]

    lock = None
    if (CHEO / "dung-khan-cap.txt").exists():
        try:
            lock = (CHEO / "dung-khan-cap.txt").read_text(encoding="utf-8").strip()[:500] or "(trống)"
        except OSError:
            lock = "(không đọc được)"

    groups = st.get("groups", [])
    gi = st.get("next_group_index", 0)
    next_groups = []
    if groups:
        i, guard = gi % len(groups), 0
        while len(next_groups) < lim["groups_per_run"] and guard < len(groups):
            g = groups[i]
            if not g.get("paused"):
                next_groups.append(g["id"])
            i, guard = (i + 1) % len(groups), guard + 1
    try:
        phrases = [l for l in (CHEO / "cau-comment.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    except OSError:
        phrases = []
    nci = st.get("next_comment_index", 0)

    last = real[-1] if real else None
    ago_min = int((now - datetime.strptime(last["at"], "%Y-%m-%d %H:%M")).total_seconds() // 60) if last else None

    errors = []
    for r in runs:
        for e in r["errors"]:
            errors.append({"at": r["at"], "kind": r["kind"], "text": e})
    errors.reverse()

    return {
        "now": now.strftime("%H:%M %d/%m"),
        "today": today,
        "model": model(),
        "limits": lim,
        "lock": lock,
        "chrome_open": chrome_open(),
        "c_today": c_today, "f_today": f_today,
        "errors_today": sum(1 for e in errors if e["at"].startswith(today)),
        "cost_today": round(sum(r["cost"] for r in runs if r["date"] == today), 4),
        "costs": costs(runs, now),
        "hist": hist,
        "daily": daily_s,  # [ngày, comment, lời mời, lượt, lỗi, tiền]
        "first_date": first,
        "next_run": next_run(),
        "runs": list(reversed(runs[-30:])),
        "last_run": last["at"] if last else None, "ago_min": ago_min,
        "errors": errors[:40],
        "groups": [{"id": g["id"], "paused": bool(g.get("paused"))} for g in groups],
        "next_groups": next_groups,
        "phrase_next": phrases[nci % len(phrases)] if phrases else "",
        "phrase_idx": nci, "phrase_total": len(phrases),
        "friends": list(reversed(sent[-30:])),
        "posts": list(reversed(st.get("commented_posts", [])[-30:])),
        "posts_total": len(st.get("commented_posts", [])),
        "friend_window": "11:00–13:59 (tối đa 2) và 19:00–21:59 (đủ %d)" % lim["friends"],
    }
