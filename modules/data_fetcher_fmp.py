"""
Data fetcher using Financial Modeling Prep API.
Free tier: 250 calls/day. Reliable from cloud IPs (unlike yfinance).
Get a key at https://financialmodelingprep.com
"""

import os
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")

# Try Streamlit secrets first, then env var
try:
    import streamlit as st
    API_KEY = st.secrets.get("FMP_API_KEY", os.getenv("FMP_API_KEY", ""))
except Exception:
    API_KEY = os.getenv("FMP_API_KEY", "")

BASE = "https://financialmodelingprep.com/api/v3"


def _get(endpoint: str, params: dict = None) -> list:
    """Generic FMP GET request."""
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
        return data if isinstance(data, list) else []
    except Exception:
        return []


def fetch_one(ticker: str) -> dict:
    """Fetch fundamentals, price history, and news for a single ticker via FMP."""
    try:
        # ---- profile (sector, industry, market cap, price) ----
        profile = _get(f"profile/{ticker}")
        if not profile:
            return {"ticker": ticker, "ok": False, "reason": "no profile"}
        p = profile[0]

        # ---- key metrics (valuation ratios) ----
        metrics = _get(f"key-metrics-ttm/{ticker}")
        m = metrics[0] if metrics else {}

        # ---- financial ratios ----
        ratios = _get(f"ratios-ttm/{ticker}")
        r = ratios[0] if ratios else {}

        # ---- analyst targets ----
        targets = _get(f"price-target-consensus", {"symbol": ticker})
        t_data = targets[0] if targets else {}

        # ---- price history (1y daily) ----
        hist_raw = _get(f"historical-price-full/{ticker}",
                        {"timeseries": 252})
        if not hist_raw or "historical" not in (hist_raw if isinstance(hist_raw, dict) else {}):
            # FMP returns dict here, not list
            hist_resp = requests.get(
                f"{BASE}/historical-price-full/{ticker}",
                params={"timeseries": 252, "apikey": API_KEY},
                timeout=10,
            ).json()
            hist_list = hist_resp.get("historical", []) if isinstance(hist_resp, dict) else []
        else:
            hist_list = hist_raw.get("historical", [])

        if not hist_list or len(hist_list) < 50:
            return {"ticker": ticker, "ok": False, "reason": "insufficient price history"}

        hist = pd.DataFrame(hist_list)
        hist["date"] = pd.to_datetime(hist["date"])
        hist = hist.sort_values("date").reset_index(drop=True)
        close = hist["close"]

        # ---- news ----
        news_raw = _get("stock_news", {"tickers": ticker, "limit": 10})
        news = [{
            "title": n.get("title", ""),
            "publisher": n.get("site", ""),
            "link": n.get("url", ""),
            "providerPublishTime": int(pd.Timestamp(n.get("publishedDate", "")).timestamp())
                                    if n.get("publishedDate") else 0,
        } for n in news_raw] if news_raw else []

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

        # ---- FCF yield ----
        fcf_yield = m.get("freeCashFlowYieldTTM") or np.nan

        return {
            "ticker": ticker,
            "ok": True,
            "name": p.get("companyName", ticker),
            "sector": p.get("sector") or "Unknown",
            "industry": p.get("industry") or "Unknown",
            "country": p.get("country") or "Unknown",
            "currency": p.get("currency") or "USD",
            "market_cap": p.get("mktCap", np.nan),
            "price": close.iloc[-1],

            # fundamentals
            "pe_ttm":          m.get("peRatioTTM", np.nan),
            "pe_fwd":          m.get("peRatioTTM", np.nan),  # FMP free tier doesn't have fwd
            "pb":              m.get("pbRatioTTM", np.nan),
            "ev_ebitda":       m.get("enterpriseValueOverEBITDATTM", np.nan),
            "peg":             r.get("priceEarningsToGrowthRatioTTM", np.nan),
            "fcf_yield":       fcf_yield,
            "div_yield":       m.get("dividendYieldTTM", 0) or 0,
            "roe":             m.get("roeTTM", np.nan),
            "roa":             r.get("returnOnAssetsTTM", np.nan),
            "debt_equity":     m.get("debtToEquityTTM", np.nan),
            "rev_growth":      np.nan,  # would need separate growth endpoint
            "earnings_growth": np.nan,
            "profit_margin":   r.get("netProfitMarginTTM", np.nan),
            "target_mean":     t_data.get("targetConsensus", np.nan),
            "recommendation":  "none",

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
    """Fetch all tickers in parallel and return a DataFrame.
    Note: FMP free tier rate-limits to ~10 requests/sec, so keep workers low.
    """
    if not API_KEY:
        print("WARNING: FMP_API_KEY not set. Add it to Streamlit secrets.")
        return pd.DataFrame()

    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_one, t): t for t in tickers}
        for i, f in enumerate(as_completed(futures), 1):
            results.append(f.result())
            if i % 10 == 0:
                print(f"  fetched {i}/{len(tickers)}")
    df = pd.DataFrame([r for r in results if r.get("ok")])
    failed = [r["ticker"] for r in results if not r.get("ok")]
    if failed:
        print(f"  failed: {len(failed)} tickers ({failed[:5]}...)")
    return df
