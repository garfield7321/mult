"""
Alpaca API v2 Client — 支援多帳戶
每個帳戶各自建立一個 AlpacaClient 實例
"""
import json
import os
import logging
import requests
from typing import Optional, Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AlpacaClient:
    def __init__(self, api_key: str, api_secret: str,
                 base_url: str = "https://paper-api.alpaca.markets/v2",
                 account_id: str = "default"):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.account_id = account_id
        self.headers = {
            "APCA-API-KEY-ID": api_key,
            "APCA-API-SECRET-KEY": api_secret,
            "Content-Type": "application/json",
        }

    # ── 基礎 HTTP ─────────────────────────────────────────
    def _get(self, endpoint: str, params: dict = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _post(self, endpoint: str, data: dict = None) -> Any:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = requests.post(url, headers=self.headers, json=data, timeout=15)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, endpoint: str) -> None:
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        resp = requests.delete(url, headers=self.headers, timeout=15)
        resp.raise_for_status()

    # ── 帳戶資訊 ──────────────────────────────────────────
    def get_account(self) -> Dict:
        """取得帳戶完整資訊（現金、淨值、狀態等）"""
        return self._get("/account")

    def get_cash(self) -> float:
        """取得可用現金"""
        acct = self.get_account()
        return float(acct["cash"])

    def get_portfolio_value(self) -> float:
        """取得投資組合總市值"""
        acct = self.get_account()
        return float(acct["portfolio_value"])

    def get_buying_power(self) -> float:
        """取得購買力（含槓桿）"""
        acct = self.get_account()
        return float(acct["buying_power"])

    # ── 持倉 ──────────────────────────────────────────────
    def get_positions(self) -> List[Dict]:
        """取得所有持倉"""
        return self._get("/positions")

    def get_position(self, symbol: str) -> Optional[Dict]:
        """取得單一持倉，若無持倉回傳 None"""
        try:
            return self._get(f"/positions/{symbol}")
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise

    def close_position(self, symbol: str) -> Dict:
        """平倉單一持倉"""
        url = f"{self.base_url}/positions/{symbol}"
        resp = requests.delete(url, headers=self.headers, timeout=15)
        resp.raise_for_status()
        return resp.json()

    # ── 訂單 ──────────────────────────────────────────────
    def place_order(self, symbol: str, qty: int, side: str,
                    order_type: str = "market",
                    time_in_force: str = "day") -> Dict:
        """
        下單
        side: 'buy' or 'sell'
        qty: 整數股數
        """
        if qty <= 0:
            raise ValueError(f"qty 必須 > 0，收到 {qty}")
        data = {
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": order_type,
            "time_in_force": time_in_force,
        }
        logger.info(f"[{self.account_id}] 下單: {side} {qty} {symbol}")
        return self._post("/orders", data)

    def get_orders(self, status: str = "all", limit: int = 100) -> List[Dict]:
        """取得訂單清單"""
        return self._get("/orders", params={"status": status, "limit": limit})

    def get_order(self, order_id: str) -> Dict:
        """取得單一訂單"""
        return self._get(f"/orders/{order_id}")

    def cancel_all_orders(self) -> None:
        """取消所有待成交訂單"""
        self._delete("/orders")

    def cancel_order(self, order_id: str) -> None:
        """取消指定訂單"""
        self._delete(f"/orders/{order_id}")

    # ── 投組歷史 ──────────────────────────────────────────
    def get_portfolio_history(self, period: str = "1M",
                              timeframe: str = "1D") -> Dict:
        """
        取得投組歷史 NAV
        period: '1D','1W','1M','3M','6M','1A'
        timeframe: '1Min','5Min','15Min','1H','1D'
        """
        return self._get("/account/portfolio/history",
                         params={"period": period, "timeframe": timeframe})

    # ── 市場狀態 ──────────────────────────────────────────
    def get_clock(self) -> Dict:
        """取得市場開收盤時間"""
        return self._get("/clock")

    def is_market_open(self) -> bool:
        """確認目前市場是否開盤"""
        return self._get("/clock").get("is_open", False)

    def get_calendar(self, start: str = None, end: str = None) -> List[Dict]:
        """取得交易日曆"""
        params = {}
        if start:
            params["start"] = start
        if end:
            params["end"] = end
        return self._get("/calendar", params=params)


# ── 多帳戶載入器 ──────────────────────────────────────────
def load_all_clients(config_path: str = "config/accounts.json") -> Dict[str, AlpacaClient]:
    """
    讀取 accounts.json，建立所有啟用帳戶的 AlpacaClient
    回傳 dict: {account_id: AlpacaClient}
    環境變數名稱由 config 中 ${VAR_NAME} 語法指定
    """
    with open(config_path, "r", encoding="utf-8") as f:
        raw = f.read()

    # 替換環境變數
    import re
    env_vars = re.findall(r"\$\{(\w+)\}", raw)
    for var in env_vars:
        val = os.environ.get(var, "")
        raw = raw.replace(f"${{{var}}}", val)

    config = json.loads(raw)
    clients = {}
    for acct in config["accounts"]:
        if not acct.get("enabled", True):
            continue
        client = AlpacaClient(
            api_key=acct["api_key"],
            api_secret=acct["api_secret"],
            base_url=acct["endpoint"],
            account_id=acct["account_id"],
        )
        clients[acct["account_id"]] = client
        logger.info(f"帳戶載入：{acct['name']} ({acct['account_id']})")
    return clients


def load_account_config(config_path: str = "config/accounts.json") -> List[Dict]:
    """讀取帳戶設定清單（含策略、Email、watchlist）"""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = f.read()
    import re
    env_vars = re.findall(r"\$\{(\w+)\}", raw)
    for var in env_vars:
        val = os.environ.get(var, "")
        raw = raw.replace(f"${{{var}}}", val)
    return json.loads(raw)["accounts"]
