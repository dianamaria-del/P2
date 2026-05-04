# Global Equity Scanner

Multi-factor screener for global large-caps (S&P 500 + STOXX 600 + Nikkei).
Combines **fundamentals**, **technicals**, and **news sentiment** into a
composite score and ranks stocks as undervalued / overvalued.

Built as an interactive **Streamlit dashboard**.

---

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. run
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

First run takes ~30-60 seconds to fetch ~80 tickers. Subsequent runs use a
1-hour cache (click "Refresh data" in the sidebar to force a re-fetch).

---

## What it does

For every ticker it pulls:

- **Fundamentals** — fwd P/E, EV/EBITDA, FCF yield, PEG, ROE, debt/equity, growth
- **Technicals** — 1m/3m/12m returns, RSI(14), SMA50/200, realized vol
- **News** — last 10 headlines with timestamps

Then it scores each on three axes (each in `[-1, +1]`):

| Sub-score | Default weight | What pushes it up |
|---|---|---|
| Fundamentals | 55% | Cheap relative to sector + high quality |
| Technicals | 25% | Mean-reversion (low RSI) + uptrend |
| Sentiment | 20% | Positive recent headlines |

The **composite score** is the weighted blend, mapped to:
**STRONG BUY** ≥ +0.50 · **BUY** ≥ +0.20 · HOLD · **SELL** ≤ -0.20 · **STRONG SELL** ≤ -0.50

---

## Dashboard tabs

1. **Rankings** — top undervalued / overvalued tables, side by side
2. **Deep Dive** — per-ticker breakdown with sub-scores, fundamentals, technicals, news
3. **Sector Map** — average score by sector, spot rotation themes
4. **Scatter** — pick any X/Y combo to spot value traps and quality compounders
5. **Export** — download full results as CSV

Sidebar lets you:
- Toggle indices on/off
- Add custom tickers (e.g. `ADM, BG, WLMIY` for agri exposure given your sector)
- Adjust factor weights live
- Change news lookback window

---

## File layout

```
stock_scanner/
├── app.py                      # Streamlit dashboard
├── config.py                   # Universe, weights, thresholds — edit me
├── requirements.txt
├── modules/
│   ├── data_fetcher.py         # yfinance wrapper, parallel fetch
│   ├── scoring.py              # z-scores, composite engine
│   └── sentiment.py            # lexicon-based; FinBERT/LLM hooks ready
└── data/                       # (created on first run, optional cache dir)
```

---

## Customization

### Expand the universe to full indices
Currently uses ~80 sample tickers for speed. To scan the full ~1,400 names:

```python
# in config.py — replace SP500_SAMPLE etc. with full constituent lists
# Easy way: scrape Wikipedia
import pandas as pd
SP500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]["Symbol"].tolist()
```

Full universe scans take 15-30 min. Consider running once daily and caching to
disk (uncomment the data caching block in `data_fetcher.py`).

### Better sentiment
The default lexicon is fast but crude. Two upgrades:

**FinBERT (free, local, ~1s/headline):**
```bash
pip install transformers torch
```
Then in `modules/sentiment.py`, uncomment the `finbert_sentiment` function and
swap it into `score_news_for_ticker`.

**LLM API (best, ~$0.50/run for full universe):**
Replace `lexicon_sentiment` with a Claude/GPT call that scores
headline + materiality.

### Replace yfinance for production
yfinance is free but occasionally rate-limited or stale. Drop-in replacements:

- **Financial Modeling Prep** — $20/mo, clean API, full fundamentals
- **Alpha Vantage** — free tier, slower
- **Refinitiv / Bloomberg** — institutional, expensive

Just rewrite `fetch_one()` in `data_fetcher.py` to return the same dict shape.

### Schedule daily runs
Streamlit Cloud auto-refreshes when accessed. For a true daily job:

```bash
# cron (Linux/Mac), every weekday at 7am
0 7 * * 1-5  cd /path/to/stock_scanner && streamlit run app.py
```

Or deploy to **Streamlit Community Cloud** (free) and bookmark the URL.

---

## Caveats — read this

This is a **screener**, not a recommendation engine.

- Composite scores cluster sensibly but extreme scores often reflect **data issues**
  (one-off earnings, stale ratios, M&A pending) or **genuine business problems**
  (value traps). Always cross-check before acting.
- yfinance fundamentals are TTM and update on company filing — not real-time.
- Sentiment from headline lexicons is noisy. Use as a filter, not a signal.
- Backtesting is not included. If you want PnL evidence the factors work, that's
  a separate project — let me know.
