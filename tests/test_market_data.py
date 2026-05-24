"""
Phase 1 Test Cases — Market Data
TC-03 即時股價測試
TC-04 市值排行測試
TC-05 P/E 本益比測試
"""
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np


# ── TC-03 即時股價測試 ──────────────────────────────────
class TestGetLatestPrices:
    def test_returns_dict_with_prices(self):
        """TC-03: 回傳字典含 symbol: price"""
        from core.market_data import get_latest_prices
        mock_close = pd.DataFrame(
            {"AAPL": [213.5, 215.3], "MSFT": [420.1, 422.0], "NVDA": [875.0, 880.0]},
            index=pd.to_datetime(["2026-05-23", "2026-05-24"])
        )
        mock_data = {"Close": mock_close}
        with patch("yfinance.download", return_value=mock_data):
            prices = get_latest_prices(["AAPL", "MSFT", "NVDA"])
        assert isinstance(prices, dict)
        assert "AAPL" in prices
        assert prices["AAPL"] == pytest.approx(215.3, abs=0.1)

    def test_single_price(self):
        from core.market_data import get_latest_price
        with patch("core.market_data.get_latest_prices", return_value={"AAPL": 215.3}):
            price = get_latest_price("AAPL")
        assert price == 215.3

    def test_invalid_symbol_returns_none(self):
        from core.market_data import get_latest_prices
        mock_close = pd.DataFrame({}, index=pd.to_datetime(["2026-05-24"]))
        with patch("yfinance.download", return_value={"Close": mock_close}):
            with patch("yfinance.Ticker") as mock_ticker:
                mock_ticker.return_value.history.return_value = pd.DataFrame()
                prices = get_latest_prices(["INVALID_XYZ"])
        assert prices.get("INVALID_XYZ") is None


# ── TC-04 市值排行測試 ──────────────────────────────────
class TestGetTop10:
    def test_returns_10_items(self):
        """TC-04: 回傳長度為 10 的清單，按市值降序"""
        from core.market_data import get_top10_by_market_cap, NASDAQ_TOP_100

        def mock_cap(sym):
            caps = {s: (100 - i) * 1e11 for i, s in enumerate(NASDAQ_TOP_100[:20])}
            return caps.get(sym, 1e10)

        with patch("core.market_data.get_market_cap", side_effect=mock_cap):
            with patch("core.market_data.get_latest_prices", return_value={s: 100.0 for s in NASDAQ_TOP_100[:20]}):
                top10 = get_top10_by_market_cap(NASDAQ_TOP_100[:20])

        assert len(top10) == 10
        # 確認降序
        caps = [x["market_cap"] for x in top10]
        assert caps == sorted(caps, reverse=True)

    def test_rank_field(self):
        from core.market_data import get_top10_by_market_cap, NASDAQ_TOP_100
        with patch("core.market_data.get_market_cap", return_value=1e12):
            with patch("core.market_data.get_latest_prices", return_value={s: 100.0 for s in NASDAQ_TOP_100[:10]}):
                top10 = get_top10_by_market_cap(NASDAQ_TOP_100[:10])
        assert top10[0]["rank"] == 1
        assert top10[-1]["rank"] == 10


# ── TC-05 P/E 本益比測試 ────────────────────────────────
class TestGetPERatio:
    def test_returns_positive_float(self):
        """TC-05: 正常股票 P/E > 0"""
        from core.market_data import get_pe_ratio
        mock_ticker = MagicMock()
        mock_ticker.info = {"trailingPE": 28.5}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            pe = get_pe_ratio("AAPL")
        assert pe == pytest.approx(28.5)
        assert pe > 0

    def test_returns_none_if_unavailable(self):
        """TC-05: 無法取得時回傳 None"""
        from core.market_data import get_pe_ratio
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            pe = get_pe_ratio("NEWSTOCK")
        assert pe is None

    def test_uses_forward_pe_as_fallback(self):
        from core.market_data import get_pe_ratio
        mock_ticker = MagicMock()
        mock_ticker.info = {"forwardPE": 22.3}
        with patch("yfinance.Ticker", return_value=mock_ticker):
            pe = get_pe_ratio("TSLA")
        assert pe == pytest.approx(22.3)


# ── 漲跌幅測試 ──────────────────────────────────────────
class TestPnlPcts:
    def test_returns_three_keys(self):
        from core.market_data import get_pnl_pcts
        mock_ticker = MagicMock()
        dates = pd.date_range("2026-04-01", periods=25, freq="B")
        prices = [200 + i for i in range(25)]
        mock_ticker.history.return_value = pd.DataFrame({"Close": prices}, index=dates)
        with patch("yfinance.Ticker", return_value=mock_ticker):
            pnl = get_pnl_pcts("AAPL")
        assert "1d" in pnl
        assert "1w" in pnl
        assert "1m" in pnl

    def test_positive_when_price_rises(self):
        from core.market_data import get_pnl_pcts
        mock_ticker = MagicMock()
        dates = pd.date_range("2026-04-01", periods=25, freq="B")
        prices = [100 + i for i in range(25)]  # 持續上漲
        mock_ticker.history.return_value = pd.DataFrame({"Close": prices}, index=dates)
        with patch("yfinance.Ticker", return_value=mock_ticker):
            pnl = get_pnl_pcts("AAPL")
        assert pnl["1d"] > 0
        assert pnl["1w"] > 0
