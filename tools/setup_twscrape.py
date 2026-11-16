"""
twscrape setup script
Usage: python setup_twscrape.py
After setup, use kol_scanner.py to find hot posts from KOLs
"""
import asyncio
import json
import os
import sys
from pathlib import Path

os.environ["TWS_TELEMETRY"] = "0"

from twscrape import API

DB_PATH = Path(__file__).parent / "twscrape_accounts.db"

async def add_account_cookies(username: str, cookies_ct0: str, cookies_auth_token: str):
    api = API(str(DB_PATH))
    await api.pool.add_account(
        username=username,
        password="",
        email="",
        email_password="",
        cookies=f"ct0={cookies_ct0}; auth_token={cookies_auth_token}",
    )
    await api.pool.login_all()
    print(f"Account @{username} added successfully!")
    return api

async def test_account():
    api = API(str(DB_PATH))
    try:
        user = await api.user_by_login("elonmusk")
        print(f"Test OK! Found @{user.username} — {user.followersCount:,} followers")
        return True
    except Exception as e:
        print(f"Test failed: {e}")
        return False


async def list_accounts():
    """Xem đang có mấy acc phụ. Mỗi acc thêm vào là một suất hạn mức nữa —
    twscrape tự xoay sang acc còn rảnh khi acc đang dùng chạm limit."""
    import sqlite3
    con = sqlite3.connect(str(DB_PATH))
    rows = list(con.execute(
        "select username, active, last_used from accounts order by username"))
    if not rows:
        print("Chua co acc nao.")
        return
    print(f"{len(rows)} acc:")
    for name, active, last in rows:
        print(f"  @{name:<20} {'dang dung' if active else 'TAT'}"
              f"   lan cuoi: {last or '-'}")

async def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python setup_twscrape.py add <username> <ct0> <auth_token>")
        print("  python setup_twscrape.py test")
        print("  python setup_twscrape.py list")
        return

    cmd = sys.argv[1]
    if cmd == "add" and len(sys.argv) == 5:
        await add_account_cookies(sys.argv[2], sys.argv[3], sys.argv[4])
        print("\nNow test with: python setup_twscrape.py test")
    elif cmd == "test":
        await test_account()
    elif cmd == "list":
        await list_accounts()
    else:
        print("Invalid args. Use: add <username> <ct0> <auth_token>")

if __name__ == "__main__":
    asyncio.run(main())
