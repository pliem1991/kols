"""Trang theo dõi chạy local — http://127.0.0.1:8787

Dùng http.server của thư viện chuẩn, không thêm phụ thuộc nào. Chạy trong thread
riêng, bind 127.0.0.1 nên không ai ngoài máy này vào được.

Bản tiếng Việt trên trang CHỈ để đọc. Bài đăng lên X luôn là bản tiếng Anh.
"""
from __future__ import annotations

import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from . import config, manual, review, state

HOST = "127.0.0.1"
DEFAULT_PORT = 8787

PAGE = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>XKols</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
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
.side{width:236px;flex:none;background:var(--card);border-right:1px solid var(--line);
 padding:22px 16px;display:flex;flex-direction:column;gap:6px;position:sticky;top:0;
 height:100vh}
.brand{display:flex;align-items:center;gap:10px;padding:0 8px 18px;font-weight:700;
 font-size:17px;letter-spacing:-.01em}
.brand i{width:30px;height:30px;border-radius:9px;background:var(--acc);color:#fff;
 display:grid;place-items:center;font-style:normal;font-size:15px}
.nav{display:block;padding:10px 12px;border-radius:11px;color:var(--mut);
 text-decoration:none;font-size:14.5px;font-weight:500;cursor:pointer}
.nav:hover{background:var(--bg)}
.nav.on{background:var(--acc);color:#fff}
.nav .n{float:right;font-size:12px;opacity:.75}
.sidefoot{margin-top:auto;border-top:1px solid var(--line);padding-top:14px;
 font-size:12.5px;color:var(--mut)}
.sidefoot b{display:block;color:var(--fg);font-size:14px}

/* ---- main ---- */
.main{flex:1;min-width:0;padding:24px 28px 56px}
.top{display:flex;align-items:center;justify-content:space-between;gap:16px;
 flex-wrap:wrap;margin-bottom:22px}
.hello{font-size:13px;color:var(--mut)}
.hello b{display:block;font-size:21px;color:var(--fg);font-weight:700;
 letter-spacing:-.02em;line-height:1.3}
.topright{display:flex;align-items:center;gap:9px;flex-wrap:wrap}
.chip{background:var(--card);border:1px solid var(--line);border-radius:99px;
 padding:7px 14px;font-size:12.5px;color:var(--mut);box-shadow:var(--shadow)}
.chip b{color:var(--fg)}
.chip.live{background:var(--no-soft);border-color:#f7c9ca;color:#a8282c}
.chip.dry{background:var(--warn-soft);border-color:#f3dcb4;color:#92610a}

/* ---- cards ---- */
.card{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
 padding:18px 20px;margin-bottom:18px;box-shadow:var(--shadow)}
.chead{display:flex;align-items:center;justify-content:space-between;gap:12px;
 margin-bottom:14px;flex-wrap:wrap}
h2{font-size:15.5px;margin:0;font-weight:650;letter-spacing:-.01em}
.sub{font-size:12.5px;color:var(--mut);margin:0}

/* ---- stat tiles ---- */
/* 6 ô chỉ số: ép đúng 6 cột, không để auto-fit xếp 5+1 lệch hàng. */
.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:14px}
@media (max-width:1180px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:620px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.stat{background:var(--card);border:1px solid var(--line);border-radius:var(--r);
 padding:16px 18px;box-shadow:var(--shadow)}
.stat .ico{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;
 font-size:15px;margin-bottom:12px}
.stat .lab{font-size:12.5px;color:var(--mut)}
.stat b{display:block;font-size:26px;font-weight:700;letter-spacing:-.02em;
 line-height:1.25;margin-top:2px}
.i1{background:var(--acc-soft);color:var(--acc)}
.i2{background:var(--ok-soft);color:var(--ok)}
.i3{background:var(--warn-soft);color:var(--warn)}
.i4{background:var(--no-soft);color:var(--no)}

/* ---- manual item ---- */
.item{border:1px solid var(--line);border-radius:13px;margin-bottom:11px;
 overflow:hidden;background:var(--card)}
.ihead{display:flex;align-items:center;gap:11px;padding:13px 15px;cursor:pointer;
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

/* ---- rows ---- */
.row{display:flex;justify-content:space-between;gap:12px;padding:10px 0;
 border-bottom:1px solid var(--line);font-size:13.5px}
.row:last-child{border:0}
.row .l{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mut{color:var(--mut)}
.pill{font-size:11px;padding:3px 9px;border-radius:99px;background:var(--acc-soft);
 color:var(--acc);font-weight:600;margin-right:8px}
.pill.g{background:var(--ok-soft);color:var(--ok)}
.empty{color:var(--mut);font-size:13.5px;padding:6px 0}
.note{color:var(--warn);font-size:13px}
img.shot{max-width:100%;border:1px solid var(--line);border-radius:11px;margin:0 0 12px}
@media (max-width:820px){
 .shell{flex-direction:column}
 .side{width:auto;height:auto;position:static;flex-direction:row;overflow-x:auto;
  align-items:center;padding:12px}
 .brand{padding:0 12px 0 4px}
 .sidefoot{display:none}
 .main{padding:18px 16px 48px}
}
</style></head><body>
<div class="shell">
 <aside class="side">
  <div class="brand"><i>X</i>XKols</div>
  <a class="nav on" onclick="go('s-stat',this)">Tổng quan</a>
  <a class="nav" onclick="go('s-manual',this)">Việc làm tay<span class="n" id="n-manual"></span></a>
  <a class="nav" onclick="go('s-pending',this)">Chờ duyệt<span class="n" id="n-pending"></span></a>
  <a class="nav" onclick="go('s-posted',this)">Đã đăng<span class="n" id="n-posted"></span></a>
  <a class="nav" onclick="go('s-ctl',this)">Điều khiển</a>
  <div class="sidefoot"><b id="sf-handle">—</b><span id="sf-mode"></span></div>
 </aside>
 <main class="main">
  <div class="top">
   <div class="hello">Xin chào<b id="hi">đang tải…</b></div>
   <div class="topright" id="chips"></div>
  </div>
  <div id="app"></div>
 </main>
</div>
<script>
let REVIEW = false;
const OPEN = new Set();      // mục nào đang mở — giữ qua mỗi lần tự nạp lại
const DRAFTS = {};
const esc = s => (s||"").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

function go(id, el){
  document.querySelectorAll('.nav').forEach(n=>n.classList.remove('on'));
  if(el) el.classList.add('on');
  const t = document.getElementById(id);
  if(t) t.scrollIntoView({behavior:'smooth', block:'start'});
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
  await fetch('/api/review?on='+(REVIEW?0:1), {method:'POST'}); load();
}
async function stop(){
  await fetch('/api/stop', {method:'POST'});
  document.getElementById('ctl').textContent = 'Đã đặt cờ dừng — app thoát ở vòng kế tiếp.';
}
function copyTo(id){
  navigator.clipboard.writeText(DRAFTS[id]||'').then(()=>{
    const b = document.getElementById('cp_'+id);
    if(b){ b.textContent='đã chép'; setTimeout(()=>b.textContent='Chép draft',1800); }
  });
}
function stat(ico, cls, n, lab){
  return '<div class="stat"><div class="ico '+cls+'">'+ico+'</div>'
    + '<div class="lab">'+lab+'</div><b>'+n+'</b></div>';
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

async function load(){
  let d;
  try { d = await (await fetch('/api/state')).json(); }
  catch(e){ document.getElementById('hi').textContent = 'Mất kết nối với app.'; return; }
  REVIEW = d.review;

  document.getElementById('hi').textContent = '@' + d.handle;
  document.getElementById('sf-handle').textContent = '@' + d.handle;
  document.getElementById('sf-mode').textContent = d.mode;
  document.getElementById('chips').innerHTML =
      '<span class="chip '+(d.mode.indexOf('THẬT')>=0?'live':'dry')+'">'+esc(d.mode)+'</span>'
    + '<span class="chip"><b>'+d.now+'</b> ICT · '
    + (d.window ? 'cửa sổ '+esc(d.window) : 'ngoài cửa sổ')+'</span>'
    + '<span class="chip">bài+reply <b>'+esc(d.models.post)+'</b></span>'
    + '<span class="chip">dịch <b>'+esc(d.models.vi)+'</b></span>';
  document.getElementById('n-manual').textContent = d.manual.length || '';
  document.getElementById('n-pending').textContent = d.pending.length || '';
  document.getElementById('n-posted').textContent = d.posted.length || '';

  let h = '<div id="s-stat" class="grid" style="margin-bottom:18px">'
    + stat('✎','i1', d.posts, 'bài gốc')
    + stat('≡','i2', d.thread?1:0, 'thread')
    + stat('❝','i1', d.quotes, 'quote')
    + stat('↩','i3', d.replies, 'reply tự động')
    + stat('⟳','i2', d.reposts, 'RT lại')
    + stat('▦','i4', d.images, 'bài có ảnh')
    + '</div>';

  h += '<div class="card"><div class="chead"><div>'
    + '<h2>Nhịp hôm nay</h2><p class="sub">bài kế '+d.next_post
    + ' · reply kế '+d.next_reply+'</p></div>'
    + '<span class="chip">chủ đề kế <b>'+esc(d.pillar_next)+'</b></span></div>'
    + '<div class="sub">Đã dùng: '+(d.pillars_used.map(esc).join(', ')||'chưa có')
    + '<br>Hạn mức/ngày: '+d.limits.replies+' reply · '+d.limits.quotes+' quote · '
    + d.limits.images+' bài có ảnh. Reply tự động CHỈ dành cho người đã tương tác '
    + 'với mình.</div></div>';

  const ms = d.manual_sum || {acts:{}, closed:0};
  const rf = d.refill || {};
  h += '<div class="card" id="s-manual"><div class="chead"><div>'
    + '<h2>Việc làm tay ('+d.manual.length+')</h2>'
    + '<p class="sub">App soạn sẵn, bạn tự bấm trên x.com. Hôm nay xong '+ms.closed
    + ' mục · reply '+(ms.acts.reply||0)+' · like '+(ms.acts.like||0)
    + ' · follow '+(ms.acts.follow||0)+' · bookmark '+(ms.acts.bookmark||0)+'</p></div>'
    + '<div><button class="pri" onclick="refill()"'+(rf.busy?' disabled':'')+'>'
    + (rf.busy?'Đang soạn…':'Tạo tiếp')+'</button>'
    + (rf.note?'<span class="sub">'+esc(rf.note)+'</span>':'')+'</div></div>';
  h += d.manual.length ? d.manual.map(manualCard).join('')
     : '<div class="empty">Chưa có mục nào — bấm "Tạo tiếp", hoặc đợi app tự nạp.</div>';
  h += '</div>';

  h += '<div class="card" id="s-pending"><div class="chead"><div>'
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

  h += '<div class="card" id="s-posted"><div class="chead">'
    + '<h2>Đã đăng hôm nay</h2></div>';
  h += d.posted.length ? d.posted.map(p=>'<div class="row"><span class="l">'
      + '<span class="pill g">'+esc(p.kind)+'</span>'+esc((p.text||'').slice(0,72))
      + '</span>'+(p.url && p.url.startsWith('http')
        ? '<a href="'+esc(p.url)+'" target="_blank">xem trên X</a>'
        : '<span class="mut">'+esc(p.url==='DRY'?'chạy thử':(p.url||''))+'</span>')
      + '</div>').join('')
    : '<div class="empty">Chưa đăng gì.</div>';
  h += '</div>';

  if(d.notes.length){
    h += '<div class="card"><div class="chead"><h2>Ghi chú và lỗi</h2></div>'
      + d.notes.map(n=>'<div class="row"><span class="note">'+esc(n)+'</span></div>').join('')
      + '</div>';
  }

  h += '<div class="card" id="s-ctl"><div class="chead"><h2>Điều khiển</h2></div>'
    + '<button class="'+(d.review?'ticked':'')+'" onclick="toggle()">'
    + (d.review?'Chế độ: duyệt tay':'Chế độ: tự động')+'</button>'
    + '<button class="no" onclick="stop()">Dừng app</button>'
    + '<div class="sub" style="margin-top:8px" id="ctl">'
    + (d.review?'Bấm để chuyển sang tự động — draft đang chờ sẽ được cho qua.'
       :'Bấm để bật duyệt tay — app sẽ hỏi bạn trước mỗi lần đăng.')+'</div></div>';

  document.getElementById('app').innerHTML = h;
}
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

    def do_GET(self):                      # noqa: N802
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif u.path == "/api/state":
            self._json(_state_payload())
        elif u.path == "/img":
            self._serve_image((parse_qs(u.query).get("p") or [""])[0])
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):                     # noqa: N802
        u = urlparse(self.path)
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
            if r["added"]:
                _REFILL["note"] = f"đã soạn thêm {r['added']} mục"
            elif not r["cands"]:
                _REFILL["note"] = ("không còn bài nào mới trong "
                                   f"{config.MANUAL_WINDOW_MIN} phút qua")
            else:
                _REFILL["note"] = (f"{r['cands']} bài nhưng bỏ hết — "
                                   + " · ".join(r["skipped"])[:300])
        except Exception as e:
            _REFILL["note"] = f"lỗi: {type(e).__name__}: {e}"
        finally:
            _REFILL["busy"] = False

    threading.Thread(target=work, daemon=True).start()
    return {"ok": True}


def _state_payload() -> dict:
    st = state.load()
    w = config.current_window()
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
        "refill": dict(_REFILL),
        "models": {"post": config.MODEL_POST, "reply": config.MODEL_REPLY,
                   "vi": config.MODEL_TRANSLATE},
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
        **snap,
    }


def start(settings, port: int = DEFAULT_PORT) -> str:
    """Bật server trong thread nền. Trả URL."""
    global _SETTINGS
    _SETTINGS = settings
    srv = Server((HOST, port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return f"http://{HOST}:{port}"
