import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

st.set_page_config(page_title="Market Detective", page_icon="🕵️‍♂️", layout="centered")

st.markdown("""
<style>
    .main { background-color: #000000; }
    .app-container { max-width: 414px; margin: 0 auto; background-color: #0f172a; min-height: 100vh; padding: 20px; border-radius: 12px; }
    .header-title { font-size: 28px; font-weight: 900; color: #f8fafc; margin-bottom: 5px; }
    .header-subtitle { font-size: 14px; color: #94a3b8; margin-bottom: 20px; }
    .status-bar { background-color: #1e293b; padding: 10px 15px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; font-size: 13px; color: #94a3b8; }
    .status-dot-live { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #10b981; margin-right: 6px; }
    .status-dot-demo { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background-color: #ef4444; margin-right: 6px; }
    .section-title { font-size: 18px; font-weight: 600; color: #f8fafc; margin-top: 25px; margin-bottom: 15px; }
    .stock-card { background-color: #1e293b; padding: 16px; border-radius: 12px; margin-bottom: 12px; border: 1px solid #334155; cursor: pointer; }
    .stock-card:hover { border-color: #3b82f6; }
    .stock-name { font-size: 16px; font-weight: 700; color: #f8fafc; }
    .stock-price { font-size: 18px; font-weight: 700; color: #f8fafc; }
    .stock-change { font-size: 14px; margin-top: 8px; }
    .bullish { color: #10b981; }
    .bearish { color: #ef4444; }
    .score-badge { display: inline-block; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 700; color: white; margin-top: 8px; }
    .score-green { background-color: #10b981; }
    .score-red { background-color: #ef4444; }
    .no-results { text-align: center; color: #94a3b8; padding: 40px 20px; }
    .disclaimer { font-size: 12px; color: #94a3b8; text-align: center; margin-top: 30px; line-height: 1.5; }
</style>
""", unsafe_allow_html=True)

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

@st.cache_data(ttl=300)
def fetch_live_data_yfinance(tickers):
    """Fetch data using yfinance library"""
    results = []
    try:
        # Fetch all stocks at once
        data = yf.download(tickers, period="3mo", group_by='ticker', progress=False)
        
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                if not info or 'currentPrice' not in info:
                    continue
                
                current_price = info.get('currentPrice', 0)
                prev_close = info.get('previousClose', current_price)
                change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
                
                # Get historical data for RSI
                hist = stock.history(period="3mo")
                if hist.empty:
                    continue
                
                closes = hist['Close'].tolist()
                
                # Calculate RSI
                rsi = 50
                if len(closes) >= 15:
                    gains, losses = 0, 0
                    for i in range(-14, 0):
                        if i-1 >= -len(closes):
                            diff = closes[i] - closes[i-1]
                            if diff > 0: gains += diff
                            else: losses -= diff
                    avg_gain = gains / 14
                    avg_loss = losses / 14
                    if avg_loss > 0:
                        rs = avg_gain / avg_loss
                        rsi = 100 - (100 / (1 + rs))
                
                # Volume analysis
                volumes = hist['Volume'].tolist()
                avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes)
                current_vol = volumes[-1] if volumes else 0
                vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
                
                # 52 Week High
                high_52w = info.get('fiftyTwoWeekHigh', max(closes) if closes else current_price)
                drop_52w = ((current_price - high_52w) / high_52w * 100) if high_52w > 0 else 0
                
                name = ticker.replace('.NS', '')
                
                results.append({
                    'name': name,
                    'price': current_price,
                    'change': change_pct,
                    'rsi': rsi,
                    'vol_ratio': vol_ratio,
                    'high_52w': high_52w,
                    'drop_52w': drop_52w
                })
            except Exception as e:
                continue
    except Exception as e:
        return []
    
    return results

def calculate_scores(data, mode):
    for stock in data:
        if mode == 'intraday':
            score = 50
            if stock['change'] > 0: score += 20
            if stock['vol_ratio'] > 1.2: score += 20
            if stock['rsi'] > 55: score += 15
            stock['intra_score'] = min(100, max(0, score))
        else:
            score = 50
            if stock['drop_52w'] < -30: score += 25
            if stock['rsi'] < 40: score += 25
            if stock['drop_52w'] < -50: score += 15
            stock['swing_score'] = min(100, max(0, score))
    return data

st.markdown('<div class="app-container">', unsafe_allow_html=True)
st.markdown('<div class="header-title">Market Detective 🕵️‍♂️</div>', unsafe_allow_html=True)

col1, col2 = st.columns(2)
with col1:
    if st.button("⚡ Intraday", use_container_width=True):
        st.session_state.mode = 'intraday'
with col2:
    if st.button(" Swing Trading", use_container_width=True):
        st.session_state.mode = 'swing'

if 'mode' not in st.session_state:
    st.session_state.mode = 'swing'
current_mode = st.session_state.mode

if st.button("🔄 Refresh Live Data", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Fetching live market data... This may take 30-60 seconds..."):
    try:
        live_data = fetch_live_data_yfinance(STOCK_UNIVERSE)
        if live_data:
            live_data = calculate_scores(live_data, current_mode)
            is_live = True
        else:
            is_live = False
            live_data = []
    except Exception as e:
        is_live = False
        live_data = []

if is_live:
    st.markdown(f"""
    <div class="status-bar">
        <span><span class="status-dot-live"></span>LIVE DATA | {datetime.now(IST).strftime('%H:%M:%S')}</span>
        <span>Live</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="header-subtitle">Live Market Data | {datetime.now(IST).strftime("%d %b %Y")}</div>', unsafe_allow_html=True)
else:
    st.markdown("""
    <div class="status-bar">
        <span><span class="status-dot-demo"></span>DEMO MODE (Live API blocked)</span>
        <span>Demo</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div class="header-subtitle">Demo Mode | Connect internet for live data</div>', unsafe_allow_html=True)

search_query = st.text_input("🔍 Search stock...", placeholder="Enter stock name...")
if search_query:
    filtered = [s for s in live_data if search_query.upper() in s['name']]
else:
    filtered = live_data

if current_mode == 'intraday':
    strong = sorted([s for s in filtered if s.get('intra_score', 0) >= 70], key=lambda x: x.get('intra_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('intra_score', 0) < 50], key=lambda x: x.get('intra_score', 0))
    
    st.markdown('<div class="section-title">Top Momentum Setups 🔥</div>', unsafe_allow_html=True)
    for s in strong:
        score = s.get('intra_score', 0)
        change_class = 'bullish' if s['change'] >= 0 else 'bearish'
        change_sign = '+' if s['change'] >= 0 else ''
        st.markdown(f"""
        <div class="stock-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {change_class}">{change_sign}{s['change']:.2f}% {'🟢' if s['change']>=0 else ''}</div>
            <span class="score-badge score-green">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)
    if not strong:
        st.markdown('<div class="no-results">No strong momentum setups</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">Weak / Bearish Setups ⚠️</div>', unsafe_allow_html=True)
    for s in weak:
        score = s.get('intra_score', 0)
        change_class = 'bullish' if s['change'] >= 0 else 'bearish'
        change_sign = '+' if s['change'] >= 0 else ''
        st.markdown(f"""
        <div class="stock-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {change_class}">{change_sign}{s['change']:.2f}%</div>
            <span class="score-badge score-red">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)
else:
    strong = sorted([s for s in filtered if s.get('swing_score', 0) >= 70], key=lambda x: x.get('swing_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('swing_score', 0) < 50], key=lambda x: x.get('swing_score', 0))
    
    st.markdown('<div class="section-title">Deep Value / Oversold 💎</div>', unsafe_allow_html=True)
    for s in strong:
        score = s.get('swing_score', 0)
        drop_class = 'bullish' if s['drop_52w'] < -30 else 'bearish'
        st.markdown(f"""
        <div class="stock-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {drop_class}">{s['drop_52w']:.1f}% from 52W High</div>
            <span class="score-badge score-green">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)
    if not strong:
        st.markdown('<div class="no-results">No deep value stocks found</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">Overbought / Weak </div>', unsafe_allow_html=True)
    for s in weak:
        score = s.get('swing_score', 0)
        drop_class = 'bullish' if s['drop_52w'] < -30 else 'bearish'
        st.markdown(f"""
        <div class="stock-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {drop_class}">{s['drop_52w']:.1f}% from 52W High</div>
            <span class="score-badge score-red">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)

st.markdown('<div class="disclaimer">⚠️ Disclaimer: Educational purpose only. Not financial advice. Verify data before trading.</div>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)
