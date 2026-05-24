"""
市場資料模組
- 即時股價（yfinance）
- NASDAQ 市值前十
- P/E 本益比
- 1日/1週/1月 漲跌幅
- Benchmark (QQQ/SPY) NAV
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import yfinance as yf

logger = logging.getLogger(__name__)

# NASDAQ Top 100 名單（市值前100，定期更新）
NASDAQ_TOP_100 = [
    "MSFT", "AAPL", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO",
    "COST", "NFLX", "AMD", "PEP", "ADBE", "CSCO", "TMUS", "TXN", "QCOM",
    "AMGN", "INTU", "HON", "AMAT", "SBUX", "BKNG", "ISRG", "GILD", "MDLZ",
    "ADI", "VRTX", "PANW", "REGN", "MU", "LRCX", "SNPS", "KLAC", "CDNS",
    "CEG", "MAR", "PYPL", "MELI", "ASML", "ABNB", "ORLY", "FTNT", "CTAS",
    "PCAR", "AZN", "DXCM", "CPRT", "ODFL", "ROST", "MRVL", "KDP", "IDXX",
    "FAST", "VRSK", "BIIB", "GEHC", "ON", "ANSS", "WBD", "TEAM", "SMCI",
    "ARM", "APP", "PLTR", "HOOD", "RBLX", "UBER", "DASH"
]


def get_latest_prices(symbols: List[str]) -> Dict[str, float]:
    """取得多支股票最新收盤價"""
    result = {}
    try:
        tickers = yf.download(symbols, period="2d", interval="1d",
                              auto_adjust=True, progress=False)
        close = tickers["Close"]
        for sym in symbols:
            if sym in close.columns:
                price = float(close[sym].dropna().iloc[-1])
                result[sym] = round(price, 2)
            else:
                result[sym] = None
    except Exception as e:
        logger.error(f"批次取價失敗: {e}")
        # fallback: 逐筆取
        for sym in symbols:
            try:
                t = yf.Ticker(sym)
                h = t.history(period="2d")
                if not h.empty:
                    result[sym] = round(float(h["Close"].iloc[-1]), 2)
                else:
                    result[sym] = None
            except Exception as ex:
                logger.warning(f"{sym} 取價失敗: {ex}")
                result[sym] = None
    return result


def get_latest_price(symbol: str) -> Optional[float]:
    """取得單支股票最新收盤價"""
    prices = get_latest_prices([symbol])
    return prices.get(symbol)


def get_market_cap(symbol: str) -> Optional[float]:
    """取得市值（單位：美元）"""
    try:
        t = yf.Ticker(symbol)
        info = t.info
        return info.get("marketCap")
    except Exception as e:
        logger.warning(f"{symbol} 市值取得失敗: {e}")
        return None


def get_top10_by_market_cap(universe: List[str] = None) -> List[Dict]:
    """
    取得指定清單中市值前 10 的股票
    回傳格式：[{symbol, market_cap, price, rank}, ...]
    """
    if universe is None:
        universe = NASDAQ_TOP_100

    logger.info(f"取得市值排行，共 {len(universe)} 支股票")
    caps = []
    for sym in universe:
        cap = get_market_cap(sym)
        if cap:
            caps.append({"symbol": sym, "market_cap": cap})

    caps.sort(key=lambda x: x["market_cap"], reverse=True)
    top10 = caps[:10]

    # 補上股價
    symbols = [x["symbol"] for x in top10]
    prices = get_latest_prices(symbols)
    for i, item in enumerate(top10):
        item["rank"] = i + 1
        item["price"] = prices.get(item["symbol"])

    return top10


def get_pe_ratio(symbol: str) -> Optional[float]:
    """
    取得本益比（P/E Ratio）
    P/E = 股價 ÷ 每股盈餘，越低代表估值相對便宜（需結合產業判斷）
    """
    try:
        t = yf.Ticker(symbol)
        info = t.info
        pe = info.get("trailingPE") or info.get("forwardPE")
        return round(float(pe), 2) if pe else None
    except Exception as e:
        logger.warning(f"{symbol} P/E 取得失敗: {e}")
        return None


def get_pnl_pcts(symbol: str) -> Dict[str, Optional[float]]:
    """
    計算個股 1日/1週/1月 漲跌幅（%）
    """
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period="35d")
        if hist.empty:
            return {"1d": None, "1w": None, "1m": None}

        close = hist["Close"]
        current = float(close.iloc[-1])

        def pct(days):
            if len(close) <= days:
                return None
            past = float(close.iloc[-days - 1])
            return round((current - past) / past * 100, 2) if past else None

        return {
            "1d": pct(1),
            "1w": pct(5),
            "1m": pct(21),
        }
    except Exception as e:
        logger.warning(f"{symbol} 漲跌幅計算失敗: {e}")
        return {"1d": None, "1w": None, "1m": None}


def get_benchmark_returns(symbols: List[str] = None) -> Dict[str, Dict]:
    """
    取得 QQQ / SPY 等 Benchmark 近期漲跌幅
    """
    if symbols is None:
        symbols = ["QQQ", "SPY"]
    result = {}
    for sym in symbols:
        result[sym] = get_pnl_pcts(sym)
    return result


def get_benchmark_nav_history(symbol: str = "QQQ", days: int = 90) -> List[Dict]:
    """
    取得 Benchmark 歷史 NAV（收盤價序列），正規化為百分比漲跌
    """
    try:
        t = yf.Ticker(symbol)
        hist = t.history(period=f"{days}d")
        if hist.empty:
            return []
        close = hist["Close"]
        base = float(close.iloc[0])
        return [
            {
                "date": str(idx.date()),
                "price": round(float(val), 2),
                "pct": round((float(val) - base) / base * 100, 2),
            }
            for idx, val in close.items()
        ]
    except Exception as e:
        logger.warning(f"{symbol} NAV 歷史取得失敗: {e}")
        return []


def predict_next_top10(current_top10: List[Dict]) -> List[str]:
    """
    基於動能（近7日漲幅）預測明日前十
    ⚠️ 此預測僅供參考，不構成投資建議
    """
    scored = []
    for item in current_top10:
        sym = item["symbol"]
        pnl = get_pnl_pcts(sym)
        score = (pnl.get("1w") or 0) * 0.6 + (pnl.get("1d") or 0) * 0.4
        scored.append({"symbol": sym, "score": score})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return [x["symbol"] for x in scored[:10]]
