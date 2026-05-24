"""
AlpacaBot Streamlit Dashboard
執行方式: streamlit run dashboard/app.py
"""
import json
import os
import sys
import math
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# 加入 project root 到 path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.alpaca_client import load_all_clients, load_account_config
from core.market_data import (
    get_latest_prices, get_pnl_pcts, get_pe_ratio,
    get_top10_by_market_cap, predict_next_top10, get_benchmark_returns,
    get_benchmark_nav_history
)
from reports.model.generate import get_history

# ── 頁面設定 ──────────────────────────────────────────────
st.set_page_config(
    page_title="AlpacaBot Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 自訂 CSS ──────────────────────────────────────────────
st.markdown("""
<style>
  .main { background-color: #0f172a; }
  .stMetric { background: #1e293b; border-radius: 10px; padding: 12px; border: 1px solid #334155; }
  .stMetric label { color: #94a3b8 !important; }
  h1, h2, h3 { color: #e2e8f0; }
  .warning-box { background:#7f1d1d20; border:1px solid #ef4444; border-radius:8px;
                  padding:10px 16px; color:#fca5a5; font-size:.85rem; margin-bottom:12px; }
</style>
""", unsafe_allow_html=True)


# ── 載入設定 ──────────────────────────────────────────────
@st.cache_data(ttl=300)
def load_configs():
    return load_account_config()


@st.cache_data(ttl=60)
def get_account_info(account_id: str):
    configs = load_configs()
    clients = load_all_clients()
    client = clients.get(account_id)
    if not client:
        return None, None
    acct = client.get_account()
    positions = client.get_positions()
    return acct, positions


@st.cache_data(ttl=300)
def get_top10_cached():
    return get_top10_by_market_cap()


@st.cache_data(ttl=600)
def get_benchmark_history_cached(symbol: str, days: int = 90):
    return get_benchmark_nav_history(symbol, days)


# ── Sidebar ───────────────────────────────────────────────
st.sidebar.title("📊 AlpacaBot")
st.sidebar.markdown("---")

configs = load_configs()
account_options = {f"{c['name']} ({c['account_id']})": c for c in configs if c.get("enabled", True)}
selected_label = st.sidebar.selectbox("選擇帳戶", list(account_options.keys()))
selected_config = account_options[selected_label]
account_id = selected_config["account_id"]

st.sidebar.markdown("---")
st.sidebar.markdown("### ⚠️ 免責聲明")
st.sidebar.caption(
    "本 Dashboard 所有資訊**僅供參考**，"
    "不構成任何投資建議。"
    "投資有風險，請謹慎評估。"
)
st.sidebar.markdown("---")
auto_refresh = st.sidebar.checkbox("自動更新（每60秒）", value=False)
if auto_refresh:
    import time; time.sleep(60); st.rerun()

# ── 主頁面 ────────────────────────────────────────────────
st.title("📊 AlpacaBot Dashboard")
st.markdown(
    f"**帳戶：** {selected_config['name']} | "
    f"**策略：** `{selected_config['active_strategy']}` | "
    f"**更新：** {datetime.now().strftime('%H:%M:%S')}"
)
st.markdown(
    '<div class="warning-box">⚠️ 本 Dashboard 所有內容僅供資訊整理與研究參考，不構成任何投資建議。'
    '投資有風險，過去績效不代表未來結果。</div>',
    unsafe_allow_html=True
)

# ── 帳戶資訊 KPI ──────────────────────────────────────────
acct, positions = get_account_info(account_id)

if acct:
    cash = float(acct.get("cash", 0))
    portfolio_value = float(acct.get("portfolio_value", 0))
    buying_power = float(acct.get("buying_power", 0))
    equity = float(acct.get("equity", portfolio_value))

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💵 現金水位", f"${cash:,.2f}")
    col2.metric("📈 投組總值", f"${portfolio_value:,.2f}")
    col3.metric("⚡ 購買力", f"${buying_power:,.2f}")
    col4.metric("🏦 帳戶狀態", acct.get("status", "N/A"))

    st.markdown("---")

    # ── NAV 走勢圖 ────────────────────────────────────────
    st.subheader("📉 NAV 走勢 vs Benchmark")

    col_toggle1, col_toggle2, col_toggle3 = st.columns([1, 1, 1])
    show_qqq = col_toggle1.checkbox("✅ QQQ（NASDAQ）", value=True)
    show_spy = col_toggle2.checkbox("✅ SPY（S&P500）", value=True)

    history = get_history(account_id)

    fig = go.Figure()

    if history:
        dates = [h["date"] for h in history]
        navs = [h.get("nav", 0) for h in history]
        base_nav = navs[0] if navs[0] else 1
        nav_pcts = [round((n - base_nav) / base_nav * 100, 2) for n in navs]

        fig.add_trace(go.Scatter(
            x=dates, y=nav_pcts,
            name="我的帳戶",
            line=dict(color="#38bdf8", width=2.5),
            fill="tozeroy",
            fillcolor="rgba(56,189,248,0.05)",
        ))

    if show_qqq:
        qqq_hist = get_benchmark_history_cached("QQQ")
        if qqq_hist:
            fig.add_trace(go.Scatter(
                x=[x["date"] for x in qqq_hist],
                y=[x["pct"] for x in qqq_hist],
                name="QQQ",
                line=dict(color="#818cf8", width=1.5, dash="dot"),
            ))

    if show_spy:
        spy_hist = get_benchmark_history_cached("SPY")
        if spy_hist:
            fig.add_trace(go.Scatter(
                x=[x["date"] for x in spy_hist],
                y=[x["pct"] for x in spy_hist],
                name="SPY",
                line=dict(color="#34d399", width=1.5, dash="dot"),
            ))

    fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#94a3b8"),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b", ticksuffix="%"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
        height=320,
        margin=dict(l=0, r=0, t=0, b=0),
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    # ── 持倉清單 ─────────────────────────────────────────
    st.subheader("📋 持倉清單")
    if positions:
        symbols = [p["symbol"] for p in positions]
        prices = get_latest_prices(symbols)

        rows = []
        for pos in positions:
            sym = pos["symbol"]
            qty = int(pos["qty"])
            avg_cost = float(pos.get("avg_entry_price", 0))
            cur_price = prices.get(sym) or float(pos.get("current_price", 0))
            mv = qty * cur_price
            upnl = mv - qty * avg_cost
            upnl_pct = upnl / (qty * avg_cost) * 100 if avg_cost else 0
            pnl = get_pnl_pcts(sym)
            pe = get_pe_ratio(sym)

            rows.append({
                "股票": sym,
                "股數": qty,
                "成本價": f"${avg_cost:.2f}",
                "現價": f"${cur_price:.2f}",
                "市值": f"${mv:,.2f}",
                "未實現損益": f"${upnl:+,.2f}",
                "損益%": f"{upnl_pct:+.1f}%",
                "1日%": f"{pnl['1d']:+.1f}%" if pnl["1d"] is not None else "-",
                "1週%": f"{pnl['1w']:+.1f}%" if pnl["1w"] is not None else "-",
                "1月%": f"{pnl['1m']:+.1f}%" if pnl["1m"] is not None else "-",
                "P/E": f"{pe:.1f}" if pe else "-",
            })

        df = pd.DataFrame(rows)

        def highlight_pnl(val):
            try:
                v = float(val.replace("$", "").replace(",", "").replace("%", "").replace("+", ""))
                color = "#22c55e" if v >= 0 else "#ef4444"
                return f"color: {color}; font-weight: 600"
            except Exception:
                return ""

        styled = df.style.applymap(
            highlight_pnl,
            subset=["未實現損益", "損益%", "1日%", "1週%", "1月%"]
        )
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("目前無持倉")

    st.markdown("---")

    # ── 持倉比重圓餅圖 ────────────────────────────────────
    if positions:
        st.subheader("🥧 持倉比重")
        mv_data = {}
        for pos in positions:
            sym = pos["symbol"]
            qty = int(pos["qty"])
            price = prices.get(sym) or float(pos.get("current_price", 0))
            mv_data[sym] = qty * price

        pie_fig = go.Figure(go.Pie(
            labels=list(mv_data.keys()),
            values=list(mv_data.values()),
            hole=0.4,
            textinfo="label+percent",
        ))
        pie_fig.update_layout(
            paper_bgcolor="#0f172a",
            plot_bgcolor="#0f172a",
            font=dict(color="#e2e8f0"),
            showlegend=True,
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(pie_fig, use_container_width=True)

else:
    st.error("無法取得帳戶資訊，請檢查 API Key 設定")

st.markdown("---")

# ── Top 10 ────────────────────────────────────────────────
col_t1, col_t2 = st.columns(2)

with col_t1:
    st.subheader("🏆 今日 Top 10（市值）")
    with st.spinner("載入中..."):
        top10 = get_top10_cached()
    if top10:
        df_top10 = pd.DataFrame([{
            "排名": f"#{x['rank']}",
            "股票": x["symbol"],
            "現價": f"${x['price']:,.2f}" if x.get("price") else "-",
            "市值(B)": f"${x['market_cap']/1e9:,.0f}B",
        } for x in top10])
        st.dataframe(df_top10, use_container_width=True, hide_index=True)
    st.caption("⚠️ 僅供資訊參考，不構成投資建議")

with col_t2:
    st.subheader("🔮 明日預測 Top 10")
    if top10:
        pred = predict_next_top10(top10)
        df_pred = pd.DataFrame([{
            "排名": f"#{i+1}",
            "股票": sym,
        } for i, sym in enumerate(pred)])
        st.dataframe(df_pred, use_container_width=True, hide_index=True)
    st.caption("⚠️ 預測基於近期動能，不構成投資建議")

st.markdown("---")

# ── 關注股票 ──────────────────────────────────────────────
st.subheader("👀 關注股票")
watchlist = selected_config.get("watchlist", {})

if watchlist:
    tabs = st.tabs(list(watchlist.keys()))
    for tab, (category, symbols) in zip(tabs, watchlist.items()):
        with tab:
            wl_prices = get_latest_prices(symbols)
            rows = []
            for sym in symbols:
                pnl = get_pnl_pcts(sym)
                pe = get_pe_ratio(sym)
                rows.append({
                    "股票": sym,
                    "現價": f"${wl_prices.get(sym):,.2f}" if wl_prices.get(sym) else "-",
                    "1日%": f"{pnl['1d']:+.1f}%" if pnl["1d"] is not None else "-",
                    "1週%": f"{pnl['1w']:+.1f}%" if pnl["1w"] is not None else "-",
                    "1月%": f"{pnl['1m']:+.1f}%" if pnl["1m"] is not None else "-",
                    "P/E": f"{pe:.1f}" if pe else "-",
                })
            df_wl = pd.DataFrame(rows)

            def highlight_wl(val):
                try:
                    v = float(val.replace("%", "").replace("+", ""))
                    return f"color: {'#22c55e' if v >= 0 else '#ef4444'}"
                except Exception:
                    return ""

            styled_wl = df_wl.style.applymap(
                highlight_wl, subset=["1日%", "1週%", "1月%"]
            )
            st.dataframe(styled_wl, use_container_width=True, hide_index=True)

st.markdown("---")

# ── 歷史報告 ──────────────────────────────────────────────
st.subheader("📁 歷史報告回查")
history_all = get_history(account_id)
if history_all:
    hist_df = pd.DataFrame([{
        "日期": h["date"],
        "NAV": f"${h.get('nav', 0):,.2f}",
        "現金": f"${h.get('cash', 0):,.2f}",
        "今日損益": f"${h.get('daily_pnl', 0):+,.2f}",
        "損益%": f"{h.get('daily_pnl_pct', 0):+.2f}%",
        "回撤%": f"{h.get('drawdown_pct', 0):.1f}%",
    } for h in sorted(history_all, key=lambda x: x["date"], reverse=True)])
    st.dataframe(hist_df, use_container_width=True, hide_index=True)
else:
    st.info("尚無歷史報告")

st.markdown("---")
st.caption(
    "⚠️ AlpacaBot | 所有資訊僅供參考，不構成投資建議 | "
    f"更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
)
