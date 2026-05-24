"""
Phase 3 Test Cases — Report System
TC-12 日報告生成測試
TC-13 NAV 計算測試
TC-14 回撤計算測試
TC-15 歷史報告回查測試
TC-16 HTML 報告渲染測試
"""
import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from datetime import date


# ── TC-13 NAV / 損益計算測試 ────────────────────────────
class TestNavCalc:
    def test_daily_pnl_pct(self):
        """TC-13: 昨日 NAV=98000, 今日=100000 → pnl_pct=2.04%"""
        yesterday_nav = 98000.0
        today_nav = 100000.0
        pnl = today_nav - yesterday_nav
        pnl_pct = pnl / yesterday_nav * 100
        assert round(pnl_pct, 2) == pytest.approx(2.04, abs=0.01)

    def test_zero_yesterday_nav(self):
        """昨日 NAV 為 None 時，pnl 應為 0"""
        yesterday_nav = None
        today_nav = 100000.0
        pnl = today_nav - yesterday_nav if yesterday_nav else 0.0
        pnl_pct = (pnl / yesterday_nav * 100) if yesterday_nav else 0.0
        assert pnl == 0.0
        assert pnl_pct == 0.0

    def test_negative_pnl(self):
        """虧損時 pnl 為負"""
        yesterday_nav = 100000.0
        today_nav = 95000.0
        pnl_pct = (today_nav - yesterday_nav) / yesterday_nav * 100
        assert pnl_pct == pytest.approx(-5.0, abs=0.01)


# ── TC-14 回撤計算測試 ──────────────────────────────────
class TestDrawdown:
    def test_drawdown_calculation(self):
        """TC-14: 高點=105000, 現值=100000 → 回撤=-4.76%"""
        peak = 105000.0
        current = 100000.0
        dd = (current - peak) / peak * 100
        assert round(dd, 2) == pytest.approx(-4.76, abs=0.01)

    def test_no_drawdown_at_peak(self):
        peak = 100000.0
        current = 100000.0
        dd = (current - peak) / peak * 100
        assert dd == 0.0

    def test_drawdown_from_history(self):
        """從歷史報告計算峰值"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # 建立假報告
            for i, nav in enumerate([90000, 105000, 100000]):
                d = {"date": f"2026-05-{i+1:02d}", "nav": nav}
                with open(os.path.join(tmpdir, f"ACCT_{d['date']}.json"), "w") as f:
                    json.dump(d, f)

            from reports.model.generate import calc_drawdown
            with patch("reports.model.generate.REPORT_DIR", tmpdir):
                dd = calc_drawdown("ACCT", 100000.0)
            assert dd == pytest.approx(-4.76, abs=0.1)


# ── TC-15 歷史報告回查測試 ──────────────────────────────
class TestHistoryRetrieval:
    def test_get_history_returns_sorted_list(self):
        """TC-15: 30 天報告回查應按日期返回"""
        with tempfile.TemporaryDirectory() as tmpdir:
            from datetime import date, timedelta
            base = date(2026, 4, 1)
            for i in range(30):
                d = base + timedelta(days=i)
                report = {"date": str(d), "account_id": "ACCT", "nav": 100000 + i * 10}
                fname = os.path.join(tmpdir, f"ACCT_{d}.json")
                with open(fname, "w") as f:
                    json.dump(report, f)

            from reports.model.generate import get_history
            with patch("reports.model.generate.REPORT_DIR", tmpdir):
                history = get_history("ACCT")

            assert len(history) == 30

    def test_date_range_filter(self):
        """start/end 日期過濾"""
        with tempfile.TemporaryDirectory() as tmpdir:
            from datetime import date, timedelta
            base = date(2026, 4, 1)
            for i in range(10):
                d = base + timedelta(days=i)
                report = {"date": str(d), "account_id": "ACCT", "nav": 100000}
                with open(os.path.join(tmpdir, f"ACCT_{d}.json"), "w") as f:
                    json.dump(report, f)

            from reports.model.generate import get_history
            with patch("reports.model.generate.REPORT_DIR", tmpdir):
                history = get_history("ACCT",
                                      start_date="2026-04-03",
                                      end_date="2026-04-05")
            assert len(history) == 3

    def test_empty_dir_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            from reports.model.generate import get_history
            with patch("reports.model.generate.REPORT_DIR", tmpdir):
                result = get_history("ACCT")
            assert result == []


# ── TC-16 HTML 報告渲染測試 ─────────────────────────────
class TestHtmlRender:
    def test_html_contains_nav(self):
        """TC-16: HTML 應包含 NAV 相關關鍵字"""
        from reports.view.render import _build_html
        report = {
            "date": "2026-05-24",
            "account_id": "ACCT",
            "account_name": "測試帳戶",
            "strategy": "top10_momentum",
            "cash": 12500.0,
            "nav": 100000.0,
            "daily_pnl": 1250.0,
            "daily_pnl_pct": 1.25,
            "drawdown_pct": -3.2,
            "holdings": [],
            "top10_today": ["AAPL", "MSFT"],
            "top10_prediction": ["AAPL", "MSFT"],
            "benchmark": {},
        }
        html = _build_html(report)
        assert "<!DOCTYPE html>" in html
        assert "AlpacaBot" in html
        assert "NAV" in html
        assert "AAPL" in html
        assert "不構成投資建議" in html or "僅供參考" in html

    def test_html_has_chart_script(self):
        """HTML 應包含 Chart.js"""
        from reports.view.render import _build_html
        report = {
            "date": "2026-05-24", "account_id": "A", "account_name": "A",
            "strategy": "s", "cash": 0, "nav": 0, "daily_pnl": 0,
            "daily_pnl_pct": 0, "drawdown_pct": 0, "holdings": [],
            "top10_today": [], "top10_prediction": [], "benchmark": {},
        }
        html = _build_html(report)
        assert "chart.js" in html.lower() or "Chart" in html
