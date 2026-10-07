import streamlit as st
import requests
from datetime import datetime

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
    .refresh-btn { background-color: #3b82f6; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; width: 100%; cursor: pointer; margin-bottom: 15px; }
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
def fetch_live_data(tickers):
    results = []
    for i in range(0, len(tickers), 10):
        batch = tickers[i:i+10]
        symbols = ",".join(batch)
        try:
            url = f"https://query1.finance.yahoo.com/v7/finance/quote?symbols={symbols}"
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'quoteResponse' in data and 'result' in data['quoteResponse']:
                    for stock in data['quoteResponse']['result']:
                        try:
                            name = stock.get('symbol', '').replace('.NS', '')
                            price = stock.get('regularMarketPrice', 0)
                            prev_close = stock.get('regularMarketPreviousClose', price)
                            change = stock.get('regularMarketChangePercent', 0)
                            volume = stock.get('regularMarketVolume', 0)
                            avg_volume = stock.get('averageDailyVolume3Month', volume)
                            high_52w = stock.get('fiftyTwoWeekHigh', price)
                            vol_ratio = volume / avg_volume if avg_volume > 0 else 1.0
                            drop_52w = ((price - high_52w) / high_52w * 100) if high_52w > 0 else 0
                            rsi = 50 + (change * 3)
                            rsi = max(0, min(100, rsi))
                            results.append({
                                'name': name, 'price': price, 'change': change,
                                'rsi': rsi, 'vol_ratio': vol_ratio,
                                'high_52w': high_52w, 'drop_52w': drop_52w
                            })
                        except:
                            continue
        except:
            continue
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
st.markdown('<div class="header-title">Market Detective 🕵️‍️</div>', unsafe_allow_html=True)

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
        live_data = fetch_live_data(STOCK_UNIVERSE)
        live_data = calculate_scores(live_data, current_mode)
        is_live = len(live_data) > 0
    except:
        live_data = []
        is_live = False

if is_live:
    st.markdown(f"""
    <div class="status-bar">
        <span><span class="status-dot-live"></span>LIVE DATA | {datetime.now().strftime('%H:%M:%S')}</span>
        <span>Live</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f'<div class="header-subtitle">Live Market Data | {datetime.now().strftime("%d %b %Y")}</div>', unsafe_allow_html=True)
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
            <div class="stock-change {change_class}">{change_sign}{s['change']:.2f}% {'🟢' if s['change']>=0 else '🔴'}</div>
            <span class="score-badge score-green">Score: {int(score)}</span>
        </div>
        """, unsafe_allow_html=True)
    if not strong:
        st.markdown('<div class="no-results">No strong momentum setups</div>', unsafe_allow_html=True)
    
    st.markdown('<div class="section-title">Weak / Bearish Setups ️</div>', unsafe_allow_html=True)
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
