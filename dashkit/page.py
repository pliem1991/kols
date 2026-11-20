"""Khung HTML cho trang theo doi — CSS, trang dang nhap, JS chung.

Khong biet gi ve X hay Facebook. App goi build() va nop vao: ten, bieu tuong,
danh sach muc ben trai, va JS rieng cua minh (cac ham v_<key> ve tung muc,
cung mot ham head(d) tra ve tieu de/chip/so dem).

CSS va trang dang nhap duoi day cat nguyen van tu app/web.py ban 18/11, sinh
boi tools/gen_page.py — sua giao dien thi sua o DAY, ca hai trang an theo.
"""
from __future__ import annotations

import json
from dataclasses import dataclass


@dataclass(frozen=True)
class Nav:
    """Mot muc ben trai. badge=True thi co so dem nho ben phai nhan."""
    key: str
    label: str
    badge: bool = False
    foot: bool = False          # day xuong duoi cung, cach ra mot khoang


LOGIN = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__</title><style>
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
<h1>__NAME__</h1>
<p>Trang điều khiển. Cần mật khẩu.</p>
<input type="password" name="p" autofocus autocomplete="current-password"
 placeholder="Mật khẩu">
<button type="submit">Vào</button>
__ERR__
</form></body></html>"""

CSS = """<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__NAME__</title>
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
.nav.jump{border:1px dashed var(--line);margin-top:8px;text-decoration:none}
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
</style></head><body>"""

SHELL = """<div class="shell">
 <aside class="side">
  <div class="brand"><i>__ICON__</i>__NAME__</div>
__NAV__
  <div class="sidefoot"><b id="sf-foot">—</b><span id="sf-sub"></span></div>
 </aside>
 <main class="main">
  <div class="top">
   <div class="hello"><span id="crumb"></span><b id="hi">đang tải…</b></div>
   <div class="topright" id="chips"></div>
  </div>
  <div id="app"></div>
 </main>
</div>
<script>
"""

JS_CORE = """/* ---------- khung chung (dashkit) ---------- */
let D = null;
const DEFAULT_VIEW = '__HOME__';
let VIEW = location.hash.slice(1) || DEFAULT_VIEW;
const OPEN = new Set();      /* muc nao dang mo - giu qua moi lan tu nap lai */
const DRAFTS = {};
const VIEWS = {};            /* dien o cuoi, sau khi app dinh nghia v_* */
const NAMES = __NAMES__;
const esc = s => (s||"").replace(/[&<>]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

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

function render(){
  if(!D) return;
  document.querySelectorAll('.nav').forEach(n=>n.classList.remove('on'));
  const nv = document.getElementById('nv-'+VIEW);
  if(nv) nv.classList.add('on');
  document.getElementById('crumb').textContent = NAMES[VIEW] || '';
  const f = VIEWS[VIEW] || VIEWS[DEFAULT_VIEW];
  document.getElementById('app').innerHTML = f ? f(D) : '';
}

async function load(){
  let d;
  try { d = await (await fetch('/api/state')).json(); }
  catch(e){ document.getElementById('hi').textContent = 'Mất kết nối vội app.'; return; }
  D = d;
  const h = (typeof head === 'function') ? (head(d) || {}) : {};
  document.getElementById('hi').textContent = h.title || '';
  document.getElementById('sf-foot').textContent = h.foot || h.title || '';
  document.getElementById('sf-sub').textContent = h.sub || '';
  document.getElementById('chips').innerHTML = h.chips || '';
  const badges = h.badges || {};
  Object.keys(badges).forEach(k => {
    const el = document.getElementById('n-'+k);
    if(el) el.textContent = badges[k] || '';
  });
  render();
}
window.addEventListener('hashchange', ()=>{
  const v = location.hash.slice(1);
  if(VIEWS[v] && v !== VIEW){ VIEW = v; render(); }
});

/* ---------- phan rieng cua app ---------- */
"""

JS_TAIL = """
/* ---------- khoi dong (dashkit) ---------- */
__KEYS__.forEach(k => { const f = window['v_'+k]; if(f) VIEWS[k] = f; });
load(); setInterval(load, __POLL__);
</script></body></html>"""



def nav_html(items: list[Nav]) -> str:
    out = []
    for n in items:
        if n.foot and '<div class="navsep"></div>' not in out:
            out.append('  <div class="navsep"></div>')
        dem = f'<span class="n" id="n-{n.key}"></span>' if n.badge else ""
        out.append(f'  <a class="nav" id="nv-{n.key}" '
                   f"onclick=\"go('{n.key}')\">{n.label}{dem}</a>")
    return "\n".join(out)


def links_html(links: list[tuple[str, str]]) -> str:
    """Nut sang trang theo doi khac (moi trang mot server, mot cong rieng)."""
    esc = lambda t: (str(t).replace("&", "&amp;").replace("<", "&lt;")
                     .replace(">", "&gt;").replace('"', "&quot;"))
    return "\n".join(f'  <a class="nav jump" href="{esc(u)}" title="Sang trang {esc(n)}">'
                     f'&#8644; {esc(n)}</a>' for n, u in links)


def login(name: str, err: str = "") -> str:
    return (LOGIN.replace("__NAME__", name)
            .replace("__ERR__", f'<div class="err">{err}</div>' if err else ""))


def build(name: str, icon: str, nav: list[Nav], app_js: str,
          home: str = "", poll_ms: int = 4000,
          links: list[tuple[str, str]] | None = None) -> str:
    """Ghep trang day du. app_js la JS rieng cua app, dat giua khung va khoi dong."""
    if not nav:
        raise ValueError("can it nhat mot muc nav")
    home = home or nav[0].key
    names = {n.key: n.label for n in nav}
    page = (CSS.replace("__NAME__", name)
            + SHELL.replace("__ICON__", icon).replace("__NAME__", name)
                   .replace("__NAV__", nav_html(nav)
                            + ("\n" + links_html(links) if links else ""))
            + JS_CORE.replace("__HOME__", home)
                     .replace("__NAMES__", json.dumps(names, ensure_ascii=False))
            + app_js
            + JS_TAIL.replace("__KEYS__", json.dumps([n.key for n in nav]))
                     .replace("__POLL__", str(poll_ms)))
    return page
