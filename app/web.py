"""Trang theo dõi chạy local — http://127.0.0.1:8787

Dùng http.server của thư viện chuẩn, không thêm phụ thuộc nào. Chạy trong thread
riêng, bind 127.0.0.1 nên không ai ngoài máy này vào được.

Bản tiếng Việt trên trang CHỈ để đọc. Bài đăng lên X luôn là bản tiếng Anh.

Trang chia thành các mục riêng (Tổng quan / Việc làm tay / Kết quả thật / Chờ
duyệt / Đã đăng / Điều khiển) và đổi mục ngay trong trình duyệt, không tải lại.
Trước 15/11 tất cả nằm chung một cột dài: cuộn mãi mới tới việc cần làm, mà
Điều khiển lại nằm cuối — dễ bấm nhầm "Dừng app".
"""
from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config, manual, payout, review, state, stats, targets

HOST = "127.0.0.1"
DEFAULT_PORT = 8787
HISTORY_DAYS = 14

# --- khóa cửa ----------------------------------------------------------------
# Trang này KHÔNG chỉ để xem: nó dừng được app, duyệt được bài đăng thật lên
# @macropandaX, và bấm "Tạo tiếp" là gọi Opus mấy lần (tốn tiền). Khi đưa ra
# internet qua Cloudflare tunnel (15/11) thì bất kỳ ai có link đều làm được
# ngần đó, mà hostname công khai thì bot quét ra.
#
# Token áp cho MỌI request, kể cả từ 127.0.0.1. Lý do không miễn cho localhost:
# cloudflared chạy ngay trên máy này nên request từ tunnel cũng hiện ra là
# 127.0.0.1 — miễn theo IP là mở toang. Phân biệt bằng header CF-Connecting-IP
# thì phải TIN vào header, hỏng một lần là mất quyền điều khiển tài khoản.
#
# File giữ token nằm ở tools/ chứ không phải posts/: endpoint /img phục vụ mọi
# file trong posts/, để token ở đó là tự đưa chìa khóa qua cửa sổ.
#
# Vào bằng MẬT KHẨU (thêm 15/11 theo yêu cầu). Token vẫn còn nhưng tụt xuống
# làm giá trị cookie — tức là "đã đăng nhập", không còn là cách vào nữa. Để
# token trong URL thì nó nằm lại trong lịch sử trình duyệt, trong link chia sẻ,
# trong ảnh chụp màn hình; mật khẩu gõ vào form thì không.
TOKEN_FILE = config.TOOLS / "web.env"
_SECRETS: dict[str, str] = {}


def _read_secrets() -> dict[str, str]:
    out: dict[str, str] = {}
    if TOKEN_FILE.exists():
        for line in TOKEN_FILE.read_text(encoding="utf-8").splitlines():
            k, _, v = line.partition("=")
            if k.strip() and v.strip():
                out[k.strip()] = v.strip()
    return out


def _secret(key: str, nbytes: int) -> str:
    """Đọc một bí mật trong tools/web.env, chưa có thì sinh rồi ghi lại."""
    global _SECRETS
    if not _SECRETS:
        _SECRETS = _read_secrets()
    if _SECRETS.get(key):
        return _SECRETS[key]
    import secrets
    _SECRETS[key] = secrets.token_urlsafe(nbytes)
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_FILE.write_text(
        "".join(f"{k}={v}\n" for k, v in _SECRETS.items()), encoding="utf-8")
    return _SECRETS[key]


def token() -> str:
    """Giá trị cookie cấp sau khi đăng nhập đúng."""
    return _secret("XKOLS_WEB_TOKEN", 24)


def password() -> str:
    """Mật khẩu vào trang. Đổi bằng cách sửa tools/web.env rồi khởi động lại."""
    return _secret("XKOLS_WEB_PASS", 9)


# Chặn dò mật khẩu. Hostname công khai thì bot sẽ thử, mà qua tunnel mọi request
# đều hiện ra là 127.0.0.1 nên không đếm theo IP được — đếm chung một sổ. Trang
# một người dùng, khóa cả cụm 5 phút là chấp nhận được.
MAX_TRIES = 8
LOCK_MIN = 5
_GUARD = {"fails": 0, "until": None}


def _locked() -> int:
    """Còn bị khóa bao nhiêu giây."""
    u = _GUARD["until"]
    if u is None:
        return 0
    left = (u - config.now()).total_seconds()
    if left <= 0:
        _GUARD.update(fails=0, until=None)
        return 0
    return int(left)


def _note_fail() -> None:
    from datetime import timedelta
    _GUARD["fails"] += 1
    if _GUARD["fails"] >= MAX_TRIES:
        _GUARD["until"] = config.now() + timedelta(minutes=LOCK_MIN)


LOGIN = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XKols</title><style>
*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:flex;align-items:center;
 justify-content:center;background:#0d1117;color:#e6edf3;
 font:16px/1.5 ui-sans-serif,system-ui,'Segoe UI',sans-serif}
form{width:100%;max-width:320px;padding:24px}
h1{font-size:19px;margin:0 0 4px}
p{margin:0 0 20px;color:#8b949e;font-size:14px}
input{width:100%;padding:12px 14px;font-size:16px;border-radius:8px;
 border:1px solid #30363d;background:#161b22;color:#e6edf3}
input:focus{outline:none;border-color:#4493f8}
button{width:100%;margin-top:12px;padding:12px;font-size:15px;font-weight:600;
 border:0;border-radius:8px;background:#238636;color:#fff;cursor:pointer}
.err{color:#f85149;font-size:14px;margin-top:14px}
</style></head><body>
<form method="post" action="/login">
<h1>XKols</h1>
<p>Trang điều khiển. Cần mật khẩu.</p>
<input type="password" name="p" autofocus autocomplete="current-password"
 placeholder="Mật khẩu">
<button type="submit">Vào</button>
__ERR__
</form></body></html>"""

PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XKols</title>
<style>
:root{
 --bg:#f4f6fb; --card:#fff; --line:#e8ecf4; --fg:#101828; --mut:#667085;
 --acc:#4f6cff; --acc-soft:#eef1ff; --ok:#12a150; --ok-soft:#e8f8ef;
 --no:#e5484d; --no-soft:#fdecec; --warn:#d97706; --warn-soft:#fdf3e4;
 --shadow:0 1px 2px rgba(16,24,40,.04), 0 10px 28px rgba(16,24,40,.06);
 --r:16px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
 font:15px/1.6 "Inter",ui-sans-serif,system-ui,"Segoe UI",sans-serif;
 -webkit-font-smoothing:antialiased}
a{color:var(--acc)}
.shell{display:flex;min-height:100vh}

/* ---- sidebar ---- */
.side{width:224px;flex:none;background:var(--card);border-right:1px solid var(--line);
 padding:22px 14px;display:flex;flex-direction:column;gap:4px;position:sticky;top:0;
 height:100vh}
.brand{display:flex;align-items:center;gap:10px;padding:0 8px 18px;font-weight:700;
 font-size:17px;letter-spacing:-.01em}
.brand i{width:30px;height:30px;border-radius:9px;background:var(--acc);color:#fff;
 display:grid;place-items:center;font-style:normal;font-size:15px}
.nav{display:block;padding:9px 12px;border-radius:11px;color:var(--mut);
 text-decoration:none;font-size:14.5px;font-weight:500;cursor:pointer}
.nav:hover{background:var(--bg)}
.nav.on{background:var(--acc);color:#fff}
.nav .n{float:right;font-size:12px;opacity:.8}
.navsep{margin-top:auto}
.sidefoot{border-top:1px solid var(--line);padding-top:14px;margin-top:14px;
 font-size:12.5px;color:var(--mut)}
.sidefoot b{display:block;color:var(--fg);font-size:14px}

/* ---- main ---- */
.main{flex:1;min-width:0;padding:22px 26px 56px}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;
 flex-wrap:wrap;margin-bottom:18px}
.hello{font-size:13px;color:var(--mut)}
.hello b{display:block;font-size:20px;color:var(--fg);font-weight:700;
 letter-spacing:-.02em;line-height:1.3}
.topright{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.chip{background:var(--card);border:1px solid var(--line);border-radius:99px;
 padding:6px 13px;font-size:12.5px;color:var(--mut);box-shadow:var(--shadow)}
.chip b{color:var(--fg)}
.chip.live{background:var(--no-soft);border-color:#f7c9ca;color:#a8282c}
.chip.dry{background:var(--warn-soft);border-color:#f3dcb4;color:#92610a}

/* ---- cards ---- */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
 padding:17px 19px;margin-bottom:16px;box-shadow:var(--shadow)}
.chead{display:flex;align-items:center;justify-content:space-between;gap:12px;
 margin-bottom:13px;flex-wrap:wrap}
h2{font-size:15px;margin:0;font-weight:650;letter-spacing:-.01em}
.sub{font-size:12.5px;color:var(--mut);margin:0}
.duo{display:grid;grid-template-columns:1.3fr 1fr;gap:16px;align-items:start}
@media (max-width:980px){.duo{grid-template-columns:1fr}}
.duo>.card{margin:0}

/* ---- stat tiles: một dải gọn, không phải 6 ô to ---- */
.strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:0;
 background:var(--card);border:1px solid var(--line);border-radius:var(--r);
 box-shadow:var(--shadow);margin-bottom:16px;overflow:hidden}
@media (max-width:980px){.strip{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:560px){.strip{grid-template-columns:repeat(2,minmax(0,1fr))}}
.cell{padding:13px 16px;border-right:1px solid var(--line);min-width:0}
.cell:last-child{border-right:0}
.cell .lab{font-size:11.5px;color:var(--mut);display:flex;align-items:center;gap:7px}
.cell .lab i{width:7px;height:7px;border-radius:3px;display:inline-block;flex:none}
.cell b{display:block;font-size:22px;font-weight:700;letter-spacing:-.02em;
 line-height:1.3}

/* ---- biểu đồ: div thuần, không thư viện ---- */
.bars{display:flex;align-items:flex-end;gap:6px;height:132px;margin-top:6px}
.bcol{flex:1;min-width:0;display:flex;flex-direction:column;align-items:center;
 gap:5px;height:100%}
.bstack{flex:1;display:flex;align-items:flex-end;justify-content:center;gap:3px;
 width:100%}
.bstack i{display:block;width:9px;max-width:40%;border-radius:4px 4px 0 0;
 min-height:2px}
.b1{background:var(--acc)} .b2{background:var(--warn)} .b3{background:var(--ok)}
.bcol span{font-size:10.5px;color:var(--mut);white-space:nowrap}
.bcol.now span{color:var(--fg);font-weight:600}
/* ---- biểu đồ ngang: việc làm tay ---- */
.hchart{margin:2px 0 14px}
.hrow{display:flex;align-items:center;gap:12px;padding:5px 0}
.hlab{width:92px;flex:none;font-size:13px;color:var(--mut)}
.hbar{flex:1;height:9px;background:var(--bg);border-radius:99px;overflow:hidden}
.hbar i{display:block;height:100%;border-radius:99px;min-width:0;
 transition:width .3s}
.hnum{width:62px;flex:none;text-align:right;font-size:13px;font-weight:600}
@media (max-width:560px){.hlab{width:70px}.hnum{width:54px}}
.legend{display:flex;gap:16px;font-size:12px;color:var(--mut);flex-wrap:wrap}
.legend i{width:9px;height:9px;border-radius:3px;display:inline-block;
 margin-right:6px}

/* ---- manual item ---- */
.item{border:1px solid var(--line);border-radius:13px;margin-bottom:10px;
 overflow:hidden;background:var(--card)}
.ihead{display:flex;align-items:center;gap:11px;padding:12px 15px;cursor:pointer;
 user-select:none}
.ihead:hover{background:var(--bg)}
.ihead .who{font-weight:600;font-size:14.5px}
.ihead .meta{font-size:12.5px;color:var(--mut)}
.ihead .peek{flex:1;min-width:0;font-size:13px;color:var(--mut);
 white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.caret{color:var(--mut);font-size:12px;transition:transform .15s}
.item.open .caret{transform:rotate(90deg)}
.ibody{display:none;padding:2px 15px 15px;border-top:1px solid var(--line)}
.item.open .ibody{display:block}
.their{color:var(--mut);font-size:13.5px;border-left:3px solid var(--line);
 padding:3px 0 3px 12px;margin:13px 0;font-style:italic}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:0 0 13px}
@media (max-width:860px){.cols{grid-template-columns:1fr}}
.col{min-width:0}
.tag{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 margin-bottom:6px;color:var(--mut);font-weight:600}
.col.vi{border-left:2px solid var(--line);padding-left:14px;color:#475467}
pre{white-space:pre-wrap;word-wrap:break-word;margin:0;font:inherit;font-size:14.5px}
.dots{display:flex;gap:5px;margin-left:auto}
.dot{width:7px;height:7px;border-radius:50%;background:var(--line)}
.dot.on{background:var(--ok)}

/* ---- buttons ---- */
button,a.btn{font:inherit;font-size:13.5px;font-weight:550;border:1px solid var(--line);
 background:var(--card);color:var(--fg);border-radius:10px;padding:8px 14px;
 cursor:pointer;margin:0 7px 7px 0;text-decoration:none;display:inline-block}
button:hover,a.btn:hover{background:var(--bg)}
button:disabled{opacity:.55;cursor:default}
.yes{background:var(--ok);border-color:var(--ok);color:#fff}
.yes:hover{background:#0e8c45}
.no{background:var(--card);border-color:#f3c9ca;color:var(--no)}
.no:hover{background:var(--no-soft)}
.pri{background:var(--acc);border-color:var(--acc);color:#fff}
.pri:hover{background:#3f58e0}
.ticked{background:var(--ok-soft);border-color:#b7e6cb;color:#0b7a3e}
.danger{border:1px solid #f3c9ca;background:var(--no-soft);border-radius:13px;
 padding:14px 16px;margin-top:4px}

/* ---- rows ---- */
.row{display:flex;justify-content:space-between;gap:12px;padding:9px 0;
 border-bottom:1px solid var(--line);font-size:13.5px}
.row:last-child{border:0}
.row .l{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mut{color:var(--mut)}
.bad{color:#f85149;font-weight:600}
.pill{font-size:11px;padding:3px 9px;border-radius:99px;background:var(--acc-soft);
 color:var(--acc);font-weight:600;margin-right:8px}
.pill.g{background:var(--ok-soft);color:var(--ok)}
.empty{color:var(--mut);font-size:13.5px;padding:6px 0}
.pay{display:grid;grid-template-columns:1fr 1fr;gap:20px}
@media (max-width:700px){.pay{grid-template-columns:1fr;gap:14px}}
.big{font-size:25px;font-weight:700;letter-spacing:-.02em;line-height:1.3;
 margin:1px 0 8px}
.big .mut{font-size:15px;font-weight:600}
.bar{height:7px;background:var(--bg);border-radius:99px;overflow:hidden;
 margin:0 0 7px}
.bar i{display:block;height:100%;background:var(--acc);border-radius:99px;
 min-width:2px}
.note{color:var(--warn);font-size:13px}
img.shot{max-width:100%;border:1px solid var(--line);border-radius:11px;margin:0 0 12px}
@media (max-width:820px){
 .shell{flex-direction:column}
 .side{width:auto;height:auto;position:static;flex-direction:row;overflow-x:auto;
  align-items:center;padding:12px;gap:6px}
 .brand{padding:0 12px 0 4px}
 .navsep{margin:0}
 .sidefoot{display:none}
 .main{padding:18px 16px 48px}
}
</style></head><body>
<div class="shell">
 <aside class="side">
  <div class="brand"><i>X</i>XKols</div>
  <a class="nav" id="nv-overview" onclick="go('overview')">Tổng quan</a>
  <a class="nav" id="nv-manual" onclick="go('manual')">Việc làm tay<span class="n" id="n-manual"></span></a>
  <a class="nav" id="nv-stats" onclick="go('stats')">Kết quả thật</a>
  <a class="nav" id="nv-targets" onclick="go('targets')">Đối tượng reply</a>
  <a class="nav" id="nv-pending" onclick="go('pending')">Chờ duyệt<span class="n" id="n-pending"></span></a>
  <a class="nav" id="nv-posted" onclick="go('posted')">Đã đăng<span class="n" id="n-posted"></span></a>
  <div class="navsep"></div>
  <a class="nav" id="nv-ctl" onclick="go('ctl')">Điều khiển</a>
  <div class="sidefoot"><b id="sf-handle">—</b><span id="sf-mode"></span></div>
 </aside>
 <main class="main">
  <div class="top">
   <div class="hello"><span id="crumb">Tổng quan</span><b id="hi">đang tải…</b></div>
   <div class="topright" id="chips"></div>
  </div>
  <div id="app"></div>
 </main>
</div>
<script>
let D = null;
let VIEW = location.hash.slice(1) || 'overview';
const OPEN = new Set();      // mục nào đang mở — giữ qua mỗi lần tự nạp lại
const DRAFTS = {};
const esc = s => (s||"").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
const NAMES = {overview:'Tổng quan', manual:'Việc làm tay', stats:'Kết quả thật',
               targets:'Đối tượng reply', pending:'Chờ duyệt',
               posted:'Đã đăng', ctl:'Điều khiển'};

function go(v){
  VIEW = v; location.hash = v;
  render();
  window.scrollTo(0, 0);
}
function toggle_item(id){
  if(OPEN.has(id)) OPEN.delete(id); else OPEN.add(id);
  const el = document.getElementById('it_'+id);
  if(el) el.classList.toggle('open');
}
async function act(id, d){
  await fetch('/api/decide?id='+id+'&d='+d, {method:'POST'}); load();
}
async function refill(){
  await fetch('/api/manual/refill', {method:'POST'}); load();
}
async function mact(id, a){
  await fetch('/api/manual?id='+id+'&act='+a, {method:'POST'}); load();
}
async function toggle(){
  await fetch('/api/review?on='+(D && D.review?0:1), {method:'POST'}); load();
}
async function stop(){
  await fetch('/api/stop', {method:'POST'});
  const el = document.getElementById('ctl');
  if(el) el.textContent = 'Đã đặt cờ dừng — app thoát ở vòng kế tiếp.';
}
function copyTo(id){
  navigator.clipboard.writeText(DRAFTS[id]||'').then(()=>{
    const b = document.getElementById('cp_'+id);
    if(b){ b.textContent='đã chép'; setTimeout(()=>b.textContent='Chép draft',1800); }
  });
}
function cell(color, n, lab){
  return '<div class="cell"><div class="lab"><i style="background:'+color+'"></i>'
    + lab+'</div><b>'+n+'</b></div>';
}

/* ---------- biểu đồ ---------- */
function bars(rows, pick, cls, fmt){
  const vals = rows.map(pick);
  const max = Math.max(1, ...vals.map(v=>Math.max(...v)));
  return '<div class="bars">' + rows.map((r,i)=>{
    const v = vals[i];
    const last = i === rows.length-1;
    return '<div class="bcol'+(last?' now':'')+'" title="'+r.date+' — '+fmt(r)+'">'
      + '<div class="bstack">'
      + v.map((x,j)=>'<i class="'+cls[j]+'" style="height:'
          + (x/max*100).toFixed(1)+'%"></i>').join('')
      + '</div><span>'+r.date.slice(8)+'</span></div>';
  }).join('') + '</div>';
}
function legend(items){
  return '<div class="legend">' + items.map(([c,t])=>
    '<span><i style="background:'+c+'"></i>'+t+'</span>').join('') + '</div>';
}

/* ---------- các mục ---------- */
function v_overview(d){
  const his = d.history || [];
  const bai = r => r.posts + r.threads + r.quotes;
  const sum = (f) => his.reduce((a,r)=>a+f(r), 0);
  const seen = his.filter(r=>bai(r)||r.replies).length || 1;

  let h = '<div class="strip">'
    + cell('var(--acc)', d.posts, 'bài gốc hôm nay')
    + cell('var(--ok)', d.thread?1:0, 'thread')
    + cell('var(--acc)', d.quotes, 'quote')
    + cell('var(--warn)', d.replies, 'reply tự động')
    + cell('var(--ok)', d.reposts, 'RT lại')
    + cell('var(--no)', d.images, 'bài có ảnh')
    + '</div>';

  const py = d.payout || {};
  h += '<div class="duo">';
  if(py.followers !== undefined){
    const w = py.week;
    h += '<div class="card"><div class="chead"><div>'
      + '<h2>Đường tới payout</h2>'
      + '<p class="sub">Hai con số X dùng để xét — không phải follower tổng, '
      + 'không phải view.</p></div>'
      + '<span class="chip">đo <b>'
      + esc(String(py.at).slice(5,16).replace("T"," "))+'</b></span></div>'
      + '<div class="pay">'
      + '<div><div class="tag">verified follower</div>'
      + '<div class="big">'+py.followers+'<span class="mut"> / '+py.need_followers+'</span></div>'
      + '<div class="bar"><i style="width:'+py.pct+'%"></i></div>'
      + '<div class="sub">'+(w ? (w.gain>=0?'+':'')+w.gain+' trong '+w.days+' ngày'
          + (py.eta_days ? ' · còn ~'+py.eta_days+' ngày'
             : ' · chưa tăng nên chưa ước lượng được')
          : 'cần thêm một lần đo nữa mới thấy xu hướng')+'</div></div>'
      + '<div><div class="tag">verified impression / 90 ngày</div>'
      + '<div class="big">'+Number(py.impressions).toLocaleString()
      + '<span class="mut"> / '+Number(py.need_impressions).toLocaleString()+'</span></div>'
      + '<div class="bar"><i style="width:'
      + Math.min(100, py.impressions/py.need_impressions*100).toFixed(3)+'%"></i></div>'
      + '<div class="sub">reply KHÔNG được tính vào con số này</div></div>'
      + '</div></div>';
  } else {
    h += '<div class="card"><div class="chead"><h2>Đường tới payout</h2></div>'
      + '<div class="empty">Chưa đọc được trang eligibility — cần chạy chế độ '
      + 'đăng thật để app mở trang đó bằng cookie.</div></div>';
  }

  // Ngoài cửa sổ thì giờ đã hẹn không có ý nghĩa gì — app ngủ tới khi cửa sổ
  // mở. Hiện "10:22" lúc 10:27 làm người đọc tưởng app chết.
  const nw = d.next_window || {};
  const sleeping = !d.window;
  // Vòng lặp còn thở không. "Ngủ" bình thường dài nhất khoảng 15 phút; lâu hơn
  // thế là nó đang nghỉ sau lỗi hoặc đã kẹt — hai chuyện người xem cần biết,
  // mà trước đây trang không nói gì (app chết lúc 02:00 đêm 16/11, trang vẫn
  // hiện y như cũ).
  function beatRow(b){
    if(!b || b.ago === undefined || b.ago < 0) return '';
    const late = b.ago > 1200;
    return '<div class="row"><span class="l mut">Vòng gần nhất</span>'
      + '<span class="'+(late?'bad':'mut')+'">'+esc(b.at||'?')
      + (b.what ? ' · '+esc(b.what) : '')
      + (late ? ' · '+Math.round(b.ago/60)+' phút trước — bất thường' : '')
      + '</span></div>';
  }
  h += '<div class="card"><div class="chead"><div><h2>Nhịp hôm nay</h2>'
    + '<p class="sub">'+(d.window ? 'đang trong cửa sổ '+esc(d.window)
        : 'ngoài cửa sổ — app đang ngủ, không đăng và không reply')+'</p></div>'
    + '<span class="chip">kế <b>'+esc(d.pillar_next)+'</b></span></div>'
    + (sleeping
      ? '<div class="row"><span class="l">Cửa sổ kế</span><b>'+esc(nw.at||'?')
        + ' <span class="mut">'+esc(nw.name||'')+'</span></b></div>'
        + '<div class="row"><span class="l mut">Mở tới</span><span class="mut">'
        + esc(nw.ends||'')+' · '+(nw.posts||0)+' bài'
        + (nw.thread?' + thread':'')+'</span></div>'
      : '<div class="row"><span class="l">Bài kế</span><b>'+d.next_post+'</b></div>'
        + '<div class="row"><span class="l">Reply kế</span><b>'+d.next_reply+'</b></div>')
    + '<div class="row"><span class="l mut">Chủ đề đã dùng</span><span class="mut">'
    + (d.pillars_used.map(esc).join(', ')||'chưa có')+'</span></div>'
    + '<div class="row"><span class="l mut">Hạn mức ngày</span><span class="mut">'
    + d.limits.replies+' reply · '+d.limits.quotes+' quote · '+d.limits.images
    + ' ảnh</span></div>'
    + beatRow(d.beat||{})+'</div>';
  h += '</div>';

  if(his.length){
    h += '<div class="card"><div class="chead"><div>'
      + '<h2>'+his.length+' ngày qua</h2>'
      + '<p class="sub">Tổng '+sum(bai)+' bài · '+sum(r=>r.replies)+' reply · '
      + sum(r=>r.reposts)+' RT lại. Trung bình '+(sum(bai)/seen).toFixed(1)
      + ' bài/ngày trên '+seen+' ngày có chạy.</p></div>'
      + legend([['var(--acc)','bài gốc + thread + quote'],['var(--warn)','reply']])
      + '</div>'
      + bars(his, r=>[bai(r), r.replies], ['b1','b2'],
             r=>bai(r)+' bài · '+r.replies+' reply');

    const vmax = Math.max(...his.map(r=>r.views||0));
    if(vmax > 0){
      h += '<div style="margin-top:18px"><div class="chead" style="margin-bottom:4px">'
        + '<span class="tag" style="margin:0">view mỗi ngày (bài gốc, đo bằng acc phụ)</span>'
        + legend([['var(--ok)','tổng view bài đăng ngày đó']])+'</div>'
        + bars(his, r=>[r.views||0], ['b3'],
               r=>(r.views||0)+' view · '+(r.measured||0)+' bài đo được')
        + '</div>';
    }
    h += '<div style="margin-top:16px"><span class="tag">7 ngày gần nhất</span>'
      + his.slice(-7).reverse().map(r=>'<div class="row"><span class="l">'
        + r.date+'</span><span class="mut">'+bai(r)+' bài · '+r.replies
        + ' reply · '+r.reposts+' RT · '+r.images+' ảnh'
        + (r.views ? ' · <b>'+r.views+'</b> view' : '')+'</span></div>').join('')
      + '</div></div>';
  }

  if(d.notes.length){
    h += '<div class="card"><div class="chead"><h2>Ghi chú và lỗi hôm nay</h2></div>'
      + d.notes.map(n=>'<div class="row"><span class="note">'+esc(n)+'</span></div>').join('')
      + '</div>';
  }
  return h;
}

const ACT_VN = {reply:'Đã reply', like:'Đã like', follow:'Đã follow',
                bookmark:'Đã bookmark'};
function manualCard(p){
  DRAFTS[p.id] = p.draft;
  const done = p.done || [];
  const chk = ['reply','like','follow','bookmark'].map(a=>
    '<button class="'+(done.indexOf(a)>=0?'ticked':'')+'" onclick="mact(\\''+p.id
      +'\\',\\''+a+'\\')">'+(done.indexOf(a)>=0?'✓ ':'')+ACT_VN[a]+'</button>').join('');
  const dots = ['reply','like','follow','bookmark'].map(a=>
    '<span class="dot'+(done.indexOf(a)>=0?' on':'')+'"></span>').join('');
  return '<div class="item'+(OPEN.has(p.id)?' open':'')+'" id="it_'+p.id+'">'
    + '<div class="ihead" onclick="toggle_item(\\''+p.id+'\\')">'
    + '<span class="caret">▶</span>'
    + '<span class="who">@'+esc(p.author)+'</span>'
    + '<span class="meta">'+Number(p.followers).toLocaleString()+' · '
    + Math.round(p.age_min)+'p · '+p.replies+' rep</span>'
    + '<span class="peek">'+esc(p.their_text)+'</span>'
    + '<span class="dots">'+dots+'</span></div>'
    + '<div class="ibody">'
    + '<div class="their">“'+esc(p.their_text)+'”</div>'
    + '<div class="cols"><div class="col"><span class="tag">tiếng Anh — bạn tự gửi</span>'
    + '<pre>'+esc(p.draft)+'</pre></div>'
    + '<div class="col vi"><span class="tag">tiếng Việt</span><pre>'
    + esc(p.draft_vi || '(chưa dịch được)')+'</pre></div></div>'
    + '<button class="pri" id="cp_'+p.id+'" onclick="copyTo(\\''+p.id+'\\')">Chép draft</button>'
    + '<a class="btn" href="'+esc(p.url)+'" target="_blank">Mở bài trên X</a>'
    + '<div style="margin-top:6px">'+chk+'</div>'
    + '<div style="margin-top:6px">'
    + '<button class="yes" onclick="mact(\\''+p.id+'\\',\\'close\\')">Xong, ẩn mục này</button>'
    + '<button class="no" onclick="mact(\\''+p.id+'\\',\\'close\\')">Bỏ qua</button>'
    + '</div></div></div>';
}

function v_manual(d){
  const ms = d.manual_sum || {acts:{}, closed:0, total:0, target:10};
  const rf = d.refill || {};
  const tot = Math.max(ms.total||0, 1);
  const line = (a, color) => {
    const n = (ms.acts||{})[a] || 0;
    return '<div class="hrow"><span class="hlab">'+ACT_VN[a].replace('Đã ','')
      + '</span><div class="hbar"><i style="width:'+(n/tot*100).toFixed(1)
      + '%;background:'+color+'"></i></div>'
      + '<span class="hnum">'+n+'<span class="mut"> / '+(ms.total||0)+'</span></span></div>';
  };
  let h = '<div class="card"><div class="chead"><div>'
    + '<h2>Việc làm tay ('+d.manual.length+')</h2>'
    + '<p class="sub">App soạn sẵn, bạn tự bấm trên x.com. Hôm nay app soạn '
    + (ms.total||0)+' mục, bạn đã đóng '+ms.closed+'.</p></div>'
    + '<div><button class="pri" onclick="refill()"'+(rf.busy?' disabled':'')+'>'
    + (rf.busy?'Đang soạn…':'Tạo tiếp')+'</button>'
    + (rf.note?'<span class="sub">'+esc(rf.note)+'</span>':'')+'</div></div>'
    + '<div class="hchart">'
    + line('reply','var(--acc)') + line('like','var(--ok)')
    + line('follow','var(--warn)') + line('bookmark','var(--no)')
    + '<div class="sub" style="margin-top:4px">Mục tiêu '+(ms.target||10)
    + ' mục/ngày — hôm nay app soạn được '+(ms.total||0)+'.</div></div>';
  h += d.manual.length ? d.manual.map(manualCard).join('')
     : '<div class="empty">Chưa có mục nào — bấm "Tạo tiếp", hoặc đợi app tự nạp.</div>';
  return h + '</div>';
}

function v_stats(d){
  const sd = d.stats || {rows:[], by_pillar:{}, by_image:{}};
  if(!sd.rows.length){
    return '<div class="card"><div class="chead"><h2>Kết quả thật</h2></div>'
      + '<div class="empty">Chưa đo được bài nào. App đọc lại view bằng acc phụ, '
      + '3 giờ một lần.</div></div>';
  }
  const avg = sd.rows.reduce((a,r)=>a+r.views,0)/sd.rows.length;
  const grp = (obj, title) => {
    const ks = Object.keys(obj);
    if(!ks.length) return '';
    return '<div style="margin-top:14px"><span class="tag">'+title+'</span>'
      + ks.map(k=>'<div class="row"><span class="l">'+esc(k)
        +' <span class="mut">('+obj[k].n+' bài)</span></span>'
        +'<span><b>'+obj[k].views+'</b> view/bài <span class="mut">· '
        +obj[k].likes+' like · cao nhất '+obj[k].best+'</span></span></div>').join('')
      + '</div>';
  };
  return '<div class="card"><div class="chead"><div>'
    + '<h2>Kết quả thật</h2><p class="sub">'+sd.rows.length
    + ' bài gần nhất · trung bình '+avg.toFixed(0)+' view/bài. '
    + 'Đây là TỔNG view, không phải impression X dùng để trả tiền — '
    + 'con số thật luôn thấp hơn.</p></div></div>'
    + grp(sd.by_pillar, 'theo chủ đề (chỉ tính bài đã đủ 6 giờ)')
    + grp(sd.by_image, 'có ảnh hay không')
    + '<div style="margin-top:14px"><span class="tag">từng bài</span>'
    + sd.rows.slice(0,15).map(r=>'<div class="row"><span class="l">'
      + '<span class="pill">'+esc(r.pillar)+'</span>'+esc(r.text.slice(0,58))
      + '</span><span class="mut">'+r.views+' view · '+r.likes+' like · '
      + r.age_h+'h</span></div>').join('')
    + '</div></div>';
}

function v_targets(d){
  const t = d.targets || {top:[], dead:[]};
  const SRC = {mention:'đã mention mình', lam_tay:'bạn bấm tay', tay:'viết tay'};
  let h = '<div class="card"><div class="chead"><div>'
    + '<h2>Đối tượng reply ('+(t.total||0)+' handle)</h2>'
    + '<p class="sub">Danh sách viết tay cộng danh sách app tự thêm. App chỉ '
    + 'thêm người đã mention mình, hoặc người bạn đã bấm reply/follow trong '
    + 'hàng đợi làm tay — không bao giờ thêm từ tìm kiếm theo từ khoá, vì X '
    + 'cấm reply tự động kiểu đó.</p></div></div>'
    + '<div class="row"><span class="l">App tự thêm</span><b>'+(t.auto||0)
    + '<span class="mut"> / '+(t.cap_auto||0)+'</span></b></div>'
    + '<div class="row"><span class="l">Thêm hôm nay</span><b>'
    + (t.added_today||0)+'<span class="mut"> / '+(t.cap_day||0)+'</span></b></div>'
    + '</div>';

  if((t.top||[]).length){
    h += '<div class="card"><div class="chead"><div><h2>Ai đang ra bài</h2>'
      + '<p class="sub">Đếm từ các vòng quét: thấy bao nhiêu bài, bao nhiêu vòng '
      + 'ra được ứng viên đạt cổng.</p></div></div>'
      + t.top.map(r=>'<div class="row"><span class="l">@'+esc(r.handle)
        + ' <span class="mut">'+esc(SRC[r.source]||r.source)+'</span></span>'
        + '<span class="mut"><b>'+r.passed+'</b> vòng ra bài · '+r.seen
        + ' bài thấy · '+r.scans+' vòng quét</span></div>').join('')
      + '</div>';
  }
  if((t.dead||[]).length){
    h += '<div class="card"><div class="chead"><div><h2>Chưa ra bài lần nào</h2>'
      + '<p class="sub">Quét nhiều vòng mà chưa có bài nào qua cổng. App chỉ tự '
      + 'gỡ những handle chính nó thêm; handle viết tay thì bạn tự quyết.</p>'
      + '</div></div>'
      + '<div class="sub">'+t.dead.map(x=>'@'+esc(x)).join(' · ')+'</div></div>';
  }
  return h;
}

function draft(p){
  const en = p.parts && p.parts.length
     ? p.parts.map((t,i)=>'['+(i+1)+'] '+esc(t)).join('\\n\\n') : esc(p.text);
  const viTxt = p.parts_vi && p.parts_vi.length
     ? p.parts_vi.map((t,i)=>'['+(i+1)+'] '+esc(t)).join('\\n\\n') : esc(p.text_vi);
  const img = p.image ? '<img class="shot" src="/img?p='+encodeURIComponent(p.image)+'">' : '';
  const tgt = p.target_url
     ? '<div class="sub" style="margin-bottom:8px">dưới bài của @'+esc(p.target_author)
       +' · <a href="'+esc(p.target_url)+'" target="_blank">mở bài gốc</a></div>' : '';
  return '<div class="item open" style="padding:15px">'
    + '<div class="sub" style="margin-bottom:9px"><span class="pill">'+esc(p.kind)
    + '</span>'+esc((p.created_at||'').slice(11,16))+' · '+(p.text||'').length
    + ' ký tự'+(p.image?' · có ảnh':'')+'</div>'+tgt
    + '<div class="cols"><div class="col"><span class="tag">tiếng Anh — bản sẽ đăng</span>'
    + '<pre>'+en+'</pre></div><div class="col vi"><span class="tag">tiếng Việt</span>'
    + '<pre>'+(viTxt||'(chưa dịch được)')+'</pre></div></div>'+img
    + '<button class="yes" onclick="act(\\''+p.id+'\\',\\'approved\\')">Duyệt &amp; đăng</button>'
    + '<button class="no" onclick="act(\\''+p.id+'\\',\\'rejected\\')">Bỏ bài này</button></div>';
}

function v_pending(d){
  let h = '<div class="card"><div class="chead"><div>'
    + '<h2>Chờ duyệt ('+d.pending.length+')</h2></div></div>';
  h += d.pending.length ? d.pending.map(draft).join('')
     : '<div class="empty">'+(d.review?'Chưa có draft nào chờ.'
        :'Đang chạy tự động, app không hỏi gì cả.')+'</div>';
  h += '</div>';
  if(d.recent.length){
    const vn = {approved:'đã duyệt', rejected:'đã bỏ', expired:'quá hạn'};
    h += '<div class="card"><div class="chead"><h2>Vừa xử lý</h2></div>'
      + d.recent.map(p=>'<div class="row"><span class="l">'+esc(p.kind)+' · '
        + esc((p.text||'').slice(0,70))+'</span><span class="mut">'
        + esc(vn[p.decision]||p.decision)+'</span></div>').join('')+'</div>';
  }
  return h;
}

function v_posted(d){
  let h = '<div class="card"><div class="chead">'
    + '<h2>Đã đăng hôm nay ('+d.posted.length+')</h2></div>';
  h += d.posted.length ? d.posted.map(p=>'<div class="row"><span class="l">'
      + '<span class="pill g">'+esc(p.kind)+'</span>'+esc((p.text||'').slice(0,72))
      + '</span>'+(p.url && p.url.startsWith('http')
        ? '<a href="'+esc(p.url)+'" target="_blank">xem trên X</a>'
        : '<span class="mut">'+esc(p.url==='DRY'?'chạy thử':(p.url||''))+'</span>')
      + '</div>').join('')
    : '<div class="empty">Chưa đăng gì.</div>';
  h += '</div>';
  const his = (d.history||[]).slice(0,-1).reverse();
  if(his.length){
    const bai = r => r.posts + r.threads + r.quotes;
    h += '<div class="card"><div class="chead"><div><h2>Những ngày trước</h2>'
      + '<p class="sub">Đếm từ state theo ngày. Link từng bài chỉ có của hôm nay '
      + 'ở trên, ngày cũ xem trực tiếp trên X.</p></div></div>'
      + his.map(r=>'<div class="row"><span class="l">'+r.date+'</span>'
        + '<span class="mut">'+bai(r)+' bài · '+r.replies+' reply · '
        + r.reposts+' RT · '+r.images+' ảnh</span></div>').join('')+'</div>';
  }
  return h;
}

function v_ctl(d){
  return '<div class="card"><div class="chead"><div><h2>Chế độ chạy</h2>'
    + '<p class="sub">Tự động thì app đăng luôn. Duyệt tay thì mỗi bài chờ bạn '
    + 'bấm ở mục Chờ duyệt.</p></div></div>'
    + '<button class="'+(d.review?'ticked':'')+'" onclick="toggle()">'
    + (d.review?'Đang: duyệt tay — bấm để chuyển tự động'
       :'Đang: tự động — bấm để bật duyệt tay')+'</button>'
    + '<div class="sub" style="margin-top:6px" id="ctl">'
    + (d.review?'Chuyển sang tự động thì draft đang chờ sẽ được cho qua.'
       :'Bật duyệt tay thì app hỏi bạn trước mỗi lần đăng.')+'</div></div>'

    + '<div class="card"><div class="chead"><h2>Cấu hình đang dùng</h2></div>'
    + '<div class="row"><span class="l">Account</span><b>@'+esc(d.handle)+'</b></div>'
    + '<div class="row"><span class="l">Chế độ</span><b>'+esc(d.mode)+'</b></div>'
    + '<div class="row"><span class="l">Model bài + reply</span><span class="mut">'
    + esc(d.models.post)+'</span></div>'
    + '<div class="row"><span class="l">Model dịch tiếng Việt</span><span class="mut">'
    + esc(d.models.vi)+'</span></div>'
    + '<div class="row"><span class="l">Hạn mức ngày</span><span class="mut">'
    + d.limits.replies+' reply · '+d.limits.quotes+' quote · '+d.limits.images
    + ' bài có ảnh</span></div>'
    + '<div class="row"><span class="l">Cửa sổ tìm bài để reply</span><span class="mut">'
    + d.limits.reply_window+' phút</span></div>'
    + '<div class="row"><span class="l">Chủ đề luân phiên</span><span class="mut">'
    + esc((d.pillars||[]).join(' · '))+'</span></div></div>'

    + '<div class="card"><div class="chead"><div><h2>Dừng app</h2>'
    + '<p class="sub">Đặt cờ STOP, app thoát ở vòng kế tiếp (không cắt giữa lúc '
    + 'đang đăng). Muốn chạy lại thì khởi động từ terminal.</p></div></div>'
    + '<div class="danger"><button class="no" onclick="stop()">Dừng app</button>'
    + '<div class="sub">Việc làm tay và state theo ngày vẫn còn nguyên.</div>'
    + '</div></div>';
}

const VIEWS = {overview:v_overview, manual:v_manual, stats:v_stats,
               targets:v_targets, pending:v_pending, posted:v_posted,
               ctl:v_ctl};

function render(){
  if(!D) return;
  document.querySelectorAll('.nav').forEach(n=>n.classList.remove('on'));
  const nv = document.getElementById('nv-'+VIEW);
  if(nv) nv.classList.add('on');
  document.getElementById('crumb').textContent = NAMES[VIEW] || '';
  document.getElementById('app').innerHTML = (VIEWS[VIEW]||v_overview)(D);
}

async function load(){
  let d;
  try { d = await (await fetch('/api/state')).json(); }
  catch(e){ document.getElementById('hi').textContent = 'Mất kết nối với app.'; return; }
  D = d;

  document.getElementById('hi').textContent = '@' + d.handle;
  document.getElementById('sf-handle').textContent = '@' + d.handle;
  document.getElementById('sf-mode').textContent = d.mode;
  document.getElementById('chips').innerHTML =
      '<span class="chip '+(d.mode.indexOf('THẬT')>=0?'live':'dry')+'">'+esc(d.mode)+'</span>'
    + '<span class="chip"><b>'+d.now+'</b> ICT · '
    + (d.window ? 'cửa sổ '+esc(d.window) : 'ngoài cửa sổ')+'</span>';
  document.getElementById('n-manual').textContent = d.manual.length || '';
  document.getElementById('n-pending').textContent = d.pending.length || '';
  document.getElementById('n-posted').textContent = d.posted.length || '';
  render();
}
window.addEventListener('hashchange', ()=>{
  const v = location.hash.slice(1);
  if(VIEWS[v] && v !== VIEW){ VIEW = v; render(); }
});
load(); setInterval(load, 4000);
</script></body></html>"""


class Server(ThreadingHTTPServer):
    """HTTPServer mặc định bật SO_REUSEADDR. Trên Windows cờ đó cho hai tiến
    trình bind CÙNG một cổng, không báo lỗi — chạy hai bản app là request đi lung
    tung giữa hai bên (gặp ngày 14/11). Tắt đi để bản thứ hai chết dứt khoát."""
    allow_reuse_address = False


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):          # im lặng, đừng chen vào log app
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        # Không cache: sửa trang xong khởi động lại là thấy ngay, khỏi phải
        # tự nạp lại trình duyệt (gặp ngày 14/11, tưởng code không ăn).
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, data: dict, code: int = 200) -> None:
        self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _serve_image(self, raw: str) -> None:
        """Chỉ cho xem ảnh nằm trong posts/ — đừng mở cả ổ đĩa ra."""
        try:
            p = Path(unquote(raw)).resolve()
            p.relative_to(config.POSTS.resolve())
        except (ValueError, OSError):
            return self._send(403, b"ngoai thu muc posts/", "text/plain")
        if not p.is_file():
            return self._send(404, b"khong thay anh", "text/plain")
        ctype = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
        self._send(200, p.read_bytes(), ctype)

    def _authed(self) -> bool:
        """Đã đăng nhập chưa — chỉ xét cookie, không nhận token trong URL."""
        import hmac
        for part in (self.headers.get("Cookie") or "").split(";"):
            k, _, v = part.strip().partition("=")
            if k == "xk":
                return hmac.compare_digest(v, token())
        return False

    def _login_page(self, err: str = "", code: int = 200) -> None:
        html = LOGIN.replace("__ERR__",
                             f'<div class="err">{err}</div>' if err else "")
        self._send(code, html.encode("utf-8"), "text/html; charset=utf-8")

    def _deny(self) -> None:
        """Trang thì đưa form đăng nhập, API thì 401 cho JS biết đường."""
        if urlparse(self.path).path in ("/", "/login"):
            return self._login_page()
        self._send(401, b"can dang nhap", "text/plain; charset=utf-8")

    def _do_login(self) -> None:
        import hmac
        left = _locked()
        if left:
            return self._login_page(
                f"Sai nhiều lần — thử lại sau {left // 60 + 1} phút.", 429)
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(min(n, 4096)).decode("utf-8", "replace")
        got = (parse_qs(body).get("p") or [""])[0]
        if not (got and hmac.compare_digest(got, password())):
            _note_fail()
            return self._login_page("Sai mật khẩu.", 401)
        _GUARD.update(fails=0, until=None)
        self.send_response(303)
        self.send_header("Location", "/")
        self.send_header(
            "Set-Cookie",
            f"xk={token()}; Path=/; HttpOnly; SameSite=Lax; Max-Age=31536000")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):                      # noqa: N802
        u = urlparse(self.path)
        if not self._authed():
            return self._deny()
        if u.path in ("/", "/login"):
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif u.path == "/api/state":
            self._json(_state_payload())
        elif u.path == "/img":
            self._serve_image((parse_qs(u.query).get("p") or [""])[0])
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):                     # noqa: N802
        u = urlparse(self.path)
        if u.path == "/login":
            return self._do_login()
        if not self._authed():
            return self._deny()
        q = parse_qs(u.query)
        if u.path == "/api/decide":
            pid = (q.get("id") or [""])[0]
            d = (q.get("d") or [""])[0]
            if d not in ("approved", "rejected"):
                return self._json({"ok": False, "why": "quyết định không hợp lệ"}, 400)
            self._json({"ok": review.decide(pid, d)})
        elif u.path == "/api/review":
            on = (q.get("on") or ["0"])[0] == "1"
            review.set_enabled(on)
            self._json({"ok": True, "review": on})
        elif u.path == "/api/manual/refill":
            self._json(_kick_refill())
        elif u.path == "/api/manual":
            pid = (q.get("id") or [""])[0]
            act = (q.get("act") or [""])[0]
            self._json({"ok": manual.mark(pid, act)})
        elif u.path == "/api/stop":
            config.STOP_FILE.write_text("dung tu trang web\n", encoding="utf-8")
            self._json({"ok": True})
        else:
            self._send(404, b"not found", "text/plain")


_SETTINGS = None
_REFILL = {"busy": False, "note": ""}


def _kick_refill() -> dict:
    """Nút "Tạo tiếp": soạn thêm việc làm tay ngay, không đợi vòng lặp.

    Chạy trong thread riêng với event loop riêng — handler HTTP phải trả lời
    ngay, mà soạn một mẻ draft mất cả phút (gọi Opus/Sonnet nhiều lần).
    """
    import asyncio
    import threading

    if _REFILL["busy"]:
        return {"ok": False, "why": "đang soạn, chờ chút"}
    if _SETTINGS is None:
        return {"ok": False, "why": "chưa có cấu hình"}

    def work():
        _REFILL.update(busy=True, note="đang soạn...")
        try:
            r = asyncio.run(manual.refill(_SETTINGS))
            # Ba lý do rất khác nhau, đừng gộp thành một câu: không có bài nào
            # trong cửa sổ / có bài nhưng đã reply tự động hoặc đã nằm trong
            # hàng đợi / có bài mới nhưng model bỏ qua hết.
            dupes = r.get("dupes", 0)
            if r["added"]:
                _REFILL["note"] = f"đã soạn thêm {r['added']} mục"
            elif not r["cands"]:
                _REFILL["note"] = ("không có bài nào qua được bộ lọc trong "
                                   f"{config.MANUAL_WINDOW_MIN} phút qua")
            elif dupes and not r["skipped"]:
                _REFILL["note"] = (f"{dupes} bài hợp lệ nhưng đã reply tự động "
                                   "hoặc đã có trong hàng đợi rồi")
            else:
                _REFILL["note"] = (f"{r['cands']} bài mới nhưng bỏ hết — "
                                   + " · ".join(x for x in r["skipped"] if x)[:300])
        except Exception as e:
            _REFILL["note"] = f"lỗi: {type(e).__name__}: {e}"
        finally:
            _REFILL["busy"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


def _history(days: int = HISTORY_DAYS) -> list[dict]:
    """Lịch sử theo ngày, có ghép view đo được của bài đăng ngày đó.

    View lấy từ cache của stats.py (acc phụ đọc lại timeline), nên chỉ những
    ngày có bài còn trong 60 bài gần nhất mới có số — ngày cũ hơn để 0 chứ
    không đoán.
    """
    rows = state.history(days)
    by_day: dict[str, dict] = {}
    for r in stats.cached().get("rows", []):
        day = (r.get("at") or "")[:10]
        if not day:
            continue
        b = by_day.setdefault(day, {"views": 0, "n": 0})
        b["views"] += int(r.get("views") or 0)
        b["n"] += 1
    for row in rows:
        b = by_day.get(row["date"])
        row["views"] = b["views"] if b else 0
        row["measured"] = b["n"] if b else 0
    return rows


def _state_payload() -> dict:
    st = state.load()
    w = config.current_window()
    nw, nw_at = config.next_window()
    snap = review.snapshot()
    nxt = [p for p in config.POST_PILLARS if p not in st.pillars_used]
    return {
        "manual": [
            {"id": i.id, "author": i.author, "url": i.url,
             "followers": i.followers, "age_min": i.age_min,
             "replies": i.replies, "their_text": i.their_text,
             "draft": i.draft, "draft_vi": i.draft_vi, "done": i.done}
            for i in manual.pending()
        ],
        "manual_sum": manual.summary(),
        "stats": stats.cached(),
        "payout": payout.progress(),
        "history": _history(),
        "targets": targets.summary(),
        "refill": dict(_REFILL),
        "models": {"post": config.MODEL_POST, "reply": config.MODEL_REPLY,
                   "vi": config.MODEL_TRANSLATE},
        "pillars": list(config.POST_PILLARS),
        "pillars_used": st.pillars_used,
        "pillar_next": nxt[0] if nxt else config.POST_PILLARS[0],
        "limits": {"replies": config.MAX_REPLIES_PER_DAY,
                   "quotes": config.QUOTES_PER_DAY,
                   "images": config.MAX_IMAGE_POSTS_PER_DAY,
                   "reply_window": config.REPLY_FRESH_MIN},
        "mode": "CHẠY THỬ, không đăng gì" if (_SETTINGS and _SETTINGS.dry_run)
                else "ĐĂNG THẬT",
        "review": review.enabled(),
        "handle": getattr(_SETTINGS, "account_handle", "?"),
        "now": f"{config.now():%H:%M}",
        "window": w.name if w else "",
        "next_window": {"name": nw.name, "at": nw_at,
                        "ends": f"{nw.end:%H:%M}", "posts": nw.posts,
                        "thread": nw.thread},
        "posts": sum(st.posts_done.values()),
        "thread": st.thread_done,
        "quotes": st.quotes_done,
        "replies": st.replies_done,
        "reposts": st.reposts_done,
        "images": len(st.images_used),
        "next_post": st.when("next_post_at"),
        "next_reply": st.when("next_reply_at"),
        "posted": st.posted[-12:][::-1],
        "notes": st.notes[-8:][::-1],
        "beat": dict(zip(("at", "what", "ago"), state.last_beat())),
        **snap,
    }


def start(settings, port: int = DEFAULT_PORT) -> str:
    """Bật server trong thread nền. Trả URL."""
    global _SETTINGS
    _SETTINGS = settings
    srv = Server((HOST, port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    password()                      # sinh sẵn để in ra log khởi động
    return f"http://{HOST}:{port}"
