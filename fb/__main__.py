"""Màn hình theo dõi bot comment chéo / kết bạn Facebook (agaubun).

Chạy:  .venv\\Scripts\\python.exe -m fb      ->  http://127.0.0.1:8788
Chỉ đọc file của bot, không đăng, không điều khiển bot.
"""
from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path

import dashkit

from . import data, followers

ROOT = Path(__file__).resolve().parent  # XKols/fb
PORT = 8788          # X giữ 8787
COOKIE = "fbk"       # X dùng "xk"

JS = r"""
const KIND = {bot:'bot', task:'task cũ', dry:'chạy thử'};
function pct(a,b){ return b ? Math.min(100, Math.round(a/b*100)) : 0; }
function head(d){
  const st = d.lock ? '<span class="chip" style="color:var(--no)"><b>BỊ KHÓA</b></span>' : '';
  return {title:'Bot Facebook agaubun', sub:'theo dõi comment chéo + kết bạn',
    foot:'FBKols',
    chips: st + '<span class="chip">model <b>'+esc(d.model)+'</b></span>'
      + '<span class="chip"><b>'+esc(d.now)+'</b></span>',
    badges:{runs:d.runs.length, errors:d.errors_today||'', friends:d.f_today||''}};
}
document.head.insertAdjacentHTML('beforeend', '<style>'
  + '#app{max-width:1180px}'
  + '.card{padding:16px 18px;margin-bottom:14px}'
  + '.card .row{padding:6px 0;font-size:13.5px}'
  + '.kv{display:grid;grid-template-columns:auto 1fr;gap:7px 14px;font-size:13.5px}'
  + '.kv>span:nth-child(odd){color:var(--mut);white-space:nowrap}'
  + '.kv>span:nth-child(even){text-align:right;min-width:0;overflow-wrap:anywhere}'
  + '.ov{display:grid;grid-template-columns:minmax(0,1fr) 320px;gap:14px;align-items:start}'
  + '.ov>.card{margin:0}'
  + '@media (max-width:980px){.ov{grid-template-columns:1fr}}'
  + '.hc{display:grid;grid-template-columns:repeat(14,minmax(0,1fr));gap:4px;align-items:end;height:190px;margin-top:6px}'
  + '.hc .c{display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;min-width:0}'
  + '.hc .v{font-size:12.5px;font-weight:700;line-height:1.1}'
  + '.hc .v.z{color:var(--mut);font-weight:400}'
  + '.hc .f{font-size:11px;color:var(--warn);font-weight:700;min-height:13px;white-space:nowrap}'
  + '.hc .b{display:block;width:70%;max-width:30px;background:var(--acc);margin-top:3px;border-radius:5px 5px 0 0}'
  + '.hc .b.fb{background:var(--warn)}'
  + '.hc .b.fb + .b{margin-top:0;border-radius:0}'
  + '.hx{display:grid;grid-template-columns:repeat(14,minmax(0,1fr));gap:4px;border-top:1px solid var(--line);margin-top:4px;padding-top:5px;text-align:center;font-size:11px;line-height:1.35}'
  + '.hx b{display:block;font-size:11.5px}.hx .now b{color:var(--acc)}.hx .bad{font-weight:700}'
  + '.runs .r{display:grid;grid-template-columns:96px 70px minmax(0,1fr) auto;gap:10px;align-items:center;padding:7px 0;border-bottom:1px solid var(--line);font-size:13.5px;cursor:pointer}'
  + '.runs .r:last-child{border:0}.runs .det{padding:4px 0 10px 12px;font-size:12.5px;border-bottom:1px solid var(--line)}'
  + '.runs .det div{padding:2px 0}'
  + '.tb{width:100%;border-collapse:collapse;font-size:13px;white-space:nowrap}'
  + '.tb th{font-weight:600;color:var(--mut);text-align:right;padding:6px 8px;border-bottom:1px solid var(--line)}'
  + '.tb td{text-align:right;padding:6px 8px;border-bottom:1px solid var(--line)}'
  + '.tb th:first-child,.tb td:first-child{text-align:left}'
  + '.tb tr.sum td{border-bottom:0;font-weight:600}'
  + '.pill{font-size:11px;padding:2px 7px;border-radius:9px;background:var(--line);color:var(--mut);text-align:center}'
  + '@media (max-width:560px){.runs .r{grid-template-columns:1fr auto}.runs .r .pill,.runs .r .m{display:none}}'
  + '</style>');
function agoTxt(m){ return m < 60 ? m+' phút' : Math.floor(m/60)+' giờ '+(m%60)+' phút'; }
function hist14(his){
  const max = Math.max(1, ...his.map(r=>r.comments+r.friends));
  const H = 140;
  const top = '<div class="hc">' + his.map(r=>
    '<div class="c" title="'+r.date+': '+r.comments+' comment, '+r.friends+' lời mời, '+r.runs+' lượt'+(r.errors?', '+r.errors+' lỗi':'')+'">'
      + '<span class="f">'+(r.friends?'+'+r.friends+' mời':'')+'</span>'
      + '<span class="v'+(r.comments?'':' z')+'">'+r.comments+'</span>'
      + (r.friends ? '<i class="b fb" style="height:'+(r.friends/max*H).toFixed(1)+'px"></i>' : '')
      + '<i class="b" style="height:'+(r.comments ? Math.max(2, r.comments/max*H) : 0).toFixed(1)+'px"></i>'
      + '</div>').join('') + '</div>';
  const axis = '<div class="hx">' + his.map((r,i)=>'<span'+(i===his.length-1?' class="now"':'')+'><b>'+r.date.slice(8)+'/'+r.date.slice(5,7)+'</b>'
    + '<span class="mut">'+(r.runs?r.runs+' lượt':'—')+'</span>'
    + (r.errors?'<br><span class="bad">'+r.errors+' lỗi</span>':'')+'</span>').join('') + '</div>';
  return top + axis;
}
function v_overview(d){
  const L = d.limits;
  let h = '';
  if(d.lock){
    h += '<div class="danger"><b>Bot đã tự khóa sau cảnh báo của Facebook.</b><br>'
      + esc(d.lock)+'<br><span class="mut">Kiểm tra tài khoản trên Chrome của bot, xong thì xóa tay file '
      + '<code>cheo/dung-khan-cap.txt</code> để bot chạy lại.</span></div>';
  }
  h += '<div class="strip">'
    + cell('var(--acc)', d.c_today+'<small class="mut"> / '+L.comments+'</small>', 'comment hôm nay')
    + cell('var(--ok)', d.f_today+'<small class="mut"> / '+L.friends+'</small>', 'lời mời hôm nay')
    + cell('var(--no)', d.errors_today, 'lỗi hôm nay')
    + cell('var(--warn)', '$'+d.cost_today.toFixed(3), 'tiền AI hôm nay')
    + cell('var(--mut)', d.groups.filter(g=>!g.paused).length+' / '+d.groups.length, 'group đang chạy')
    + cell('var(--mut)', d.posts_total, 'bài đã comment')
    + '</div>';
  const his = d.hist;
  const sum = f => his.reduce((a,r)=>a+f(r),0);
  const hr = new Date().getHours();
  const late = d.last_run && d.ago_min > 180 && hr >= 9 && hr <= 22;
  h += '<div class="ov"><div class="card"><div class="chead"><div><h2>14 ngày qua</h2>'
    + '<p class="sub">'+sum(r=>r.comments)+' comment · '+sum(r=>r.friends)+' lời mời · '
    + sum(r=>r.runs)+' lượt · ~$'+sum(r=>r.cost).toFixed(3)+' (không tính chạy thử)</p></div>'
    + legend([['var(--acc)','comment'],['var(--warn)','lời mời']])+'</div>'
    + hist14(his) + '</div>';
  h += '<div class="card"><div class="chead"><h2>Trạng thái</h2></div><div class="kv">'
    + '<span>Lượt gần nhất</span><span class="'+(late?'bad':'')+'">'
    + (d.last_run ? esc(d.last_run.slice(11))+' · '+agoTxt(d.ago_min)+' trước'+(late?' (lâu bất thường)':'') : 'chưa có')+'</span>'
    + '<span>Chrome bot</span><span>'+(d.chrome_open?'<b class="ok">đang mở</b>':'tắt')+'</span>'
    + '<span>Group kế</span><span>'+(d.next_groups.map(esc).join('<br>')||'-')+'</span>'
    + '<span>Câu kế</span><span>'+esc(d.phrase_next)+'</span>'
    + '<span>Mỗi lượt</span><span>'+L.run_min+'–'+L.run_max+' comment · '+L.groups_per_run+' group</span>'
    + '<span>Kết bạn</span><span>≥'+L.mutual+' bạn chung<br>11–14h tối đa 2 · 19–22h đủ '+L.friends+'</span>'
    + '</div></div></div>';
  return h;
}
function tk(n){ return n>=1e6 ? (n/1e6).toFixed(2)+'M' : n>=1e3 ? Math.round(n/1e3)+'K' : String(n||0); }
const usd = (n,dg) => n==null ? '—' : '$'+n.toFixed(dg==null?3:dg);
function v_cost(d){
  const C = d.costs;
  let h = '<div class="strip">'
    + cell('var(--acc)', usd(C.today.cost), 'hôm nay')
    + cell('var(--acc)', usd(C.d7.cost), '7 ngày')
    + cell('var(--acc)', usd(C.d30.cost), '30 ngày')
    + cell('var(--mut)', usd(C.all.cost), 'từ trước tới giờ')
    + cell('var(--warn)', usd(C.avg_run), 'trung bình 1 lượt')
    + cell('var(--warn)', usd(C.all.per_comment, 4), 'trung bình 1 comment')
    + '</div>';
  const days = C.days.filter(r=>r.runs).reverse();
  h += '<div class="card"><div class="chead"><div><h2>Chi phí mỗi ngày</h2>'
    + '<p class="sub">Tính cả lượt chạy thử vì vẫn gọi AI thật. Số tiền là ước tính bot ghi trong log.md theo bảng giá của browser-use. Lượt --test3 không ghi log nên không có ở đây.</p></div></div>'
    + (days.length ? '<div style="overflow-x:auto"><table class="tb"><thead><tr><th>Ngày</th><th>Lượt AI</th><th>Request</th><th>Token vào</th><th>Token ra</th><th>Comment</th><th>Tiền</th></tr></thead><tbody>'
      + days.map(r=>'<tr><td>'+r.date.slice(8)+'/'+r.date.slice(5,7)+'</td><td>'+r.runs+'</td><td>'+r.requests+'</td><td>'+tk(r.tin)+'</td><td>'+tk(r.tout)+'</td><td>'+r.comments+'</td><td><b>'+usd(r.cost,4)+'</b></td></tr>').join('')
      + '<tr class="sum"><td>Tổng 30 ngày</td><td>'+C.d30.runs+'</td><td></td><td>'+tk(C.d30.tin)+'</td><td>'+tk(C.d30.tout)+'</td><td></td><td><b>'+usd(C.d30.cost,4)+'</b></td></tr>'
      + '</tbody></table></div>' : '<p class="sub">Chưa có lượt nào dùng AI.</p>')
    + '</div>';
  const runs = d.runs.filter(r=>r.requests||r.cost);
  if(runs.length){
    h += '<div class="card"><div class="chead"><div><h2>Từng lượt</h2><p class="sub">'+runs.length+' lượt dùng AI gần nhất</p></div></div>'
      + '<div style="overflow-x:auto"><table class="tb"><thead><tr><th>Lúc</th><th>Loại</th><th>Model</th><th>Request</th><th>Token vào</th><th>Token ra</th><th>Comment</th><th>Tiền</th></tr></thead><tbody>'
      + runs.map(r=>'<tr><td>'+esc(r.at.slice(8,10)+'/'+r.at.slice(5,7)+' '+r.at.slice(11))+'</td><td>'+KIND[r.kind]+'</td><td class="mut">'+esc((r.model||'').replace('claude-',''))+'</td><td>'+r.requests+'</td><td>'+tk(r.tin)+'</td><td>'+tk(r.tout)+'</td><td>'+r.comments+'</td><td><b>'+usd(r.cost,4)+'</b></td></tr>').join('')
      + '</tbody></table></div></div>';
  }
  return h;
}
function v_runs(d){
  if(!d.runs.length) return '<div class="card">Chưa có lượt chạy nào trong log.md.</div>';
  return '<div class="card runs"><div class="chead"><div><h2>Lượt chạy</h2><p class="sub">'+d.runs.length+' lượt gần nhất · bấm một dòng để xem chi tiết</p></div></div>'
    + d.runs.map((r,i)=>{
      const id = 'run'+i, open = OPEN.has(id);
      return '<div class="r" onclick="toggle_item(\''+id+'\');render()">'
        + '<span>'+esc(r.at.slice(5).replace('-','/'))+'</span>'
        + '<span class="pill">'+KIND[r.kind]+'</span>'
        + '<span><b>'+r.comments+'</b> comment'+(r.friends?' · <b>'+r.friends+'</b> lời mời':'')
        + (r.errors.length?' · <span class="bad">'+r.errors.length+' lỗi</span>':'')+'</span>'
        + '<span class="mut m">'+(r.requests?tk(r.tin)+' vào · '+tk(r.tout)+' ra · ':'')+(r.cost?'<b>$'+r.cost.toFixed(4)+'</b>':'')+'</span></div>'
        + (open ? '<div class="det">'+r.lines.map(l=>'<div class="'+(r.errors.includes(l)?'note':'mut')+'">'+esc(l)+'</div>').join('')+'</div>' : '');
    }).join('') + '</div>';
}
function v_errors(d){
  let h = '';
  if(d.lock) h += '<div class="danger"><b>Đang khóa:</b> '+esc(d.lock)+'</div>';
  if(!d.errors.length) return h + '<div class="card"><span class="ok">Không có lỗi nào trong log.</span></div>';
  return h + '<div class="card"><div class="chead"><h2>Lỗi và cảnh báo</h2><p class="sub">mới nhất trước</p></div>'
    + d.errors.map(e=>'<div class="row"><span class="l mut" style="flex:none">'+esc(e.at)+' · '+KIND[e.kind]
      + '</span><span class="note" style="text-align:right">'+esc(e.text)+'</span></div>').join('')
    + '</div>';
}
function v_friends(d){
  if(!d.friends.length) return '<div class="card">Chưa gửi lời mời nào (chưa có ket-ban.json).'
    + '<p class="sub">Chỉ gửi '+esc(d.friend_window)+', người có từ '+d.limits.mutual+' bạn chung.</p></div>';
  return '<div class="card"><div class="chead"><h2>Lời mời đã gửi</h2><p class="sub">30 gần nhất</p></div>'
    + d.friends.map(x=>'<div class="row"><span class="l">'
      + (x.profile?'<a href="'+esc(x.profile)+'" target="_blank" rel="noopener">'+esc(x.name)+'</a>':esc(x.name))
      + '</span><span class="mut">'+(x.mutual||'?')+' bạn chung · '+esc(x.time||x.date||'')+'</span></div>').join('')
    + '</div>';
}
/* ---------- live follower ---------- */
const PREV = {};
const fmtN = n => n==null ? '—' : n.toLocaleString('vi-VN');
const sgn = n => n==null ? '<span class="mut">chưa đủ dữ liệu</span>'
  : '<b style="color:'+(n>0?'var(--ok)':n<0?'var(--no)':'var(--mut)')+'">'+(n>0?'+':'')+fmtN(n)+'</b>';
function odo(id, val){
  const s = val==null ? '—' : val.toLocaleString('vi-VN');
  return '<div class="odo" id="'+id+'">' + [...s].map(ch => /\d/.test(ch)
    ? '<span class="dg"><span class="col" data-v="'+ch+'">'
      + [0,1,2,3,4,5,6,7,8,9].map(n=>'<span>'+n+'</span>').join('') + '</span></span>'
    : '<span class="sep">'+ch+'</span>').join('') + '</div>';
}
function spin(id, key, val){
  /* vẽ ở số cũ rồi lăn sang số mới, giống bộ đếm cơ */
  requestAnimationFrame(()=>{
    const el = document.getElementById(id); if(!el) return;
    const cols = el.querySelectorAll('.col');
    const old = PREV[key]==null ? null : PREV[key].toLocaleString('vi-VN').replace(/\D/g,'');
    const neu = [...cols].map(c=>c.dataset.v);
    cols.forEach((c,i)=>{
      const o = old && old.length===neu.length ? old[i] : neu[i];
      c.style.transition='none'; c.style.transform='translateY(-'+o+'0%)';
    });
    requestAnimationFrame(()=>requestAnimationFrame(()=>{
      cols.forEach(c=>{ c.style.transition='transform 1.4s cubic-bezier(.2,.8,.2,1)';
                        c.style.transform='translateY(-'+c.dataset.v+'0%)'; });
    }));
    PREV[key] = val;
  });
}
function chart(series){
  if(series.length < 2) return '<p class="sub">Cần ít nhất 2 lần ghi để vẽ biểu đồ.</p>';
  const W=760,H=200,P=34;
  const t = series.map(p=>new Date(p[0].replace(' ','T')).getTime()), v = series.map(p=>p[1]);
  const t0=Math.min(...t), t1=Math.max(...t), v0=Math.min(...v), v1=Math.max(...v);
  const x = a => P + (t1===t0?0:(a-t0)/(t1-t0))*(W-P-8);
  const y = b => H-22 - (v1===v0?0.5:(b-v0)/(v1-v0))*(H-40);
  const pts = t.map((a,i)=>x(a).toFixed(1)+','+y(v[i]).toFixed(1)).join(' ');
  return '<svg viewBox="0 0 '+W+' '+H+'" style="width:100%;height:auto">'
    + '<text x="0" y="'+(y(v1)+4)+'" font-size="11" fill="currentColor" opacity=".6">'+fmtN(v1)+'</text>'
    + '<text x="0" y="'+(y(v0)+4)+'" font-size="11" fill="currentColor" opacity=".6">'+fmtN(v0)+'</text>'
    + '<polyline points="'+pts+'" fill="none" stroke="var(--acc)" stroke-width="2.5" stroke-linejoin="round"/>'
    + t.map((a,i)=>'<circle cx="'+x(a).toFixed(1)+'" cy="'+y(v[i]).toFixed(1)+'" r="3" fill="var(--acc)"><title>'
      + series[i][0]+' — '+fmtN(v[i])+'</title></circle>').join('')
    + '<text x="'+P+'" y="'+(H-4)+'" font-size="11" fill="currentColor" opacity=".6">'+series[0][0]+'</text>'
    + '<text x="'+(W-8)+'" y="'+(H-4)+'" font-size="11" text-anchor="end" fill="currentColor" opacity=".6">'+series[series.length-1][0]+'</text>'
    + '</svg>';
}
async function addFol(){
  const f = document.getElementById('in_f').value, r = document.getElementById('in_r').value;
  const res = await fetch('/api/followers?followers='+encodeURIComponent(f)+'&friends='+encodeURIComponent(r), {method:'POST'});
  const j = await res.json();
  document.getElementById('in_msg').textContent = j.ok ? 'Đã ghi.' : (j.why||'Lỗi');
  if(j.ok){ document.getElementById('in_f').value=''; document.getElementById('in_r').value=''; load(); }
}
function bigCard(key, label, F){
  const x = F[key];
  setTimeout(()=>spin('odo_'+key, key, x.now), 0);
  return '<div class="card" style="text-align:center"><div class="chead" style="justify-content:center"><h2>'+label+'</h2></div>'
    + odo('odo_'+key, x.now)
    + '<p class="sub">'+(x.at ? 'ghi lúc '+esc(x.at)+' · nguồn '+(x.src==='tay'?'nhập tay':esc(x.src)) : 'chưa có số nào')+'</p>'
    + '<div class="row"><span class="l mut">24 giờ</span>'+sgn(x.d24)+'</div>'
    + '<div class="row"><span class="l mut">7 ngày</span>'+sgn(x.d7)+'</div></div>';
}
document.head.insertAdjacentHTML('beforeend', '<style>'
  + '.odo{display:inline-flex;font:700 64px/1 ui-monospace,Consolas,monospace;margin:6px 0 4px;letter-spacing:1px}'
  + '.odo .dg{display:inline-block;height:1em;overflow:hidden}'
  + '.odo .col{display:flex;flex-direction:column}.odo .col span{height:1em}'
  + '.odo .sep{opacity:.5}'
  + '.duo.two{grid-template-columns:1fr 1fr;margin-top:14px}'
  + '@media (max-width:980px){.duo.two{grid-template-columns:1fr}}'
  + '@media (max-width:560px){.odo{font-size:44px}}</style>');
function v_live(d){
  /* trang tự nạp lại: giữ chữ đang gõ và chỗ con trỏ */
  const keep = {};
  ['in_f','in_r'].forEach(id=>{ const e=document.getElementById(id); if(e) keep[id]=e.value; });
  const foc = document.activeElement && document.activeElement.id;
  setTimeout(()=>{
    Object.keys(keep).forEach(id=>{ const e=document.getElementById(id); if(e) e.value=keep[id]; });
    if(foc && foc.startsWith('in_')){ const e=document.getElementById(foc); if(e){ e.focus(); e.selectionStart=e.selectionEnd=e.value.length; } }
  }, 0);
  const F = d.fol;
  let h = '<div class="duo">' + bigCard('followers','Người theo dõi',F) + bigCard('friends','Bạn bè',F) + '</div>';
  h += '<div class="duo two">'
    + '<div class="card"><div class="chead"><div><h2>Người theo dõi theo thời gian</h2>'
    + '<p class="sub">'+F.followers.series.length+' lần ghi</p></div></div>' + chart(F.followers.series) + '</div>'
    + '<div class="card"><div class="chead"><div><h2>Bạn bè theo thời gian</h2>'
    + '<p class="sub">'+F.friends.series.length+' lần ghi</p></div></div>' + chart(F.friends.series) + '</div></div>';
  h += '<div class="card" style="margin-top:14px"><div class="chead"><div><h2>Nhập tay</h2>'
    + '<p class="sub">Bot tự ghi sau mỗi lượt chạy thật. Muốn ghi ngay thì nhập số đang thấy trên trang cá nhân.</p></div></div>'
    + '<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">'
    + '<input id="in_f" inputmode="numeric" placeholder="người theo dõi" style="padding:8px 10px;border-radius:9px;border:1px solid var(--line);width:160px">'
    + '<input id="in_r" inputmode="numeric" placeholder="bạn bè" style="padding:8px 10px;border-radius:9px;border:1px solid var(--line);width:120px">'
    + '<button onclick="addFol()" style="padding:8px 14px;border-radius:9px;border:0;background:var(--acc);color:#fff;cursor:pointer">Ghi số</button>'
    + '<span id="in_msg" class="mut"></span></div></div>';
  return h;
}

function v_groups(d){
  return '<div class="duo"><div class="card"><div class="chead"><h2>Group</h2></div>'
    + d.groups.map(g=>'<div class="row"><span class="l">'
      + '<a href="https://www.facebook.com/groups/'+esc(g.id)+'" target="_blank" rel="noopener">'+esc(g.id)+'</a></span>'
      + (g.paused?'<span class="bad">tạm dừng</span>':(d.next_groups.includes(g.id)?'<span class="ok">lượt kế</span>':'<span class="mut">chạy</span>'))
      + '</div>').join('') + '</div>'
    + '<div class="card"><div class="chead"><h2>Bài đã comment</h2><p class="sub">30 gần nhất / '+d.posts_total+'</p></div>'
    + d.posts.map(p=>'<div class="row"><span class="mut">'+esc(p)+'</span></div>').join('') + '</div></div>';
}
"""

def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    gate = dashkit.Gate(env_file=ROOT / "fb.env",
                        token_key="FBKOLS_WEB_TOKEN", pass_key="FBKOLS_WEB_PASS",
                        now=datetime.now, cookie=COOKIE)
    dash = dashkit.Dash(
        name="FBKols", icon="F",
        nav=[dashkit.Nav("overview", "Tổng quan"),
             dashkit.Nav("live", "Live follower"),
             dashkit.Nav("runs", "Lượt chạy", badge=True),
             dashkit.Nav("cost", "Chi phí AI"),
             dashkit.Nav("errors", "Lỗi", badge=True),
             dashkit.Nav("friends", "Kết bạn", badge=True),
             dashkit.Nav("groups", "Group & bài")],
        app_js=JS, state=lambda: {**data.state(), "fol": followers.state()}, gate=gate, port=PORT, poll_ms=10000,
    )
    dash.posts["/api/followers"] = followers.add_manual
    url = dashkit.serve(dash)
    gate.password()  # lần đầu tự sinh và ghi vào tools/web.env
    print(f"FBKols: {url}  (mật khẩu trong {ROOT / 'fb.env'}, khóa FBKOLS_WEB_PASS)", flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
