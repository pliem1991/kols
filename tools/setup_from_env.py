"""
Add X account to twscrape DB from tools/x_account.env
Usage: python setup_from_env.py
"""
import asyncio
import os
from pathlib import Path

os.environ["TWS_TELEMETRY"] = "0"

from twscrape import API

HERE = Path(__file__).parent
ENV_PATH = HERE / "x_account.env"
DB_PATH = HERE / "twscrape_accounts.db"


def load_env(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Khong tim thay {path}")
    data = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


async def main():
    cfg = load_env(ENV_PATH)
    username = cfg.get("X_USERNAME", "")
    ct0 = cfg.get("X_CT0", "")
    auth_token = cfg.get("X_AUTH_TOKEN", "")

    missing = [k for k, v in (("X_USERNAME", username), ("X_CT0", ct0), ("X_AUTH_TOKEN", auth_token)) if not v]
    if missing:
        raise SystemExit("Chua dien: " + ", ".join(missing) + f"\nMo file: {ENV_PATH}")

    api = API(str(DB_PATH))
    await api.pool.add_account(
        username=username,
        password="",
        email="",
        email_password="",
        cookies=f"ct0={ct0}; auth_token={auth_token}",
    )
    await api.pool.login_all()
    print(f"Da add account @{username} vao {DB_PATH.name}")

    try:
        user = await api.user_by_login("elonmusk")
        print(f"Test OK! Found @{user.username} - {user.followersCount:,} followers")
    except Exception as e:
        print(f"Test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())
