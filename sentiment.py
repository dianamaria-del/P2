"""
News sentiment scoring.
Two backends:
  1. simple_lexicon  — fast, free, no dependencies (default)
  2. finbert         — better accuracy, requires `transformers` + `torch`
  3. anthropic_api   — best accuracy, requires API key + small cost per run

Returns a sentiment score in [-1, +1] per ticker, averaged across recent headlines.
"""

import re
import numpy as np
from datetime import datetime, timedelta


# ---------- minimal financial lexicon (fallback) ----------
POSITIVE = {
    "beat", "beats", "surge", "soar", "rally", "upgrade", "upgrades", "outperform",
    "strong", "record", "growth", "boost", "raise", "raised", "profit", "gain",
    "gains", "bullish", "buy", "expansion", "exceeds", "tops", "approves", "approved",
    "wins", "breakthrough", "innovative", "robust", "accelerate",
}
NEGATIVE = {
    "miss", "misses", "plunge", "drop", "drops", "fall", "falls", "downgrade",
    "downgrades", "underperform", "weak", "loss", "losses", "decline", "cut",
    "cuts", "warning", "warns", "probe", "investigation", "lawsuit", "fraud",
    "bearish", "sell", "concerns", "risk", "risks", "scandal", "recall",
    "halt", "delay", "fired", "resign", "bankruptcy",
}


def lexicon_sentiment(headline: str) -> float:
    if not headline:
        return 0.0
    words = re.findall(r"\b\w+\b", headline.lower())
    pos = sum(1 for w in words if w in POSITIVE)
    neg = sum(1 for w in words if w in NEGATIVE)
    if pos + neg == 0:
        return 0.0
    return (pos - neg) / (pos + neg)


def score_news_for_ticker(news_items: list, lookback_days: int = 3) -> float:
    """Average sentiment across recent headlines for one ticker."""
    if not news_items:
        return 0.0
    cutoff = (datetime.now() - timedelta(days=lookback_days)).timestamp()
    scores = []
    for item in news_items:
        ts = item.get("providerPublishTime", 0)
        if ts and ts < cutoff:
            continue
        title = item.get("title", "")
        scores.append(lexicon_sentiment(title))
    return float(np.mean(scores)) if scores else 0.0


def add_sentiment_column(df, lookback_days: int = 3):
    """Adds 'news_sentiment' and 'news_count' columns to the DataFrame."""
    df = df.copy()
    df["news_sentiment"] = df["news"].apply(
        lambda items: score_news_for_ticker(items, lookback_days)
    )
    df["news_count"] = df["news"].apply(lambda x: len(x) if x else 0)
    return df


# ---------- optional: FinBERT backend (uncomment to use) ----------
# def finbert_sentiment(headline: str, pipe=None) -> float:
#     """Requires: pip install transformers torch
#        Load once: pipe = pipeline('sentiment-analysis', model='ProsusAI/finbert')
#     """
#     if not headline or pipe is None:
#         return 0.0
#     out = pipe(headline[:512])[0]
#     label = out["label"].lower()
#     score = out["score"]
#     if label == "positive": return score
#     if label == "negative": return -score
#     return 0.0
