"""Dữ liệu thị trường trực tiếp, tính chỉ báo tại chỗ.

Thay cho reports/ của TradingAgents (bỏ ngày 14/11 theo yêu cầu chủ dự án). Lý do
thật sự: report đó là file chép tay từ dự án khác, không tự cập nhật, nên ngày
14/11 app vẫn phải dùng số liệu của 13/11.

Nguồn: yfinance (Yahoo Finance), không cần API key. Chỉ ĐỌC, không đặt lệnh gì.
Kết quả cache theo ngày ở posts/.state/market_YYYYMMDD.json để khỏi gọi lại nhiều lần.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import config

SYMBOLS = ("BTC-USD", "ETH-USD")
CACHE_MAX_AGE_MIN = 45


@dataclass
class Snapshot:
    symbol: str
    as_of: str                       # ISO, giờ của nến cuối
    fetched_at: str = ""
    close: float = 0.0
    prev_close: float = 0.0
    chg_1d_pct: float = 0.0
    chg_7d_pct: float = 0.0
    chg_30d_pct: float = 0.0
    high_30d: float = 0.0
    high_30d_date: str = ""
    low_30d: float = 0.0
    low_30d_date: str = ""
    rsi14: float = 0.0
    macd: float = 0.0
    macd_signal: float = 0.0
    macd_hist: float = 0.0
    sma20: float = 0.0
    sma50: float = 0.0
    sma200: float = 0.0
    ema10: float = 0.0
    bb_upper: float = 0.0
    bb_lower: float = 0.0
    atr14: float = 0.0
    volume: float = 0.0
    rsi_history: list[tuple[str, float]] = field(default_factory=list)
    closes: list[tuple[str, float]] = field(default_factory=list)   # 90 phiên cuối

    @property
    def levels(self) -> list[tuple[str, float]]:
        rows = [("BB lower", self.bb_lower), ("20 SMA", self.sma20),
                ("50 SMA", self.sma50), ("200 SMA", self.sma200),
                ("10 EMA", self.ema10), ("BB upper", self.bb_upper)]
        return sorted([(k, v) for k, v in rows if v], key=lambda x: x[1])


def _cache_path(day: str) -> Path:
    return config.STATE_DIR / f"market_{day}.json"


def _load_cache() -> dict | None:
    p = _cache_path(f"{config.now():%Y%m%d}")
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(data["fetched_at"])
        age_min = (config.now() - fetched).total_seconds() / 60
        return data if age_min < CACHE_MAX_AGE_MIN else None
    except Exception:
        return None


def _save_cache(data: dict) -> None:
    config.STATE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(f"{config.now():%Y%m%d}").write_text(
        json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def _indicators(df) -> dict:
    """RSI14 (Wilder), MACD(12,26,9), SMA/EMA, Bollinger(20,2), ATR14."""
    import pandas as pd  # noqa: F401  (yfinance kéo pandas về rồi)

    close = df["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    # Wilder dùng trung bình mũ với alpha = 1/14, không phải trung bình trượt.
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - 100 / (1 + rs)

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False).mean()

    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()

    tr = pd.concat([
        df["High"] - df["Low"],
        (df["High"] - close.shift()).abs(),
        (df["Low"] - close.shift()).abs(),
    ], axis=1).max(axis=1)

    return {
        "rsi": rsi, "macd": macd, "signal": signal, "hist": macd - signal,
        "sma20": sma20, "sma50": close.rolling(50).mean(),
        "sma200": close.rolling(200).mean(),
        "ema10": close.ewm(span=10, adjust=False).mean(),
        "bb_upper": sma20 + 2 * std20, "bb_lower": sma20 - 2 * std20,
        "atr": tr.ewm(alpha=1 / 14, adjust=False).mean(),
    }


def _f(series, i=-1) -> float:
    try:
        v = float(series.iloc[i])
        return 0.0 if v != v else round(v, 2)       # NaN -> 0
    except Exception:
        return 0.0


def fetch(symbol: str) -> Snapshot | None:
    """Một ảnh chụp thị trường cho 1 mã. None nếu không lấy được dữ liệu."""
    try:
        import yfinance as yf
        df = yf.download(symbol, period="1y", interval="1d",
                         auto_adjust=False, progress=False)
    except Exception:
        return None
    if df is None or len(df) < 60:
        return None
    if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
        df.columns = df.columns.get_level_values(0)   # yfinance trả cột 2 tầng

    ind = _indicators(df)
    close = df["Close"]
    last_30 = df.tail(30)
    hi_i = last_30["High"].idxmax()
    lo_i = last_30["Low"].idxmin()

    def pct(back: int) -> float:
        if len(close) <= back:
            return 0.0
        a, b = float(close.iloc[-1]), float(close.iloc[-1 - back])
        return round((a - b) / b * 100, 2) if b else 0.0

    snap = Snapshot(
        symbol=symbol,
        as_of=df.index[-1].to_pydatetime().replace(tzinfo=timezone.utc).isoformat(),
        fetched_at=config.now().isoformat(),
        close=_f(close), prev_close=_f(close, -2),
        chg_1d_pct=pct(1), chg_7d_pct=pct(7), chg_30d_pct=pct(30),
        high_30d=round(float(last_30["High"].max()), 2),
        high_30d_date=f"{hi_i:%d %b}",
        low_30d=round(float(last_30["Low"].min()), 2),
        low_30d_date=f"{lo_i:%d %b}",
        rsi14=_f(ind["rsi"]), macd=_f(ind["macd"]),
        macd_signal=_f(ind["signal"]), macd_hist=_f(ind["hist"]),
        sma20=_f(ind["sma20"]), sma50=_f(ind["sma50"]), sma200=_f(ind["sma200"]),
        ema10=_f(ind["ema10"]), bb_upper=_f(ind["bb_upper"]),
        bb_lower=_f(ind["bb_lower"]), atr14=_f(ind["atr"]),
        volume=float(df["Volume"].iloc[-1]),
        rsi_history=[(f"{d:%d %b}", round(float(v), 2))
                     for d, v in ind["rsi"].tail(14).items() if v == v],
        closes=[(f"{d:%Y-%m-%d}", round(float(v), 2))
                for d, v in close.tail(90).items()],
    )
    return snap


def get(symbols: tuple[str, ...] = SYMBOLS, refresh: bool = False) -> list[Snapshot]:
    """Ảnh chụp cho các mã, dùng cache trong ngày nếu còn mới."""
    if not refresh:
        cached = _load_cache()
        if cached:
            return [Snapshot(**s) for s in cached.get("snapshots", [])]

    snaps = [s for sym in symbols if (s := fetch(sym))]
    if snaps:
        _save_cache({"fetched_at": config.now().isoformat(),
                     "snapshots": [asdict(s) for s in snaps]})
    return snaps


def primary() -> Snapshot | None:
    snaps = get()
    return snaps[0] if snaps else None


def as_prompt_block(snaps: list[Snapshot]) -> str:
    """Khối số liệu để nhét vào prompt. Ghi rõ ngày của từng con số."""
    if not snaps:
        return "(no market data available — do not invent figures)"
    out = []
    for s in snaps:
        day = s.as_of[:10]
        out.append(
            f"{s.symbol} — daily candle for {day} (UTC)\n"
            f"  close ${s.close:,.2f}  ({s.chg_1d_pct:+.2f}% 1d, "
            f"{s.chg_7d_pct:+.2f}% 7d, {s.chg_30d_pct:+.2f}% 30d)\n"
            f"  30d high ${s.high_30d:,.2f} ({s.high_30d_date}), "
            f"30d low ${s.low_30d:,.2f} ({s.low_30d_date})\n"
            f"  RSI14 {s.rsi14}   MACD {s.macd} vs signal {s.macd_signal} "
            f"(hist {s.macd_hist})\n"
            f"  10 EMA ${s.ema10:,.2f}  20 SMA ${s.sma20:,.2f}  "
            f"50 SMA ${s.sma50:,.2f}  200 SMA ${s.sma200:,.2f}\n"
            f"  Bollinger ${s.bb_lower:,.2f} – ${s.bb_upper:,.2f}   "
            f"ATR14 {s.atr14}"
        )
    return "\n\n".join(out)


if __name__ == "__main__":
    for s in get(refresh=True):
        print(f"{s.symbol} {s.as_of[:10]} close {s.close:,.2f} "
              f"({s.chg_1d_pct:+.2f}%) RSI {s.rsi14} MACD {s.macd}")


# --- tương quan: dùng cho ảnh minh hoạ bài lập luận (pillar take) -------------
# Thêm 14/11. Bài take không được đọc chỉ báo, nhưng KHÔNG có nghĩa là không
# được có số. Một luận điểm kiểu "token AI đi theo crypto chứ không theo AI" đo
# được: tương quan lợi suất ngày với BTC so với với NVDA.
AI_TOKENS = ("FET-USD", "TAO22974-USD", "NEAR-USD", "ICP-USD")
AI_LABELS = {"FET-USD": "FET", "TAO22974-USD": "TAO", "NEAR-USD": "NEAR",
             "ICP-USD": "ICP"}


def correlations(tokens=AI_TOKENS, vs=("BTC-USD", "NVDA"), days: int = 90):
    """Tương quan lợi suất ngày của từng token với từng mốc so sánh.

    Chỉ giữ phiên nào CẢ chứng khoán lẫn crypto cùng có dữ liệu — crypto chạy
    7 ngày/tuần, NVDA thì không, không căn thì tương quan ra sai.
    Trả (rows, n_phien, as_of) hoặc (None, 0, "") nếu thiếu dữ liệu.
    """
    import yfinance as yf
    tickers = list(tokens) + list(vs)
    try:
        d = yf.download(tickers, period="6mo", interval="1d",
                        progress=False, auto_adjust=True)["Close"]
    except Exception:
        return None, 0, ""
    d = d.dropna(axis=1, how="all").dropna(how="any")
    have = [t for t in tokens if t in d.columns]
    vs = [v for v in vs if v in d.columns]
    if len(d) < 30 or not have or len(vs) < 2:
        return None, 0, ""
    r = d.pct_change().dropna().tail(days)
    rows = []
    for t in have:
        rows.append({
            "token": AI_LABELS.get(t, t.split("-")[0]),
            "corr": {v: float(r[t].corr(r[v])) for v in vs},
            "chg": float(d[t].iloc[-1] / d[t].iloc[-len(r)] - 1) * 100,
        })
    return rows, len(r), str(d.index[-1])[:10]
