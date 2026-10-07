import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# ==========================================
# 1. PAGE CONFIG & CUSTOM CSS (Same as HTML)
# ==========================================
st.set_page_config(page_title="Market Detective - LIVE", page_icon="🕵️♂️", layout="centered")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&display=swap');
    
    * { font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif; }
    
    .main { background-color: #000000; }
    
    .app-container {
        max-width: 414px;
        margin: 0 auto;
        background-color: #0f172a;
        min-height: 100vh;
        padding: 20px;
        border-radius: 12px;
    }
    
    .header-title {
        font-size: 28px;
        font-weight: 900;
        color: #f8fafc;
        margin-bottom: 5px;
    }
    
    .header-subtitle {
        font-size: 14px;
        color: #94a3b8;
        margin-bottom: 20px;
    }
    
    .status-bar {
        background-color: #1e293b;
        padding: 10px 15px;
        border-radius: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        font-size: 13px;
        color: #94a3b8;
    }
    
    .status-dot-live {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #10b981;
        margin-right: 6px;
    }
    
    .status-dot-demo {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background-color: #ef4444;
        margin-right: 6px;
    }
    
    .refresh-btn {
        background-color: #3b82f6;
        color: white;
        border: none;
        padding: 12px 20px;
        border-radius: 8px;
        font-size: 14px;
        font-weight: 600;
        width: 100%;
        cursor: pointer;
        margin-bottom: 15px;
    }
    
    .refresh-btn:hover { background-color: #2563eb; }
    
    .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #f8fafc;
        margin-top: 25px;
        margin-bottom: 15px;
    }
    
    .stock-card {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 12px;
        border: 1px solid #334155;
        cursor: pointer;
    }
    
    .stock-card:hover { border-color: #3b82f6; }
    
    .stock-name {
        font-size: 16px;
        font-weight: 700;
        color: #f8fafc;
    }
    
    .stock-price {
        font-size: 18px;
        font-weight: 700;
        color: #f8fafc;
        text-align: right;
    }
    
    .stock-change {
        font-size: 14px;
        margin-top: 8px;
    }
    
    .bullish { color: #10b981; }
    .bearish { color: #ef4444; }
    
    .score-badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 700;
        color: white;
        margin-top: 8px;
    }
    
    .score-green { background-color: #10b981; }
    .score-yellow { background-color: #f59e0b; }
    .score-red { background-color: #ef4444; }
    .score-blue { background-color: #3b82f6; }
    
    .analysis-header {
        font-size: 24px;
        font-weight: 700;
        color: #f8fafc;
        margin-bottom: 5px;
    }
    
    .analysis-price {
        font-size: 32px;
        font-weight: 900;
        color: #f8fafc;
        margin-bottom: 20px;
    }
    
    .score-card-box {
        background-color: #1e293b;
        padding: 25px;
        border-radius: 16px;
        text-align: center;
        margin-bottom: 20px;
        border: 2px solid #10b981;
    }
    
    .score-title-text {
        color: #94a3b8;
        font-size: 14px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .score-huge {
        font-size: 56px;
        font-weight: 900;
        color: #10b981;
        margin: 10px 0;
    }
    
    .score-label-text {
        font-size: 16px;
        font-weight: 600;
        color: #10b981;
    }
    
    .ai-card {
        background-color: #1e293b;
        padding: 16px;
        border-radius: 12px;
        margin-bottom: 20px;
        border-left: 4px solid #3b82f6;
    }
    
    .ai-title {
        color: #3b82f6;
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 8px;
    }
    
    .ai-text {
        color: #cbd5e1;
        font-size: 15px;
        line-height: 1.5;
    }
    
    .evidence-item {
        display: flex;
        align-items: center;
        padding: 12px 0;
        border-bottom: 1px solid #334155;
        color: #f8fafc;
        font-size: 15px;
    }
    
    .dot {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        margin-right: 15px;
        flex-shrink: 0;
    }
    
    .dot-green { background-color: #10b981; }
    .dot-red { background-color: #ef4444; }
    .dot-yellow { background-color: #f59e0b; }
    .dot-blue { background-color: #3b82f6; }
    
    .disclaimer {
        font-size: 12px;
        color: #94a3b8;
        text-align: center;
        margin-top: 30px;
        line-height: 1.5;
    }
    
    .no-results {
        text-align: center;
        color: #94a3b8;
        padding: 40px 20px;
    }
    
    div[data-testid="stSidebar"] { background-color: #0f172a; }
    div[data-testid="stSidebar"] .stMarkdown { color: #f8fafc; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. STOCK UNIVERSE
# ==========================================
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

# ==========================================
# 3. DATA FETCHING
# ==========================================
@st.cache_data(ttl=300)
def fetch_live_data(tickers):
    """Fetch real data from Yahoo Finance"""
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="3mo")
            info = stock.info
            
            if hist.empty or 'currentPrice' not in info:
                continue
            
            current_price = info.get('currentPrice', 0)
            prev_close = info.get('previousClose', hist['Close'].iloc[-2] if len(hist) > 1 else current_price)
            change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
            
            # Calculate RSI
            closes = hist['Close'].tolist()
            rsi = 50
            if len(closes) >= 15:
                gains, losses = 0, 0
                for i in range(-14, 0):
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
            
            # 20 SMA
            sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current_price
            
            # 52 Week High
            high_52w = info.get('fiftyTwoWeekHigh', max(closes) if closes else current_price)
            drop_52w = ((current_price - high_52w) / high_52w * 100) if high_52w else 0
            
            # Fundamental data
            roe = (info.get('returnOnEquity', 0) or 0) * 100
            de_ratio = (info.get('debtToEquity', 0) or 0) / 100
            pe = info.get('trailingPE', 0) or 0
            
            name = ticker.replace('.NS', '')
            
            results.append({
                'name': name,
                'ticker': ticker,
                'price': current_price,
                'change': change_pct,
                'rsi': rsi,
                'vol_ratio': vol_ratio,
                'sma20': sma20,
                'prev_close': prev_close,
                'high_52w': high_52w,
                'drop_52w': drop_52w,
                'roe': roe,
                'de_ratio': de_ratio,
                'pe': pe
            })
        except Exception as e:
            continue
    return results

def calculate_scores(data, mode):
    """Calculate detective scores"""
    for stock in data:
        if mode == 'intraday':
            score = 50
            if stock['change'] > 0: score += 20
            if stock['vol_ratio'] > 1.2: score += 20
            if stock['rsi'] > 55: score += 15
            if stock['price'] > stock['sma20']: score += 15
            stock['intra_score'] = min(100, max(0, score))
        else:
            score = 50
            if stock['drop_52w'] < -30: score += 25
            if stock['rsi'] < 40: score += 25
            if stock['price'] > stock['sma20']: score += 25
            if stock['roe'] > 15: score += 10
            if stock['de_ratio'] < 1.0: score += 10
            stock['swing_score'] = min(100, max(0, score))
    return data

# ==========================================
# 4. UI RENDERING
# ==========================================
st.markdown('<div class="app-container">', unsafe_allow_html=True)

# Header
st.markdown('<div class="header-title">Market Detective 🕵️‍♂️</div>', unsafe_allow_html=True)

# Mode Toggle
col1, col2 = st.columns(2)
with col1:
    intraday_active = st.button("⚡ Intraday", key="intraday_btn", use_container_width=True)
with col2:
    swing_active = st.button("📈 Swing Trading", key="swing_btn", use_container_width=True)

# Default mode
if 'mode' not in st.session_state:
    st.session_state.mode = 'swing'

if intraday_active:
    st.session_state.mode = 'intraday'
elif swing_active:
    st.session_state.mode = 'swing'

current_mode = st.session_state.mode

# Status bar
status_text = "Connecting..."
status_class = "status-dot-demo"

# Fetch data
if st.button("🔄 Refresh Live Data", use_container_width=True, key="refresh"):
    st.cache_data.clear()

with st.spinner("Fetching live market data..."):
    try:
        live_data = fetch_live_data(STOCK_UNIVERSE)
        live_data = calculate_scores(live_data, current_mode)
        if live_data:
            status_text = f"LIVE DATA | {datetime.now().strftime('%H:%M:%S')}"
            status_class = "status-dot-live"
        else:
            raise Exception("No data")
    except:
        live_data = []
        status_text = "DEMO MODE (Live API blocked)"
        status_class = "status-dot-demo"

# Status bar HTML
st.markdown(f"""
<div class="status-bar">
    <span><span class="{status_class}"></span>{status_text}</span>
    <span>{'Live' if status_class == 'status-dot-live' else 'Demo'}</span>
</div>
""", unsafe_allow_html=True)

# Update subtitle
if status_class == 'status-dot-live':
    st.markdown(f'<div class="header-subtitle">Live Market Data | {datetime.now().strftime("%d %b %Y")}</div>', unsafe_allow_html=True)
else:
    st.markdown('<div class="header-subtitle">Demo Mode | Connect internet for live data</div>', unsafe_allow_html=True)

# Search
search_query = st.text_input("🔍 Search stock...", key="search", placeholder="Enter stock name...")

# Filter and sort
if search_query:
    filtered = [s for s in live_data if search_query.upper() in s['name']]
else:
    filtered = live_data

# Categorize
if current_mode == 'intraday':
    strong = sorted([s for s in filtered if s.get('intra_score', 0) >= 70], key=lambda x: x.get('intra_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('intra_score', 0) < 50], key=lambda x: x.get('intra_score', 0))
    neutral = [s for s in filtered if 50 <= s.get('intra_score', 0) < 70]
    
    st.markdown('<div class="section-title">Top Momentum Setups 🔥</div>', unsafe_allow_html=True)
    for s in strong:
        score = s.get('intra_score', 0)
        color_class = 'score-green' if score >= 70 else 'score-yellow' if score >= 50 else 'score-red'
        change_class = 'bullish' if s['change'] >= 0 else 'bearish'
        change_sign = '+' if s['change'] >= 0 else ''
        
        st.markdown(f"""
        <div class="stock-card" onclick="void(0)">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {change_class}">{change_sign}{s['change']:.2f}% {'🟢' if s['change']>=0 else '🔴'}</div>
            <span class="score-badge {color_class}">Score: {int(score)}</span>
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
    
    if not weak:
        st.markdown('<div class="no-results">No weak setups</div>', unsafe_allow_html=True)

else:  # Swing mode
    strong = sorted([s for s in filtered if s.get('swing_score', 0) >= 70], key=lambda x: x.get('swing_score', 0), reverse=True)
    weak = sorted([s for s in filtered if s.get('swing_score', 0) < 50], key=lambda x: x.get('swing_score', 0))
    neutral = [s for s in filtered if 50 <= s.get('swing_score', 0) < 70]
    
    st.markdown('<div class="section-title">Deep Value / Oversold 💎</div>', unsafe_allow_html=True)
    for s in strong:
        score = s.get('swing_score', 0)
        color_class = 'score-green' if score >= 70 else 'score-yellow'
        drop_class = 'bullish' if s['drop_52w'] < -30 else 'bearish'
        
        st.markdown(f"""
        <div class="stock-card">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <span class="stock-name">{s['name']}</span>
                <span class="stock-price">₹{s['price']:.2f}</span>
            </div>
            <div class="stock-change {drop_class}">{s['drop_52w']:.1f}% from 52W High</div>
            <span class="score-badge {color_class}">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)
    
    if not strong:
        st.markdown('<div class="no-results">No deep value stocks found</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">Overbought / Weak 📉</div>', unsafe_allow_html=True)
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