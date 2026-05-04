"""
Diana's Global Equity Scanner — Streamlit dashboard
Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from config import UNIVERSE, WEIGHTS, RUN_SETTINGS, US_MEGACAPS
from modules.data_fetcher import fetch_universe
from modules.sentiment import add_sentiment_column
from modules.scoring import compute_composite

# ============================================================
# SECTOR COLOR PALETTE
# ============================================================
# GICS-style sector colors. Consistent across all tabs.
SECTOR_COLORS = {
    "Technology":             "#4C78A8",  # blue
    "Communication Services": "#54A24B",  # green
    "Consumer Cyclical":      "#F58518",  # orange
    "Consumer Defensive":     "#9D7660",  # brown
    "Consumer Staples":       "#9D7660",  # brown (alt naming)
    "Healthcare":             "#E45756",  # red
    "Financial Services":     "#72B7B2",  # teal
    "Financials":             "#72B7B2",  # teal (alt naming)
    "Industrials":            "#B279A2",  # purple
    "Energy":                 "#EECA3B",  # yellow
    "Basic Materials":        "#FF9DA6",  # pink
    "Materials":              "#FF9DA6",  # pink (alt naming)
    "Real Estate":            "#BAB0AC",  # grey
    "Utilities":              "#5778A4",  # dark blue
    "Unknown":                "#CCCCCC",  # light grey
}

def sector_color(sector: str) -> str:
    """Return hex color for a sector, with fallback."""
    return SECTOR_COLORS.get(sector, "#888888")

def sector_badge(sector: str) -> str:
    """Return HTML for a colored sector badge."""
    color = sector_color(sector)
    return (
        f"<span style='background:{color}; color:white; padding:2px 8px; "
        f"border-radius:10px; font-size:0.78rem; font-weight:600; "
        f"white-space:nowrap;'>{sector}</span>"
    )


# ============================================================
# FORMATTING HELPERS
# ============================================================
def _fmt(x, dp=2):
    if pd.isna(x): return "—"
    try: return f"{x:,.{dp}f}"
    except: return str(x)

def _fmt_pct(x):
    if pd.isna(x): return "—"
    return f"{x*100:+.1f}%"

def _fmt_mcap(x):
    if pd.isna(x): return "—"
    if x > 1e12: return f"${x/1e12:.2f}T"
    if x > 1e9:  return f"${x/1e9:.1f}B"
    return f"${x/1e6:.0f}M"

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(
    page_title="Diana's Global Equity Scanner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- light styling ----
st.markdown("""
<style>
    .main .block-container {padding-top: 2rem; max-width: 1400px;}
    .metric-card {
        background: #f6f8fb; padding: 1rem; border-radius: 8px;
        border-left: 4px solid #0B5394;
    }
    .verdict-buy {color: #1E7B3A; font-weight: 700;}
    .verdict-sell {color: #B23B3B; font-weight: 700;}
    .verdict-hold {color: #666; font-weight: 600;}
    .small {font-size: 0.85rem; color: #666;}
</style>
""", unsafe_allow_html=True)


# ============================================================
# DATA LOADING (cached)
# ============================================================
@st.cache_data(ttl=86400, show_spinner=False)
def load_data(tickers: tuple, lookback_days: int, scan_day: str):
    """Fetch + sentiment + score. The scan_day parameter forces a new
    cache entry once per calendar day, ensuring fresh data daily."""
    df = fetch_universe(list(tickers), max_workers=RUN_SETTINGS["max_workers"])
    if df.empty:
        return df
    df = add_sentiment_column(df, lookback_days=lookback_days)
    df = compute_composite(df)
    return df


def get_scan_day_key():
    """Returns a string that changes once per day at midnight US Eastern.
    Used as a cache-busting key so a fresh scan happens once per day."""
    from datetime import datetime, timezone, timedelta
    et_now = datetime.now(timezone.utc) + timedelta(hours=-5)
    return et_now.strftime("%Y-%m-%d")


# ============================================================
# SIDEBAR — Universe & filters
# ============================================================
st.sidebar.title("⚙️ Scanner Controls")

st.sidebar.markdown("### Universe")
indices = st.sidebar.multiselect(
    "Index",
    options=["US Top 50"],
    default=["US Top 50"],
)

custom_tickers = st.sidebar.text_area(
    "Custom tickers (comma-separated)",
    value="",
    help="Add e.g. ADM, BG, WLMIY for agri/commodities exposure"
)

# Build universe
selected = []
if "US Top 50" in indices: selected += US_MEGACAPS
if custom_tickers.strip():
    selected += [t.strip().upper() for t in custom_tickers.split(",") if t.strip()]
selected = list(dict.fromkeys(selected))   # dedupe, preserve order

st.sidebar.caption(f"**{len(selected)} tickers** in universe")

# Sector filter (applied after data loads — see below)
st.sidebar.markdown("### Sector filter")
# We can't populate this until df is loaded, so we use a placeholder
sector_filter_placeholder = st.sidebar.empty()

st.sidebar.markdown("### Factor weights")
w_fund = st.sidebar.slider("Fundamentals", 0.0, 1.0, WEIGHTS["fundamentals"], 0.05)
w_tech = st.sidebar.slider("Technicals",   0.0, 1.0, WEIGHTS["technicals"],   0.05)
w_sent = st.sidebar.slider("Sentiment",    0.0, 1.0, WEIGHTS["sentiment"],    0.05)
total_w = w_fund + w_tech + w_sent or 1
w_fund, w_tech, w_sent = w_fund/total_w, w_tech/total_w, w_sent/total_w
st.sidebar.caption(f"Normalized: F={w_fund:.2f} · T={w_tech:.2f} · S={w_sent:.2f}")

st.sidebar.markdown("### News")
lookback = st.sidebar.slider("News lookback (days)", 1, 14, RUN_SETTINGS["news_lookback_days"])

st.sidebar.markdown("---")
st.sidebar.markdown("### Data freshness")

try:
    from budget import hours_since_last_scan, record_scan
    hours_since = hours_since_last_scan()
except Exception:
    hours_since = 999
    def record_scan(): pass

if hours_since >= 24:
    st.sidebar.info("🔄 Fresh scan will run on this visit.")
else:
    hours_left = 24 - hours_since
    st.sidebar.success(
        f"✅ Data is current.\n\n"
        f"Last scan: {hours_since:.1f}h ago.\n\n"
        f"Next auto-refresh in {hours_left:.1f}h."
    )


# ============================================================
# HEADER
# ============================================================
st.title("📊 Diana's Global Equity Scanner")
st.markdown(
    "<div class='small'>Multi-factor screen across global large-caps · "
    "Fundamentals + Technicals + News sentiment</div>",
    unsafe_allow_html=True,
)
st.markdown("---")


# ============================================================
# LOAD DATA
# ============================================================
if not selected:
    st.warning("Pick at least one index or add custom tickers in the sidebar.")
    st.stop()

scan_day = get_scan_day_key()
with st.spinner(f"Scanning {len(selected)} tickers... (~30-60s on first daily visit)"):
    df = load_data(tuple(selected), lookback, scan_day)

# Mark scan as recorded (best-effort — for sidebar display)
try:
    if hours_since >= 24:
        record_scan()
except Exception:
    pass

if df.empty:
    st.error("No data could be fetched. Check tickers / network connection.")
    st.stop()

# Apply user weights (override config defaults)
df["score_composite"] = (
    w_fund * df["score_fund"] + w_tech * df["score_tech"] + w_sent * df["score_sent"]
).clip(-1, 1)

# Re-label verdicts
def _label(s):
    if s >= 0.50: return "STRONG BUY"
    if s >= 0.20: return "BUY"
    if s >= -0.20: return "HOLD"
    if s >= -0.50: return "SELL"
    return "STRONG SELL"
df["verdict"] = df["score_composite"].apply(_label)

# Now populate the sector filter with actual sectors from the data
all_sectors = sorted(df["sector"].dropna().unique().tolist())
with sector_filter_placeholder.container():
    selected_sectors = st.multiselect(
        "Show sectors",
        options=all_sectors,
        default=all_sectors,
        key="sector_filter",
    )
if selected_sectors:
    df = df[df["sector"].isin(selected_sectors)].reset_index(drop=True)

# ============================================================
# TOP METRICS
# ============================================================
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Universe", f"{len(df)}")
c2.metric("Strong Buy", int((df["score_composite"] >= 0.50).sum()))
c3.metric("Buy", int(((df["score_composite"] >= 0.20) & (df["score_composite"] < 0.50)).sum()))
c4.metric("Sell", int(((df["score_composite"] <= -0.20) & (df["score_composite"] > -0.50)).sum()))
c5.metric("Strong Sell", int((df["score_composite"] <= -0.50).sum()))

# Sector mini-overview
st.markdown("##### Sector breakdown")
sector_summary = df.groupby("sector").agg(
    n=("ticker", "count"),
    avg_score=("score_composite", "mean"),
).reset_index().sort_values("avg_score", ascending=False)

sector_html = "<div style='display:flex; flex-wrap:wrap; gap:6px; margin-bottom:1rem;'>"
for _, row in sector_summary.iterrows():
    color = sector_color(row["sector"])
    score_color = "#1E7B3A" if row["avg_score"] >= 0.20 else (
                  "#B23B3B" if row["avg_score"] <= -0.20 else "#666")
    sector_html += (
        f"<div style='background:{color}1A; border-left:3px solid {color}; "
        f"padding:6px 10px; border-radius:4px; min-width:130px;'>"
        f"<div style='font-size:0.78rem; font-weight:600; color:{color};'>{row['sector']}</div>"
        f"<div style='font-size:0.7rem; color:#666;'>{int(row['n'])} names</div>"
        f"<div style='font-size:0.85rem; font-weight:700; color:{score_color};'>"
        f"{row['avg_score']:+.2f}</div>"
        f"</div>"
    )
sector_html += "</div>"
st.markdown(sector_html, unsafe_allow_html=True)

# ============================================================
# TABS
# ============================================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "🎯 Rankings", "🔍 Deep Dive", "🗺️ Sector Map", "📈 Scatter", "📥 Export"
])


# ---------- TAB 1: Rankings ----------
with tab1:
    st.subheader("🟢 Top Undervalued")
    top_n = st.slider("Show top N", 5, 40, 15, key="under_n")
    top_under = df.nlargest(top_n, "score_composite")[[
        "ticker", "name", "sector", "country", "price", "pe_fwd",
        "ev_ebitda", "fcf_yield", "roe", "ret_12m", "rsi",
        "score_fund", "score_tech", "score_sent", "score_composite", "verdict"
    ]].copy()
    top_under["fcf_yield"] = (top_under["fcf_yield"]*100).round(1)
    top_under["roe"] = (top_under["roe"]*100).round(1)
    top_under["ret_12m"] = (top_under["ret_12m"]*100).round(1)

    def _color_sector(val):
        color = sector_color(val)
        return f"background-color: {color}33; color: #222; font-weight: 600;"

    st.dataframe(
        top_under.style.format({
            "price": "{:.2f}", "pe_fwd": "{:.1f}", "ev_ebitda": "{:.1f}",
            "fcf_yield": "{:.1f}%", "roe": "{:.1f}%", "ret_12m": "{:+.1f}%",
            "rsi": "{:.0f}",
            "score_fund": "{:+.2f}", "score_tech": "{:+.2f}",
            "score_sent": "{:+.2f}", "score_composite": "{:+.2f}",
        }).background_gradient(
            subset=["score_composite"], cmap="RdYlGn", vmin=-1, vmax=1
        ).map(_color_sector, subset=["sector"]),
        use_container_width=True, hide_index=True, height=540,
    )


# ---------- TAB 2: Deep Dive ----------
with tab2:
    st.subheader("Per-ticker deep dive")
    pick = st.selectbox(
        "Choose a ticker",
        options=df.sort_values("score_composite", ascending=False)["ticker"].tolist(),
        format_func=lambda t: f"{t}  —  {df[df.ticker==t].iloc[0]['name']}  ({df[df.ticker==t].iloc[0]['verdict']})",
    )
    if pick:
        row = df[df.ticker == pick].iloc[0]

        # Header
        cA, cB = st.columns([2, 1])
        with cA:
    st.markdown(f"### {row['name']} ({row['ticker']})")
    st.markdown(
        f"{sector_badge(row['sector'])} "
        f"<span style='color:#666; font-size:0.9rem;'>"
        f"{row['industry']} · {row['country']} · "
        f"{row['currency']} {row['price']:.2f} · "
        f"Mkt cap {_fmt_mcap(row['market_cap'])}</span>",
        unsafe_allow_html=True,
    )
        with cB:
            verdict_class = "verdict-buy" if "BUY" in row["verdict"] else (
                            "verdict-sell" if "SELL" in row["verdict"] else "verdict-hold")
            st.markdown(
                f"<div class='metric-card'><div class='small'>Composite Score</div>"
                f"<div style='font-size:2rem;'><b>{row['score_composite']:+.2f}</b></div>"
                f"<div class='{verdict_class}'>{row['verdict']}</div></div>",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # Score breakdown chart
        scores = pd.DataFrame({
            "Factor": ["Fundamentals", "Technicals", "Sentiment"],
            "Score": [row["score_fund"], row["score_tech"], row["score_sent"]],
            "Weight": [w_fund, w_tech, w_sent],
        })
        scores["Contribution"] = scores["Score"] * scores["Weight"]
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=scores["Factor"], y=scores["Score"],
            marker_color=["#0B5394", "#5BA85B", "#D67676"],
            text=[f"{s:+.2f}" for s in scores["Score"]],
            textposition="outside",
        ))
        fig.update_layout(
            title="Sub-scores (range: -1 to +1)",
            yaxis_range=[-1.1, 1.1], height=320,
            margin=dict(t=40, b=20, l=20, r=20),
        )
        fig.add_hline(y=0, line_dash="dash", line_color="grey")
        st.plotly_chart(fig, use_container_width=True)

        # Fundamentals & technicals tables
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Fundamentals**")
            fund_df = pd.DataFrame({
                "Metric": ["Forward P/E", "Trailing P/E", "P/B", "EV/EBITDA", "PEG",
                           "FCF Yield", "Dividend Yield", "ROE", "ROA",
                           "Debt/Equity", "Profit Margin", "Revenue Growth", "Earnings Growth"],
                "Value": [
                    _fmt(row.get("pe_fwd")), _fmt(row.get("pe_ttm")), _fmt(row.get("pb")),
                    _fmt(row.get("ev_ebitda")), _fmt(row.get("peg")),
                    _fmt_pct(row.get("fcf_yield")), _fmt_pct(row.get("div_yield")),
                    _fmt_pct(row.get("roe")), _fmt_pct(row.get("roa")),
                    _fmt(row.get("debt_equity")), _fmt_pct(row.get("profit_margin")),
                    _fmt_pct(row.get("rev_growth")), _fmt_pct(row.get("earnings_growth")),
                ],
            })
            st.dataframe(fund_df, hide_index=True, use_container_width=True)

        with col2:
            st.markdown("**Technicals**")
            tech_df = pd.DataFrame({
                "Metric": ["1m return", "3m return", "12m return",
                           "RSI(14)", "Price vs SMA50", "Price vs SMA200",
                           "30d realized vol", "Analyst target", "Analyst recommendation"],
                "Value": [
                    _fmt_pct(row.get("ret_1m")), _fmt_pct(row.get("ret_3m")),
                    _fmt_pct(row.get("ret_12m")), _fmt(row.get("rsi"), 0),
                    f"{(row['price']/row['sma50']-1)*100:+.1f}%" if row.get('sma50') else "—",
                    f"{(row['price']/row['sma200']-1)*100:+.1f}%" if row.get('sma200') and not pd.isna(row['sma200']) else "—",
                    _fmt_pct(row.get("vol_30d")),
                    _fmt(row.get("target_mean")),
                    str(row.get("recommendation", "—")).upper(),
                ],
            })
            st.dataframe(tech_df, hide_index=True, use_container_width=True)

        # News
        st.markdown("**Recent headlines**")
        if row.get("news"):
            for item in row["news"][:8]:
                title = item.get("title", "")
                publisher = item.get("publisher", "")
                link = item.get("link", "")
                ts = item.get("providerPublishTime", 0)
                date = datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""
                if title:
                    st.markdown(f"- [{title}]({link})  *— {publisher}, {date}*")
        else:
            st.caption("No recent headlines.")


# ---------- TAB 3: Sector heatmap ----------
with tab3:
    st.subheader("Sector valuation heatmap")
    sec = df.groupby("sector").agg(
        avg_score=("score_composite", "mean"),
        count=("ticker", "count"),
        avg_pe=("pe_fwd", "median"),
        avg_ret_12m=("ret_12m", "median"),
    ).reset_index()
    sec = sec[sec["count"] >= 2].sort_values("avg_score", ascending=True)

    fig = px.bar(
        sec, x="avg_score", y="sector", orientation="h",
        color="avg_score", color_continuous_scale="RdYlGn",
        range_color=[-0.5, 0.5],
        labels={"avg_score": "Avg composite score", "sector": ""},
        hover_data={"count": True, "avg_pe": ":.1f", "avg_ret_12m": ":.1%"},
        text=sec["avg_score"].apply(lambda x: f"{x:+.2f}"),
    )
    fig.update_layout(height=500, margin=dict(t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)
    st.caption(f"Sectors with ≥2 names. {len(df)} tickers across {len(sec)} sectors.")


# ---------- TAB 4: Scatter ----------
with tab4:
    st.subheader("Valuation vs Quality scatter")
    st.caption("Each dot = one stock. Hover for details. Use this to spot value traps "
               "(high score but weak fundamentals) and quality compounders.")

    cc1, cc2 = st.columns(2)
    x_metric = cc1.selectbox("X axis", ["pe_fwd", "ev_ebitda", "fcf_yield", "ret_12m", "rsi"], index=0)
    y_metric = cc2.selectbox("Y axis", ["roe", "score_fund", "score_tech", "score_composite", "earnings_growth"], index=0)

    plot_df = df.dropna(subset=[x_metric, y_metric]).copy()
    fig = px.scatter(
    plot_df, x=x_metric, y=y_metric,
    color="sector",
    color_discrete_map=SECTOR_COLORS,
    size=plot_df["market_cap"].fillna(1e9).clip(1e9, 3e12),
    hover_name="ticker",
    hover_data={"name": True, "verdict": True,
                "score_composite": ":.2f"},
)
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True)


# ---------- TAB 5: Export ----------
with tab5:
    st.subheader("Export results")
    export_df = df.drop(columns=["news"], errors="ignore").copy()
    csv = export_df.to_csv(index=False)
    st.download_button(
        "📥 Download full results (CSV)",
        data=csv,
        file_name=f"equity_scan_{datetime.now():%Y%m%d_%H%M}.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.dataframe(export_df, use_container_width=True, height=600)


# ============================================================
# FOOTER / METHODOLOGY
# ============================================================
with st.expander("ℹ️ Methodology & caveats"):
    st.markdown("""
    **Composite score** = weighted blend of three sub-scores, each in **[-1, +1]**:

    - **Fundamentals (default 55%)** — sector-relative z-scores of forward P/E,
      EV/EBITDA, FCF yield, PEG, ROE, debt/equity. Lower valuation multiples and
      higher quality push the score up.
    - **Technicals (default 25%)** — 3m momentum, RSI(14) (mean-reversion at extremes),
      price vs 200d SMA (trend).
    - **Sentiment (default 20%)** — average lexicon-based sentiment of recent headlines
      (last N days). For production, swap in FinBERT or an LLM API in `modules/sentiment.py`.

    **Verdict bands**: Strong Buy ≥ +0.50 · Buy ≥ +0.20 · Hold · Sell ≤ -0.20 · Strong Sell ≤ -0.50.

    **Caveats** — this is a screener, not a recommendation engine.
    Composite scores cluster reasonably, but extreme scores often reflect data issues
    (one-offs in earnings, stale fundamentals) or genuine business problems
    (value traps). Always cross-check with primary sources before acting.

    **Data sources** — yfinance for fundamentals/prices/news (free, occasionally
    flaky). For institutional use, replace `data_fetcher.py` with Refinitiv,
    Bloomberg, or Financial Modeling Prep.
    """)


# ============================================================
# END
# ============================================================
