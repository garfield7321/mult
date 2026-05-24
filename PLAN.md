# AlpacaBot — 全自動美股投資系統 專案計劃書

> 版本 v1.0 | 日期：2026-05-24  
> **⚠️ 本系統所有輸出內容僅供資訊整理與研究參考，不構成任何投資建議。**

---

## 一、專案概述

AlpacaBot 是一套以 Alpaca API 為核心的全自動美股投資系統，目標提供：

- 多帳戶自動下單（策略由 JSON 定義）
- Streamlit 視覺化 Dashboard
- 每日 Email 日報（上午 6 點）
- GitHub Actions 自動觸發買賣
- 歷史報告儲存與回查
- NAV / 回撤圖表 vs NASDAQ / S&P500 對比

---

## 二、系統架構總覽

```
AlpacaBot/
├── config/
│   ├── accounts.json          # 帳戶設定（多帳戶）
│   └── strategies/
│       ├── top10_momentum.json  # 動能策略
│       ├── value_pe.json        # 本益比策略
│       └── [新增策略只需加json]
├── core/
│   ├── alpaca_client.py       # Alpaca API 封裝
│   ├── market_data.py         # 股價 / 市值 / P/E 資料
│   ├── strategy_engine.py     # 讀取 JSON 策略執行交易
│   ├── rebalancer.py          # 再平衡邏輯
│   └── notifier.py            # Email 通知
├── reports/
│   ├── model/                 # 報告資料層（JSON）
│   │   └── YYYY-MM-DD.json
│   └── view/                  # 報告呈現層（HTML/Text）
│       └── YYYY-MM-DD.html
├── dashboard/
│   └── app.py                 # Streamlit Dashboard
├── tests/                     # 每階段測試
├── .github/
│   └── workflows/
│       └── daily_trade.yml    # GitHub Actions 主流程
├── CLAUDE.md                  # 專案記憶（供 AI / 開發者快速上手）
└── PLAN.md                    # 本計劃書
```

---

## 三、JSON 策略格式規範

> **新增策略只需新增一個 JSON 檔，不需修改任何 Python 代碼。**

```json
{
  "strategy_id": "top10_momentum",
  "name": "Nasdaq 市值前十動能策略",
  "description": "每日選出 Nasdaq 市值前十，各投入 10% 資金，只買整數股",
  "universe": "NASDAQ_TOP100",
  "selection": {
    "method": "market_cap",
    "top_n": 10
  },
  "allocation": {
    "per_stock_pct": 10,
    "whole_shares_only": true
  },
  "rebalance": {
    "on_new_deposit": true,
    "monthly": true,
    "day_of_month": 1
  },
  "entry": {
    "type": "market",
    "time_in_force": "day"
  },
  "exit": {
    "stop_loss_pct": -15,
    "take_profit_pct": null
  },
  "notify": {
    "on_trade": true,
    "daily_report": true,
    "email_time": "06:00"
  }
}
```

### 帳戶設定格式

```json
{
  "accounts": [
    {
      "account_id": "PA3M7XRBN5WC",
      "name": "主帳戶",
      "endpoint": "https://paper-api.alpaca.markets/v2",
      "api_key": "YOUR_KEY",
      "api_secret": "YOUR_SECRET",
      "active_strategy": "top10_momentum",
      "email": "user@example.com",
      "watchlist": {
        "科技股": ["AAPL", "MSFT", "NVDA", "META"],
        "AI相關": ["PLTR", "AI", "SOUN", "BBAI"],
        "ETF": ["QQQ", "SPY", "ARKK"]
      }
    }
  ]
}
```

---

## 四、開發階段規劃

---

### Phase 1：基礎建設（第 1～2 週）

**目標：** Alpaca API 連線、帳戶資訊讀取、基礎資料獲取

**功能清單：**
- [ ] Alpaca 帳戶連線（支援多帳戶）
- [ ] 讀取現金、持倉、帳戶狀態
- [ ] 讀取即時股價
- [ ] 讀取 NASDAQ 市值前十股票
- [ ] 讀取個股 P/E 本益比

**📋 Test Cases Phase 1：**

```
TC-01 帳戶連線測試
  Given: 正確的 API Key/Secret
  When:  呼叫 GET /v2/account
  Then:  回傳 status=ACTIVE, cash>0

TC-02 多帳戶隔離測試
  Given: 兩組不同帳戶設定
  When:  同時初始化兩個 client
  Then:  各自回傳正確帳戶資訊，互不干擾

TC-03 即時股價測試
  Given: 股票代碼 ["AAPL","MSFT","NVDA"]
  When:  呼叫 market_data.get_latest_price()
  Then:  回傳字典含 symbol, price, timestamp

TC-04 市值排行測試
  Given: universe="NASDAQ_TOP100"
  When:  呼叫 market_data.get_top10_by_market_cap()
  Then:  回傳長度為 10 的清單，按市值降序排列

TC-05 P/E 本益比測試
  Given: 股票代碼 "AAPL"
  When:  呼叫 market_data.get_pe_ratio("AAPL")
  Then:  回傳數字 > 0 或 None（若無法取得）
```

---

### Phase 2：策略引擎（第 3～4 週）

**目標：** JSON 策略載入、買賣邏輯、再平衡

**功能清單：**
- [ ] 從 JSON 載入策略設定
- [ ] 計算各股應投入金額（10% × 現金）
- [ ] 只買整數股（floor 取整）
- [ ] 執行市價單下單
- [ ] 新資金進入時再平衡
- [ ] 每月初再平衡

**📋 Test Cases Phase 2：**

```
TC-06 策略載入測試
  Given: top10_momentum.json
  When:  strategy_engine.load("top10_momentum")
  Then:  成功解析所有欄位，無 KeyError

TC-07 資金分配計算測試
  Given: cash=100000, top_n=10, per_stock_pct=10
  When:  計算每檔應買金額
  Then:  每檔 = 10000, 總和 = 100000

TC-08 整數股計算測試
  Given: 每檔資金=10000, AAPL 股價=213.5
  When:  rebalancer.calc_shares(10000, 213.5)
  Then:  回傳 46（floor(10000/213.5)=46）

TC-09 下單測試（Paper Trading）
  Given: 帳戶 PA3M7XRBN5WC, 買入 AAPL 10 股
  When:  alpaca_client.place_order(symbol,qty,side)
  Then:  回傳 order_id, status in ["new","accepted"]

TC-10 再平衡觸發測試（新資金）
  Given: 當前持倉 + 偵測到 cash 增加 > 1000
  When:  rebalancer.check_and_rebalance()
  Then:  重新計算目標持倉，產生調整訂單清單

TC-11 每月再平衡測試
  Given: 日期 = 月初第一天
  When:  rebalancer.monthly_check()
  Then:  觸發再平衡流程，log 寫入 "monthly_rebalance"
```

---

### Phase 3：日報告系統（第 5～6 週）

**目標：** Model-View 分離，JSON 儲存報告，HTML 呈現

**功能清單：**
- [ ] 每日產生 JSON 報告（model 層）
- [ ] 報告包含：現金、持倉、盈虧、NAV、回撤
- [ ] NAV 線圖加入 NASDAQ / S&P500 對比（可勾選）
- [ ] HTML 報告（view 層）
- [ ] 歷史報告儲存與回查（依日期索引）

**JSON 報告格式：**

```json
{
  "date": "2026-05-24",
  "account_id": "PA3M7XRBN5WC",
  "strategy": "top10_momentum",
  "cash": 12500.00,
  "portfolio_value": 100000.00,
  "nav": 100000.00,
  "daily_pnl": 1250.00,
  "daily_pnl_pct": 1.25,
  "drawdown_pct": -3.2,
  "holdings": [
    {
      "symbol": "AAPL",
      "qty": 46,
      "avg_cost": 210.5,
      "current_price": 215.3,
      "market_value": 9897.8,
      "unrealized_pnl": 220.8,
      "pnl_1d_pct": 1.2,
      "pnl_1w_pct": 3.5,
      "pnl_1m_pct": 8.2,
      "pe_ratio": 28.5
    }
  ],
  "top10_today": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","COST","NFLX"],
  "top10_prediction": ["AAPL","MSFT","NVDA","AMZN","GOOGL","META","TSLA","AVGO","COST","NFLX"],
  "benchmark": {
    "qqq_1d_pct": 0.85,
    "spy_1d_pct": 0.72
  }
}
```

**📋 Test Cases Phase 3：**

```
TC-12 日報告生成測試
  Given: 帳戶資料 + 持倉資料
  When:  report_model.generate(account_id, date)
  Then:  產生 reports/model/2026-05-24.json，含所有必要欄位

TC-13 NAV 計算測試
  Given: 昨日 NAV=98000, 今日 portfolio_value=100000
  When:  計算 daily_pnl_pct
  Then:  = (100000-98000)/98000 * 100 = 2.04%

TC-14 回撤計算測試
  Given: 歷史 NAV 高點=105000, 當前=100000
  When:  計算 drawdown_pct
  Then:  = (100000-105000)/105000 * 100 = -4.76%

TC-15 歷史報告回查測試
  Given: 報告目錄有 30 天 JSON
  When:  report.get_history(account_id, start, end)
  Then:  回傳日期範圍內的報告清單

TC-16 HTML 報告渲染測試
  Given: 2026-05-24.json
  When:  report_view.render(date)
  Then:  產生 reports/view/2026-05-24.html，包含圖表
```

---

### Phase 4：Email 通知（第 7 週）

**目標：** 每日 6 點發送日報、即時交易通知

**功能清單：**
- [ ] SMTP Email 發送模組
- [ ] 每日 6AM 日報（含持倉、盈虧、Top10）
- [ ] 即時交易通知（下單成功、成交）
- [ ] 三大類關注股清單（科技股、AI 相關、ETF）
- [ ] Email 內容友善白話化

**Email 日報結構：**

```
主旨：📊 [AlpacaBot] 2026-05-24 投資日報 | 今日損益 +$1,250 (+1.25%)

帳戶：PA3M7XRBN5WC（主帳戶）
現金水位：$12,500
投資組合總值：$100,000
今日損益：+$1,250（+1.25%）
本月回撤：-3.2%

📌 今日 Top 10 持倉：
  1. AAPL  $215.3  今日+1.2%  本週+3.5%  本月+8.2%  P/E:28.5
  ...

📈 明日預測 Top 10：[清單]

👀 我的關注股：
  [科技股] AAPL:+1.2% MSFT:+0.8% ...
  [AI相關] PLTR:+3.1% AI:+2.4% ...
  [ETF]    QQQ:+0.85% SPY:+0.72% ...

⚠️ 以上內容僅供資訊整理與研究參考，不構成投資建議。
```

**📋 Test Cases Phase 4：**

```
TC-17 Email 發送測試
  Given: 正確 SMTP 設定 + 收件人
  When:  notifier.send_daily_report(account_id, date)
  Then:  Email 成功送出，回傳 message_id

TC-18 交易即時通知測試
  Given: 訂單 order_id 狀態變為 "filled"
  When:  notifier.on_order_filled(order)
  Then:  在 30 秒內發出 Email，主旨含 "成交通知"

TC-19 多帳戶 Email 隔離測試
  Given: 帳戶 A email=a@x.com, 帳戶 B email=b@x.com
  When:  同時發送兩帳戶日報
  Then:  各自收到對應帳戶的報告，不互相混淆
```

---

### Phase 5：Streamlit Dashboard（第 8～9 週）

**目標：** 視覺化 Dashboard，支援多帳戶切換

**Dashboard 功能：**

```
┌─────────────────────────────────────────────────┐
│  AlpacaBot Dashboard    帳戶：[下拉選單]          │
├──────────────┬──────────────┬───────────────────┤
│  💵 現金水位  │ 📈 投組總值  │ 📉 今日損益        │
│  $12,500     │  $100,000   │ +$1,250 (+1.25%)  │
├──────────────┴──────────────┴───────────────────┤
│  NAV 走勢圖  [☑ NASDAQ] [☑ S&P500]              │
│  ~~~線圖~~~                                      │
├─────────────────────────────────────────────────┤
│  持倉清單                                        │
│  Symbol | 股數 | 成本 | 現價 | 1日% | 1週% | 1月%│
├─────────────────────────────────────────────────┤
│  今日 Top 10 | 明日預測 Top 10                   │
├─────────────────────────────────────────────────┤
│  關注股票                                        │
│  [科技股] [AI相關] [ETF]  — Tab 切換             │
└─────────────────────────────────────────────────┘
```

**📋 Test Cases Phase 5：**

```
TC-20 Dashboard 載入測試
  Given: Streamlit app 啟動
  When:  瀏覽器開啟 localhost:8501
  Then:  頁面在 3 秒內載入，無 Exception

TC-21 多帳戶切換測試
  Given: 兩個帳戶設定
  When:  切換帳戶下拉選單
  Then:  所有數據更新為選定帳戶的資料

TC-22 NAV 比對圖表測試
  Given: 30 天歷史 NAV + QQQ + SPY 資料
  When:  勾選 NASDAQ / S&P500
  Then:  圖表正確顯示 / 隱藏對應線條

TC-23 持倉損益百分比測試
  Given: 持倉資料含 1日/1週/1月 盈虧
  When:  渲染持倉清單
  Then:  正值顯示綠色，負值顯示紅色
```

---

### Phase 6：GitHub Actions 自動化（第 10 週）

**目標：** 一條 Workflow 走遍所有帳戶，執行買賣

**GitHub Actions 主流程（daily_trade.yml）：**

```yaml
name: Daily Trade Execution

on:
  schedule:
    - cron: '30 13 * * 1-5'  # 台灣時間 21:30（美股開盤 30 分後）
  workflow_dispatch:

jobs:
  trade:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run strategy for all accounts
        env:
          ACCOUNTS_CONFIG: ${{ secrets.ACCOUNTS_CONFIG }}
        run: python core/strategy_engine.py --run-all
      - name: Generate daily reports
        run: python reports/model/generate.py --all
      - name: Send email reports
        run: python core/notifier.py --send-daily
      - name: Commit reports
        run: |
          git config user.name "AlpacaBot"
          git config user.email "bot@alpacabot.com"
          git add reports/
          git commit -m "Daily report $(date +%Y-%m-%d)" || echo "No changes"
          git push
```

**📋 Test Cases Phase 6：**

```
TC-24 Workflow 觸發測試
  Given: GitHub Actions cron 設定正確
  When:  手動觸發 workflow_dispatch
  Then:  Workflow 成功完成，exit code=0

TC-25 多帳戶順序執行測試
  Given: accounts.json 有 2 個帳戶
  When:  strategy_engine.py --run-all
  Then:  每個帳戶依序執行策略，各自 log 分離

TC-26 報告提交測試
  Given: 報告生成完成
  When:  git commit & push
  Then:  reports/ 目錄有新增的 JSON 和 HTML 檔案
```

---

## 五、技術堆疊

| 類別 | 技術 |
|------|------|
| API 串接 | Alpaca Trade API v2 |
| 市場資料 | yfinance / Alpaca Data API |
| Dashboard | Streamlit |
| 圖表 | Plotly |
| Email | smtplib / SendGrid |
| 排程 | GitHub Actions（cron） |
| 資料儲存 | JSON 檔案（本地 / Git） |
| 策略定義 | JSON |
| 測試 | pytest |
| 環境管理 | python-dotenv |

---

## 六、多帳戶 × 策略管理規則

| 規則 | 說明 |
|------|------|
| 一帳戶同時只能用一策略 | accounts.json 中 `active_strategy` 欄位控制 |
| 更換策略 | 修改 `active_strategy` → 下次執行即套用新策略 |
| 新增策略 | 只需在 `config/strategies/` 新增 JSON，不改 Python |
| 策略隔離 | 不同帳戶策略互不影響 |

---

## 七、開發時程總覽

```
Week 01-02  Phase 1  基礎建設（API連線、市場資料）
Week 03-04  Phase 2  策略引擎（JSON策略、下單、再平衡）
Week 05-06  Phase 3  日報告系統（Model-View分離、歷史儲存）
Week 07     Phase 4  Email 通知（日報、即時通知）
Week 08-09  Phase 5  Streamlit Dashboard
Week 10     Phase 6  GitHub Actions 自動化
Week 11     整合測試、文件、CLAUDE.md 更新
```

---

## 八、投資風險與資料限制提醒

> ⚠️ **重要聲明**
>
> 1. 本系統所有輸出（排名、預測、績效分析）**僅供資訊整理與研究參考，不構成任何投資建議**。
> 2. 股票預測模型基於歷史資料，**過去績效不代表未來結果**。
> 3. 市值排行、P/E 比等資料存在延遲，**不應作為即時交易依據**。
> 4. Paper Trading 結果不等同實際市場表現，**實盤交易請謹慎評估風險**。
> 5. 本益比（P/E Ratio）= 股價 ÷ 每股盈餘，數字越低不代表越好買，需結合產業特性判斷。
> 6. 回撤（Drawdown）= 從最高點下跌的幅度，衡量最大可能虧損。

---

## 九、CLAUDE.md 記憶重點

> 此檔案讓 AI 或新進開發者快速上手本專案。

```markdown
# AlpacaBot 專案記憶

## 核心設計原則
- 策略 = JSON，不改 Python 代碼
- 報告 Model-View 分離（JSON + HTML）
- 一帳戶同時只能用一策略
- GitHub Actions 是唯一執行入口
- 每股投入 10%，只買整數股

## 重要檔案
- config/accounts.json       帳戶 + 策略設定
- config/strategies/*.json   所有策略定義
- core/strategy_engine.py    讀 JSON 策略，執行交易
- core/rebalancer.py         再平衡（新資金/每月初）
- reports/model/             日報 JSON（永久保存）
- dashboard/app.py           Streamlit 入口
- .github/workflows/daily_trade.yml  自動執行入口

## API
- Alpaca Paper: https://paper-api.alpaca.markets/v2
- 市場資料: yfinance + Alpaca Data API

## 再平衡觸發
1. 新資金進入（cash 增加 > $1000）
2. 每月 1 日執行
```

---

*計劃書版本：v1.0 | AlpacaBot Project*
