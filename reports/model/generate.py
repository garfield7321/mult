"""
日報告 Model 層
- 產生每日 JSON 報告（純資料，不含 UI）
- 儲存歷史報告，支援回查
"""
import json
import logging
import os
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional

from core.alpaca_client import AlpacaClient, load_all_clients, load_account_config
from core.market_data import (
    get_pnl_pcts, get_pe_ratio, get_top10_by_market_cap,
    predict_next_top10, get_benchmark_returns, get_latest_prices
)

logger = logging.getLogger(__name__)

REPORT_DIR = "reports/model"


def _report_path(account_id: str, report_date: str) -> str:
    return os.path.join(REPORT_DIR, f"{account_id}_{report_date}.json")


def calc_drawdown(account_id: str, current_nav: float) -> float:
    """
    計算從歷史最高點的回撤（%）
    回撤 = (現值 - 歷史高點) / 歷史高點 × 100
    """
    files = sorted([
        f for f in os.listdir(REPORT_DIR)
        if f.startswith(account_id) and f.endswith(".json") and "state" not in f
    ])
    peak = current_nav
    for fname in files:
        try:
            with open(os.path.join(REPORT_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            nav = data.get("nav", 0)
            if nav > peak:
                peak = nav
        except Exception:
            pass
    if peak == 0:
        return 0.0
    return round((current_nav - peak) / peak * 100, 2)


def get_yesterday_nav(account_id: str) -> Optional[float]:
    """取得昨日 NAV"""
    yesterday = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
    path = _report_path(account_id, yesterday)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("nav")
    return None


def generate_report(client: AlpacaClient, account_config: Dict,
                    report_date: str = None) -> Dict:
    """
    產生單一帳戶的日報 JSON

    資料結構 (Model 層)：
    - date, account_id, strategy
    - cash, portfolio_value, nav
    - daily_pnl, daily_pnl_pct, drawdown_pct
    - holdings: [{symbol, qty, avg_cost, current_price, market_value,
                  unrealized_pnl, pnl_1d_pct, pnl_1w_pct, pnl_1m_pct, pe_ratio}]
    - top10_today, top10_prediction
    - benchmark: {QQQ:{1d,1w,1m}, SPY:{1d,1w,1m}}
    """
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    os.makedirs(REPORT_DIR, exist_ok=True)

    account = client.get_account()
    cash = float(account["cash"])
    portfolio_value = float(account["portfolio_value"])

    # NAV & 損益
    yesterday_nav = get_yesterday_nav(account_config["account_id"])
    daily_pnl = portfolio_value - yesterday_nav if yesterday_nav else 0.0
    daily_pnl_pct = (daily_pnl / yesterday_nav * 100) if yesterday_nav else 0.0
    drawdown_pct = calc_drawdown(account_config["account_id"], portfolio_value)

    # 持倉明細
    positions = client.get_positions()
    symbols = [p["symbol"] for p in positions]
    prices = get_latest_prices(symbols) if symbols else {}

    holdings = []
    for pos in positions:
        sym = pos["symbol"]
        qty = int(pos["qty"])
        avg_cost = float(pos.get("avg_entry_price", 0))
        current_price = prices.get(sym) or float(pos.get("current_price", 0))
        market_value = round(qty * current_price, 2)
        unrealized_pnl = round(market_value - qty * avg_cost, 2)
        pnl = get_pnl_pcts(sym)
        pe = get_pe_ratio(sym)

        holdings.append({
            "symbol": sym,
            "qty": qty,
            "avg_cost": round(avg_cost, 2),
            "current_price": round(current_price, 2),
            "market_value": market_value,
            "unrealized_pnl": unrealized_pnl,
            "pnl_1d_pct": pnl.get("1d"),
            "pnl_1w_pct": pnl.get("1w"),
            "pnl_1m_pct": pnl.get("1m"),
            "pe_ratio": pe,
        })

    # Top 10
    top10_data = get_top10_by_market_cap()
    top10_today = [x["symbol"] for x in top10_data]
    top10_pred = predict_next_top10(top10_data)

    # Benchmark
    benchmark = get_benchmark_returns(["QQQ", "SPY"])

    report = {
        "date": report_date,
        "account_id": account_config["account_id"],
        "account_name": account_config["name"],
        "strategy": account_config["active_strategy"],
        "cash": round(cash, 2),
        "portfolio_value": round(portfolio_value, 2),
        "nav": round(portfolio_value, 2),
        "daily_pnl": round(daily_pnl, 2),
        "daily_pnl_pct": round(daily_pnl_pct, 2),
        "drawdown_pct": drawdown_pct,
        "holdings": holdings,
        "top10_today": top10_today,
        "top10_prediction": top10_pred,
        "benchmark": benchmark,
        "generated_at": datetime.now().isoformat(),
    }

    # 儲存 JSON
    path = _report_path(account_config["account_id"], report_date)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    logger.info(f"日報已儲存: {path}")

    return report


def generate_all_reports(config_path: str = "config/accounts.json",
                         report_date: str = None) -> Dict[str, Dict]:
    """產生所有帳戶的日報"""
    accounts = load_account_config(config_path)
    clients = load_all_clients(config_path)
    results = {}

    for acct in accounts:
        if not acct.get("enabled", True):
            continue
        acct_id = acct["account_id"]
        logger.info(f"產生報告：{acct['name']} ({acct_id})")
        try:
            report = generate_report(clients[acct_id], acct, report_date)
            results[acct_id] = report
        except Exception as e:
            logger.error(f"帳戶 {acct_id} 報告生成失敗: {e}")

    return results


def get_history(account_id: str, start_date: str = None,
                end_date: str = None) -> List[Dict]:
    """
    取得帳戶歷史報告（依日期排序）
    start_date / end_date: 'YYYY-MM-DD'
    """
    if not os.path.exists(REPORT_DIR):
        return []

    files = sorted([
        f for f in os.listdir(REPORT_DIR)
        if f.startswith(account_id) and f.endswith(".json") and "state" not in f
    ])

    reports = []
    for fname in files:
        # 從檔名取得日期 accountid_YYYY-MM-DD.json
        date_str = fname.replace(f"{account_id}_", "").replace(".json", "")
        if start_date and date_str < start_date:
            continue
        if end_date and date_str > end_date:
            continue
        try:
            with open(os.path.join(REPORT_DIR, fname), "r", encoding="utf-8") as f:
                reports.append(json.load(f))
        except Exception as e:
            logger.warning(f"讀取 {fname} 失敗: {e}")

    return reports


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--date", type=str, default=None)
    args = parser.parse_args()

    if args.all:
        generate_all_reports(report_date=args.date)
