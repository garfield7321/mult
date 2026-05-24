"""
Phase 2 Test Cases — Strategy Engine
TC-06 策略載入測試
TC-07 資金分配計算測試
TC-08 整數股計算測試
TC-10 再平衡觸發測試
TC-11 每月再平衡測試
"""
import json
import math
import os
import pytest
import tempfile
from unittest.mock import patch, MagicMock

from core.strategy_engine import load_strategy, calc_target_positions, select_stocks


# ── TC-06 策略載入測試 ──────────────────────────────────
class TestLoadStrategy:
    def test_loads_top10_momentum(self):
        """TC-06: 載入 top10_momentum.json 應成功解析所有欄位"""
        strategy = load_strategy("top10_momentum")
        assert "strategy_id" in strategy
        assert "selection" in strategy
        assert "allocation" in strategy
        assert "rebalance" in strategy
        assert "entry" in strategy
        assert "exit" in strategy
        assert "notify" in strategy
        assert strategy["allocation"]["per_stock_pct"] == 10

    def test_loads_value_pe(self):
        strategy = load_strategy("value_pe")
        assert strategy["strategy_id"] == "value_pe"
        assert strategy["selection"]["method"] == "pe_ratio"

    def test_missing_strategy_raises(self):
        """不存在的策略應拋出 FileNotFoundError"""
        with pytest.raises(FileNotFoundError):
            load_strategy("non_existent_strategy_xyz")

    def test_strategy_has_required_keys(self):
        strategy = load_strategy("top10_momentum")
        required = ["strategy_id", "name", "selection", "allocation", "entry", "exit"]
        for key in required:
            assert key in strategy, f"缺少必要欄位: {key}"


# ── TC-07 資金分配計算測試 ──────────────────────────────
class TestCalcTargetPositions:
    def _make_strategy(self, pct=10):
        return {
            "allocation": {"per_stock_pct": pct, "whole_shares_only": True, "max_positions": 10},
            "entry": {"type": "market", "time_in_force": "day"},
            "exit": {"stop_loss_pct": -15, "take_profit_pct": None},
        }

    def _make_stocks(self, n=10, price=100.0):
        return [{"symbol": f"SYM{i}", "price": price, "rank": i+1} for i in range(n)]

    def test_each_stock_gets_10_pct(self):
        """TC-07: cash=100000, top_n=10, pct=10 → 每檔預算 10000"""
        strategy = self._make_strategy(10)
        stocks = self._make_stocks(10, price=100.0)
        positions = calc_target_positions(strategy, 100000.0, stocks)
        assert len(positions) == 10
        for p in positions:
            assert p["target_value"] == pytest.approx(10000.0, abs=200)

    def test_total_allocation(self):
        """TC-07: 所有標的投入總額 ≤ 現金"""
        strategy = self._make_strategy(10)
        stocks = self._make_stocks(10, price=150.0)
        positions = calc_target_positions(strategy, 100000.0, stocks)
        total = sum(p["target_value"] for p in positions)
        assert total <= 100000.0

    def test_whole_shares_only(self):
        """TC-08: 只買整數股"""
        strategy = self._make_strategy(10)
        stocks = [{"symbol": "AAPL", "price": 213.5, "rank": 1}]
        positions = calc_target_positions(strategy, 100000.0, stocks)
        assert positions[0]["target_qty"] == math.floor(10000 / 213.5)
        assert isinstance(positions[0]["target_qty"], int)

    def test_aapl_calc(self):
        """TC-08: 每檔資金=10000, AAPL 股價=213.5 → 46股"""
        strategy = self._make_strategy(10)
        stocks = [{"symbol": "AAPL", "price": 213.5, "rank": 1}]
        positions = calc_target_positions(strategy, 100000.0, stocks)
        assert positions[0]["target_qty"] == 46

    def test_skip_if_cant_afford_one_share(self):
        """股價過高無法買 1 股時應跳過"""
        strategy = self._make_strategy(10)
        stocks = [{"symbol": "BRK", "price": 999999.0, "rank": 1}]
        positions = calc_target_positions(strategy, 100000.0, stocks)
        assert len(positions) == 0

    def test_invalid_price_skipped(self):
        strategy = self._make_strategy(10)
        stocks = [{"symbol": "BAD", "price": None, "rank": 1},
                  {"symbol": "GOOD", "price": 100.0, "rank": 2}]
        positions = calc_target_positions(strategy, 100000.0, stocks)
        symbols = [p["symbol"] for p in positions]
        assert "BAD" not in symbols
        assert "GOOD" in symbols


# ── TC-11 每月再平衡測試 ────────────────────────────────
class TestMonthlyRebalance:
    def test_triggers_on_first_day(self):
        from core.rebalancer import is_monthly_rebalance_day
        from datetime import date
        with patch("core.rebalancer.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            assert is_monthly_rebalance_day(last_month="2026-05") is True

    def test_no_trigger_mid_month(self):
        from core.rebalancer import is_monthly_rebalance_day
        from datetime import date
        with patch("core.rebalancer.date") as mock_date:
            mock_date.today.return_value = date(2026, 5, 15)
            assert is_monthly_rebalance_day() is False

    def test_no_trigger_if_same_month(self):
        from core.rebalancer import is_monthly_rebalance_day
        from datetime import date
        with patch("core.rebalancer.date") as mock_date:
            mock_date.today.return_value = date(2026, 6, 1)
            assert is_monthly_rebalance_day(last_month="2026-06") is False


# ── TC-10 新資金偵測測試 ────────────────────────────────
class TestNewDeposit:
    def test_detects_deposit(self):
        from core.rebalancer import is_new_deposit
        assert is_new_deposit(current_cash=105000, last_cash=100000, threshold=1000) is True

    def test_no_trigger_below_threshold(self):
        from core.rebalancer import is_new_deposit
        assert is_new_deposit(current_cash=100500, last_cash=100000, threshold=1000) is False

    def test_no_trigger_same_cash(self):
        from core.rebalancer import is_new_deposit
        assert is_new_deposit(current_cash=100000, last_cash=100000) is False

    def test_no_trigger_less_cash(self):
        from core.rebalancer import is_new_deposit
        assert is_new_deposit(current_cash=99000, last_cash=100000) is False
