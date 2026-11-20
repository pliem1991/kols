"""Ảnh dạy chiến lược trading: EMA 50/200 cắt nhau, RSI phân kỳ.

Khác hẳn app/chart.py: những ảnh kia nói "thị trường ĐANG thế này", ảnh ở đây
nói "cái mẫu hình người ta hay nhắc TRÔNG như thế này". Chủ dự án yêu cầu
18/11: bài giải thích chiến lược, có hình càng tốt.

Hai luật tự đặt cho module này:

1. KHÔNG vẽ mẫu hình bịa. Mỗi ảnh phải tìm được ví dụ THẬT trong dữ liệu giá
   thật; không tìm được thì trả None và bài đăng không ảnh. Vẽ một đường cong
   minh hoạ rồi dán nhãn "golden cross" là nói dối người đọc.
2. Ảnh luôn ghi rõ mẫu hình này sai thường xuyên, và luôn mang dòng "Not
   financial advice." — xem workflows/compliance.md. Dạy cách đọc một chỉ báo
   là kiến thức; nói nó báo mua là call kèo.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from . import config
from .chart import ACCENT, BG, DOWN, FG, GRID, MUTED, UP, m

GOLD = "#d29922"
PURPLE = "#bc8cff"

FOOT = ("A real example from price history, not an illustration.   ·   "
        "These patterns fail often.   ·   Data: Yahoo Finance.   ·   "
        "AI-generated chart.   ·   Not financial advice.")


def _ema(vals: list[float], span: int) -> list[float]:
    k = 2.0 / (span + 1.0)
    out: list[float] = []
    cur = None
    for v in vals:
        cur = v if cur is None else v * k + cur * (1.0 - k)
        out.append(cur)
    return out


def _rsi(vals: list[float], n: int = 14) -> list[float]:
    """RSI kiểu Wilder, cùng cách tính với app/market.py."""
    out = [50.0] * len(vals)
    if len(vals) < n + 1:
        return out
    gains = losses = 0.0
    for i in range(1, n + 1):
        d = vals[i] - vals[i - 1]
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    ag, al = gains / n, losses / n
    for i in range(n + 1, len(vals)):
        d = vals[i] - vals[i - 1]
        ag = (ag * (n - 1) + max(d, 0.0)) / n
        al = (al * (n - 1) + max(-d, 0.0)) / n
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _series(symbol: str, period: str = "2y"):
    """(nhãn ngày, giá đóng cửa). Trả ([], []) nếu không lấy được."""
    try:
        import yfinance as yf
        df = yf.download(symbol, period=period, interval="1d",
                         auto_adjust=False, progress=False)
    except Exception:
        return [], []
    if df is None or len(df) < 60:
        return [], []
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)
    close = df["Close"]
    return ([f"{d:%d %b %y}" for d in close.index],
            [float(v) for v in close.to_list()])


def _frame(ax, title: str) -> None:
    ax.set_facecolor(BG)
    ax.set_title(title, color=FG, fontsize=17, pad=14, loc="left")
    ax.tick_params(colors=MUTED, labelsize=11.5)
    ax.grid(color=GRID, lw=1)
    for s in ax.spines.values():
        s.set_visible(False)


def _xticks(ax, labels: list[str], n: int = 6) -> None:
    step = max(1, len(labels) // n)
    ax.set_xticks(range(0, len(labels), step))
    ax.set_xticklabels(labels[::step], rotation=20, ha="right")


def _sma(vals: list[float], n: int) -> list[float]:
    out: list[float] = []
    run = 0.0
    for i, v in enumerate(vals):
        run += v
        if i >= n:
            run -= vals[i - n]
        out.append(run / min(i + 1, n))
    return out


def _crosses(fast: list[float], slow: list[float],
             start: int) -> list[tuple[int, bool]]:
    out = []
    for i in range(start, len(fast)):
        up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
        dn = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
        if up or dn:
            out.append((i, up))
    return out


def cross_card(symbol: str = "BTC-USD",
               out_path: Path | None = None) -> Path | None:
    """Golden Cross / Death Cross — lần cắt THẬT gần nhất, không có thì bỏ.

    Vẽ bằng SMA 50/200 chứ không phải EMA: bản kinh điển của hai cái tên này
    dùng trung bình ĐƠN GIẢN 50 và 200 phiên. Bản EMA cũng phổ biến và cắt sớm
    hơn vài ngày, nên ngày cắt của bản EMA được ghi ở chân ảnh thay vì vẽ thêm
    hai đường nữa cho rối.
    """
    labels, closes = _series(symbol, "2y")
    if len(closes) < 260:
        return None
    e50, e200 = _sma(closes, 50), _sma(closes, 200)

    crosses = _crosses(e50, e200, 210)
    ema_crosses = _crosses(_ema(closes, 50), _ema(closes, 200), 210)
    if not crosses:
        return None

    last = crosses[-1][0]
    lo = max(205, last - 150)
    hi = min(len(closes), last + 120)
    if hi - lo < 60:
        lo = max(205, hi - 160)
    shown = [c for c in crosses if lo <= c[0] < hi]

    out = out_path or (config.POSTS / "img"
                       / f"strategy-cross_{symbol}_{labels[-1].replace(' ', '')}.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.07, 0.24, 0.88, 0.56])
    x = range(hi - lo)
    ax.plot(x, closes[lo:hi], color=MUTED, lw=1.6, alpha=0.65, label=symbol)
    ax.plot(x, e50[lo:hi], color=PURPLE, lw=2.6, label="50-day average (fast)")
    ax.plot(x, e200[lo:hi], color=GOLD, lw=2.6, label="200-day average (slow)")

    for i, up in shown:
        px = i - lo
        ax.axvline(px, color=UP if up else DOWN, lw=1.3, ls="--", alpha=0.75)
        ax.scatter([px], [e50[i]], s=120, zorder=5,
                   color=UP if up else DOWN, edgecolor=BG, linewidth=1.5)
        # Nhãn sát mép phải bị cắt mất chữ -> đẩy ngược vào trong.
        span = max(hi - lo, 1)
        side = "right" if px > span * 0.82 else (
            "left" if px < span * 0.18 else "center")
        ax.annotate("Golden Cross" if up else "Death Cross",
                    xy=(px, e50[i]), color=UP if up else DOWN,
                    fontsize=14.5, fontweight="bold", ha=side,
                    va="bottom" if up else "top")

    _frame(ax, f"Golden Cross and Death Cross  ·  50 vs 200-day average  ·  {symbol}")
    _xticks(ax, labels[lo:hi])
    ax.yaxis.set_major_formatter(lambda v, _: m(v))
    leg = ax.legend(loc="upper left", frameon=False, fontsize=13.5)
    for t in leg.get_texts():
        t.set_color(FG)

    marked = ", ".join(f"{labels[i]} ({'Golden' if up else 'Death'})"
                       for i, up in shown) or labels[crosses[-1][0]]
    near = [f"{labels[i]} ({'Golden' if up else 'Death'})"
            for i, up in ema_crosses if lo <= i < hi]
    fig.text(0.07, 0.15,
             "Fast average above slow is called a Golden Cross; below it, a Death "
             "Cross. Both are drawn from past prices, so both arrive late.",
             color=FG, fontsize=14.5, va="top")
    fig.text(0.07, 0.105,
             f"Marked here: {marked}."
             + (f"   Same signal on exponential averages (EMA): {', '.join(near)}."
                if near else ""),
             color=MUTED, fontsize=13.5, va="top")
    fig.text(0.07, 0.055, FOOT, color=MUTED, fontsize=12.5, va="top")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def _swings(vals: list[float], w: int = 5, high: bool = True) -> list[int]:
    out = []
    for i in range(w, len(vals) - w):
        win = vals[i - w:i + w + 1]
        if (high and vals[i] == max(win)) or (not high and vals[i] == min(win)):
            if not out or i - out[-1] > w:
                out.append(i)
    return out


def rsi_divergence_card(symbol: str = "BTC-USD",
                        out_path: Path | None = None) -> Path | None:
    """Giá tạo đỉnh cao hơn mà RSI tạo đỉnh thấp hơn (hoặc ngược lại).

    Tìm ví dụ thật trong 1 năm gần nhất; không có thì trả None.
    """
    labels, closes = _series(symbol, "1y")
    if len(closes) < 120:
        return None
    rsi = _rsi(closes)

    found = None          # (i1, i2, bearish)
    for bear in (True, False):
        idx = _swings(closes, 5, high=bear)
        idx = [i for i in idx if i > 30]
        for a, b in zip(idx, idx[1:]):
            if not (12 <= b - a <= 90):
                continue
            if bear and closes[b] > closes[a] * 1.01 and rsi[b] < rsi[a] - 3:
                found = (a, b, True)
            if not bear and closes[b] < closes[a] * 0.99 and rsi[b] > rsi[a] + 3:
                found = (a, b, False)
    if not found:
        return None
    i1, i2, bear = found
    lo = max(0, i1 - 35)
    hi = min(len(closes), i2 + 35)

    out = out_path or (config.POSTS / "img"
                       / f"strategy-rsidiv_{symbol}_{labels[-1].replace(' ', '')}.png")
    out.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(16, 9), dpi=100, facecolor=BG)
    ax = fig.add_axes([0.07, 0.50, 0.88, 0.33])
    axr = fig.add_axes([0.07, 0.24, 0.88, 0.20])
    x = list(range(hi - lo))
    colour = DOWN if bear else UP

    ax.plot(x, closes[lo:hi], color=ACCENT, lw=2.4)
    for i in (i1, i2):
        ax.scatter([i - lo], [closes[i]], s=130, color=colour,
                   edgecolor=BG, linewidth=1.5, zorder=5)
    ax.plot([i1 - lo, i2 - lo], [closes[i1], closes[i2]],
            color=colour, lw=2, ls="--")
    ax.annotate("higher high" if bear else "lower low",
                xy=(i2 - lo, closes[i2]), color=colour, fontsize=14,
                fontweight="bold", ha="center",
                va="bottom" if bear else "top")
    _frame(ax, f"Price and its RSI disagreeing  ·  {symbol}")
    ax.set_xticks([])
    ax.yaxis.set_major_formatter(lambda v, _: m(v))

    axr.plot(x, rsi[lo:hi], color=FG, lw=2.2)
    axr.axhline(30, color=UP, lw=1.2, ls="--", alpha=0.8)
    axr.axhline(70, color=DOWN, lw=1.2, ls="--", alpha=0.8)
    for i in (i1, i2):
        axr.scatter([i - lo], [rsi[i]], s=130, color=colour,
                    edgecolor=BG, linewidth=1.5, zorder=5)
    axr.plot([i1 - lo, i2 - lo], [rsi[i1], rsi[i2]], color=colour, lw=2, ls="--")
    axr.annotate("lower high" if bear else "higher low",
                 xy=(i2 - lo, rsi[i2]), color=colour, fontsize=14,
                 fontweight="bold", ha="center",
                 va="top" if bear else "bottom")
    _frame(axr, "RSI 14 — how fast the price has been rising or falling")
    _xticks(axr, labels[lo:hi])

    line = ("Price made a higher high while RSI made a lower one: the move up "
            "lost speed."
            if bear else
            "Price made a lower low while RSI made a higher one: the move down "
            "lost speed.")
    fig.text(0.07, 0.16, line, color=FG, fontsize=14.5, va="top")
    fig.text(0.07, 0.115,
             f"Seen here between {labels[i1]} and {labels[i2]}. "
             "Losing speed is not the same as turning around.",
             color=MUTED, fontsize=13.5, va="top")
    fig.text(0.07, 0.055, FOOT, color=MUTED, fontsize=12.5, va="top")
    fig.savefig(out, facecolor=BG)
    plt.close(fig)
    return out


def card_for(text: str, symbol: str = "BTC-USD") -> Path | None:
    """Chọn ảnh theo CHÍNH chữ trong bài, không theo chủ đề chung.

    Cùng lý do với biểu đồ trend (sửa 16/11): gắn ảnh nói chuyện khác bài là
    tự làm hỏng bài. Bài nói về mẫu hình nào thì vẽ mẫu hình đó, còn không thì
    đăng chay.
    """
    low = text.lower()
    if "diverg" in low or ("rsi" in low and "cross" not in low):
        return rsi_divergence_card(symbol)
    if ("golden cross" in low or "death cross" in low or "ema" in low
            or "moving average" in low or "cross" in low
            or "50-day" in low or "200-day" in low):
        return cross_card(symbol)
    return None


# Tên cũ, giữ lại cho chỗ nào còn gọi. Ảnh vẽ bằng SMA chứ không phải EMA.
ema_cross_card = cross_card
