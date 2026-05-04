"""
Configuration for the global equity scanner.
Edit this file to change universe, weights, or email settings.
"""

# ============ UNIVERSE ============
# Top liquid names per index. Expand to full constituents in production.
# Full lists: scrape Wikipedia or use index provider files.

SP500_SAMPLE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "JNJ", "WMT", "PG", "MA", "HD", "CVX", "ABBV", "PFE",
    "KO", "PEP", "MRK", "BAC", "TMO", "COST", "DIS", "ADBE", "NFLX",
    "CRM", "AMD", "INTC", "ORCL", "MCD", "NKE", "BA", "GS", "CAT", "GE"
]

STOXX600_SAMPLE = [
    "ASML.AS", "NESN.SW", "NOVO-B.CO", "MC.PA", "RMS.PA", "SAP.DE",
    "SHEL.L", "AZN.L", "HSBA.L", "TTE.PA", "OR.PA", "SIE.DE", "ALV.DE",
    "BP.L", "ULVR.L", "LIN.DE", "SAN.PA", "BNP.PA", "AIR.PA", "RIO.L",
    "GLEN.L", "DGE.L", "BATS.L", "ROG.SW", "NOVN.SW"
]

NIKKEI_SAMPLE = [
    "7203.T", "6758.T", "9984.T", "8306.T", "6861.T", "9432.T", "8035.T",
    "7974.T", "6098.T", "4063.T", "6594.T", "8316.T", "9433.T", "4502.T",
    "8001.T", "8031.T", "6501.T", "7267.T", "6902.T", "9983.T"
]

UNIVERSE = SP500_SAMPLE + STOXX600_SAMPLE + NIKKEI_SAMPLE

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
