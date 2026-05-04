"""
Configuration for the global equity scanner.
Edit this file to change universe, weights, or email settings.
"""

# ============ UNIVERSE: Top 50 US companies by market cap ============
# At ~4 API calls per ticker, ~50 tickers = ~200 calls per scan.
# Fits within FMP Basic 250-calls/day budget with 50 calls of headroom.

US_MEGACAPS = [
    "NVDA", "GOOGL", "AAPL", "MSFT", "AMZN", "AVGO", "META", "TSLA", "BRK-B", "WMT",
    "LLY", "JPM", "V", "XOM", "MA", "ORCL", "JNJ", "COST", "PG", "HD",
    "NFLX", "BAC", "ABBV", "CVX", "KO", "CRM", "TMUS", "WFC", "CSCO", "PM",
    "IBM", "ABT", "MCD", "LIN", "GE", "MRK", "AXP", "DIS", "NOW", "ISRG",
    "T", "PEP", "GS", "INTU", "RTX", "TXN", "BKNG", "QCOM", "CAT",
]

UNIVERSE = US_MEGACAPS

# Legacy aliases (kept so app.py imports don't break)
SP500_SAMPLE = US_MEGACAPS
STOXX600_SAMPLE = []
NIKKEI_SAMPLE = []

# ============ FACTOR WEIGHTS ============
# Composite score = w_fund * fundamentals + w_tech * technicals + w_sent * sentiment
# All sub-scores normalized to [-1, +1] where +1 = strongly undervalued / bullish
WEIGHTS = {
    "fundamentals": 0.55,
    "technicals":   0.25,
    "sentiment":    0.20,
}

# ============ FUNDAMENTAL SUB-WEIGHTS ============
FUND_WEIGHTS = {
    "pe_vs_sector":      0.25,  # lower P/E vs sector → undervalued
    "ev_ebitda":         0.20,
    "fcf_yield":         0.20,
    "peg":               0.15,
    "roic":              0.10,  # quality overlay
    "debt_equity":       0.10,  # quality overlay (lower = better)
}

# ============ THRESHOLDS ============
# Composite score interpretation
SCORE_THRESHOLDS = {
    "strong_buy":   0.50,   # top tier undervalued
    "buy":          0.20,
    "hold_high":    0.20,
    "hold_low":    -0.20,
    "sell":        -0.20,
    "strong_sell": -0.50,
}

# ============ EMAIL SETTINGS ============
# Fill these in before running send_report.py
EMAIL_CONFIG = {
    "smtp_server":   "smtp.gmail.com",
    "smtp_port":     587,
    "sender_email":  "your.email@gmail.com",
    "sender_password": "YOUR_APP_PASSWORD",  # use an app-specific password, not main pwd
    "recipient":     "diana@example.com",
    "subject_prefix": "[Daily Equity Scan]",
}

# ============ DATA / RUN SETTINGS ============
RUN_SETTINGS = {
    "top_n_each_side":   15,    # report top 15 undervalued + top 15 overvalued
    "min_market_cap_usd": 5e9,  # skip illiquid names below 5bn
    "news_lookback_days": 3,
    "request_timeout":    10,
    "max_workers":        8,    # parallel fetch threads
}
