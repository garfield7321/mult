"""
策略引擎
- 從 JSON 載入策略
- 根據策略選股、計算下單量
- 執行買進/賣出
- 支援多帳戶獨立運行
"""
import json
import logging
import math
import os
from typing import Dict, List, Optional, Tuple

from core.alpaca_client import AlpacaClient, load_all_clients, load_account_config
from core.market_data import (
    get_top10_by_market_cap, get_latest_prices, get_pe_ratio, NASDAQ_TOP_100
)

logger = logging.getLogger(__name__)

STRATEGY_DIR = "config/strategies"


def load_strategy(strategy_id: str) -> Dict:
    """從 JSON 檔案載入策略設定"""
    path = os.path.join(STRATEGY_DIR, f"{strategy_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"策略檔案不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        strategy = json.load(f)
    logger.info(f"載入策略: {strategy['name']}")
    return strategy


def select_stocks(strategy: Dict) -> List[Dict]:
    """
    根據策略選出目標股票清單
    回傳: [{symbol, price, market_cap/pe_ratio, rank}, ...]
    """
    method = strategy["selection"]["method"]
    top_n = strategy["selection"]["top_n"]

    if method == "market_cap":
        stocks = get_top10_by_market_cap()
        return stocks[:top_n]

    elif method == "pe_ratio":
        filters = strategy["selection"].get("filter", {})
        pe_min = filters.get("pe_ratio_min", 0)
        pe_max = filters.get("pe_ratio_max", 9999)

        pe_list = []
        for sym in NASDAQ_TOP_100[:50]:  # 限前50避免太慢
            pe = get_pe_ratio(sym)
            if pe and pe_min <= pe <= pe_max:
                pe_list.append({"symbol": sym, "pe_ratio": pe})

        sort_asc = strategy["selection"].get("sort_order", "asc") == "asc"
        pe_list.sort(key=lambda x: x["pe_ratio"], reverse=not sort_asc)
        result = pe_list[:top_n]

        prices = get_latest_prices([x["symbol"] for x in result])
        for i, item in enumerate(result):
            item["rank"] = i + 1
            item["price"] = prices.get(item["symbol"])
        return result

    else:
        raise ValueError(f"不支援的選股方法: {method}")


def calc_target_positions(strategy: Dict, cash_available: float,
                           stocks: List[Dict]) -> List[Dict]:
    """
    計算目標持倉
    per_stock_pct: 每檔投入百分比
    whole_shares_only: 只買整數股
    回傳: [{symbol, price, target_qty, target_value}, ...]
    """
    alloc = strategy["allocation"]
    pct = alloc["per_stock_pct"] / 100.0
    whole_only = alloc.get("whole_shares_only", True)

    positions = []
    for stock in stocks:
        price = stock.get("price")
        if not price or price <= 0:
            logger.warning(f"{stock['symbol']} 無效股價，跳過")
            continue
        budget = cash_available * pct
        qty = math.floor(budget / price) if whole_only else budget / price
        if qty < 1:
            logger.warning(f"{stock['symbol']} 資金不足買 1 股（需 {price:.2f}，預算 {budget:.2f}）")
            continue
        positions.append({
            "symbol": stock["symbol"],
            "price": price,
            "target_qty": int(qty),
            "target_value": round(qty * price, 2),
        })
    return positions


def execute_strategy(client: AlpacaClient, strategy: Dict,
                     dry_run: bool = False) -> List[Dict]:
    """
    執行策略：選股 → 計算目標持倉 → 比對現有持倉 → 下單
    dry_run=True 時只計算不下單（測試用）
    回傳訂單清單
    """
    account = client.get_account()
    cash = float(account["cash"])
    portfolio_value = float(account["portfolio_value"])

    logger.info(f"[{client.account_id}] 現金: ${cash:,.2f} | 總值: ${portfolio_value:,.2f}")

    # 1. 選股
    stocks = select_stocks(strategy)
    logger.info(f"選出 {len(stocks)} 支股票: {[s['symbol'] for s in stocks]}")

    # 2. 計算目標持倉
    target_positions = calc_target_positions(strategy, cash, stocks)

    # 3. 取得現有持倉
    current_positions = {p["symbol"]: p for p in client.get_positions()}

    orders_placed = []

    # 4. 賣出不在目標清單的持倉
    target_symbols = {p["symbol"] for p in target_positions}
    for sym, pos in current_positions.items():
        if sym not in target_symbols:
            qty = int(pos["qty"])
            logger.info(f"[{client.account_id}] 賣出 {qty} 股 {sym}（不在目標清單）")
            if not dry_run:
                try:
                    order = client.place_order(sym, qty, "sell")
                    orders_placed.append({**order, "_action": "sell", "_reason": "not_in_target"})
                except Exception as e:
                    logger.error(f"賣出 {sym} 失敗: {e}")

    # 5. 檢查停損觸發
    exit_cfg = strategy.get("exit", {})
    stop_loss = exit_cfg.get("stop_loss_pct")
    take_profit = exit_cfg.get("take_profit_pct")

    for sym, pos in current_positions.items():
        if sym not in target_symbols:
            continue
        pnl_pct = float(pos.get("unrealized_plpc", 0)) * 100
        if stop_loss and pnl_pct <= stop_loss:
            qty = int(pos["qty"])
            logger.info(f"[{client.account_id}] 停損賣出 {sym}：虧損 {pnl_pct:.1f}%")
            if not dry_run:
                try:
                    order = client.place_order(sym, qty, "sell")
                    orders_placed.append({**order, "_action": "sell", "_reason": "stop_loss"})
                except Exception as e:
                    logger.error(f"停損 {sym} 失敗: {e}")
        elif take_profit and pnl_pct >= take_profit:
            qty = int(pos["qty"])
            logger.info(f"[{client.account_id}] 停利賣出 {sym}：獲利 {pnl_pct:.1f}%")
            if not dry_run:
                try:
                    order = client.place_order(sym, qty, "sell")
                    orders_placed.append({**order, "_action": "sell", "_reason": "take_profit"})
                except Exception as e:
                    logger.error(f"停利 {sym} 失敗: {e}")

    # 6. 買進目標股票（若尚未持有或數量不足）
    for target in target_positions:
        sym = target["symbol"]
        target_qty = target["target_qty"]
        current = current_positions.get(sym)
        current_qty = int(current["qty"]) if current else 0
        diff_qty = target_qty - current_qty

        if diff_qty > 0:
            logger.info(f"[{client.account_id}] 買入 {diff_qty} 股 {sym}")
            if not dry_run:
                try:
                    order = client.place_order(sym, diff_qty, "buy",
                                               order_type=strategy["entry"]["type"],
                                               time_in_force=strategy["entry"]["time_in_force"])
                    orders_placed.append({**order, "_action": "buy", "_reason": "target_allocation"})
                except Exception as e:
                    logger.error(f"買入 {sym} 失敗: {e}")
        else:
            logger.info(f"[{client.account_id}] {sym} 持倉足夠（{current_qty}/{target_qty}），跳過")

    logger.info(f"[{client.account_id}] 策略執行完成，共 {len(orders_placed)} 筆訂單")
    return orders_placed


def run_all_accounts(config_path: str = "config/accounts.json",
                     dry_run: bool = False) -> Dict[str, List[Dict]]:
    """
    走遍所有帳戶，根據各自的 active_strategy 執行買賣
    GitHub Actions 主入口
    """
    accounts = load_account_config(config_path)
    clients = load_all_clients(config_path)
    all_orders = {}

    for acct in accounts:
        if not acct.get("enabled", True):
            continue
        acct_id = acct["account_id"]
        strategy_id = acct["active_strategy"]
        logger.info(f"\n{'='*50}")
        logger.info(f"帳戶: {acct['name']} ({acct_id}) | 策略: {strategy_id}")

        try:
            client = clients[acct_id]
            strategy = load_strategy(strategy_id)
            orders = execute_strategy(client, strategy, dry_run=dry_run)
            all_orders[acct_id] = orders
        except Exception as e:
            logger.error(f"帳戶 {acct_id} 執行失敗: {e}")
            all_orders[acct_id] = []

    return all_orders


if __name__ == "__main__":
    import argparse
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(description="AlpacaBot Strategy Engine")
    parser.add_argument("--run-all", action="store_true", help="執行所有帳戶")
    parser.add_argument("--dry-run", action="store_true", help="試算模式（不實際下單）")
    parser.add_argument("--account", type=str, help="指定帳戶 ID")
    parser.add_argument("--strategy", type=str, help="指定策略 ID")
    args = parser.parse_args()

    if args.run_all:
        results = run_all_accounts(dry_run=args.dry_run)
        for acct_id, orders in results.items():
            print(f"\n帳戶 {acct_id}: {len(orders)} 筆訂單")
    else:
        parser.print_help()
        sys.exit(1)
