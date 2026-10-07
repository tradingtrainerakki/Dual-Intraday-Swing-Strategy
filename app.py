import streamlit as st
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Market Detective", page_icon="🕵️♂️", layout="centered")

STOCK_UNIVERSE = [
    "TATAMOTORS.NS", "RELIANCE.NS", "SBIN.NS", "ICICIBANK.NS", "TCS.NS",
    "INFY.NS", "HDFCBANK.NS", "M&M.NS", "BAJFINANCE.NS", "TATASTEEL.NS",
    "IRFC.NS", "RVNL.NS", "ZOMATO.NS", "IREDA.NS", "SUZLON.NS",
    "LT.NS", "AXISBANK.NS", "KOTAKBANK.NS", "WIPRO.NS", "HCLTECH.NS",
    "ADANIENT.NS", "ADANIPORTS.NS", "TITAN.NS", "ASIANPAINT.NS", "SUNPHARMA.NS",
    "BAJAJ-AUTO.NS", "MARUTI.NS", "ULTRACEMCO.NS", "POWERGRID.NS", "NTPC.NS",
    "ONGC.NS", "COALINDIA.NS", "GAIL.NS", "BPCL.NS", "IOC.NS",
    "BANKINDIA.NS", "PNB.NS", "CANBK.NS", "INDUSINDBK.NS", "FEDERALBNK.NS",
    "TATAPOWER.NS", "NHPC.NS", "SJVN.NS", "BEL.NS", "BHEL.NS",
    "HAL.NS", "MAZDOCK.NS", "COFORGE.NS", "LTIM.NS", "PERSISTENT.NS"
]

@st.cache_data(ttl=600)
def fetch_data(tickers):
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            if hist.empty:
                continue
            closes = hist['Close'].tolist()
            volumes = hist['Volume'].tolist()
            current_price = closes[-1] if closes else 0
            prev_close = closes[-2] if len(closes) > 1 else current_price
            change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
            rsi = 50
            if len(closes) >= 15:
                gains, losses = 0, 0
                for i in range(-14, 0):
                    if abs(i) < len(closes):
                        diff = closes[i] - closes[i-1]
                        if diff > 0:
                            gains += diff
                        else:
                            losses -= diff
                avg_gain = gains / 14
                avg_loss = losses / 14
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
            avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes) if volumes else 1
            current_vol = volumes[-1] if volumes else 0
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            high_52w = max(closes) if closes else current_price
            drop_52w = ((current_price - high_52w) / high_52w * 100) if high_52w > 0 else 0
            info = stock.info
            pe_ratio = info.get('trailingPE', 0) or 0
            roe = info.get('returnOnEquity', 0) or 0
            roe_pct = roe * 100 if roe else 0
            de_ratio = info.get('debtToEquity', 0) or 0
            de_ratio_decimal = de_ratio / 100 if de_ratio > 1 else de_ratio
            market_cap = info.get('marketCap', 0) or 0
            market_cap_cr = market_cap / 10000000 if market_cap else 0
            name = ticker.replace('.NS', '')
            results.append({
                'name': name,
                'price': current_price,
                'change': change_pct,
                'rsi': rsi,
                'vol_ratio': vol_ratio,
                'high_52w': high_52w,
                'drop_52w': drop_52w,
                'pe_ratio': pe_ratio,
                'roe_pct': roe_pct,
                'de_ratio': de_ratio_decimal,
                'market_cap_cr': market_cap_cr
            })
        except Exception as e:
            continue
    return results

def calc_scores(data, mode):
    for stock in data:
        if mode == 'intraday':
            score = 50
            if stock['change'] > 0:
                score += 20
            if stock['vol_ratio'] > 1.2:
                score += 20
            if stock['rsi'] > 55:
                score += 15
            stock['intra_score'] = min(100, max(0, score))
        else:
            tech_score = 50
            fund_score = 0
            tech_met = 0
            if stock['drop_52w'] < -40:
                tech_score += 15
                tech_met += 1
            elif stock['drop_52w'] < -25:
                tech_score += 8
                tech_met += 1
            if stock['rsi'] < 45:
                tech_score += 10
                tech_met += 1
            elif stock['rsi'] < 55:
                tech_score += 5
            fund_met = 0
            if stock['roe_pct'] > 12:
                fund_score += 10
                fund_met += 1
            if stock['de_ratio'] < 1.5:
                fund_score += 10
                fund_met += 1
            if 0 < stock['pe_ratio'] < 25:
                fund_score += 10
                fund_met += 1
            if stock['market_cap_cr'] > 1000:
                fund_score += 5
                fund_met += 1
            if tech_met >= 2 and fund_met >= 3:
                tech_score += 10
            stock['swing_score'] = min(100, max(0, tech_score + fund_score))
    return data

st.title("🕵️♂️ Market Detective")

col1, col2 = st.columns(2)
with col1:
    if st.button("⚡ Intraday", use_container_width=True):
        st.session_state.mode = 'intraday'
with col2:
    if st.button("📈 Swing Trading", use_container_width=True):
        st.session_state.mode = 'swing'

if 'mode' not in st.session_state:
    st.session_state.mode = 'swing'
current_mode = st.session_state.mode

if st.button("🔄 Refresh Live Data", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Fetching live market data..."):
    try:
        live_data = fetch_data(STOCK_UNIVERSE)
        if live_data:
            live_data = calc_scores(live_data, current_mode)
            is_live = True
        else:
            is_live = False
            live_data = []
    except Exception as e:
        is_live = False
        live_data = []

if is_live:
    st.success(f"✅ LIVE DATA | {datetime.now(IST).strftime('%H:%M:%S')}")
else:
    st.error("❌ DEMO MODE - Live data fetch failed")

search_query = st.text_input("🔍 Search stock...", placeholder="Enter stock name...")
if search_query:
    filtered = [s for s in live_data if search_query.upper() in s['name']]
else:
    filtered = live_data

if current_mode == 'intraday':
    strong = sorted([s for s in filtered if s.get('intra_score', 0) >= 70], key=lambda x: x.get('intra_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('intra_score', 0) < 50], key=lambda x: x.get('intra_score', 0))
    st.subheader("🔥 Top Momentum Setups")
    for s in strong:
        score = s.get('intra_score', 0)
        change_sign = '+' if s['change'] >= 0 else ''
        st.markdown(f"### {s['name']} - ₹{s['price']:.2f}")
        st.markdown(f"**Change:** {change_sign}{s['change']:.2f}% | **RSI:** {s['rsi']:.1f} | **Vol Ratio:** {s['vol_ratio']:.2f}x")
        st.markdown(f"**Score:** {int(score)}/100 ")
        st.markdown("---")
    if not strong:
        st.info("No strong momentum setups found")
    st.subheader("⚠️ Weak / Bearish Setups")
    for s in weak:
        score = s.get('intra_score', 0)
        change_sign = '+' if s['change'] >= 0 else ''
        st.markdown(f"### {s['name']} - ₹{s['price']:.2f}")
        st.markdown(f"**Change:** {change_sign}{s['change']:.2f}% | **RSI:** {s['rsi']:.1f}")
        st.markdown(f"**Score:** {int(score)}/100 🔴")
        st.markdown("---")
else:
    strong = sorted([s for s in filtered if s.get('swing_score', 0) >= 70], key=lambda x: x.get('swing_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('swing_score', 0) < 50], key=lambda x: x.get('swing_score', 0))
    st.subheader("💎 Deep Value + Strong Fundamentals")
    for s in strong:
        score = s.get('swing_score', 0)
        drop_color = "🟢" if s['drop_52w'] < -30 else "🔴"
        st.markdown(f"### {s['name']} - ₹{s['price']:.2f}")
        st.markdown(f"**Drop from 52W High:** {drop_color} {s['drop_52w']:.1f}%")
        st.markdown(f"**P/E:** {s['pe_ratio']:.1f} | **ROE:** {s['roe_pct']:.1f}% | **D/E:** {s['de_ratio']:.2f} | **Cap:** ₹{s['market_cap_cr']:.0f}Cr")
        st.markdown(f"**Score:** {int(score)}/100 🎯")
        st.markdown("---")
    if not strong:
        st.info("No deep value stocks with strong fundamentals found")
    st.subheader("📉 Weak Fundamentals / Overvalued")
    for s in weak:
        score = s.get('swing_score', 0)
        drop_color = "🟢" if s['drop_52w'] < -30 else ""
        st.markdown(f"### {s['name']} - ₹{s['price']:.2f}")
        st.markdown(f"**Drop from 52W High:** {drop_color} {s['drop_52w']:.1f}%")
        st.markdown(f"**P/E:** {s['pe_ratio']:.1f} | **ROE:** {s['roe_pct']:.1f}% | **D/E:** {s['de_ratio']:.2f}")
        st.markdown(f"**Score:** {int(score)}/100 ⚠️")
        st.markdown("---")

st.warning("⚠️ Disclaimer: Educational purpose only. Not financial advice. Verify data before trading.")
