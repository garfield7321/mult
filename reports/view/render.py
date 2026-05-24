"""
日報告 View 層
- 讀取 JSON Model → 渲染 HTML 報告
- 包含 NAV 線圖（含 NASDAQ/S&P500 對比）
- 儲存為 reports/view/accountid_YYYY-MM-DD.html
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

VIEW_DIR = "reports/view"
MODEL_DIR = "reports/model"


def _color(val: float) -> str:
    return "#22c55e" if val >= 0 else "#ef4444"


def _arrow(val: float) -> str:
    return "▲" if val >= 0 else "▼"


def render_report(account_id: str, report_date: str = None) -> str:
    """
    讀取 JSON 日報 → 渲染成 HTML 報告
    回傳 HTML 字串，並儲存到 reports/view/
    """
    if report_date is None:
        report_date = datetime.now().strftime("%Y-%m-%d")

    model_path = os.path.join(MODEL_DIR, f"{account_id}_{report_date}.json")
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"日報 JSON 不存在: {model_path}")

    with open(model_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    html = _build_html(report)

    os.makedirs(VIEW_DIR, exist_ok=True)
    view_path = os.path.join(VIEW_DIR, f"{account_id}_{report_date}.html")
    with open(view_path, "w", encoding="utf-8") as f:
        f.write(html)
    logger.info(f"HTML 報告已產生: {view_path}")
    return html


def _build_html(report: Dict) -> str:
    date_str = report.get("date", "")
    account_name = report.get("account_name", report.get("account_id", ""))
    strategy = report.get("strategy", "")
    cash = report.get("cash", 0)
    nav = report.get("nav", 0)
    pnl = report.get("daily_pnl", 0)
    pnl_pct = report.get("daily_pnl_pct", 0)
    drawdown = report.get("drawdown_pct", 0)
    holdings = report.get("holdings", [])
    top10 = report.get("top10_today", [])
    pred10 = report.get("top10_prediction", [])
    benchmark = report.get("benchmark", {})

    # NAV 歷史（從 Model 目錄掃描）
    account_id = report.get("account_id", "")
    nav_history = _load_nav_history(account_id, date_str)
    nav_labels = json.dumps([x["date"] for x in nav_history])
    nav_values = json.dumps([x["nav"] for x in nav_history])
    qqq_values = json.dumps([x.get("qqq") for x in nav_history])
    spy_values  = json.dumps([x.get("spy") for x in nav_history])

    # 持倉表格
    holding_rows = ""
    for h in holdings:
        sym = h.get("symbol","")
        qty = h.get("qty", 0)
        cost = h.get("avg_cost", 0)
        price = h.get("current_price", 0)
        mv = h.get("market_value", 0)
        upnl = h.get("unrealized_pnl", 0)
        d1 = h.get("pnl_1d_pct") or 0
        w1 = h.get("pnl_1w_pct") or 0
        m1 = h.get("pnl_1m_pct") or 0
        pe = h.get("pe_ratio")
        holding_rows += f"""
        <tr>
          <td><span class="sym">{sym}</span></td>
          <td>{qty}</td>
          <td>${cost:.2f}</td>
          <td>${price:.2f}</td>
          <td>${mv:,.2f}</td>
          <td style="color:{_color(upnl)};font-weight:600">${upnl:+,.2f}</td>
          <td style="color:{_color(d1)}">{_arrow(d1)}{abs(d1):.1f}%</td>
          <td style="color:{_color(w1)}">{_arrow(w1)}{abs(w1):.1f}%</td>
          <td style="color:{_color(m1)}">{_arrow(m1)}{abs(m1):.1f}%</td>
          <td>{pe if pe else '-'}</td>
        </tr>"""

    top10_chips = "".join(
        f'<span class="chip">{i+1}. {s}</span>' for i, s in enumerate(top10))
    pred10_chips = "".join(
        f'<span class="chip pred">{i+1}. {s}</span>' for i, s in enumerate(pred10))

    qqq_1d = (benchmark.get("QQQ") or {}).get("1d") or 0
    spy_1d = (benchmark.get("SPY") or {}).get("1d") or 0

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlpacaBot 日報 {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh;padding:1.5rem}}
  h1{{font-size:1.6rem;background:linear-gradient(135deg,#38bdf8,#818cf8);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
  .header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem;flex-wrap:wrap;gap:8px}}
  .subtitle{{color:#94a3b8;font-size:.88rem}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:1rem;margin-bottom:1.5rem}}
  .kpi{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1rem 1.2rem}}
  .kpi .label{{font-size:.75rem;color:#94a3b8;margin-bottom:.3rem}}
  .kpi .value{{font-size:1.4rem;font-weight:700}}
  .card{{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:1.2rem;margin-bottom:1.2rem}}
  .card h2{{font-size:.95rem;color:#94a3b8;margin-bottom:1rem}}
  table{{width:100%;border-collapse:collapse;font-size:.82rem}}
  th{{background:#0f172a;color:#64748b;padding:8px 10px;text-align:left;border-bottom:1px solid #334155}}
  td{{padding:8px 10px;border-bottom:1px solid #1e293b}}
  tr:hover td{{background:#1e293b55}}
  .sym{{background:#1d4ed820;color:#38bdf8;border-radius:4px;padding:2px 6px;font-weight:600}}
  .chips{{display:flex;flex-wrap:wrap;gap:8px}}
  .chip{{background:#1e3a5f;color:#7dd3fc;border-radius:20px;padding:4px 12px;font-size:.82rem;font-weight:600}}
  .chip.pred{{background:#3b0764;color:#e879f9}}
  .toggle-row{{display:flex;gap:12px;margin-bottom:12px;align-items:center}}
  .toggle-row label{{display:flex;align-items:center;gap:6px;font-size:.85rem;color:#94a3b8;cursor:pointer}}
  .chart-wrap{{position:relative;height:280px}}
  .footer{{text-align:center;margin-top:2rem;font-size:.78rem;color:#475569}}
  .bench-row{{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem}}
</style>
</head>
<body>
<div class="header">
  <div>
    <h1>📊 AlpacaBot 日報</h1>
    <div class="subtitle">{date_str} | {account_name} | 策略：{strategy}</div>
  </div>
</div>

<div class="kpi-grid">
  <div class="kpi"><div class="label">💵 現金水位</div><div class="value">${cash:,.0f}</div></div>
  <div class="kpi"><div class="label">📈 投組總值 (NAV)</div><div class="value">${nav:,.0f}</div></div>
  <div class="kpi"><div class="label">今日損益</div><div class="value" style="color:{_color(pnl_pct)}">{_arrow(pnl_pct)}{abs(pnl_pct):.2f}%<br><small style="font-size:.9rem">${pnl:+,.0f}</small></div></div>
  <div class="kpi"><div class="label">最大回撤</div><div class="value" style="color:{_color(-abs(drawdown))}">{drawdown:.1f}%</div></div>
  <div class="kpi"><div class="label">QQQ 今日</div><div class="value" style="color:{_color(qqq_1d)}">{_arrow(qqq_1d)}{abs(qqq_1d):.2f}%</div></div>
  <div class="kpi"><div class="label">SPY 今日</div><div class="value" style="color:{_color(spy_1d)}">{_arrow(spy_1d)}{abs(spy_1d):.2f}%</div></div>
</div>

<div class="card">
  <h2>📉 NAV 走勢 vs Benchmark</h2>
  <div class="toggle-row">
    <label><input type="checkbox" id="chk-nav" checked onchange="toggleLine(0)"> 我的帳戶</label>
    <label><input type="checkbox" id="chk-qqq" checked onchange="toggleLine(1)"> QQQ (NASDAQ)</label>
    <label><input type="checkbox" id="chk-spy" checked onchange="toggleLine(2)"> SPY (S&P500)</label>
  </div>
  <div class="chart-wrap">
    <canvas id="navChart"></canvas>
  </div>
</div>

<div class="card">
  <h2>📋 持倉清單</h2>
  <table>
    <thead>
      <tr><th>股票</th><th>股數</th><th>成本</th><th>現價</th><th>市值</th><th>未實現損益</th><th>1日</th><th>1週</th><th>1月</th><th>P/E</th></tr>
    </thead>
    <tbody>{holding_rows if holding_rows else '<tr><td colspan="10" style="color:#64748b;text-align:center">尚無持倉</td></tr>'}</tbody>
  </table>
</div>

<div class="card">
  <h2>🏆 今日 Top 10（市值排行）</h2>
  <div class="chips">{top10_chips if top10_chips else '<span style="color:#64748b">暫無資料</span>'}</div>
</div>

<div class="card">
  <h2>🔮 明日預測 Top 10 <span style="color:#ef4444;font-size:.8rem">⚠️ 僅供參考，不構成投資建議</span></h2>
  <div class="chips">{pred10_chips if pred10_chips else '<span style="color:#64748b">暫無資料</span>'}</div>
</div>

<div class="footer">
  ⚠️ 本報告所有內容僅供資訊整理與研究參考，不構成任何投資建議。<br>
  投資有風險，過去績效不代表未來結果。P/E = 股價 ÷ 每股盈餘。回撤 = 從歷史高點下跌幅度。<br>
  AlpacaBot | 自動產生於 {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

<script>
const labels = {nav_labels};
const navData = {nav_values};
const qqqData = {qqq_values};
const spyData  = {spy_values};

// 正規化為百分比變動
function normalize(arr) {{
  const base = arr.find(v => v !== null && v !== undefined);
  if (!base) return arr;
  return arr.map(v => v === null ? null : parseFloat(((v - base) / base * 100).toFixed(2)));
}}

const ctx = document.getElementById('navChart').getContext('2d');
const chart = new Chart(ctx, {{
  type: 'line',
  data: {{
    labels,
    datasets: [
      {{ label:'我的帳戶', data: normalize(navData), borderColor:'#38bdf8', backgroundColor:'rgba(56,189,248,.08)', tension:.3, pointRadius:2, fill:true }},
      {{ label:'QQQ', data: normalize(qqqData), borderColor:'#818cf8', backgroundColor:'transparent', tension:.3, pointRadius:2 }},
      {{ label:'SPY', data: normalize(spyData), borderColor:'#34d399', backgroundColor:'transparent', tension:.3, pointRadius:2 }},
    ]
  }},
  options: {{
    responsive: true,
    maintainAspectRatio: false,
    plugins: {{
      legend: {{ labels: {{ color:'#94a3b8' }} }},
      tooltip: {{ mode:'index', intersect:false }}
    }},
    scales: {{
      x: {{ ticks: {{ color:'#64748b', maxTicksLimit:8 }}, grid: {{ color:'#1e293b' }} }},
      y: {{ ticks: {{ color:'#64748b', callback: v => v+'%' }}, grid: {{ color:'#1e293b' }} }}
    }}
  }}
}});

function toggleLine(idx) {{
  chart.data.datasets[idx].hidden = !chart.data.datasets[idx].hidden;
  chart.update();
}}
</script>
</body>
</html>"""


def _load_nav_history(account_id: str, up_to_date: str) -> List[Dict]:
    """從歷史 JSON 建構 NAV / benchmark 時序"""
    if not os.path.exists(MODEL_DIR):
        return []
    files = sorted([
        f for f in os.listdir(MODEL_DIR)
        if f.startswith(account_id) and f.endswith(".json") and "state" not in f
    ])
    result = []
    for fname in files:
        date_str = fname.replace(f"{account_id}_", "").replace(".json", "")
        if date_str > up_to_date:
            continue
        try:
            with open(os.path.join(MODEL_DIR, fname), "r", encoding="utf-8") as f:
                data = json.load(f)
            bm = data.get("benchmark", {})
            result.append({
                "date": date_str,
                "nav": data.get("nav"),
                "qqq": (bm.get("QQQ") or {}).get("1d"),
                "spy": (bm.get("SPY") or {}).get("1d"),
            })
        except Exception:
            pass
    return result
