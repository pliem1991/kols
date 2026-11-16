"""Nạp acc phụ twscrape từ các file tools/x_account*.env vào kho.

Vì sao đọc từ FILE chứ không nhận tham số dòng lệnh: cookie dán vào lệnh thì
nằm lại trong lịch sử shell (PSReadLine lưu ra đĩa), mà cookie là chìa khóa vào
thẳng tài khoản. File *.env đã nằm trong .gitignore.

Nhiều acc phụ = nhiều suất hạn mức; twscrape tự xoay sang acc còn rảnh. Thêm
acc thứ hai: chép x_account.env thành x_account2.env rồi điền giá trị mới.

Dùng: python setup_from_env.py
"""
import asyncio
import os
from pathlib import Path

os.environ["TWS_TELEMETRY"] = "0"

from twscrape import API

HERE = Path(__file__).parent
DB_PATH = HERE / "twscrape_accounts.db"
# x_main.env là acc CHÍNH (@macropandaX, dùng cho Playwright) — không khớp mẫu
# này, và không được phép lọt vào kho đọc.
PATTERN = "x_account*.env"


def load_env(path: Path) -> dict:
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


async def main():
    files = sorted(HERE.glob(PATTERN))
    if not files:
        raise SystemExit(f"Khong thay file nao khop {PATTERN} trong {HERE}")

    import sqlite3
    api = API(str(DB_PATH))
    # twscrape chỉ cảnh báo khi acc đã có chứ không báo lỗi, nên tự xem trước:
    # in "đã nạp" cho một acc vốn đã nằm sẵn trong kho là nói dối người đọc.
    try:
        con = sqlite3.connect(str(DB_PATH))
        have = {r[0].lower() for r in con.execute("select username from accounts")}
    except sqlite3.Error:
        have = set()
    added, skipped = [], []
    for path in files:
        cfg = load_env(path)
        username = cfg.get("X_USERNAME", "")
        ct0 = cfg.get("X_CT0", "")
        auth_token = cfg.get("X_AUTH_TOKEN", "")
        missing = [k for k, v in (("X_USERNAME", username), ("X_CT0", ct0),
                                  ("X_AUTH_TOKEN", auth_token)) if not v]
        if missing:
            skipped.append(f"{path.name}: chua dien " + ", ".join(missing))
            continue
        if username.lower() in have:
            skipped.append(f"{path.name}: @{username} da co trong kho roi")
            continue
        try:
            await api.pool.add_account(
                username=username,
                password="",
                email="",
                email_password="",
                cookies=f"ct0={ct0}; auth_token={auth_token}",
            )
            added.append(f"@{username} (tu {path.name})")
        except Exception as e:
            # Acc da co trong kho thi khong phai loi — chay lai script la binh thuong.
            skipped.append(f"{path.name}: {type(e).__name__}: {e}")

    if added:
        await api.pool.login_all()
        for a in added:
            print("da nap", a)
    for s in skipped:
        print("bo qua", s)

    con = sqlite3.connect(str(DB_PATH))
    rows = list(con.execute("select username from accounts order by username"))
    print(f"\nKho hien co {len(rows)} acc: "
          + ", ".join("@" + r[0] for r in rows))

    try:
        user = await api.user_by_login("elonmusk")
        print(f"Test OK! Found @{user.username} - {user.followersCount:,} followers")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
