"""
Phase 1 Test Cases — Alpaca Client
TC-01 帳戶連線測試
TC-02 多帳戶隔離測試
TC-09 下單測試（Paper Trading）
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from core.alpaca_client import AlpacaClient, load_all_clients

FAKE_KEY = "FAKE_KEY"
FAKE_SECRET = "FAKE_SECRET"
BASE_URL = "https://paper-api.alpaca.markets/v2"


def make_client(account_id="PA_TEST"):
    return AlpacaClient(FAKE_KEY, FAKE_SECRET, BASE_URL, account_id)


# ── TC-01 帳戶連線測試 ──────────────────────────────────
class TestGetAccount:
    def test_returns_active_account(self):
        """TC-01: 正確 Key 應回傳 status=ACTIVE, cash>0"""
        client = make_client()
        mock_resp = {
            "account_number": "PA3M7XRBN5WC",
            "status": "ACTIVE",
            "cash": "100000",
            "portfolio_value": "100000",
            "buying_power": "200000",
            "currency": "USD",
        }
        with patch.object(client, "_get", return_value=mock_resp):
            acct = client.get_account()
        assert acct["status"] == "ACTIVE"
        assert float(acct["cash"]) > 0

    def test_get_cash_returns_float(self):
        """現金應為浮點數"""
        client = make_client()
        with patch.object(client, "_get", return_value={"cash": "12345.67", "status": "ACTIVE"}):
            cash = client.get_cash()
        assert isinstance(cash, float)
        assert cash == 12345.67

    def test_get_portfolio_value(self):
        client = make_client()
        with patch.object(client, "_get", return_value={"portfolio_value": "99999.5"}):
            pv = client.get_portfolio_value()
        assert pv == 99999.5

    def test_invalid_key_raises(self):
        """TC-01: 錯誤 Key 應拋出 HTTPError"""
        import requests
        client = make_client()
        with patch("requests.get") as mock_get:
            resp = MagicMock()
            resp.raise_for_status.side_effect = requests.exceptions.HTTPError("401")
            mock_get.return_value = resp
            with pytest.raises(requests.exceptions.HTTPError):
                client.get_account()


# ── TC-02 多帳戶隔離測試 ────────────────────────────────
class TestMultiAccount:
    def test_two_clients_independent(self):
        """TC-02: 兩個 client 應回傳各自帳戶資訊"""
        client_a = make_client("ACCOUNT_A")
        client_b = make_client("ACCOUNT_B")

        resp_a = {"account_number": "A001", "cash": "50000", "status": "ACTIVE"}
        resp_b = {"account_number": "B001", "cash": "75000", "status": "ACTIVE"}

        with patch.object(client_a, "_get", return_value=resp_a):
            acct_a = client_a.get_account()
        with patch.object(client_b, "_get", return_value=resp_b):
            acct_b = client_b.get_account()

        assert acct_a["account_number"] == "A001"
        assert acct_b["account_number"] == "B001"
        assert acct_a["cash"] != acct_b["cash"]

    def test_account_id_stored(self):
        client = make_client("MY_ACCOUNT")
        assert client.account_id == "MY_ACCOUNT"


# ── TC-09 下單測試 ──────────────────────────────────────
class TestPlaceOrder:
    def test_buy_order_returns_order_id(self):
        """TC-09: 買入 AAPL 10 股，回傳 order_id"""
        client = make_client()
        mock_order = {
            "id": "abc-123",
            "symbol": "AAPL",
            "qty": "10",
            "side": "buy",
            "type": "market",
            "status": "new",
        }
        with patch.object(client, "_post", return_value=mock_order):
            order = client.place_order("AAPL", 10, "buy")
        assert order["id"] == "abc-123"
        assert order["status"] in ["new", "accepted", "pending_new"]

    def test_sell_order(self):
        client = make_client()
        mock_order = {"id": "xyz-456", "symbol": "MSFT", "qty": "5", "side": "sell", "status": "new"}
        with patch.object(client, "_post", return_value=mock_order):
            order = client.place_order("MSFT", 5, "sell")
        assert order["side"] == "sell"

    def test_zero_qty_raises(self):
        """qty <= 0 應拋出 ValueError"""
        client = make_client()
        with pytest.raises(ValueError):
            client.place_order("AAPL", 0, "buy")

    def test_negative_qty_raises(self):
        client = make_client()
        with pytest.raises(ValueError):
            client.place_order("AAPL", -5, "buy")

    def test_get_positions(self):
        client = make_client()
        mock_pos = [
            {"symbol": "AAPL", "qty": "46", "avg_entry_price": "210.5"},
        ]
        with patch.object(client, "_get", return_value=mock_pos):
            positions = client.get_positions()
        assert len(positions) == 1
        assert positions[0]["symbol"] == "AAPL"

    def test_is_market_open(self):
        client = make_client()
        with patch.object(client, "_get", return_value={"is_open": True}):
            assert client.is_market_open() is True
        with patch.object(client, "_get", return_value={"is_open": False}):
            assert client.is_market_open() is False
