import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


st.set_page_config(page_title="Market Detective Pro", page_icon="🕵️‍♂️", layout="wide")

# ==================== STOCK UNIVERSE ====================
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

# ==================== SESSION STATE ====================
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []
if 'trades' not in st.session_state:
    st.session_state.trades = []
if 'mode' not in st.session_state:
    st.session_state.mode = 'swing'
if 'page' not in st.session_state:
    st.session_state.page = 'scanner'
if 'selected_stock' not in st.session_state:
    st.session_state.selected_stock = None

# ==================== DATA FETCHING ====================
@st.cache_data(ttl=600)
def fetch_data(tickers):
    results = []
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            
            # ✅ FIX 1: 3mo ke saath 1y bhi fetch karo 52-week high ke liye
            hist = stock.history(period="3mo")
            hist_1y = stock.history(period="1y")  # 52-week data
            
            if hist.empty:
                continue
                
            closes = hist['Close'].tolist()
            volumes = hist['Volume'].tolist()
            current_price = closes[-1] if closes else 0
            prev_close = closes[-2] if len(closes) > 1 else current_price
            change_pct = ((current_price - prev_close) / prev_close * 100) if prev_close else 0
            
            # RSI calculation (same as before)
            rsi = 50
            if len(closes) >= 15:
                gains, losses = 0, 0
                for i in range(-14, 0):
                    if abs(i) < len(closes):
                        diff = closes[i] - closes[i-1]
                        if diff > 0: gains += diff
                        else: losses -= diff
                avg_gain = gains / 14
                avg_loss = losses / 14
                if avg_loss > 0:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
            
            # Volume ratio (same)
            avg_vol = sum(volumes[-20:]) / 20 if len(volumes) >= 20 else sum(volumes) / len(volumes) if volumes else 1
            current_vol = volumes[-1] if volumes else 0
            vol_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0
            
            # ✅ FIX 1 CONTINUED: Actual 52-week high calculation
            if not hist_1y.empty:
                high_52w = hist_1y['High'].max()  # 1 saal ka HIGH
            else:
                high_52w = max(closes) if closes else current_price
            
            drop_52w = ((current_price - high_52w) / high_52w * 100) if high_52w > 0 else 0
            
            # Fundamentals
            info = stock.info
            
            # ✅ FIX 2: Better None handling
            pe_ratio = info.get('trailingPE')
            if pe_ratio is None:
                pe_ratio = info.get('forwardPE', 0) or 0
            
            industry_pe = info.get('industryPe') or info.get('industryPE') or 0
            
            roe = info.get('returnOnEquity') or 0
            roe_pct = (roe * 100) if roe and roe < 1 else (roe if roe else 0)
            
            de_ratio = info.get('debtToEquity') or 0
            de_ratio_decimal = (de_ratio / 100) if de_ratio and de_ratio > 1 else (de_ratio if de_ratio else 0)
            
            market_cap = info.get('marketCap') or 0
            market_cap_cr = market_cap / 10000000 if market_cap else 0
            industry = info.get('industry', 'N/A')
            name = ticker.replace('.NS', '')
            
            results.append({
                'name': name, 'ticker': ticker, 'price': current_price, 'change': change_pct,
                'rsi': rsi, 'vol_ratio': vol_ratio, 'high_52w': high_52w, 'drop_52w': drop_52w,
                'pe_ratio': pe_ratio, 'industry_pe': industry_pe, 'roe_pct': roe_pct,
                'de_ratio': de_ratio_decimal, 'market_cap_cr': market_cap_cr, 'industry': industry
            })
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            continue
    return results
# ==================== SCORING ====================
def calc_scores(data, mode):
    for stock in data:
        if mode == 'intraday':
            score = 50
            if stock['change'] > 0: score += 20
            if stock['vol_ratio'] > 1.2: score += 20
            if stock['rsi'] > 55: score += 15
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
            if stock['roe_pct'] > 12: fund_score += 10; fund_met += 1
            if stock['de_ratio'] < 1.5: fund_score += 10; fund_met += 1
            if 0 < stock['pe_ratio'] < 25: fund_score += 10; fund_met += 1
            if stock['market_cap_cr'] > 1000: fund_score += 5; fund_met += 1
            if tech_met >= 2 and fund_met >= 3: tech_score += 10
            stock['swing_score'] = min(100, max(0, tech_score + fund_score))
    return data

# ==================== PE ANALYSIS ====================
def pe_analysis(stock):
    pe = stock['pe_ratio']
    ind_pe = stock['industry_pe']
    if pe <= 0: return "N/A", ""
    if ind_pe <= 0:
        if pe < 20: return "Sasta (Undervalued)", "🟢"
        elif pe < 30: return "Fair Valued", "🟡"
        else: return "Mehenga (Overvalued)", "🔴"
    discount = ((ind_pe - pe) / ind_pe) * 100
    if pe < ind_pe * 0.7: return f"Bahut Sasta ({discount:.0f}% discount)", "🟢"
    elif pe < ind_pe: return f"Sasta ({discount:.0f}% discount)", "🟢"
    elif pe < ind_pe * 1.2: return "Fair Valued", ""
    else:
        premium = ((pe - ind_pe) / ind_pe) * 100
        return f"Mehenga ({premium:.0f}% premium)", "🔴"

# ==================== STOCK DETAIL PAGE ====================
def show_stock_detail(stock_name, live_data):
    stock = next((s for s in live_data if s['name'] == stock_name), None)
    if not stock:
        st.error("Stock data not found.")
        return
    
    st.button("⬅️ Back to Scanner", on_click=lambda: st.session_state.update({'selected_stock': None}))
    
    st.title(f"🕵️‍️ {stock['name']} - Detailed Analysis")
    st.subheader(f"💰 Current Price: ₹{stock['price']:.2f} ({stock['change']:+.2f}%)")
    
    # 1. Chart
    st.markdown("### 📈 1 Year Price Chart")
    try:
        hist_data = yf.Ticker(stock['ticker']).history(period="1y")
        if not hist_data.empty:
            st.line_chart(hist_data['Close'])
        else:
            st.info("Chart data not available.")
    except:
        st.error("Could not load chart data.")
    
    # 2. Key Metrics
    st.markdown("### 📊 Key Fundamentals")
    pe_status, pe_emoji = pe_analysis(stock)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("P/E Ratio", f"{stock['pe_ratio']:.1f} {pe_emoji}")
        st.caption(f"Industry P/E: {stock['industry_pe']:.1f}")
    with col2:
        st.metric("ROE", f"{stock['roe_pct']:.1f}%")
    with col3:
        st.metric("Debt/Equity", f"{stock['de_ratio']:.2f}")
    with col4:
        st.metric("Market Cap", f"₹{stock['market_cap_cr']:.0f} Cr")
    
    st.info(f"**Valuation Verdict:** {pe_status}")
    
    # 3. Peer Comparison
    st.markdown("### 🏭 Peer Comparison (Same Industry)")
    peers = [s for s in live_data if s['industry'] == stock['industry'] and s['name'] != stock['name']]
    if peers:
        peer_data = [{'Name': p['name'], 'Price': p['price'], 'P/E': p['pe_ratio'], 'ROE %': p['roe_pct'], 'D/E': p['de_ratio']} for p in peers[:5]]
        st.table(pd.DataFrame(peer_data))
    else:
        st.info("No direct peers found in the current scan list.")
    
    # 4. Recent News
    st.markdown("### 📰 Recent News")
    try:
        news = yf.Ticker(stock['ticker']).news
        if news:
            for item in news[:3]:
                title = item.get('title', 'No Title')
                link = item.get('link', '#')
                st.markdown(f"- [{title}]({link})")
        else:
            st.info("No recent news found.")
    except:
        st.warning("Could not fetch news (Yahoo Finance restriction).")

# ==================== MAIN APP ====================
st.title("🕵️‍♂️ Market Detective Pro")

# Navigation
nav_col1, nav_col2, nav_col3, nav_col4 = st.columns(4)
with nav_col1:
    if st.button("📊 Scanner", use_container_width=True):
        st.session_state.page = 'scanner'
        st.session_state.selected_stock = None
with nav_col2:
    if st.button("⭐ Watchlist", use_container_width=True):
        st.session_state.page = 'watchlist'
        st.session_state.selected_stock = None
with nav_col3:
    if st.button("📓 Trade Journal", use_container_width=True):
        st.session_state.page = 'journal'
        st.session_state.selected_stock = None
with nav_col4:
    if st.button("ℹ️ About", use_container_width=True):
        st.session_state.page = 'about'
        st.session_state.selected_stock = None

# Fetch Data
if st.button("🔄 Refresh Live Data", use_container_width=True):
    st.cache_data.clear()

with st.spinner("Fetching live market data..."):
    try:
        live_data = fetch_data(STOCK_UNIVERSE)
        if live_data:
            live_data = calc_scores(live_data, st.session_state.mode)
            is_live = True
        else:
            is_live = False
            live_data = []
    except:
        is_live = False
        live_data = []

if is_live:
    st.success(f"✅ LIVE DATA | {len(live_data)} stocks loaded")
else:
    st.error("❌ Data fetch failed.")

# ==================== ROUTING ====================
if st.session_state.selected_stock:
    show_stock_detail(st.session_state.selected_stock, live_data)

elif st.session_state.page == 'scanner':
    st.subheader(" Stock Scanner")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("⚡ Intraday Mode", use_container_width=True):
            st.session_state.mode = 'intraday'
    with col2:
        if st.button("📈 Swing Trading Mode", use_container_width=True):
            st.session_state.mode = 'swing'
    
    st.info(f"Current Mode: **{st.session_state.mode.upper()}**")
    
    search_query = st.text_input("🔍 Search stock...", placeholder="Enter stock name...")
    filtered = [s for s in live_data if search_query.upper() in s['name']] if search_query else live_data
    
    if st.session_state.mode == 'intraday':
        strong = sorted([s for s in filtered if s.get('intra_score', 0) >= 70], key=lambda x: x.get('intra_score', 0), reverse=True)
        st.subheader(" Top Momentum Setups")
        for s in strong:
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(f"### {s['name']}")
                st.markdown(f"**₹{s['price']:.2f}** ({s['change']:+.2f}%)")
            with col2:
                st.markdown(f"**RSI:** {s['rsi']:.1f} | **Vol:** {s['vol_ratio']:.2f}x")
            with col3:
                st.markdown(f"### 🎯 {int(s['intra_score'])}")
                if st.button(f" Details", key=f"det_{s['name']}"):
                    st.session_state.selected_stock = s['name']
                    st.rerun()
            st.markdown("---")
    else:
        strong = sorted([s for s in filtered if s.get('swing_score', 0) >= 70], key=lambda x: x.get('swing_score', 0), reverse=True)
        st.subheader("💎 Deep Value + Strong Fundamentals")
        for s in strong:
            pe_status, pe_emoji = pe_analysis(s)
            col1, col2, col3 = st.columns([2, 2, 1])
            with col1:
                st.markdown(f"### {s['name']}")
                st.markdown(f"**₹{s['price']:.2f}** ({s['drop_52w']:.1f}% from 52W)")
            with col2:
                st.markdown(f"**P/E:** {s['pe_ratio']:.1f} {pe_emoji} | **Ind PE:** {s['industry_pe']:.1f}")
                st.markdown(f"**ROE:** {s['roe_pct']:.1f}% | **D/E:** {s['de_ratio']:.2f}")
                st.markdown(f"**Verdict:** {pe_status}")
            with col3:
                st.markdown(f"### 🎯 {int(s['swing_score'])}")
                if st.button(f" Details", key=f"det_{s['name']}"):
                    st.session_state.selected_stock = s['name']
                    st.rerun()
            st.markdown("---")

elif st.session_state.page == 'watchlist':
    st.subheader("⭐ My Watchlist")
    if not st.session_state.watchlist:
        st.info("Your watchlist is empty.")
    else:
        for stock_name in st.session_state.watchlist:
            stock = next((s for s in live_data if s['name'] == stock_name), None)
            if stock:
                pe_status, pe_emoji = pe_analysis(stock)
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"### {stock['name']}")
                    st.markdown(f"**{stock['price']:.2f}**")
                with col2:
                    st.markdown(f"**P/E:** {stock['pe_ratio']:.1f} {pe_emoji} | **ROE:** {stock['roe_pct']:.1f}%")
                    st.markdown(f"**Verdict:** {pe_status}")
                with col3:
                    if st.button(f"🔍 Details", key=f"wdet_{stock['name']}"):
                        st.session_state.selected_stock = stock['name']
                        st.rerun()
                    if st.button(f"❌ Remove", key=f"wrem_{stock['name']}"):
                        st.session_state.watchlist.remove(stock['name'])
                        st.rerun()
                st.markdown("---")

elif st.session_state.page == 'journal':
    st.subheader("📓 Trade Journal")
    with st.form("new_trade"):
        col1, col2, col3 = st.columns(3)
        with col1:
            t_stock = st.text_input("Stock Name")
            t_entry = st.number_input("Entry Price", min_value=0.0)
            t_sl = st.number_input("Stop Loss", min_value=0.0)
        with col2:
            t_target = st.number_input("Target", min_value=0.0)
            t_exit = st.number_input("Exit Price (0 if open)", min_value=0.0)
            t_qty = st.number_input("Quantity", min_value=1, value=1)
        with col3:
            t_setup = st.selectbox("Setup", ["Swing Buy", "Intraday", "Breakout", "Value Buy"])
            t_reason = st.text_area("Reason")
        if st.form_submit_button("💾 Save Trade"):
            if t_stock and t_entry > 0:
                risk = t_entry - t_sl if t_sl > 0 else 1
                reward = t_target - t_entry if t_target > 0 else 0
                pnl = (t_exit - t_entry) * t_qty if t_exit > 0 else 0
                st.session_state.trades.append({
                    'date': datetime.now(IST).strftime('%Y-%m-%d'), 'stock': t_stock,
                    'entry': t_entry, 'sl': t_sl, 'target': t_target, 'exit': t_exit,
                    'qty': t_qty, 'setup': t_setup, 'reason': t_reason,
                    'rr': round(reward/risk, 2), 'pnl': round(pnl, 2),
                    'status': 'Closed' if t_exit > 0 else 'Open'
                })
                st.success("Trade saved!")
                st.rerun()
    
    if st.session_state.trades:
        st.markdown("---")
        st.subheader("📊 Statistics")
        closed = [t for t in st.session_state.trades if t['status'] == 'Closed']
        wins = [t for t in closed if t['pnl'] > 0]
        total_pnl = sum(t['pnl'] for t in closed)
        win_rate = (len(wins) / len(closed) * 100) if closed else 0
        c1, c2, c3 = st.columns(3)
        c1.metric("Total Trades", len(closed))
        c2.metric("Win Rate", f"{win_rate:.1f}%")
        c3.metric("Total P&L", f"₹{total_pnl:.2f}")
        
        st.subheader("📋 Trade History")
        for t in reversed(st.session_state.trades):
            st.markdown(f"**{t['stock']}** ({t['setup']}) - {t['date']} | P&L: ₹{t['pnl']:.2f} | Status: {t['status']}")

elif st.session_state.page == 'about':
    st.subheader("ℹ️ About Market Detective Pro")
    st.markdown("""
    **Features:**
    - 🔍 **Scanner:** 50+ stocks scan (Technical + Fundamental)
    - 💎 **Swing Logic:** 60-70% drop + strong fundamentals
    - 📊 **Industry PE:** Stock P/E vs Industry P/E comparison
    - ⭐ **Watchlist:** Save favorite stocks
    - 📓 **Trade Journal:** Log trades, track P&L and Win Rate
    - 🔍 **Stock Detail Page:** Charts, News, and Peer Comparison
    
    ⚠️ **Disclaimer:** Educational purpose only. Not financial advice.
    """)

st.markdown("---")
st.caption("⚠️ Educational tool only. Not financial advice. Data from Yahoo Finance (delayed).")
