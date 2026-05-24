"""
再平衡模組
觸發條件：
1. 新資金進入（cash 增加超過門檻）
2. 每月第一個交易日
"""
import json
import logging
import math
import os
from datetime import datetime, date
from typing import Dict, List, Optional

from core.alpaca_client import AlpacaClient
from core.market_data import get_latest_prices
from core.strategy_engine import load_strategy, select_stocks, calc_target_positions

logger = logging.getLogger(__name__)

STATE_DIR = "reports/model"


def _state_file(account_id: str) -> str:
    return os.path.join(STATE_DIR, f"{account_id}_state.json")


def load_state(account_id: str) -> Dict:
    """讀取帳戶上次記錄的現金快照"""
    path = _state_file(account_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_cash": 0.0, "last_rebalance_month": None}


def save_state(account_id: str, state: Dict) -> None:
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(_state_file(account_id), "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def is_new_deposit(current_cash: float, last_cash: float,
                   threshold: float = 1000.0) -> bool:
    """偵測是否有新資金進入"""
    return (current_cash - last_cash) >= threshold


def is_monthly_rebalance_day(last_month: Optional[str] = None) -> bool:
    """判斷今天是否應執行每月再平衡（每月 1 日）"""
    today = date.today()
    if today.day != 1:
        return False
    month_key = f"{today.year}-{today.month:02d}"
    return last_month != month_key


def rebalance(client: AlpacaClient, strategy: Dict,
              reason: str = "manual", dry_run: bool = False) -> List[Dict]:
    """
    執行再平衡：
    1. 選出目標股票
    2. 取得目前持倉
    3. 計算差額 → 下買/賣單
    """
    account = client.get_account()
    cash = float(account["cash"])
    portfolio_value = float(account["portfolio_value"])

    # 可用於再平衡的資金 = 現金 + 持倉總市值（全部重新配置）
    investable = portfolio_value

    logger.info(f"[{client.account_id}] 再平衡觸發（{reason}）| 投組總值: ${investable:,.2f}")

    stocks = select_stocks(strategy)
    targets = calc_target_positions(strategy, investable, stocks)
    current_positions = {p["symbol"]: int(p["qty"]) for p in client.get_positions()}

    orders = []
    target_map = {t["symbol"]: t["target_qty"] for t in targets}

    # 賣出多餘持倉
    for sym, cur_qty in current_positions.items():
        tgt_qty = target_map.get(sym, 0)
        diff = cur_qty - tgt_qty
        if diff > 0:
            logger.info(f"[{client.account_id}] 再平衡賣出 {diff} 股 {sym}")
            if not dry_run:
                try:
                    order = client.place_order(sym, diff, "sell")
                    orders.append({**order, "_action": "sell", "_reason": reason})
                except Exception as e:
                    logger.error(f"再平衡賣出 {sym} 失敗: {e}")

    # 買入不足持倉
    for target in targets:
        sym = target["symbol"]
        tgt_qty = target["target_qty"]
        cur_qty = current_positions.get(sym, 0)
        diff = tgt_qty - cur_qty
        if diff > 0:
            logger.info(f"[{client.account_id}] 再平衡買入 {diff} 股 {sym}")
            if not dry_run:
                try:
                    order = client.place_order(sym, diff, "buy")
                    orders.append({**order, "_action": "buy", "_reason": reason})
                except Exception as e:
                    logger.error(f"再平衡買入 {sym} 失敗: {e}")

    logger.info(f"[{client.account_id}] 再平衡完成，共 {len(orders)} 筆訂單")
    return orders


def check_and_rebalance(client: AlpacaClient, strategy: Dict,
                        dry_run: bool = False) -> List[Dict]:
    """
    自動偵測是否需要再平衡（新資金 / 每月初），並執行
    """
    state = load_state(client.account_id)
    account = client.get_account()
    current_cash = float(account["cash"])
    last_cash = float(state.get("last_cash", 0))
    last_month = state.get("last_rebalance_month")

    deposit_threshold = strategy.get("rebalance", {}).get("deposit_threshold", 1000)
    orders = []

    # 偵測新資金
    if strategy.get("rebalance", {}).get("on_new_deposit", True):
        if is_new_deposit(current_cash, last_cash, deposit_threshold):
            logger.info(f"[{client.account_id}] 偵測到新資金 (${current_cash - last_cash:,.2f})")
            orders += rebalance(client, strategy, reason="new_deposit", dry_run=dry_run)

    # 偵測每月初
    if strategy.get("rebalance", {}).get("monthly", True):
        if is_monthly_rebalance_day(last_month):
            logger.info(f"[{client.account_id}] 每月再平衡")
            orders += rebalance(client, strategy, reason="monthly", dry_run=dry_run)
            today = date.today()
            state["last_rebalance_month"] = f"{today.year}-{today.month:02d}"

    # 更新狀態
    state["last_cash"] = current_cash
    if not dry_run:
        save_state(client.account_id, state)

    return orders
