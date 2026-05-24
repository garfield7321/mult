"""
Email 通知模組
- 每日 6AM 日報
- 即時交易通知
- 支援多帳戶各自的 email
"""
import os
import smtplib
import logging
import json
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def _smtp_config() -> Dict:
    return {
        "host": os.environ.get("SMTP_HOST", "smtp.gmail.com"),
        "port": int(os.environ.get("SMTP_PORT", "587")),
        "user": os.environ.get("SMTP_USER", ""),
        "password": os.environ.get("SMTP_PASSWORD", ""),
    }


def send_email(to: str, subject: str, html_body: str) -> bool:
    """發送 HTML Email"""
    cfg = _smtp_config()
    if not cfg["user"] or not cfg["password"]:
        logger.warning("SMTP 未設定，跳過寄信")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = cfg["user"]
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(cfg["host"], cfg["port"]) as server:
            server.ehlo()
            server.starttls()
            server.login(cfg["user"], cfg["password"])
            server.sendmail(cfg["user"], [to], msg.as_string())
        logger.info(f"Email 發送成功 → {to}")
        return True
    except Exception as e:
        logger.error(f"Email 發送失敗: {e}")
        return False


def _color(val: float) -> str:
    return "#22c55e" if val >= 0 else "#ef4444"


def _arrow(val: float) -> str:
    return "▲" if val >= 0 else "▼"


def build_daily_report_html(report: Dict, account_config: Dict) -> str:
    """
    根據日報 JSON 產生 Email HTML
    report: reports/model/YYYY-MM-DD.json 的內容
    """
    date_str = report.get("date", datetime.now().strftime("%Y-%m-%d"))
    cash = report.get("cash", 0)
    nav = report.get("nav", 0)
    pnl = report.get("daily_pnl", 0)
    pnl_pct = report.get("daily_pnl_pct", 0)
    drawdown = report.get("drawdown_pct", 0)
    holdings = report.get("holdings", [])
    top10 = report.get("top10_today", [])
    pred10 = report.get("top10_prediction", [])
    watchlist = account_config.get("watchlist", {})
    benchmark = report.get("benchmark", {})
    strategy = report.get("strategy", "")

    pnl_color = _color(pnl_pct)
    dd_color = _color(-drawdown)

    # 持倉表格
    holding_rows = ""
    for h in holdings:
        sym = h.get("symbol", "")
        qty = h.get("qty", 0)
        cost = h.get("avg_cost", 0)
        price = h.get("current_price", 0)
        mv = h.get("market_value", 0)
        upnl = h.get("unrealized_pnl", 0)
        d1 = h.get("pnl_1d_pct", 0) or 0
        w1 = h.get("pnl_1w_pct", 0) or 0
        m1 = h.get("pnl_1m_pct", 0) or 0
        pe = h.get("pe_ratio", "-")
        holding_rows += f"""
        <tr>
          <td><b>{sym}</b></td>
          <td>{qty}</td>
          <td>${cost:.2f}</td>
          <td>${price:.2f}</td>
          <td>${mv:,.2f}</td>
          <td style="color:{_color(upnl)}">${upnl:+,.2f}</td>
          <td style="color:{_color(d1)}">{_arrow(d1)}{abs(d1):.1f}%</td>
          <td style="color:{_color(w1)}">{_arrow(w1)}{abs(w1):.1f}%</td>
          <td style="color:{_color(m1)}">{_arrow(m1)}{abs(m1):.1f}%</td>
          <td>{pe if pe else '-'}</td>
        </tr>"""

    # 關注股
    watchlist_html = ""
    for category, symbols in watchlist.items():
        watchlist_html += f"<tr><td><b>{category}</b></td>"
        watchlist_html += "".join(f"<td>{s}</td>" for s in symbols)
        watchlist_html += "</tr>"

    # Benchmark
    qqq = benchmark.get("QQQ", {})
    spy = benchmark.get("SPY", {})
    qqq_1d = qqq.get("1d", 0) or 0
    spy_1d = spy.get("1d", 0) or 0

    top10_str = " ".join(f"{i+1}.{s}" for i, s in enumerate(top10))
    pred10_str = " ".join(f"{i+1}.{s}" for i, s in enumerate(pred10))

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head><meta charset="UTF-8">
<style>
  body {{ font-family: 'Helvetica Neue', Arial, sans-serif; background:#f8fafc; color:#1e293b; margin:0; padding:20px; }}
  .container {{ max-width:700px; margin:auto; background:#fff; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,.08); }}
  .header {{ background:linear-gradient(135deg,#1e40af,#7c3aed); color:#fff; padding:24px 28px; }}
  .header h1 {{ margin:0; font-size:1.4rem; }}
  .header p {{ margin:4px 0 0; opacity:.8; font-size:.9rem; }}
  .kpi-row {{ display:flex; gap:12px; padding:20px 28px; background:#f1f5f9; }}
  .kpi {{ flex:1; background:#fff; border-radius:8px; padding:14px 16px; border:1px solid #e2e8f0; }}
  .kpi .label {{ font-size:.75rem; color:#64748b; }}
  .kpi .value {{ font-size:1.3rem; font-weight:700; margin-top:4px; }}
  .section {{ padding:20px 28px; border-top:1px solid #f1f5f9; }}
  .section h2 {{ font-size:1rem; color:#475569; margin:0 0 12px; }}
  table {{ width:100%; border-collapse:collapse; font-size:.82rem; }}
  th {{ background:#f8fafc; color:#64748b; padding:8px 10px; text-align:left; border-bottom:2px solid #e2e8f0; }}
  td {{ padding:8px 10px; border-bottom:1px solid #f1f5f9; }}
  .top10 {{ display:flex; flex-wrap:wrap; gap:8px; }}
  .chip {{ background:#eff6ff; color:#1d4ed8; border-radius:20px; padding:4px 12px; font-size:.82rem; font-weight:600; }}
  .footer {{ background:#f8fafc; padding:16px 28px; font-size:.78rem; color:#94a3b8; border-top:1px solid #e2e8f0; }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>📊 AlpacaBot 投資日報</h1>
    <p>{date_str} | 策略：{strategy} | ⚠️ 僅供參考，不構成投資建議</p>
  </div>

  <div class="kpi-row">
    <div class="kpi"><div class="label">💵 現金水位</div><div class="value">${cash:,.0f}</div></div>
    <div class="kpi"><div class="label">📈 投組總值</div><div class="value">${nav:,.0f}</div></div>
    <div class="kpi"><div class="label">今日損益</div><div class="value" style="color:{pnl_color}">{_arrow(pnl_pct)}{abs(pnl_pct):.2f}%<br><small>${pnl:+,.0f}</small></div></div>
    <div class="kpi"><div class="label">最大回撤</div><div class="value" style="color:{dd_color}">{drawdown:.1f}%</div></div>
  </div>

  <div class="kpi-row" style="background:#fff; padding-top:0; padding-bottom:4px;">
    <div class="kpi"><div class="label">QQQ 今日</div><div class="value" style="color:{_color(qqq_1d)}">{_arrow(qqq_1d)}{abs(qqq_1d):.2f}%</div></div>
    <div class="kpi"><div class="label">SPY 今日</div><div class="value" style="color:{_color(spy_1d)}">{_arrow(spy_1d)}{abs(spy_1d):.2f}%</div></div>
  </div>

  <div class="section">
    <h2>📋 持倉清單</h2>
    <table>
      <thead>
        <tr>
          <th>股票</th><th>股數</th><th>成本</th><th>現價</th><th>市值</th>
          <th>未實現損益</th><th>1日</th><th>1週</th><th>1月</th><th>P/E</th>
        </tr>
      </thead>
      <tbody>{holding_rows}</tbody>
    </table>
  </div>

  <div class="section">
    <h2>🏆 今日 Top 10</h2>
    <div class="top10">{''.join(f'<span class="chip">{i+1}. {s}</span>' for i, s in enumerate(top10))}</div>
  </div>

  <div class="section">
    <h2>🔮 明日預測 Top 10 <small style="color:#ef4444">（僅供參考）</small></h2>
    <div class="top10">{''.join(f'<span class="chip" style="background:#fdf4ff;color:#7e22ce">{i+1}. {s}</span>' for i, s in enumerate(pred10))}</div>
  </div>

  <div class="section">
    <h2>👀 我的關注股</h2>
    <table>
      <tbody>{watchlist_html}</tbody>
    </table>
  </div>

  <div class="footer">
    ⚠️ 本報告所有內容僅供資訊整理與研究參考，不構成任何投資建議。<br>
    股票投資有風險，過去績效不代表未來結果。本益比（P/E）= 股價 ÷ 每股盈餘。<br>
    回撤（Drawdown）= 從歷史高點下跌的幅度，衡量最大可能虧損。<br>
    AlpacaBot | 自動產生於 {datetime.now().strftime('%Y-%m-%d %H:%M')}
  </div>
</div>
</body>
</html>"""
    return html


def send_daily_report(account_config: Dict, report_date: str = None) -> bool:
    """
    寄送每日日報
    """
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    report_path = f"reports/model/{account_config['account_id']}_{report_date}.json"
    if not os.path.exists(report_path):
        logger.warning(f"日報 JSON 不存在: {report_path}")
        return False

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    html = build_daily_report_html(report, account_config)
    pnl_pct = report.get("daily_pnl_pct", 0)
    arrow = "▲" if pnl_pct >= 0 else "▼"
    subject = f"📊 AlpacaBot 日報 {report_date} | 今日 {arrow}{abs(pnl_pct):.2f}%"

    return send_email(account_config["email"], subject, html)


def send_trade_notification(account_config: Dict, order: Dict) -> bool:
    """
    即時交易通知
    """
    action = order.get("_action", order.get("side", "?"))
    symbol = order.get("symbol", "?")
    qty = order.get("qty", "?")
    status = order.get("status", "?")
    reason = order.get("_reason", "")

    action_emoji = "🟢 買入" if action == "buy" else "🔴 賣出"
    subject = f"⚡ AlpacaBot 交易通知 | {action_emoji} {symbol} {qty} 股"

    html = f"""<!DOCTYPE html>
<html lang="zh-TW"><head><meta charset="UTF-8"></head>
<body style="font-family:Arial,sans-serif;background:#f8fafc;padding:20px">
<div style="max-width:500px;margin:auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 16px rgba(0,0,0,.08)">
  <div style="background:{'#15803d' if action=='buy' else '#b91c1c'};color:#fff;padding:20px 24px">
    <h2 style="margin:0">{action_emoji} 成交通知</h2>
  </div>
  <div style="padding:20px 24px">
    <table style="width:100%;font-size:.95rem">
      <tr><td style="color:#64748b;padding:6px 0">股票代碼</td><td><b>{symbol}</b></td></tr>
      <tr><td style="color:#64748b;padding:6px 0">買/賣</td><td>{action_emoji}</td></tr>
      <tr><td style="color:#64748b;padding:6px 0">股數</td><td>{qty} 股</td></tr>
      <tr><td style="color:#64748b;padding:6px 0">訂單狀態</td><td>{status}</td></tr>
      <tr><td style="color:#64748b;padding:6px 0">原因</td><td>{reason}</td></tr>
      <tr><td style="color:#64748b;padding:6px 0">時間</td><td>{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
    </table>
  </div>
  <div style="background:#f8fafc;padding:12px 24px;font-size:.78rem;color:#94a3b8">
    ⚠️ 本通知僅供資訊參考，不構成投資建議。
  </div>
</div>
</body></html>"""

    return send_email(account_config["email"], subject, html)
