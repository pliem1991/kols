"""Tab "Video viral X" trên trang 8788, kèm lịch quét.

Chủ dự án chốt 21/11: phần này thuộc về bot Facebook, không phải bot X. Nên
TIẾN TRÌNH NÀY giữ lịch quét — `python -m fb` chạy là có quét, bot X tắt hay
bật không liên quan.

Thuật toán tìm video nằm ở `viral/` (package dùng chung, không nằm trong app/
của X). Ở đây chỉ có: gọi quét khi đến giờ, và vẽ tab.
"""
from __future__ import annotations

import asyncio
import sys
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from viral import scan, store  # noqa: E402

HOURS_TEXT = " và ".join(f"{h}:00" for h in scan.HOURS)
_BUSY = threading.Lock()


def state() -> dict:
    return store.state()


def scan_if_due(now: datetime | None = None) -> None:
    """Đến giờ thì quét một lượt. Gọi từ vòng lặp của fb/__main__.py.

    Chạy trong một thread riêng: một lượt quét mất 20-40 giây, mà vòng lặp
    chính còn phải phục vụ trang web. Khoá _BUSY để hai lượt không chồng nhau
    nếu lượt trước chạy lâu hơn nhịp kiểm tra.
    """
    if not scan.due(now) or _BUSY.locked():
        return

    def work() -> None:
        with _BUSY:
            try:
                r = asyncio.run(scan.run())
                print(f"[{datetime.now():%H:%M:%S}] video viral: thêm "
                      f"{r['them']} mới, cập nhật {r['capnhat']} cũ", flush=True)
            except Exception as e:
                # Mất một lượt quét không đáng để trang theo dõi chết theo.
                print(f"[{datetime.now():%H:%M:%S}] quét video viral lỗi: "
                      f"{type(e).__name__}: {e}", flush=True)

    threading.Thread(target=work, daemon=True).start()


def set_status(q: dict[str, list[str]]) -> dict:
    """Nút bấm trên trang: /api/viral?url=...&status=..."""
    url = (q.get("url") or [""])[0]
    status = (q.get("status") or [""])[0]
    if not url:
        return {"ok": False, "why": "thiếu url"}
    return store.set_status(url, status)


JS = r"""
/* ---- Video viral X ---- */
let VF_TOPIC = 'tất cả', VF_STATUS = 'moi';
const VST = {moi:'mới', da_chon:'đã chọn', da_lam:'đã làm', bo:'bỏ'};

document.head.insertAdjacentHTML('beforeend', '<style>'
  + '.vv{display:grid;grid-template-columns:132px minmax(0,1fr);gap:14px;'
  +   'padding:14px 0;border-top:1px solid var(--line)}'
  + '.vv:first-of-type{border-top:0}'
  + '.vv img{width:132px;height:86px;object-fit:cover;border-radius:9px;background:var(--line)}'
  + '.vv .no{width:132px;height:86px;border-radius:9px;background:var(--line);'
  +   'display:flex;align-items:center;justify-content:center;color:var(--mut);font-size:11px}'
  + '.vv h3{margin:0 0 3px;font-size:14.5px;font-weight:650;line-height:1.35}'
  + '.vv .meta{color:var(--mut);font-size:12px;margin:2px 0 7px}'
  + '.vv .meta b{color:inherit}'
  + '.vnums{display:flex;gap:12px;flex-wrap:wrap;font-size:12.5px;margin-bottom:8px}'
  + '.vnums i{font-style:normal;color:var(--mut)}'
  + '.vfil{display:flex;gap:7px;flex-wrap:wrap;margin:10px 0 2px}'
  + '.vfil button{border:1px solid var(--line);background:none;border-radius:999px;'
  +   'padding:4px 11px;font:inherit;font-size:12.5px;color:var(--mut);cursor:pointer}'
  + '.vfil button.on{background:var(--acc);border-color:var(--acc);color:#fff}'
  + '.vact button{border:1px solid var(--line);background:none;border-radius:8px;'
  +   'padding:4px 10px;font:inherit;font-size:12.5px;cursor:pointer;margin-right:6px;color:inherit}'
  + '.vact button.on{background:var(--acc);border-color:var(--acc);color:#fff}'
  + '</style>');

function vFmt(n){ return (n||0).toLocaleString('vi-VN'); }
function vAge(m){
  if(m == null) return '';
  if(m < 60) return m + ' phút';
  const h = m/60;
  return h < 24 ? h.toFixed(1).replace('.0','') + ' giờ' : (h/24).toFixed(1).replace('.0','') + ' ngày';
}
function vPick(kind, val){
  if(kind === 'topic') VF_TOPIC = val; else VF_STATUS = val;
  render();
}
async function vSet(url, status){
  await fetch('/api/viral?url=' + encodeURIComponent(url) + '&status=' + status,
              {method:'POST'});
  load();
}

function v_viral(d){
  const all = (d.viral && d.viral.videos) || [];
  const topics = ['tất cả'].concat((d.viral && d.viral.topics) || []);
  const rows = all.filter(v =>
    (VF_TOPIC === 'tất cả' || v.topic === VF_TOPIC) &&
    (VF_STATUS === 'tất cả' || (v.status || 'moi') === VF_STATUS));

  let h = '<div class="card"><div class="chead"><div>'
    + '<h2>Video viral trên X</h2><p class="sub">'
    + all.length + ' video trong danh sách · cập nhật ' + esc((d.viral && d.viral.updated) || '—')
    + ' · chỉ liệt kê, không tải, không đăng</p></div></div>'
    + '<div class="vfil">' + topics.map(t =>
        '<button class="' + (t === VF_TOPIC ? 'on' : '') + '" onclick="vPick(\'topic\',\''
        + t.replace(/'/g, "\\'") + '\')">' + esc(t) + '</button>').join('')
    + '</div><div class="vfil">' + ['moi','da_chon','da_lam','bo','tất cả'].map(s =>
        '<button class="' + (s === VF_STATUS ? 'on' : '') + '" onclick="vPick(\'status\',\''
        + s + '\')">' + esc(VST[s] || s) + '</button>').join('')
    + '</div></div>';

  if(!rows.length){
    return h + '<div class="card"><p class="sub">Không có video nào khớp bộ lọc.</p></div>';
  }

  h += '<div class="card">' + rows.map(v => {
    const st = v.status || 'moi';
    return '<div class="vv">'
      + (v.thumbnail
          ? '<a href="' + esc(v.url) + '" target="_blank" rel="noopener">'
            + '<img src="' + esc(v.thumbnail) + '" alt="" loading="lazy"></a>'
          : '<div class="no">không có ảnh</div>')
      + '<div>'
      + '<h3><a href="' + esc(v.url) + '" target="_blank" rel="noopener">'
      + esc(v.desc || v.text || v.url) + '</a></h3>'
      + '<p class="meta">' + esc(v.author) + ' · đăng ' + esc(v.posted_at || '')
      + ' (' + vAge(v.age_min) + ' trước) · ' + (v.duration_sec || 0) + ' giây · '
      + '<b>' + esc(v.topic || 'khác') + '</b> · '
      + (v.has_speech === true ? 'có lời nói, cần phụ đề'
         : v.has_speech === false ? 'không lời, chỉ cần hook' : 'chưa rõ lời nói')
      + '</p>'
      + '<div class="vnums">'
      + '<span><i>view</i> <b>' + vFmt(v.views) + '</b></span>'
      + '<span><i>thích</i> ' + vFmt(v.likes) + '</span>'
      + '<span><i>đăng lại</i> ' + vFmt(v.reposts) + '</span>'
      + '<span><i>trả lời</i> ' + vFmt(v.replies) + '</span>'
      + '<span><i>tăng</i> ' + vFmt(v.rate) + ' view/giờ</span>'
      + '</div>'
      + '<div class="vact">' + ['moi','da_chon','da_lam','bo'].map(s =>
          '<button class="' + (s === st ? 'on' : '') + '" onclick="vSet(\''
          + v.url + '\',\'' + s + '\')">' + VST[s] + '</button>').join('')
      + '</div></div></div>';
  }).join('') + '</div>';
  return h;
}
"""
