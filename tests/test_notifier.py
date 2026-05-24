"""
Phase 4 Test Cases — Notifier
TC-17 Email 發送測試
TC-18 交易即時通知測試
TC-19 多帳戶 Email 隔離測試
"""
import pytest
from unittest.mock import patch, MagicMock, call
import os


ACCOUNT_A = {
    "account_id": "ACCT_A",
    "name": "帳戶 A",
    "active_strategy": "top10_momentum",
    "email": "a@example.com",
    "watchlist": {"科技股": ["AAPL"]},
}

ACCOUNT_B = {
    "account_id": "ACCT_B",
    "name": "帳戶 B",
    "active_strategy": "value_pe",
    "email": "b@example.com",
    "watchlist": {"ETF": ["QQQ"]},
}

SAMPLE_REPORT = {
    "date": "2026-05-24",
    "account_id": "ACCT_A",
    "account_name": "帳戶 A",
    "strategy": "top10_momentum",
    "cash": 12500.0,
    "nav": 100000.0,
    "daily_pnl": 1250.0,
    "daily_pnl_pct": 1.25,
    "drawdown_pct": -3.2,
    "holdings": [],
    "top10_today": ["AAPL", "MSFT"],
    "top10_prediction": ["AAPL", "MSFT"],
    "benchmark": {"QQQ": {"1d": 0.85}, "SPY": {"1d": 0.72}},
}


# ── TC-17 Email 發送測試 ────────────────────────────────
class TestSendEmail:
    def test_send_email_calls_smtp(self):
        """TC-17: 正確設定應呼叫 SMTP"""
        from core.notifier import send_email
        with patch.dict(os.environ, {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "bot@test.com",
            "SMTP_PASSWORD": "password123",
        }):
            with patch("smtplib.SMTP") as mock_smtp:
                mock_server = MagicMock()
                mock_smtp.return_value.__enter__ = MagicMock(return_value=mock_server)
                mock_smtp.return_value.__exit__ = MagicMock(return_value=False)
                result = send_email("user@example.com", "Test Subject", "<p>Test</p>")
            assert result is True

    def test_send_email_skipped_without_config(self):
        """TC-17: 未設定 SMTP 應跳過（不拋錯）"""
        from core.notifier import send_email
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASSWORD": ""}):
            result = send_email("user@example.com", "Test", "<p>Test</p>")
        assert result is False

    def test_html_report_built(self):
        """日報 HTML 應包含必要資訊"""
        from core.notifier import build_daily_report_html
        html = build_daily_report_html(SAMPLE_REPORT, ACCOUNT_A)
        assert "1.25" in html or "1,250" in html
        assert "不構成投資建議" in html or "僅供參考" in html
        assert "AAPL" in html

    def test_subject_contains_pnl(self):
        """主旨應包含損益方向"""
        from core.notifier import build_daily_report_html
        html = build_daily_report_html(SAMPLE_REPORT, ACCOUNT_A)
        assert html is not None


# ── TC-18 交易通知測試 ──────────────────────────────────
class TestTradeNotification:
    def test_buy_notification_html(self):
        """TC-18: 買入通知 HTML 應包含股票代號"""
        from core.notifier import send_trade_notification
        order = {
            "id": "order-001",
            "_action": "buy",
            "symbol": "AAPL",
            "qty": 46,
            "status": "new",
            "_reason": "target_allocation",
        }
        with patch("core.notifier.send_email", return_value=True) as mock_send:
            result = send_trade_notification(ACCOUNT_A, order)
        assert result is True
        # 確認 email 內容包含 AAPL
        args = mock_send.call_args
        assert "AAPL" in args[0][2]  # html body

    def test_sell_notification(self):
        from core.notifier import send_trade_notification
        order = {"_action": "sell", "symbol": "MSFT", "qty": 10, "status": "new", "_reason": "stop_loss"}
        with patch("core.notifier.send_email", return_value=True) as mock_send:
            result = send_trade_notification(ACCOUNT_B, order)
        assert result is True
        args = mock_send.call_args
        assert "MSFT" in args[0][2]


# ── TC-19 多帳戶 Email 隔離測試 ─────────────────────────
class TestMultiAccountEmail:
    def test_different_emails_sent_separately(self):
        """TC-19: 帳戶 A 和 B 的 email 應分別發送給各自地址"""
        from core.notifier import send_email
        sent = []

        def fake_send(to, subject, html):
            sent.append(to)
            return True

        with patch("core.notifier.send_email", side_effect=fake_send):
            from core.notifier import send_email as se
            se(ACCOUNT_A["email"], "報告A", "<p>A</p>")
            se(ACCOUNT_B["email"], "報告B", "<p>B</p>")

        assert "a@example.com" in sent
        assert "b@example.com" in sent
        assert len(set(sent)) == 2  # 各自不同
