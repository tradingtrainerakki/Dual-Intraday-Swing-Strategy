import time
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Market Detective Pro", page_icon="🕵️", layout="wide")

# ==================== STOCK UNIVERSE ====================
# Note: Tata Motors demerged (TMPV / TMCV) and Zomato is now Eternal.
# If any ticker fails, the app lists it under "Failed tickers".
STOCK_UNIVERSE = [
    "TMPV.NS", "TMCV.NS", "RELIANCE.NS", "SBIN.NS", "ICICIBANK.NS",
    "TCS.NS", "INFY.NS", "HDFCBANK.NS", "M&M.NS", "BAJFINANCE.NS",
    "TATASTEEL.NS", "IRFC.NS", "RVNL.NS", "ETERNAL.NS", "IREDA.NS",
    "SUZLON.NS", "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "WIPRO.NS",
    "HCLTECH.NS", "ADANIENT.NS", "ADANIPORTS.NS", "TITAN.NS", "ASIANPAINT.NS",
    "SUNPHARMA.NS", "BAJAJ-AUTO.NS", "MARUTI.NS", "ULTRACEMCO.NS", "POWERGRID.NS",
    "NTPC.NS", "ONGC.NS", "COALINDIA.NS", "GAIL.NS", "BPCL.NS",
    "IOC.NS", "BANKINDIA.NS", "PNB.NS", "CANBK.NS", "INDUSINDBK.NS",
    "FEDERALBNK.NS", "TATAPOWER.NS", "NHPC.NS", "SJVN.NS", "BEL.NS",
    "BHEL.NS", "HAL.NS", "MAZDOCK.NS", "COFORGE.NS", "LTIM.NS", "PERSISTENT.NS",
]

# Approximate sector P/E benchmarks (edit these whenever you like).
SECTOR_PE_BENCHMARK = {
    "Technology": 27.0,
    "Financial Services": 16.0,
    "Energy": 14.0,
    "Utilities": 18.0,
    "Industrials": 30.0,
    "Consumer Cyclical": 30.0,
    "Consumer Defensive": 40.0,
    "Basic Materials": 15.0,
    "Healthcare": 30.0,
    "Communication Services": 22.0,
    "Real Estate": 30.0,
}
DEFAULT_PE_BENCHMARK = 22.0
FINANCIAL_SECTORS = {"Financial Services"}

PAGES = ["📊 Scanner", "⭐ Watchlist", "📓 Journal", "ℹ️ About"]


# ==================== SESSION STATE ====================
def init_state():
    defaults = {
        "watchlist": [],
        "trades": [],
        "mode": "swing",
        "page": PAGES[0],
        "selected_stock": None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


def clear_selected():
    st.session_state.selected_stock = None


# ==================== SMALL HELPERS ====================
def safe_float(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if np.isnan(v) or np.isinf(v):
        return None
    return v


def fmt(v, nd=1, prefix="", suffix=""):
    if v is None:
        return "N/A"
    return f"{prefix}{v:.{nd}f}{suffix}"


def market_status():
    now = datetime.now(IST)
    open_t = now.replace(hour=9, minute=15, second=0, microsecond=0)
    close_t = now.replace(hour=15, minute=30, second=0, microsecond=0)
    if now.weekday() >= 5:
        return False, "बाज़ार बंद (वीकेंड)", now
    if open_t <= now <= close_t:
        return True, "बाज़ार खुला है", now
    return False, "बाज़ार बंद है", now


def calc_qty(price, sl, capital, risk_pct):
    if price is None or sl is None:
        return 0
    per_share = abs(price - sl)
    if per_share <= 0:
        return 0
    qty = int((capital * risk_pct / 100) // per_share)
    return max(0, min(qty, int(capital // price)))


# ==================== INDICATORS ====================
def rsi_wilder(close, n=14):
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)
    return rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)


def atr_wilder(df, n=14):
    prev_close = df["Close"].shift(1)
    tr = pd.concat(
        [
            df["High"] - df["Low"],
            (df["High"] - prev_close).abs(),
            (df["Low"] - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean()


def session_vwap(day_df):
    tp = (day_df["High"] + day_df["Low"] + day_df["Close"]) / 3
    cum_v = day_df["Volume"].cumsum().replace(0, np.nan)
    return (tp * day_df["Volume"]).cumsum() / cum_v


# ==================== PRICE DATA (BATCH DOWNLOAD) ====================
def _download(tickers, period, interval, retries=3):
    last_err = None
    for attempt in range(retries):
        try:
            df = yf.download(
                list(tickers),
                period=period,
                interval=interval,
                group_by="ticker",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            if df is not None and not df.empty:
                return df
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Yahoo से डेटा नहीं मिला ({last_err})")


def _split(df, tickers):
    out = {}
    if not isinstance(df.columns, pd.MultiIndex):
        return out
    level0 = set(df.columns.get_level_values(0))
    for t in tickers:
        if t in level0:
            d = df[t].dropna(subset=["Close"])
            if not d.empty:
                out[t] = d
    return out


def _to_ist(d):
    d = d.copy()
    if d.index.tz is None:
        d.index = d.index.tz_localize("UTC").tz_convert(IST)
    else:
        d.index = d.index.tz_convert(IST)
    return d


@st.cache_data(ttl=900, show_spinner=False)
def fetch_daily(tickers: tuple):
    df = _download(tickers, "1y", "1d")
    return _split(df, tickers)


@st.cache_data(ttl=120, show_spinner=False)
def fetch_intraday(tickers: tuple):
    df = _download(tickers, "5d", "5m")
    return {t: _to_ist(d) for t, d in _split(df, tickers).items()}


# ==================== DAILY METRICS ====================
def daily_metrics(ticker, d):
    if len(d) < 60:
        return None
    close, high, low, vol = d["Close"], d["High"], d["Low"], d["Volume"]
    price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2])
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    hi52 = float(high.tail(252).max())
    atr = safe_float(atr_wilder(d).iloc[-1])
    rsi = safe_float(rsi_wilder(close).iloc[-1])
    avg_vol20 = float(vol.iloc[-21:-1].mean())
    v5, v20 = float(vol.tail(5).mean()), float(vol.tail(20).mean())
    low10 = float(low.tail(10).min())
    low_prev10 = float(low.iloc[-20:-10].min())
    return {
        "name": ticker.replace(".NS", ""),
        "ticker": ticker,
        "price": price,
        "prev_close": prev_close,
        "change": (price - prev_close) / prev_close * 100 if prev_close else 0.0,
        "high_52w": hi52,
        "drop_52w": (price - hi52) / hi52 * 100 if hi52 > 0 else 0.0,
        "rsi": rsi,
        "ema20": ema20,
        "ema50": ema50,
        "atr": atr,
        "avg_vol20": avg_vol20,
        "vol_trend": (v5 / v20) if v20 > 0 else None,
        "higher_low": low10 > low_prev10,
        "swing_low20": float(low.tail(20).min()),
        "last_date": d.index[-1],
    }


# ==================== INTRADAY METRICS + SCORE ====================
def intraday_metrics(m, d5, now_ist, is_open):
    last_day = d5.index[-1].date()
    today = d5[d5.index.date == last_day]
    if len(today) < 4:
        return None
    prev_sessions = d5[d5.index.date < last_day]
    prev_close = (
        float(prev_sessions["Close"].iloc[-1]) if not prev_sessions.empty else m["prev_close"]
    )
    price = float(today["Close"].iloc[-1])
    vwap = safe_float(session_vwap(today).iloc[-1])
    or_high = float(today["High"].iloc[:3].max())
    or_low = float(today["Low"].iloc[:3].min())

    if is_open and last_day == now_ist.date():
        start = now_ist.replace(hour=9, minute=15, second=0, microsecond=0)
        frac = min(max((now_ist - start).total_seconds() / 60 / 375, 0.05), 1.0)
    else:
        frac = 1.0
    day_vol = float(today["Volume"].sum())
    rel_vol = day_vol / (m["avg_vol20"] * frac) if m["avg_vol20"] > 0 else None
    rsi5 = safe_float(rsi_wilder(d5["Close"]).iloc[-1])

    return {
        "i_price": price,
        "i_change": (price - prev_close) / prev_close * 100 if prev_close else 0.0,
        "vwap": vwap,
        "or_high": or_high,
        "or_low": or_low,
        "rel_vol": rel_vol,
        "rsi5": rsi5,
        "last_candle": today.index[-1],
    }


def score_intraday(m):
    long_s, short_s = 0, 0
    long_r, short_r = [], []
    price = m["i_price"]
    vwap = m["vwap"]
    if vwap:
        if price > vwap:
            long_s += 20
            long_r.append("VWAP के ऊपर")
        elif price < vwap:
            short_s += 20
            short_r.append("VWAP के नीचे")
    if price > m["or_high"]:
        long_s += 20
        long_r.append("Opening Range ब्रेकआउट")
    elif price < m["or_low"]:
        short_s += 20
        short_r.append("Opening Range ब्रेकडाउन")
    rv = m["rel_vol"]
    if rv is not None:
        pts = 20 if rv >= 1.5 else 10 if rv >= 1.2 else 0
        if pts:
            long_s += pts
            short_s += pts
            long_r.append(f"वॉल्यूम {rv:.1f}x")
            short_r.append(f"वॉल्यूम {rv:.1f}x")
    ch = m["i_change"]
    if 0.5 <= ch <= 4:
        long_s += 15
        long_r.append(f"दिन में {ch:+.1f}%")
    elif -4 <= ch <= -0.5:
        short_s += 15
        short_r.append(f"दिन में {ch:+.1f}%")
    r = m["rsi5"]
    if r is not None:
        if 55 <= r <= 72:
            long_s += 15
            long_r.append(f"RSI(5m) {r:.0f}")
        elif 28 <= r <= 45:
            short_s += 15
            short_r.append(f"RSI(5m) {r:.0f}")
    if price > m["ema20"]:
        long_s += 10
        long_r.append("डेली EMA20 के ऊपर")
    else:
        short_s += 10
        short_r.append("डेली EMA20 के नीचे")

    if long_s >= short_s:
        direction, score, reasons = "LONG", long_s, long_r
        sl = max(m["or_low"], price * 0.988)
        if sl >= price:
            sl = price * 0.99
        target = price + 2 * (price - sl)
    else:
        direction, score, reasons = "SHORT", short_s, short_r
        sl = min(m["or_high"], price * 1.012)
        if sl <= price:
            sl = price * 1.01
        target = price - 2 * (sl - price)
    m["direction"] = direction
    m["intra_score"] = score
    m["intra_reasons"] = reasons
    m["i_sl"] = sl
    m["i_target"] = target


# ==================== FUNDAMENTALS (ON-DEMAND, CACHED 6 HOURS) ====================
FUND_KEYS = (
    "trailingPE", "trailingEps", "returnOnEquity", "debtToEquity",
    "marketCap", "industry", "sector", "profitMargins",
)


@st.cache_data(ttl=21600, show_spinner=False)
def fetch_fundamental(ticker: str):
    last_err = None
    for attempt in range(3):
        try:
            info = yf.Ticker(ticker).info
            if info and (
                info.get("marketCap")
                or info.get("trailingPE")
                or info.get("returnOnEquity") is not None
            ):
                time.sleep(0.3)
                return {k: info.get(k) for k in FUND_KEYS}
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(1.2 * (attempt + 1))
    # Raising means the failure is NOT cached, so the next run retries.
    raise RuntimeError(f"Fundamentals नहीं मिले ({last_err})")


def attach_fundamentals(s):
    if s.get("fund_loaded") or s.get("fund_failed"):
        return s
    try:
        raw = fetch_fundamental(s["ticker"])
    except Exception:  # noqa: BLE001
        s["fund_failed"] = True
        return s

    price = s["price"]
    eps = safe_float(raw.get("trailingEps"))
    pe = safe_float(raw.get("trailingPE"))
    loss_making = False
    if pe is None or pe <= 0:
        if eps is not None and eps > 0:
            pe = price / eps
        else:
            pe = None
            loss_making = eps is not None and eps <= 0
    roe = safe_float(raw.get("returnOnEquity"))
    de = safe_float(raw.get("debtToEquity"))
    margin = safe_float(raw.get("profitMargins"))
    mcap = safe_float(raw.get("marketCap"))
    sector = raw.get("sector") or "Unknown"
    industry = raw.get("industry") or "Unknown"
    is_fin = sector in FINANCIAL_SECTORS

    s.update(
        {
            "fund_loaded": True,
            "pe_ratio": pe,
            "loss_making": loss_making,
            "roe_pct": roe * 100 if roe is not None else None,
            # Yahoo gives D/E in percent (45.3 means 0.453)
            "de_ratio": None if is_fin or de is None else de / 100,
            "profit_margin": margin * 100 if margin is not None else None,
            "market_cap_cr": mcap / 1e7 if mcap else None,
            "sector": sector,
            "industry": industry,
            "is_financial": is_fin,
            "industry_pe": SECTOR_PE_BENCHMARK.get(sector, DEFAULT_PE_BENCHMARK),
        }
    )
    return s


def pe_analysis(s):
    if not s.get("fund_loaded"):
        return "डेटा उपलब्ध नहीं", "⚪"
    if s.get("loss_making"):
        return "कंपनी घाटे में (P/E लागू नहीं)", "🔴"
    pe, ind = s.get("pe_ratio"), s.get("industry_pe")
    if pe is None:
        return "डेटा उपलब्ध नहीं", "⚪"
    if not ind or ind <= 0:
        return "तुलना संभव नहीं", "⚪"
    ratio = pe / ind
    if ratio < 0.7:
        return f"काफ़ी सस्ता ({(1 - ratio) * 100:.0f}% discount)", "🟢"
    if ratio < 1:
        return f"सस्ता ({(1 - ratio) * 100:.0f}% discount)", "🟢"
    if ratio < 1.2:
        return "उचित मूल्य", "🟡"
    return f"महँगा ({(ratio - 1) * 100:.0f}% premium)", "🔴"


# ==================== SWING SCORE ====================
def score_swing(s):
    tech = 0
    d = s["drop_52w"]
    if d <= -40:
        tech += 12
    elif d <= -25:
        tech += 8
    elif d <= -15:
        tech += 4
    r = s["rsi"]
    if r is not None:
        if 30 <= r <= 50:
            tech += 8
        elif r < 30:
            tech += 5
        elif 50 < r <= 60:
            tech += 4
    if s["price"] > s["ema20"]:
        tech += 10
    if s["price"] > s["ema50"]:
        tech += 5
    if s["higher_low"]:
        tech += 8
    if s["vol_trend"] is not None and s["vol_trend"] >= 1.2:
        tech += 7

    fund = 0.0
    avail = 0
    status = "not_screened"
    if s.get("fund_failed"):
        status = "failed"
    elif s.get("fund_loaded"):
        pts, mx = 0, 0
        roe = s["roe_pct"]
        if roe is not None:
            mx += 12
            avail += 1
            pts += 12 if roe >= 15 else 6 if roe >= 10 else 0
        de = s["de_ratio"]
        if de is not None:
            mx += 10
            avail += 1
            pts += 10 if de < 1 else 5 if de < 1.5 else 0
        pe = s["pe_ratio"]
        if pe is not None:
            mx += 12
            avail += 1
            ind = s["industry_pe"]
            pts += 12 if pe < ind else 6 if pe < ind * 1.2 else 0
        elif s["loss_making"]:
            mx += 12
            avail += 1
        mg = s["profit_margin"]
        if mg is not None:
            mx += 8
            avail += 1
            pts += 8 if mg >= 10 else 4 if mg >= 5 else 0
        mc = s["market_cap_cr"]
        if mc is not None:
            mx += 8
            avail += 1
            pts += 8 if mc >= 5000 else 4 if mc >= 1000 else 0
        fund = pts / mx * 50 if mx > 0 else 0.0
        status = "complete" if avail >= 4 else "incomplete"

    s["tech_score"] = tech
    s["fund_score"] = round(fund, 1)
    s["fund_avail"] = avail
    s["fund_status"] = status
    s["swing_score"] = int(round(tech + fund))

    atr = s["atr"] or s["price"] * 0.02
    sl = max(s["swing_low20"] - 0.25 * atr, s["price"] - 3 * atr)
    if sl >= s["price"]:
        sl = s["price"] - 2 * atr
    s["sw_sl"] = sl
    s["sw_target"] = s["price"] + 2 * (s["price"] - sl)


# ==================== UI PIECES ====================
def get_stock(name, stocks):
    return next((x for x in stocks if x["name"] == name), None)


def add_watch(name):
    if name not in st.session_state.watchlist:
        st.session_state.watchlist.append(name)


def render_intraday_card(s, capital, risk_pct, prefix):
    c1, c2, c3 = st.columns([2, 3, 1])
    qty = calc_qty(s["i_price"], s["i_sl"], capital, risk_pct)
    with c1:
        icon = "🟢" if s["direction"] == "LONG" else "🔴"
        st.markdown(f"### {s['name']}")
        st.markdown(f"**₹{s['i_price']:.2f}** ({s['i_change']:+.2f}%)  \n{icon} **{s['direction']}**")
    with c2:
        st.markdown(
            f"**VWAP:** {fmt(s['vwap'], 2)} | **RSI(5m):** {fmt(s['rsi5'], 0)} | "
            f"**Vol:** {fmt(s['rel_vol'], 2, suffix='x')}"
        )
        st.markdown(
            f"**SL:** ₹{s['i_sl']:.2f} | **Target (1:2):** ₹{s['i_target']:.2f} | **Qty:** {qty}"
        )
        st.caption("कारण: " + ", ".join(s["intra_reasons"]))
    with c3:
        st.markdown(f"### 🎯 {s['intra_score']}")
        if st.button("🔍 Details", key=f"{prefix}_det_{s['name']}"):
            st.session_state.selected_stock = s["name"]
            st.rerun()
        if st.button("⭐ Add", key=f"{prefix}_add_{s['name']}"):
            add_watch(s["name"])
            st.toast(f"{s['name']} watchlist में जुड़ गया")
    st.markdown("---")


def render_swing_card(s, capital, risk_pct, prefix):
    pe_status, pe_emoji = pe_analysis(s)
    qty = calc_qty(s["price"], s["sw_sl"], capital, risk_pct)
    risk_pct_move = (s["price"] - s["sw_sl"]) / s["price"] * 100
    c1, c2, c3 = st.columns([2, 3, 1])
    with c1:
        st.markdown(f"### {s['name']}")
        st.markdown(f"**₹{s['price']:.2f}** ({s['drop_52w']:.1f}% from 52W High)")
    with c2:
        if s.get("fund_loaded"):
            st.markdown(
                f"**P/E:** {fmt(s['pe_ratio'])} {pe_emoji} | **Sector P/E (approx):** {fmt(s['industry_pe'])}"
            )
            de_txt = "लागू नहीं" if s.get("is_financial") else fmt(s["de_ratio"], 2)
            st.markdown(f"**ROE:** {fmt(s['roe_pct'], suffix='%')} | **D/E:** {de_txt}")
            st.markdown(f"**Verdict:** {pe_status}")
        st.markdown(
            f"**SL:** ₹{s['sw_sl']:.2f} ({risk_pct_move:.1f}% नीचे) | "
            f"**Target (1:2):** ₹{s['sw_target']:.2f} | **Qty:** {qty}"
        )
        st.caption(
            f"Technical {s['tech_score']}/50 + Fundamental {s['fund_score']}/50 "
            f"(डेटा {s['fund_avail']}/5 मापदंड)"
        )
    with c3:
        st.markdown(f"### 🎯 {s['swing_score']}")
        if st.button("🔍 Details", key=f"{prefix}_det_{s['name']}"):
            st.session_state.selected_stock = s["name"]
            st.rerun()
        if st.button("⭐ Add", key=f"{prefix}_add_{s['name']}"):
            add_watch(s["name"])
            st.toast(f"{s['name']} watchlist में जुड़ गया")
    st.markdown("---")


def parse_news(item):
    c = item.get("content") or {}
    title = c.get("title") or item.get("title") or "No title"
    link = (
        (c.get("canonicalUrl") or {}).get("url")
        or (c.get("clickThroughUrl") or {}).get("url")
        or item.get("link")
        or "#"
    )
    return title, link


def show_stock_detail(name, stocks, daily_map, intra_map, capital, risk_pct):
    s = get_stock(name, stocks)
    if not s:
        st.error("इस स्टॉक का डेटा नहीं मिला।")
        if st.button("⬅️ Back", key="back_missing"):
            clear_selected()
            st.rerun()
        return
    if st.button("⬅️ Back to Scanner", key="back_btn"):
        clear_selected()
        st.rerun()

    with st.spinner("Fundamentals लोड हो रहे हैं..."):
        attach_fundamentals(s)
    score_swing(s)

    st.title(f"🕵️ {s['name']} - Detailed Analysis")
    st.subheader(f"💰 ₹{s['price']:.2f} ({s['change']:+.2f}%)")

    tab_swing, tab_intra = st.tabs(["📈 Swing View", "⚡ Intraday View"])

    with tab_swing:
        d = daily_map[s["ticker"]]
        chart = pd.DataFrame(
            {
                "Close": d["Close"],
                "EMA20": d["Close"].ewm(span=20, adjust=False).mean(),
                "EMA50": d["Close"].ewm(span=50, adjust=False).mean(),
            }
        ).tail(180)
        st.line_chart(chart)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("52W High से दूरी", f"{s['drop_52w']:.1f}%")
        c2.metric("RSI (14)", fmt(s["rsi"], 0))
        c3.metric("EMA20 के ऊपर?", "हाँ" if s["price"] > s["ema20"] else "नहीं")
        c4.metric("Higher Low?", "हाँ" if s["higher_low"] else "नहीं")

        st.markdown("### Key Fundamentals")
        if s.get("fund_loaded"):
            pe_status, pe_emoji = pe_analysis(s)
            f1, f2, f3, f4, f5 = st.columns(5)
            f1.metric("P/E", f"{fmt(s['pe_ratio'])} {pe_emoji}")
            f1.caption(f"Sector P/E (approx): {fmt(s['industry_pe'])}")
            f2.metric("ROE", fmt(s["roe_pct"], suffix="%"))
            f3.metric("Debt/Equity", "लागू नहीं" if s["is_financial"] else fmt(s["de_ratio"], 2))
            f4.metric("Profit Margin", fmt(s["profit_margin"], suffix="%"))
            f5.metric("Market Cap", fmt(s["market_cap_cr"], 0, "₹", " Cr"))
            st.info(f"**Valuation Verdict:** {pe_status}  |  Sector: {s['sector']} / {s['industry']}")
        else:
            st.warning("Fundamentals Yahoo से नहीं मिले। इस स्टॉक पर फ़ंडामेंटल आधारित फ़ैसला न लें।")

        qty = calc_qty(s["price"], s["sw_sl"], capital, risk_pct)
        st.markdown("### सुझावी स्तर (सिर्फ़ संदर्भ के लिए)")
        l1, l2, l3, l4 = st.columns(4)
        l1.metric("Entry (CMP)", f"₹{s['price']:.2f}")
        l2.metric("Stop-Loss", f"₹{s['sw_sl']:.2f}")
        l3.metric("Target (1:2)", f"₹{s['sw_target']:.2f}")
        l4.metric("Qty", qty)
        st.caption(f"Swing Score: {s['swing_score']} (Technical {s['tech_score']}/50 + Fundamental {s['fund_score']}/50)")

        st.markdown("### 🏭 Same Sector के Peers (स्कैन लिस्ट में)")
        peers = [x for x in stocks if x.get("sector") == s.get("sector") and x["name"] != s["name"] and x.get("fund_loaded")]
        if peers:
            st.table(
                pd.DataFrame(
                    [
                        {
                            "Name": p["name"],
                            "Price": round(p["price"], 2),
                            "P/E": p["pe_ratio"],
                            "ROE %": None if p["roe_pct"] is None else round(p["roe_pct"], 1),
                        }
                        for p in peers[:6]
                    ]
                )
            )
        else:
            st.info("अभी लोड किए गए डेटा में कोई peer नहीं मिला।")

        st.markdown("### 📰 Recent News")
        try:
            news = yf.Ticker(s["ticker"]).news
            if news:
                for item in news[:4]:
                    title, link = parse_news(item)
                    st.markdown(f"- [{title}]({link})")
            else:
                st.info("कोई ताज़ा ख़बर नहीं मिली।")
        except Exception:  # noqa: BLE001
            st.warning("ख़बरें नहीं आ सकीं (Yahoo restriction)।")

    with tab_intra:
        d5 = intra_map.get(s["ticker"]) if intra_map else None
        if d5 is None or "i_price" not in s:
            st.info("Intraday डेटा अभी उपलब्ध नहीं है। Scanner में Intraday मोड चुनकर दोबारा खोलिए।")
        else:
            score_intraday(s)
            last_day = d5.index[-1].date()
            today = d5[d5.index.date == last_day]
            st.line_chart(pd.DataFrame({"Price": today["Close"], "VWAP": session_vwap(today)}))
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Direction", s["direction"])
            i2.metric("Score", s["intra_score"])
            i3.metric("VWAP", fmt(s["vwap"], 2))
            i4.metric("Rel. Volume", fmt(s["rel_vol"], 2, suffix="x"))
            st.markdown(
                f"**SL:** ₹{s['i_sl']:.2f} | **Target (1:2):** ₹{s['i_target']:.2f} | "
                f"**Qty:** {calc_qty(s['i_price'], s['i_sl'], capital, risk_pct)}"
            )
            st.caption("कारण: " + ", ".join(s["intra_reasons"]))


# ==================== HEADER ====================
st.title("🕵️ Market Detective Pro")

is_open, mkt_text, now_ist = market_status()

with st.sidebar:
    st.header("⚙️ सेटिंग्स")
    capital = st.number_input("ट्रेडिंग कैपिटल (₹)", min_value=10000, value=100000, step=10000)
    risk_pct = st.number_input("प्रति ट्रेड जोखिम (%)", min_value=0.1, max_value=5.0, value=1.0, step=0.1)
    min_score = st.slider("Scanner के लिए न्यूनतम स्कोर", 40, 95, 70, 5)
    if st.button("🔄 Refresh Live Data"):
        fetch_daily.clear()
        fetch_intraday.clear()
        st.toast("प्राइस डेटा रिफ्रेश हो रहा है")
    st.caption("Fundamentals 6 घंटे तक cache रहते हैं (बार-बार Yahoo को कॉल न जाए)।")

st.radio("Navigation", PAGES, horizontal=True, key="page", label_visibility="collapsed", on_change=clear_selected)
st.caption(f"🕒 अभी (IST): {now_ist.strftime('%d %b %Y, %H:%M:%S')} | {'🟢' if is_open else '🔴'} {mkt_text}")

# ==================== LOAD MARKET DATA ====================
page = st.session_state.page
need_market = bool(st.session_state.selected_stock) or page in (PAGES[0], PAGES[1])

stocks, daily_map, intra_map = [], {}, {}
failed = []

if need_market:
    with st.spinner("Yahoo से मार्केट डेटा लोड हो रहा है..."):
        try:
            daily_map = fetch_daily(tuple(STOCK_UNIVERSE))
        except Exception as e:  # noqa: BLE001
            st.error(f"❌ डेटा लोड नहीं हुआ: {e}")
            daily_map = {}

    for t in STOCK_UNIVERSE:
        if t in daily_map:
            m = daily_metrics(t, daily_map[t])
            if m:
                stocks.append(m)
            else:
                failed.append(t)
        else:
            failed.append(t)

    want_intraday = st.session_state.mode == "intraday" or bool(st.session_state.selected_stock)
    if stocks and want_intraday:
        try:
            intra_map = fetch_intraday(tuple(STOCK_UNIVERSE))
            for s in stocks:
                d5 = intra_map.get(s["ticker"])
                if d5 is not None:
                    im = intraday_metrics(s, d5, now_ist, is_open)
                    if im:
                        s.update(im)
        except Exception as e:  # noqa: BLE001
            st.warning(f"Intraday डेटा नहीं आया: {e}")

    if stocks:
        last_daily = max(s["last_date"] for s in stocks)
        intra_times = [s["last_candle"] for s in stocks if "last_candle" in s]
        msg = f"✅ {len(stocks)}/{len(STOCK_UNIVERSE)} स्टॉक्स लोड | डेली डेटा की आख़िरी तारीख़: {last_daily.strftime('%d %b %Y')}"
        if intra_times:
            msg += f" | आख़िरी 5m कैंडल: {max(intra_times).strftime('%d %b %H:%M')} IST"
        st.success(msg)
        if not is_open:
            st.info("बाज़ार बंद है, इसलिए दिख रहा डेटा पिछले ट्रेडिंग सत्र का है। ट्रेड के फ़ैसले बाज़ार खुलने के बाद ताज़ा डेटा देखकर लें।")
    if failed:
        with st.expander(f"⚠️ Failed tickers ({len(failed)})"):
            st.write(", ".join(failed))
            st.caption("ये टिकर Yahoo पर नहीं मिले या डेटा कम था। नाम बदले हों तो STOCK_UNIVERSE में ठीक कर लें।")

# ==================== ROUTING ====================
if st.session_state.selected_stock:
    if stocks:
        show_stock_detail(st.session_state.selected_stock, stocks, daily_map, intra_map, capital, risk_pct)
    else:
        st.error("डेटा उपलब्ध नहीं है।")
        if st.button("⬅️ Back", key="back_nodata"):
            clear_selected()
            st.rerun()

elif page == PAGES[0]:
    st.subheader("📊 Stock Scanner")
    st.radio(
        "Mode",
        ["intraday", "swing"],
        format_func=lambda x: "⚡ Intraday" if x == "intraday" else "📈 Swing Trading",
        horizontal=True,
        key="mode",
    )
    st.warning("यह स्कोर सिर्फ़ शॉर्टलिस्ट बनाने के लिए है, खरीद/बिक्री का सिग्नल नहीं। हर ट्रेड से पहले चार्ट ख़ुद देखें और Stop-Loss पहले तय करें।")
    query = st.text_input("🔍 Search stock...", placeholder="Enter stock name...", key="search_box")

    if not stocks:
        st.info("कोई डेटा नहीं मिला। थोड़ी देर बाद Refresh कीजिए।")
    elif st.session_state.mode == "intraday":
        for s in stocks:
            if "i_price" in s:
                score_intraday(s)
        pool = [s for s in stocks if "intra_score" in s]
        if query:
            pool = [s for s in pool if query.upper() in s["name"]]
        strong = sorted([s for s in pool if s["intra_score"] >= min_score], key=lambda x: x["intra_score"], reverse=True)
        st.subheader("🔥 Top Momentum Setups")
        if not strong:
            st.info(f"{min_score}+ स्कोर वाला कोई सेटअप नहीं मिला। साइडबार से न्यूनतम स्कोर घटाकर देखें।")
        for s in strong:
            render_intraday_card(s, capital, risk_pct, "i")
    else:
        cands = [s for s in stocks if s["drop_52w"] <= -15]
        if cands:
            prog = st.progress(0.0, text="Fundamentals लोड हो रहे हैं (पहली बार थोड़ा समय लगेगा)...")
            for i, s in enumerate(cands):
                attach_fundamentals(s)
                prog.progress((i + 1) / len(cands))
            prog.empty()
        for s in stocks:
            score_swing(s)
        pool = stocks
        if query:
            pool = [s for s in pool if query.upper() in s["name"]]

        strong = sorted(
            [s for s in pool if s["fund_status"] == "complete" and s["swing_score"] >= min_score],
            key=lambda x: x["swing_score"],
            reverse=True,
        )
        st.subheader("💎 Deep Value + Strong Fundamentals")
        st.caption("शर्तें: 52W High से 15%+ नीचे, फ़ंडामेंटल का कम से कम 4/5 डेटा उपलब्ध, और स्कोर ≥ न्यूनतम स्कोर।")
        if not strong:
            st.info("कोई स्टॉक सभी शर्तें पूरी नहीं करता। साइडबार से न्यूनतम स्कोर घटाकर देखें।")
        for s in strong:
            render_swing_card(s, capital, risk_pct, "s")

        partial = [s for s in pool if s["fund_status"] in ("incomplete", "failed")]
        if partial:
            with st.expander(f"⚠️ डेटा अधूरा ({len(partial)}) - इन पर फ़ंडामेंटल फ़ैसला न लें"):
                st.dataframe(
                    pd.DataFrame(
                        [
                            {
                                "Stock": p["name"],
                                "Price": round(p["price"], 2),
                                "52W से दूरी %": round(p["drop_52w"], 1),
                                "Technical /50": p["tech_score"],
                                "फ़ंडामेंटल डेटा": "नहीं मिला" if p["fund_status"] == "failed" else f"{p['fund_avail']}/5",
                            }
                            for p in partial
                        ]
                    ),
                    hide_index=True,
                )

        with st.expander("📋 सभी स्टॉक्स की तालिका"):
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "Stock": s["name"],
                            "Price": round(s["price"], 2),
                            "52W से दूरी %": round(s["drop_52w"], 1),
                            "RSI": None if s["rsi"] is None else round(s["rsi"], 0),
                            "Score": s["swing_score"],
                            "Status": s["fund_status"],
                        }
                        for s in sorted(pool, key=lambda x: x["swing_score"], reverse=True)
                    ]
                ),
                hide_index=True,
            )

elif page == PAGES[1]:
    st.subheader("⭐ My Watchlist")
    if not st.session_state.watchlist:
        st.info("Watchlist खाली है। Scanner के कार्ड में '⭐ Add' दबाकर स्टॉक जोड़िए।")
    elif not stocks:
        st.info("डेटा लोड नहीं हुआ।")
    else:
        for name in list(st.session_state.watchlist):
            s = get_stock(name, stocks)
            if not s:
                continue
            attach_fundamentals(s)
            pe_status, pe_emoji = pe_analysis(s)
            c1, c2, c3 = st.columns([2, 3, 1])
            with c1:
                st.markdown(f"### {s['name']}")
                st.markdown(f"**₹{s['price']:.2f}** ({s['change']:+.2f}% आज)")
            with c2:
                st.markdown(f"**P/E:** {fmt(s.get('pe_ratio'))} {pe_emoji} | **ROE:** {fmt(s.get('roe_pct'), suffix='%')}")
                st.markdown(f"**Verdict:** {pe_status}")
            with c3:
                if st.button("🔍 Details", key=f"w_det_{name}"):
                    st.session_state.selected_stock = name
                    st.rerun()
                if st.button("❌ Remove", key=f"w_rem_{name}"):
                    st.session_state.watchlist.remove(name)
                    st.rerun()
            st.markdown("---")

elif page == PAGES[2]:
    st.subheader("📓 Trade Journal")
    st.caption("ध्यान दें: Journal सिर्फ़ इस सेशन में रहता है। पेज रिफ्रेश होने पर मिट जाएगा, इसलिए नीचे से CSV डाउनलोड करते रहिए।")

    today_str = datetime.now(IST).strftime("%Y-%m-%d")
    today_count = sum(1 for t in st.session_state.trades if t["date"] == today_str)
    if today_count >= 1:
        st.warning(f"आज आप {today_count} ट्रेड दर्ज कर चुके हैं। आपका फ्रेमवर्क एक ट्रेड प्रतिदिन का है।")

    with st.form("new_trade"):
        c1, c2, c3 = st.columns(3)
        with c1:
            t_stock = st.text_input("Stock Name")
            t_dir = st.selectbox("Direction", ["Long", "Short"])
            t_entry = st.number_input("Entry Price", min_value=0.0)
        with c2:
            t_sl = st.number_input("Stop Loss (ज़रूरी)", min_value=0.0)
            t_target = st.number_input("Target", min_value=0.0)
            t_exit = st.number_input("Exit Price (0 अगर खुला है)", min_value=0.0)
        with c3:
            t_qty = st.number_input("Quantity", min_value=1, value=1)
            t_setup = st.selectbox("Setup", ["Swing Buy", "Intraday", "Breakout", "Value Buy"])
            t_reason = st.text_area("Reason")
        if st.form_submit_button("💾 Save Trade"):
            sl_ok = t_sl > 0 and ((t_dir == "Long" and t_sl < t_entry) or (t_dir == "Short" and t_sl > t_entry))
            if not t_stock or t_entry <= 0:
                st.error("Stock का नाम और Entry Price भरिए।")
            elif not sl_ok:
                st.error("Stop-Loss ज़रूरी है: Long में Entry से नीचे, Short में Entry से ऊपर।")
            else:
                risk = abs(t_entry - t_sl)
                reward = abs(t_target - t_entry) if t_target > 0 else 0
                sign = 1 if t_dir == "Long" else -1
                pnl = (t_exit - t_entry) * t_qty * sign if t_exit > 0 else 0
                st.session_state.trades.append(
                    {
                        "date": today_str, "stock": t_stock.upper(), "direction": t_dir,
                        "entry": t_entry, "sl": t_sl, "target": t_target, "exit": t_exit,
                        "qty": t_qty, "setup": t_setup, "reason": t_reason,
                        "rr": round(reward / risk, 2), "pnl": round(pnl, 2),
                        "status": "Closed" if t_exit > 0 else "Open",
                    }
                )
                st.success("Trade saved!")
                st.rerun()

    if st.session_state.trades:
        st.markdown("---")
        st.subheader("📊 Statistics")
        closed = [t for t in st.session_state.trades if t["status"] == "Closed"]
        wins = [t for t in closed if t["pnl"] > 0]
        total_pnl = sum(t["pnl"] for t in closed)
        win_rate = (len(wins) / len(closed) * 100) if closed else 0
        avg_rr = (sum(t["rr"] for t in closed) / len(closed)) if closed else 0
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Closed Trades", len(closed))
        s2.metric("Win Rate", f"{win_rate:.1f}%")
        s3.metric("Total P&L", f"₹{total_pnl:,.2f}")
        s4.metric("Avg R:R (planned)", f"{avg_rr:.2f}")

        st.subheader("📜 Trade History")
        hist_df = pd.DataFrame(st.session_state.trades).iloc[::-1]
        st.dataframe(hist_df, hide_index=True)
        st.download_button(
            "⬇️ Journal CSV डाउनलोड करें",
            hist_df.to_csv(index=False).encode("utf-8"),
            file_name="trade_journal.csv",
            mime="text/csv",
        )

    st.markdown("---")
    up = st.file_uploader("पुराना Journal CSV वापस लाएँ", type="csv")
    if up is not None and st.button("♻️ Restore"):
        try:
            st.session_state.trades = pd.read_csv(up).iloc[::-1].to_dict("records")
            st.rerun()
        except Exception:  # noqa: BLE001
            st.error("CSV पढ़ी नहीं जा सकी।")

elif page == PAGES[3]:
    st.subheader("ℹ️ About Market Detective Pro")
    st.markdown(
        """
**यह कैसे काम करता है**
- **Intraday:** आख़िरी सत्र के 5-मिनट डेटा से VWAP, Opening Range ब्रेकआउट, Relative Volume, RSI और डेली ट्रेंड देखकर LONG/SHORT स्कोर बनता है।
- **Swing:** 52W High से गिरावट, RSI, EMA20/50, Higher Low, वॉल्यूम ट्रेंड (50 अंक) और ROE, D/E, P/E, Profit Margin, Market Cap (50 अंक)।
- **डेटा न मिलने पर** अंक नहीं मिलते और स्टॉक "Strong Fundamentals" में नहीं गिना जाता।
- **बैंक/NBFC** में D/E लागू नहीं माना जाता।
- **Sector P/E** अनुमानित benchmark है (कोड में `SECTOR_PE_BENCHMARK` बदल सकते हैं)।
- **SL/Target/Qty** सिर्फ़ संदर्भ के लिए हैं। साइडबार में अपनी कैपिटल और जोखिम % भरिए।

⚠️ **Disclaimer:** सिर्फ़ शैक्षणिक उपयोग के लिए। यह वित्तीय सलाह नहीं है। Yahoo का डेटा देरी से आ सकता है।
"""
    )

st.markdown("---")
st.caption("⚠️ Educational tool only. Not financial advice. Data from Yahoo Finance (may be delayed).")
