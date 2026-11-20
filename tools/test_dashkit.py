"""Smoke test dashkit — khung man hinh theo doi dung chung.

Chay duoc MOT MINH, khong can app/ va khong can API key: do la ca y nghia cua
no. Project Facebook se chay dung bo test nay de biet khung con lanh.
"""
import ast
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import dashkit  # noqa: E402

fail = []


def check(name, cond, extra=""):
    print(("  OK   " if cond else "  FAIL ") + name + (f"  {extra}" if extra else ""))
    if not cond:
        fail.append(name)


print("1) dashkit khong duoc biet gi ve app/")
# Day la ranh gioi quan trong nhat: dashkit ma import app/ thi no khong con
# dung chung duoc nua, va project Facebook keo theo ca X.
for f in sorted((ROOT / "dashkit").glob("*.py")):
    tree = ast.parse(f.read_text(encoding="utf-8"))
    bad = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            bad += [a.name for a in n.names if a.name.split(".")[0] == "app"]
        elif isinstance(n, ast.ImportFrom) and n.module:
            if n.module.split(".")[0] == "app":
                bad.append(n.module)
    check(f"{f.name} khong import app", not bad, ", ".join(bad))

print("\n2) cong mat khau")
env = ROOT / "posts" / ".state" / "test_dashkit.env"
env.parent.mkdir(parents=True, exist_ok=True)
env.unlink(missing_ok=True)
NOW = {"t": datetime(2026, 11, 20, 10, 0)}
g = dashkit.Gate(env_file=env, token_key="T_TOKEN", pass_key="T_PASS",
                 now=lambda: NOW["t"], cookie="tt", max_tries=3, lock_min=5)
pw = g.password()
check("tu sinh mat khau va ghi file", bool(pw) and env.exists())
check("doc lai dung mat khau cu", dashkit.Gate(
    env_file=env, token_key="T_TOKEN", pass_key="T_PASS",
    now=lambda: NOW["t"]).password() == pw)
check("mat khau khac token", pw != g.token())
check("cookie dung thi vao duoc", g.authed(f"tt={g.token()}"))
check("cookie sai thi chan", not g.authed("tt=xxx"))
check("ten cookie khac thi chan", not g.authed(f"xk={g.token()}"))
check("khong co cookie thi chan", not g.authed(None))
check("token trong URL khong duoc tinh la dang nhap",
      not g.authed(f"?tok={g.token()}"))

print("\n3) chan do mat khau")
for _ in range(3):
    g.accept("sai")
check("sai 3 lan thi khoa", g.locked() > 0)
check("chua het gio thi van khoa",
      (NOW.update(t=NOW["t"] + timedelta(minutes=4)), g.locked() > 0)[1])
NOW["t"] += timedelta(minutes=2)
check("het 5 phut thi mo khoa", g.locked() == 0)
check("mat khau dung thi qua", g.accept(pw))
check("qua roi thi so sai ve 0", g.locked() == 0)
env.unlink(missing_ok=True)

print("\n4) dung trang")
nav = [dashkit.Nav("overview", "Tong quan"),
       dashkit.Nav("bai", "Bai dang", badge=True),
       dashkit.Nav("ctl", "Dieu khien", foot=True)]
JS = ("function head(d){return {title:d.who, sub:'xem', chips:'<b>'+d.now+'</b>',"
      " badges:{bai:d.n}};}\n"
      "function v_overview(d){return '<i>tong quan</i>';}\n"
      "function v_bai(d){return '<i>bai</i>';}\n"
      "function v_ctl(d){return '<i>ctl</i>';}\n")
html = dashkit.build("TestKit", "T", nav, JS)
check("co the nav", all(f'id="nv-{n.key}"' in html for n in nav))
check("chi muc badge moi co so dem",
      'id="n-bai"' in html and 'id="n-overview"' not in html)
check("muc foot bi day xuong duoi", html.index('navsep') < html.index('nv-ctl'))
check("ten app vao title va goc trai",
      "<title>TestKit</title>" in html and "<i>T</i>TestKit" in html)
check("JS cua app nam trong trang", "function v_bai(d)" in html)
check("ham ve dung chung co san",
      all(f"function {f}(" in html for f in ("cell", "bars", "legend")))
check("co nhan mac dinh", '"overview"' in html or "'overview'" in html)
check("trang dang nhap doi ten theo app",
      "<h1>TestKit</h1>" in dashkit.login("TestKit"))
check("bao loi hien ra o trang dang nhap",
      "Sai mat khau." in dashkit.login("TestKit", "Sai mat khau."))
try:
    dashkit.build("X", "X", [], JS)
    check("nav rong phai bao loi", False)
except ValueError:
    check("nav rong phai bao loi", True)

print("\n5) chay that mot vong")
PORT = 8791
hits = {"state": 0}


def payload():
    hits["state"] += 1
    return {"who": "@ai-do", "now": "10:32", "n": 2}


env2 = ROOT / "posts" / ".state" / "test_dashkit2.env"
env2.unlink(missing_ok=True)
g2 = dashkit.Gate(env_file=env2, token_key="T2", pass_key="P2",
                  now=datetime.now, cookie="tk2")
dash = dashkit.Dash(name="TestKit", icon="T", nav=nav, app_js=JS,
                    state=payload, gate=g2, port=PORT,
                    posts={"/api/thu": lambda q: {"ok": True, "id": (q.get("id") or [""])[0]},
                           "/api/xau": lambda q: {"ok": False, "why": "khong duoc"}},
                    image_root=ROOT / "posts")
url = dashkit.serve(dash)
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))


def ask(path, data=None):
    return op.open(url + path, data=data, timeout=5)


def code(path, data=None):
    try:
        return ask(path, data).status
    except urllib.error.HTTPError as e:
        return e.code


check("chua dang nhap: trang chinh ra form", 'name="p"' in
      ask("/").read().decode("utf-8"))
check("chua dang nhap: API tra 401", code("/api/state") == 401)
check("chua dang nhap: nut bam tra 401", code("/api/thu", b"") == 401)
check("sai mat khau tra 401", code("/login", b"p=sai") == 401)
check("dung mat khau thi vao", code(
    "/login", urllib.parse.urlencode({"p": g2.password()}).encode()) == 200)
page = ask("/").read().decode("utf-8")
check("vao roi thi ra trang that", 'class="shell"' in page and "v_bai" in page)
check("/api/state goi duoc ham cua app",
      json.loads(ask("/api/state").read())["who"] == "@ai-do" and hits["state"])
check("nut bam nhan query",
      json.loads(ask("/api/thu?id=7", b"").read())["id"] == "7")
check("tra ve co 'why' thi thanh 400", code("/api/xau", b"") == 400)
check("duong khong co tra 404", code("/khong-co") == 404)
check("/img chan file ngoai image_root",
      code("/img?p=" + urllib.parse.quote(r"C:\Windows\win.ini")) == 403)
check("GET vao nut bam tra 404", code("/api/thu") == 404)
env2.unlink(missing_ok=True)

print()
if fail:
    print(f"THAT BAI {len(fail)}: " + ", ".join(fail))
    sys.exit(1)
print("TAT CA DAT")
