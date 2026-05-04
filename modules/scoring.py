"""
Scoring engine.
Converts raw factors → z-scores within sector → sub-scores → composite.
Output: each ticker gets a score in roughly [-1, +1] where +1 = strongly undervalued.
"""

import numpy as np
import pandas as pd
from config import WEIGHTS, FUND_WEIGHTS, SCORE_THRESHOLDS


def _zscore(s: pd.Series, invert: bool = False) -> pd.Series:
    """Robust z-score. invert=True means lower raw value → higher score."""
    s = pd.to_numeric(s, errors="coerce")
    med = s.median(skipna=True)
    mad = (s - med).abs().median(skipna=True)
    if pd.isna(mad) or mad == 0:
        return pd.Series(0, index=s.index)
    z = (s - med) / (1.4826 * mad)
    z = z.clip(-3, 3) / 3.0     # squeeze to [-1, +1]
    return -z if invert else z


def score_fundamentals(df: pd.DataFrame) -> pd.Series:
    """Return per-ticker fundamentals sub-score in [-1, +1]."""
    out = pd.Series(0.0, index=df.index)
    by_sector = df.groupby("sector", group_keys=False)

    # Lower P/E vs sector → undervalued (invert)
    pe_score = by_sector["pe_fwd"].apply(lambda s: _zscore(s, invert=True))
    out += FUND_WEIGHTS["pe_vs_sector"] * pe_score.fillna(0)

    # Lower EV/EBITDA → undervalued
    ev_score = by_sector["ev_ebitda"].apply(lambda s: _zscore(s, invert=True))
    out += FUND_WEIGHTS["ev_ebitda"] * ev_score.fillna(0)

    # Higher FCF yield → undervalued
    fcf_score = by_sector["fcf_yield"].apply(lambda s: _zscore(s, invert=False))
    out += FUND_WEIGHTS["fcf_yield"] * fcf_score.fillna(0)

    # Lower PEG → undervalued (but penalize negative PEGs as garbage)
    peg_clean = df["peg"].where(df["peg"] > 0)
    peg_score = peg_clean.groupby(df["sector"]).transform(lambda s: _zscore(s, invert=True))
    out += FUND_WEIGHTS["peg"] * peg_score.fillna(0)

    # Higher ROE/ROA → quality (we use ROE as ROIC proxy)
    roic_score = by_sector["roe"].apply(lambda s: _zscore(s, invert=False))
    out += FUND_WEIGHTS["roic"] * roic_score.fillna(0)

    # Lower debt/equity → quality
    de_score = by_sector["debt_equity"].apply(lambda s: _zscore(s, invert=True))
    out += FUND_WEIGHTS["debt_equity"] * de_score.fillna(0)

    return out.clip(-1, 1)


def score_technicals(df: pd.DataFrame) -> pd.Series:
    """Technical sub-score. Combines momentum, mean-reversion, trend."""
    out = pd.Series(0.0, index=df.index)

    # 3m momentum (positive = bullish, but capped to avoid chasing extremes)
    mom_z = _zscore(df["ret_3m"]).clip(-0.7, 0.7)
    out += 0.40 * mom_z.fillna(0)

    # RSI: <30 oversold (bullish), >70 overbought (bearish)
    rsi = df["rsi"].fillna(50)
    rsi_score = ((50 - rsi) / 30).clip(-1, 1)   # 30→+0.67, 70→-0.67
    out += 0.30 * rsi_score

    # Trend: above 200d SMA = +0.5, below = -0.5
    trend = df["above_sma200"].astype(float) - 0.5
    out += 0.30 * trend.fillna(0)

    return out.clip(-1, 1)


def score_sentiment(df: pd.DataFrame, sentiment_col: str = "news_sentiment") -> pd.Series:
    """Sentiment sub-score from news. Uses pre-computed news_sentiment column."""
    if sentiment_col not in df.columns:
        return pd.Series(0.0, index=df.index)
    return df[sentiment_col].clip(-1, 1).fillna(0)


def compute_composite(df: pd.DataFrame) -> pd.DataFrame:
    """Add fundamental, technical, sentiment, and composite scores."""
    df = df.copy()
    df["score_fund"] = score_fundamentals(df)
    df["score_tech"] = score_technicals(df)
    df["score_sent"] = score_sentiment(df)
    df["score_composite"] = (
        WEIGHTS["fundamentals"] * df["score_fund"]
        + WEIGHTS["technicals"]   * df["score_tech"]
        + WEIGHTS["sentiment"]    * df["score_sent"]
    ).clip(-1, 1)
    df["verdict"] = df["score_composite"].apply(_label)
    return df


def _label(s: float) -> str:
    if s >= SCORE_THRESHOLDS["strong_buy"]:    return "STRONG BUY"
    if s >= SCORE_THRESHOLDS["buy"]:           return "BUY"
    if s >= SCORE_THRESHOLDS["hold_low"]:      return "HOLD"
    if s >= SCORE_THRESHOLDS["strong_sell"]:   return "SELL"
    return "STRONG SELL"
