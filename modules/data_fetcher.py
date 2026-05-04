"""
Data fetcher using Financial Modeling Prep STABLE API endpoints.
Works with Basic (free) tier: 250 calls/day.
Get a key at https://financialmodelingprep.com
"""
 
import os
import requests
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")
 
# Try Streamlit secrets first, then env var
try:
    import streamlit as st
    API_KEY = st.secrets.get("FMP_API_KEY", os.getenv("FMP_API_KEY", ""))
except Exception:
    API_KEY = os.getenv("FMP_API_KEY", "")
 
BASE = "https://financialmodelingprep.com/stable"
 
 
def _get(endpoint: str, params: dict = None):
    """Generic FMP stable GET request. Returns parsed JSON or [] on failure."""
    if not API_KEY:
        return []
    url = f"{BASE}/{endpoint}"
    p = {"apikey": API_KEY}
    if params:
        p.update(params)
    try:
        r = requests.get(url, params=p, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        # FMP sometimes returns dict with Error Message, sometimes list
        if isinstance(data, dict) and "Error Message" in data:
            return []
        return data
    except Exception:
        return []
 
 
def _safe_first(data):
    """Return first element of a list, or empty dict."""
    if isinstance(data, list) and data:
        return data[0]
    return {}
 
 
def fetch_one(ticker: str) -> dict:
    """Fetch fundamentals, price history, and news for a single ticker."""
    try:
        # ---- profile ----
        profile = _safe_first(_get("profile", {"symbol": ticker}))
        if not profile:
            return {"ticker": ticker, "ok": False, "reason": "no profile"}
 
        # ---- key metrics TTM ----
        metrics = _safe_first(_get("key-metrics-ttm", {"symbol": ticker}))
 
        # ---- ratios TTM ----
        ratios = _safe_first(_get("ratios-ttm", {"symbol": ticker}))
 
        # ---- price history (1y daily) ----
        hist_resp = _get("historical-price-eod/full", {"symbol": ticker})
        # Stable endpoint returns either a list directly or dict with "historical"
        if isinstance(hist_resp, dict):
            hist_list = hist_resp.get("historical", [])
        elif isinstance(hist_resp, list):
            hist_list = hist_resp
        else:
            hist_list = []
 
        if not hist_list or len(hist_list) < 50:
            return {"ticker": ticker, "ok": False, "reason": "insufficient price history"}
 
        # Limit to last 252 trading days for technical calcs
        hist_list = hist_list[:252] if len(hist_list) > 252 else hist_list
        hist = pd.DataFrame(hist_list)
        hist["date"] = pd.to_datetime(hist["date"])
        hist = hist.sort_values("date").reset_index(drop=True)
 
        # Price column varies by endpoint — try common names
        price_col = next((c for c in ["close", "adjClose", "price"] if c in hist.columns), None)
        if not price_col:
            return {"ticker": ticker, "ok": False, "reason": "no price column"}
        close = hist[price_col]
 
        # ---- news (may be paid on stable; gracefully degrade) ----
        news_raw = _get("news/stock", {"symbols": ticker, "limit": 10})
        news = []
        if isinstance(news_raw, list):
            for n in news_raw[:10]:
                ts = 0
                if n.get("publishedDate"):
                    try:
                        ts = int(pd.Timestamp(n["publishedDate"]).timestamp())
                    except Exception:
                        ts = 0
                news.append({
                    "title": n.get("title", ""),
                    "publisher": n.get("site", n.get("publisher", "")),
                    "link": n.get("url", ""),
                    "providerPublishTime": ts,
                })
 
        # ---- compute technicals ----
        ret_1m  = (close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else np.nan
        ret_3m  = (close.iloc[-1] / close.iloc[-63] - 1) if len(close) > 63 else np.nan
        ret_12m = (close.iloc[-1] / close.iloc[0] - 1)
        sma50   = close.rolling(50).mean().iloc[-1]
        sma200  = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
        vol_30d = close.pct_change().rolling(30).std().iloc[-1] * np.sqrt(252)
 
        # RSI(14)
        delta = close.diff()
        up = delta.clip(lower=0).rolling(14).mean()
        dn = (-delta.clip(upper=0)).rolling(14).mean()
        rs = up / dn.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else np.nan
 
        # ---- pull values from metrics & ratios with fallbacks ----
        # FMP stable field names (verified against current docs)
        pe       = metrics.get("peRatioTTM") or ratios.get("priceToEarningsRatioTTM") or np.nan
        pb       = metrics.get("pbRatioTTM") or ratios.get("priceToBookRatioTTM") or np.nan
        ev_ebitda = (metrics.get("enterpriseValueOverEBITDATTM")
                     or metrics.get("evToEBITDATTM") or np.nan)
        peg      = ratios.get("priceEarningsToGrowthRatioTTM") or np.nan
        fcf_yield = (metrics.get("freeCashFlowYieldTTM")
                     or ratios.get("freeCashFlowYieldTTM") or np.nan)
        div_yield = (metrics.get("dividendYieldTTM")
                     or ratios.get("dividendYieldTTM") or 0) or 0
        roe      = metrics.get("roeTTM") or ratios.get("returnOnEquityTTM") or np.nan
        roa      = ratios.get("returnOnAssetsTTM") or np.nan
        de       = (metrics.get("debtToEquityTTM")
                    or ratios.get("debtToEquityRatioTTM") or np.nan)
        margin   = ratios.get("netProfitMarginTTM") or np.nan
 
        return {
            "ticker": ticker,
            "ok": True,
            "name": profile.get("companyName", ticker),
            "sector": profile.get("sector") or "Unknown",
            "industry": profile.get("industry") or "Unknown",
            "country": profile.get("country") or "Unknown",
            "currency": profile.get("currency") or "USD",
            "market_cap": profile.get("mktCap") or profile.get("marketCap", np.nan),
            "price": close.iloc[-1],
 
            # fundamentals
            "pe_ttm": pe,
            "pe_fwd": pe,  # Basic tier doesn't have forward; use TTM
            "pb": pb,
            "ev_ebitda": ev_ebitda,
            "peg": peg,
            "fcf_yield": fcf_yield,
            "div_yield": div_yield,
            "roe": roe,
            "roa": roa,
            "debt_equity": de,
            "rev_growth": np.nan,
            "earnings_growth": np.nan,
            "profit_margin": margin,
            "target_mean": np.nan,
            "recommendation": "none",
 
            # technicals
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_12m": ret_12m,
            "sma50": sma50,
            "sma200": sma200,
            "rsi": rsi,
            "vol_30d": vol_30d,
            "above_sma200": close.iloc[-1] > sma200 if not pd.isna(sma200) else False,
 
            # news
            "news": news,
        }
    except Exception as e:
        return {"ticker": ticker, "ok": False, "reason": str(e)}
 
 
def fetch_universe(tickers: list, max_workers: int = 4) -> pd.DataFrame:
    """Fetch all tickers in parallel.
    NOTE: Basic tier = 250 calls/day. Each ticker uses ~4-5 calls.
    With ~80 tickers you'll burn ~320-400 calls per scan.
    The 1h Streamlit cache helps, but you may still hit limits.
    Recommend: trim universe to ~40 tickers, OR upgrade to Starter ($19/mo).
    """
    if not API_KEY:
        print("WARNING: FMP_API_KEY not set in Streamlit secrets.")
        return pd.DataFrame()
 
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_one, t): t for t in tickers}
        for i, f in enumerate(as_completed(futures), 1):
            results.append(f.result())
            if i % 10 == 0:
                print(f"  fetched {i}/{len(tickers)}")
    df = pd.DataFrame([r for r in results if r.get("ok")])
    failed = [r for r in results if not r.get("ok")]
    if failed:
        reasons = {}
        for f in failed:
            reasons[f.get("reason", "unknown")] = reasons.get(f.get("reason", "unknown"), 0) + 1
        print(f"  failed: {len(failed)} tickers. Reasons: {reasons}")
    return df
