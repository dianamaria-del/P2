"""
Data fetcher: pulls fundamentals, price history, and news for each ticker.
Uses yfinance (free) as the primary source. Replaceable with FMP / Alpha Vantage
/ Refinitiv for production-grade data.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import warnings
warnings.filterwarnings("ignore")


def fetch_one(ticker: str) -> dict:
    """Fetch fundamentals, price history and news for a single ticker."""
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}

        # ---- price history (1y daily for technicals) ----
        hist = t.history(period="1y", interval="1d")
        if hist.empty or len(hist) < 50:
            return {"ticker": ticker, "ok": False, "reason": "no price data"}

        # ---- news ----
        try:
            news = t.news[:10] if hasattr(t, "news") else []
        except Exception:
            news = []

        # ---- compute extras ----
        close = hist["Close"]
        ret_1m = (close.iloc[-1] / close.iloc[-21] - 1) if len(close) > 21 else np.nan
        ret_3m = (close.iloc[-1] / close.iloc[-63] - 1) if len(close) > 63 else np.nan
        ret_12m = (close.iloc[-1] / close.iloc[0] - 1)
        sma50  = close.rolling(50).mean().iloc[-1]
        sma200 = close.rolling(200).mean().iloc[-1] if len(close) >= 200 else np.nan
        vol_30d = close.pct_change().rolling(30).std().iloc[-1] * np.sqrt(252)

        # RSI(14)
        delta = close.diff()
        up = delta.clip(lower=0).rolling(14).mean()
        dn = (-delta.clip(upper=0)).rolling(14).mean()
        rs = up / dn.replace(0, np.nan)
        rsi = 100 - 100 / (1 + rs.iloc[-1]) if not pd.isna(rs.iloc[-1]) else np.nan

        return {
            "ticker": ticker,
            "ok": True,
            "name": info.get("longName") or info.get("shortName") or ticker,
            "sector": info.get("sector", "Unknown"),
            "industry": info.get("industry", "Unknown"),
            "country": info.get("country", "Unknown"),
            "currency": info.get("currency", "USD"),
            "market_cap": info.get("marketCap", np.nan),
            "price": close.iloc[-1],

            # fundamentals
            "pe_ttm":         info.get("trailingPE", np.nan),
            "pe_fwd":         info.get("forwardPE", np.nan),
            "pb":             info.get("priceToBook", np.nan),
            "ev_ebitda":      info.get("enterpriseToEbitda", np.nan),
            "peg":            info.get("pegRatio", np.nan),
            "fcf_yield":      _fcf_yield(info),
            "div_yield":      info.get("dividendYield", 0) or 0,
            "roe":            info.get("returnOnEquity", np.nan),
            "roa":            info.get("returnOnAssets", np.nan),
            "debt_equity":    info.get("debtToEquity", np.nan),
            "rev_growth":     info.get("revenueGrowth", np.nan),
            "earnings_growth":info.get("earningsGrowth", np.nan),
            "profit_margin":  info.get("profitMargins", np.nan),
            "target_mean":    info.get("targetMeanPrice", np.nan),
            "recommendation": info.get("recommendationKey", "none"),

            # technicals
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_12m": ret_12m,
            "sma50":  sma50,
            "sma200": sma200,
            "rsi":    rsi,
            "vol_30d": vol_30d,
            "above_sma200": close.iloc[-1] > sma200 if not pd.isna(sma200) else False,

            # news
            "news": news,
        }
    except Exception as e:
        return {"ticker": ticker, "ok": False, "reason": str(e)}


def _fcf_yield(info: dict) -> float:
    """Compute FCF yield = free cash flow / market cap."""
    fcf = info.get("freeCashflow")
    mcap = info.get("marketCap")
    if fcf and mcap and mcap > 0:
        return fcf / mcap
    return np.nan


def fetch_universe(tickers: list, max_workers: int = 8) -> pd.DataFrame:
    """Fetch all tickers in parallel and return a DataFrame."""
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = {ex.submit(fetch_one, t): t for t in tickers}
        for i, f in enumerate(as_completed(futures), 1):
            r = f.result()
            results.append(r)
            if i % 10 == 0:
                print(f"  fetched {i}/{len(tickers)}")
    df = pd.DataFrame([r for r in results if r.get("ok")])
    failed = [r["ticker"] for r in results if not r.get("ok")]
    if failed:
        print(f"  failed: {len(failed)} tickers ({failed[:5]}...)")
    return df
