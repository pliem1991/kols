"""Trang theo dõi của app X — phần riêng của X.

Khung trang (server, cổng mật khẩu, CSS, JS đổi mục/tự nạp lại/biểu đồ cột)
nằm trong dashkit/ từ 20/11, để project Facebook dùng lại được. Ở đây chỉ còn:
các mục của riêng X, số liệu nhồi vào /api/state, và mấy nút gọi về app.

Bản tiếng Việt trên trang CHỈ để đọc. Bài đăng lên X luôn là bản tiếng Anh.

Trang chia thành các mục riêng (Tổng quan / Việc làm tay / Kết quả thật / Chờ
duyệt / Đã đăng / Điều khiển) và đổi mục ngay trong trình duyệt, không tải lại.
Trước 15/11 tất cả nằm chung một cột dài: cuộn mãi mới tới việc cần làm, mà
Điều khiển lại nằm cuối — dễ bấm nhầm "Dừng app".
"""
from __future__ import annotations

import dashkit

from . import config, manual, payout, review, state, stats, targets

HOST = "127.0.0.1"
DEFAULT_PORT = 8787
HISTORY_DAYS = 14

# Trang này KHÔNG chỉ để xem: nó dừng được app, duyệt được bài đăng thật lên
# @macropandaX, và bấm "Tạo tiếp" là gọi Opus mấy lần (tốn tiền). Khi đưa ra
# internet qua Cloudflare tunnel (15/11) thì bất kỳ ai có link đều làm được
# ngần đó, mà hostname công khai thì bot quét ra. Luật của cổng và lý do chọn
# như vậy nằm trong dashkit/gate.py.
#
# File giữ token nằm ở tools/ chứ không phải posts/: endpoint /img phục vụ mọi
# file trong posts/, để token ở đó là tự đưa chìa khóa qua cửa sổ.
TOKEN_FILE = config.TOOLS / "web.env"

# Tên cookie "xk" đã cấp cho trình duyệt từ 15/11 — đổi là mọi người đang đăng
# nhập bị đẩy ra. App khác (Facebook) PHẢI dùng tên khác, xem dashkit/gate.py.
GATE = dashkit.Gate(env_file=TOKEN_FILE,
                    token_key="XKOLS_WEB_TOKEN",
                    pass_key="XKOLS_WEB_PASS",
                    now=config.now,
                    cookie="xk")


def password() -> str:
    """Mật khẩu vào trang. Đổi bằng cách sửa tools/web.env rồi khởi động lại."""
    return GATE.password()


NAV = [
    dashkit.Nav("overview", "Tổng quan"),
    dashkit.Nav("manual", "Việc làm tay", badge=True),
    dashkit.Nav("stats", "Kết quả thật"),
    dashkit.Nav("targets", "Đối tượng reply"),
    dashkit.Nav("pending", "Chờ duyệt", badge=True),
    dashkit.Nav("posted", "Đã đăng", badge=True),
    dashkit.Nav("ctl", "Điều khiển", foot=True),
]


JS = """/* ---------- nút gọi về app ---------- */
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

/* ---------- tiêu đề, chip, số đếm ---------- */
function head(d){
  return {
    title: '@' + d.handle,
    foot:  '@' + d.handle,
    sub:   d.mode,
    chips: '<span class="chip '+(d.mode.indexOf('THẬT')>=0?'live':'dry')+'">'
             + esc(d.mode)+'</span>'
         + '<span class="chip"><b>'+d.now+'</b> ICT · '
         + (d.window ? 'cửa sổ '+esc(d.window) : 'ngoài cửa sổ')+'</span>',
    badges: {manual: d.manual.length, pending: d.pending.length,
             posted: d.posted.length},
  };
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
    + ' mục/ngày — hôm nay app soạn được '+(ms.total||0)+'.'
    + (ms.expired ? ' Bỏ '+ms.expired+' mục để quá '
        + Math.round((ms.stale_min||180)/60)+' giờ chưa reply.' : '')
    + '</div></div>';
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
}"""


# --- mấy nút trên trang ------------------------------------------------------
def _r_decide(q: dashkit.server.Query) -> dict:
    pid = (q.get("id") or [""])[0]
    d = (q.get("d") or [""])[0]
    if d not in ("approved", "rejected"):
        return {"ok": False, "why": "quyết định không hợp lệ"}
    return {"ok": review.decide(pid, d)}


def _r_review(q: dashkit.server.Query) -> dict:
    on = (q.get("on") or ["0"])[0] == "1"
    review.set_enabled(on)
    return {"ok": True, "review": on}


def _r_manual(q: dashkit.server.Query) -> dict:
    pid = (q.get("id") or [""])[0]
    act = (q.get("act") or [""])[0]
    return {"ok": manual.mark(pid, act)}


def _r_stop(_q: dashkit.server.Query) -> dict:
    config.STOP_FILE.write_text("dung tu trang web\n", encoding="utf-8")
    return {"ok": True}


ROUTES = {
    "/api/decide": _r_decide,
    "/api/review": _r_review,
    "/api/manual/refill": lambda _q: _kick_refill(),
    "/api/manual": _r_manual,
    "/api/stop": _r_stop,
}


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
    return dashkit.serve(dashkit.Dash(
        name="XKols", icon="X", nav=NAV, app_js=JS,
        state=_state_payload, gate=GATE, posts=ROUTES,
        image_root=config.POSTS, home="overview",
        host=HOST, port=port,
    ))
