"""Sinh ảnh biểu đồ từ dữ liệu thị trường lấy trực tiếp (app/market.py).

Vẽ bằng matplotlib, không mở browser, không watermark, không phải cắt gì. Cùng
input ra cùng ảnh.

Trước ngày 14/11 module này đọc reports/ của TradingAgents, mà report đó không có
chuỗi giá nên chỉ vẽ được thang mốc. Giờ có 90 phiên gần nhất nên vẽ đường giá thật.

Luật ảnh (workflows/compliance.md): các mốc là QUAN SÁT, không phải điểm vào hay
giá mục tiêu. Ảnh luôn mang dòng "Not financial advice." và nói rõ do AI tạo.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")                     # không cần màn hình
import matplotlib.pyplot as plt

from . import config, market

# Bảng màu tối, đọc được cả khi X hiển thị ở chế độ sáng.
BG = "#0d1117"
FG = "#e6edf3"
MUTED = "#8b949e"
GRID = "#21262d"
UP = "#3fb950"
DOWN = "#f85149"
ACCENT = "#58a6ff"

def m(v: float, dec: int = 0) -> str:
    r"""Tiền tệ cho matplotlib.

    Hai dấu $ trong cùng một chuỗi bị matplotlib hiểu là công thức toán và in ra
    chữ nghiêng kiểu LaTeX (gặp 14/11: dòng "30-day range $66,536–$84,840" ra
    thành chữ nghiêng dính liền). Phải escape thành \$.
    """
    return f"\\${v:,.{dec}f}"


LEVEL_COLOURS = {
    "200 SMA": "#d29922", "50 SMA": "#bc8cff", "20 SMA": "#6e7681",
    "10 EMA": "#39c5cf", "BB lower": "#3fb950", "BB upper": "#f85149",
}


def render(snap: market.Snapshot, out_path: Path) -> Path:
    """Đường giá 90 phiên + các mốc kỹ thuật + panel RSI."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    closes = snap.closes or []
    has_rsi = len(snap.rsi_history) >= 3

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.055, 0.30, 0.62, 0.50])
    ax_rsi = fig.add_axes([0.74, 0.30, 0.215, 0.50]) if has_rsi else None

    # --- tiêu đề: nói về THỊ TRƯỜNG, không nói về công cụ vẽ ra nó
    day = snap.as_of[:10]
    try:
        day = f"{datetime.fromisoformat(snap.as_of):%d %b %Y}"
    except Exception:
        pass
    fig.text(0.055, 0.935, f"{snap.symbol} — price and levels", color=FG,
             fontsize=26, fontweight="bold", va="top")
    chg_col = UP if snap.chg_1d_pct >= 0 else DOWN
    fig.text(0.055, 0.874, f"Daily candles through {day}", color=MUTED,
             fontsize=14.5, va="top")
    fig.text(0.40, 0.874, m(snap.close), color=FG, fontsize=15,
             fontweight="bold", va="top")
    fig.text(0.47, 0.874, f"{snap.chg_1d_pct:+.2f}% 1d   "
             f"{snap.chg_7d_pct:+.2f}% 7d   {snap.chg_30d_pct:+.2f}% 30d",
             color=chg_col, fontsize=14.5, va="top")

    # --- đường giá
    ax.set_facecolor(BG)
    if closes:
        xs = list(range(len(closes)))
        ys = [v for _, v in closes]
        ax.plot(xs, ys, color=ACCENT, lw=2.3, zorder=5)
        ax.fill_between(xs, min(ys) * 0.985, ys, color=ACCENT, alpha=0.07, zorder=2)
        ax.scatter([xs[-1]], [ys[-1]], s=70, color=ACCENT, zorder=6)

        # Đường kẻ DỪNG trước lề phải, nhãn nằm trong lề đó — vẽ axhline suốt
        # chiều ngang thì gạch ngang qua chữ.
        rows = [(lab, v) for lab, v in snap.levels if v]
        lo_all = min([*(v for _, v in rows), min(ys)])
        hi_all = max([*(v for _, v in rows), max(ys)])
        min_gap = (hi_all - lo_all) * 0.042          # khoảng cách tối thiểu giữa 2 nhãn
        label_x = len(xs) + len(xs) * 0.02
        last_y = None
        for label, value in rows:
            col = LEVEL_COLOURS.get(label, MUTED)
            ax.plot([0, len(xs) - 1], [value, value], color=col, lw=1.5,
                    ls="--", alpha=0.85, zorder=3)
            ty = value
            if last_y is not None and ty - last_y < min_gap:
                ty = last_y + min_gap             # đẩy nhãn lên cho khỏi chồng
            last_y = ty
            ax.plot([len(xs) - 1, label_x], [value, ty], color=col, lw=0.9,
                    alpha=0.5, zorder=3)
            ax.text(label_x + len(xs) * 0.01, ty,
                    f"{label} {m(value)}", color=col, fontsize=12.5,
                    va="center", ha="left")

        # Nhãn trục x: khoảng 6 mốc ngày, đọc được
        step = max(1, len(closes) // 6)
        ticks = xs[::step]
        ax.set_xticks(ticks)
        ax.set_xticklabels(
            [f"{datetime.fromisoformat(closes[i][0]):%d %b}" for i in ticks],
            rotation=0)
        ax.set_xlim(0, len(xs) + len(xs) * 0.34)   # chừa chỗ cho nhãn mốc

        lo = min(min(ys), *(v for _, v in snap.levels if v))
        hi = max(max(ys), *(v for _, v in snap.levels if v))
        pad = (hi - lo) * 0.08 or hi * 0.02
        ax.set_ylim(lo - pad, hi + pad)

    ax.yaxis.set_major_formatter(lambda v, _: m(v))
    ax.tick_params(colors=MUTED, labelsize=12)
    ax.grid(color=GRID, lw=1)
    for s in ax.spines.values():
        s.set_visible(False)

    # --- panel RSI
    if ax_rsi is not None:
        ax_rsi.set_facecolor(BG)
        labels = [k for k, _ in snap.rsi_history]
        vals = [v for _, v in snap.rsi_history]
        ax_rsi.plot(range(len(vals)), vals, color=ACCENT, lw=2.4, marker="o", ms=5)
        ax_rsi.axhline(30, color=UP, lw=1.4, ls="--", alpha=0.85)
        ax_rsi.axhline(70, color=DOWN, lw=1.4, ls="--", alpha=0.85)
        ax_rsi.text(0, 31, "30", color=UP, fontsize=11, va="bottom")
        ax_rsi.text(0, 71, "70", color=DOWN, fontsize=11, va="bottom")
        step = max(1, len(labels) // 5)
        ax_rsi.set_xticks(range(0, len(labels), step))
        ax_rsi.set_xticklabels(labels[::step], rotation=30, ha="right")
        ax_rsi.set_ylim(min(15, min(vals) - 6), max(75, max(vals) + 6))
        ax_rsi.set_title("RSI 14", color=FG, fontsize=15, pad=12, loc="left")
        ax_rsi.tick_params(colors=MUTED, labelsize=11.5)
        ax_rsi.grid(color=GRID, lw=1)
        for s in ax_rsi.spines.values():
            s.set_visible(False)
        ax_rsi.text(len(vals) - 1, vals[-1], f"  {vals[-1]:.1f}", color=ACCENT,
                    fontsize=13.5, fontweight="bold", va="center")

    # --- chân ảnh
    extra = (f"30-day range {m(snap.low_30d)} ({snap.low_30d_date}) – "
             f"{m(snap.high_30d)} ({snap.high_30d_date})"
             f"     MACD {snap.macd:,.0f} vs signal {snap.macd_signal:,.0f}"
             f"     ATR14 {snap.atr14:,.0f}")
    fig.text(0.055, 0.185, extra, color=FG, fontsize=14, va="top")
    fig.text(0.055, 0.092,
             "Levels are observations, not entries or targets.   ·   "
             "Data: Yahoo Finance.   ·   AI-generated chart.   ·   "
             "Not financial advice.", color=MUTED, fontsize=13, va="top")

    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path


def latest_card(out_path: Path | None = None, symbol: str = "") -> Path | None:
    """Vẽ ảnh từ dữ liệu thị trường mới nhất. None nếu không lấy được dữ liệu.

    `symbol` là mã mà BÀI đang nói tới — thêm 15/11. Trước đó luôn lấy mã đầu
    danh sách (BTC), nên bài viết về ETH vẫn kèm chart BTC.
    """
    snaps = [s for s in market.get() if s.closes]
    if not snaps:
        return None
    snap = next((s for s in snaps if s.symbol == symbol), snaps[0])
    out = out_path or (config.POSTS / "img"
                       / f"{snap.symbol}_{snap.as_of[:10]}.png")
    return render(snap, out)


def corr_card(out_path: Path | None = None) -> Path | None:
    """Ảnh cho bài lập luận: token AI bám BTC hay bám NVDA?

    Thêm 14/11. Trước đó chỉ vẽ được biểu đồ giá, nên bài nào không có số liệu
    thị trường là không có ảnh — mà đúng những bài đó mới cần hình để người ta
    dừng lại. Ảnh này KHÔNG phải trang trí: nó là bằng chứng của luận điểm.
    """
    rows, n, as_of = market.correlations()
    if not rows:
        return None
    out = out_path or (config.POSTS / "img" / f"ai-tokens-corr_{as_of}.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.10, 0.26, 0.84, 0.50], facecolor=BG)

    labels = [r["token"] for r in rows][::-1]
    btc = [r["corr"]["BTC-USD"] for r in rows][::-1]
    nvda = [r["corr"]["NVDA"] for r in rows][::-1]
    y = range(len(labels))
    h = 0.36
    # Nhãn trong ảnh luôn tiếng Anh — ảnh đăng lên X cho người đọc tiếng Anh,
    # bản tiếng Việt chỉ nằm trên trang duyệt của mình.
    ax.barh([i + h / 2 for i in y], btc, height=h, color=ACCENT, label="vs BTC")
    ax.barh([i - h / 2 for i in y], nvda, height=h, color="#d29922",
            label="vs NVDA")
    for i, (b, nv) in enumerate(zip(btc, nvda)):
        ax.text(b + 0.012, i + h / 2, f"{b:.2f}", color=FG, fontsize=15,
                va="center")
        ax.text(nv + 0.012, i - h / 2, f"{nv:.2f}", color=FG, fontsize=15,
                va="center")

    ax.set_yticks(list(y)); ax.set_yticklabels(labels, color=FG, fontsize=17)
    ax.set_xlim(0, max(btc + nvda) * 1.18)
    ax.tick_params(colors=MUTED, labelsize=13)
    ax.set_xlabel("Daily-return correlation, last 90 sessions",
                  color=MUTED, fontsize=14, labelpad=10)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    leg = ax.legend(loc="lower right", frameon=False, fontsize=15)
    for t in leg.get_texts():
        t.set_color(FG)

    fig.text(0.10, 0.90, "AI tokens still trade with crypto, not with AI",
             color=FG, fontsize=30, va="top", weight="bold")
    fig.text(0.10, 0.835,
             f"Correlation of daily returns, {n} sessions through {as_of}",
             color=MUTED, fontsize=16, va="top")
    fig.text(0.10, 0.15,
             "Correlation is co-movement, not cause — and it shifts over time.",
             color=FG, fontsize=14, va="top")
    fig.text(0.10, 0.085,
             "Data: Yahoo Finance.   ·   AI-generated chart.   ·   "
             "Not financial advice.", color=MUTED, fontsize=13, va="top")

    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def flow_card(title: str, steps: list[str], loop: bool = False,
              note: str = "", out_path: Path | None = None) -> Path | None:
    """Sơ đồ cơ chế cho bài explainer: 3-5 bước, có thể nối vòng.

    Thêm 14/11. explainer cố ý không có số liệu nên trước giờ luôn ra bài không
    ảnh — mà đúng loại bài này lại dễ vẽ nhất: nó MÔ TẢ một chuỗi bước. Bài
    "liquidation cascade" tối nay là vòng lặp 4 bước, đọc chữ chậm hơn nhìn hình.
    """
    steps = [s.strip() for s in steps if s and s.strip()][:5]
    if len(steps) < 3:
        return None
    out = out_path or (config.POSTS / "img"
                       / f"flow_{config.now():%Y%m%d-%H%M%S}.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    import textwrap
    n = len(steps)
    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0, 0, 1, 1], facecolor=BG)
    ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")

    fig.text(0.055, 0.90, title[:70], color=FG, fontsize=30, va="top",
             weight="bold")

    top, bot = 70.0, 44.0
    gap = 3.2
    w = (92.0 - gap * (n - 1)) / n
    centres = []
    for i, s in enumerate(steps):
        x = 4.0 + i * (w + gap)
        ax.add_patch(plt.Rectangle((x, bot), w, top - bot, facecolor="#161b22",
                                   edgecolor=ACCENT if i == 0 else GRID, lw=2,
                                   zorder=2))
        ax.text(x + w / 2, top - 5.0, str(i + 1), color=MUTED, fontsize=15,
                ha="center", va="top", zorder=3)
        ax.text(x + w / 2, (top + bot) / 2 - 1.5,
                "\n".join(textwrap.wrap(s, max(14, int(w * 0.62)))),
                color=FG, fontsize=17, ha="center", va="center", zorder=3)
        centres.append((x, x + w))
        if i:
            ax.annotate("", xy=(x - 0.6, (top + bot) / 2),
                        xytext=(centres[i - 1][1] + 0.6, (top + bot) / 2),
                        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=2.2))

    if loop:
        # Mũi tên vòng về bước 1 — đó mới là điểm của một feedback loop.
        # fraction tính theo khoảng cách GIỮA hai đầu (gần hết chiều ngang),
        # nên 0.22 kéo mũi tên xuống tận chân hình, đè lên dòng chú thích.
        ax.annotate("", xy=(centres[0][0] + w / 2, bot - 0.6),
                    xytext=(centres[-1][0] + w / 2, bot - 0.6),
                    arrowprops=dict(arrowstyle="-|>", color=DOWN, lw=2.2,
                                    connectionstyle="bar,fraction=-0.085"))
        ax.text(50, bot - 18.0, "then it repeats",
                color=DOWN, fontsize=16, ha="center", va="top")

    if note:
        fig.text(0.055, 0.185, note[:120], color=FG, fontsize=15, va="top")
    fig.text(0.055, 0.075,
             "Mechanism, not a prediction.   ·   AI-generated diagram.   ·   "
             "Not financial advice.", color=MUTED, fontsize=13, va="top")

    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def trend_card(trends: list[dict], out_path: Path | None = None) -> Path | None:
    """Bao nhiêu tài khoản RIÊNG BIỆT đang nhắc tới mỗi chủ đề.

    Đây là số mình tự đo (app/scan.py), không phải bảng trending của X — nên
    nó nói được điều bảng kia không nói: mức độ lan trong đúng giới của mình.
    """
    rows = [t for t in (trends or []) if t.get("accounts", 0) >= 2][:8]
    if len(rows) < 3:
        return None
    # Biểu đồ cột mà mọi cột bằng nhau thì không nói gì cả. Gặp 15/11: tám chủ
    # đề, cột nào cũng đúng 2 tài khoản — người xem không rút ra được thứ tự
    # nào. Cần ít nhất một chủ đề nhô hẳn lên, và phải có chênh lệch.
    vals = [t["accounts"] for t in rows]
    if max(vals) < 3 or max(vals) == min(vals):
        return None
    out = out_path or (config.POSTS / "img"
                       / f"trend_{config.now():%Y%m%d}.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.26, 0.24, 0.68, 0.52], facecolor=BG)
    labels = [t["term"] for t in rows][::-1]
    vals = [t["accounts"] for t in rows][::-1]
    ax.barh(range(len(labels)), vals, color=ACCENT, height=0.6)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.015, i, str(v), color=FG, fontsize=16,
                va="center")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, color=FG, fontsize=17)
    ax.set_xlim(0, max(vals) * 1.15)
    ax.set_xticks(range(0, max(vals) + 1))
    ax.tick_params(colors=MUTED, labelsize=13)
    ax.set_xlabel("separate accounts posting about it", color=MUTED,
                  fontsize=14, labelpad=10)
    for s in ax.spines.values():
        s.set_color(GRID)
    ax.grid(axis="x", color=GRID, lw=0.8)
    ax.set_axisbelow(True)

    fig.text(0.055, 0.90, "What the timeline is actually on today",
             color=FG, fontsize=30, va="top", weight="bold")
    fig.text(0.055, 0.835,
             f"Distinct accounts per topic, last 12 hours, "
             f"{config.now():%d %b %Y}", color=MUTED, fontsize=16, va="top")
    fig.text(0.055, 0.14,
             "Counted by accounts, not mentions — one person posting five times "
             "is not a trend.", color=FG, fontsize=14, va="top")
    fig.text(0.055, 0.075,
             "Measured from a fixed list of accounts.   ·   AI-generated chart."
             "   ·   Not financial advice.", color=MUTED, fontsize=13, va="top")

    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


if __name__ == "__main__":
    import sys
    if "--corr" in sys.argv:
        print(corr_card() or "không lấy được dữ liệu tương quan")
        raise SystemExit
    p = latest_card()
    print(p or "không lấy được dữ liệu thị trường để vẽ")
