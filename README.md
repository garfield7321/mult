# AlpacaBot — 全自動美股投資系統

> ⚠️ 本系統所有輸出內容**僅供資訊整理與研究參考，不構成任何投資建議。**
> 投資有風險，過去績效不代表未來結果。

---

## 功能總覽

| 功能 | 說明 |
|------|------|
| 🤖 自動下單 | 根據 JSON 策略每日自動選股、下單 |
| 📊 Dashboard | Streamlit 視覺化儀錶板（NAV/持倉/Top10/關注股）|
| 📧 Email 日報 | 每天上午 6 點發送盈虧日報 |
| ⚡ 即時通知 | 每筆成交立即 Email 通知 |
| 🏆 Top 10 分析 | Nasdaq 市值前十分析 + 明日預測 |
| 💹 本益比計算 | 每日自動計算各股 P/E 比 |
| 📁 歷史報告 | 每日報告永久儲存，可隨時回查 |
| 🔄 自動再平衡 | 新資金進入或每月初自動再平衡 |
| 👥 多帳戶支援 | 每帳戶獨立策略、Email、watchlist |
| 🔧 JSON 策略 | 新增策略只需加一個 JSON，不改程式碼 |

---

## 快速開始

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 設定環境變數

```bash
cp .env.example .env
# 填入 Alpaca API Key 和 Email SMTP 設定
```

### 3. 啟動 Dashboard

```bash
streamlit run dashboard/app.py
```

### 4. 試算（不實際下單）

```bash
python core/strategy_engine.py --run-all --dry-run
```

### 5. 產生今日日報

```bash
python reports/model/generate.py --all
```

### 6. 執行測試

```bash
pytest tests/ -v
```

---

## 目錄結構

```
AlpacaBot/
├── config/
│   ├── accounts.json              # 帳戶設定
│   └── strategies/
│       ├── top10_momentum.json    # 市值前十策略
│       └── value_pe.json          # 低本益比策略
├── core/
│   ├── alpaca_client.py           # Alpaca API 封裝
│   ├── market_data.py             # 市場資料（yfinance）
│   ├── strategy_engine.py         # 策略執行引擎
│   ├── rebalancer.py              # 再平衡模組
│   └── notifier.py                # Email 通知
├── reports/
│   ├── model/generate.py          # JSON 報告（Model 層）
│   └── view/render.py             # HTML 報告（View 層）
├── dashboard/app.py               # Streamlit Dashboard
├── tests/                         # 26 個測試 Cases
└── .github/workflows/
    └── daily_trade.yml            # GitHub Actions 自動排程
```

---

## 策略 JSON 格式

新增策略只需在 `config/strategies/` 新增一個 JSON 檔：

```json
{
  "strategy_id": "my_strategy",
  "name": "我的策略",
  "selection": { "method": "market_cap", "top_n": 10 },
  "allocation": { "per_stock_pct": 10, "whole_shares_only": true },
  "rebalance": { "on_new_deposit": true, "monthly": true, "day_of_month": 1 },
  "entry": { "type": "market", "time_in_force": "day" },
  "exit": { "stop_loss_pct": -15, "take_profit_pct": null }
}
```

---

## GitHub Actions 設定

在 GitHub → Settings → Secrets 設定：

| Secret | 說明 |
|--------|------|
| `ALPACA_KEY_1` | Alpaca API Key |
| `ALPACA_SECRET_1` | Alpaca API Secret |
| `SMTP_HOST` | SMTP 伺服器（e.g. smtp.gmail.com）|
| `SMTP_PORT` | SMTP Port（587）|
| `SMTP_USER` | 寄件人 Email |
| `SMTP_PASSWORD` | SMTP 密碼（Gmail 建議用應用程式密碼）|
| `NOTIFY_EMAIL` | 收件人 Email |

---

## Dashboard 功能

- 💵 現金水位 / 📈 投組總值 / 今日損益 / 最大回撤
- 📉 NAV 走勢圖（可勾選 QQQ / SPY 對比）
- 📋 持倉清單（含 1日/1週/1月 損益%、P/E）
- 🥧 持倉比重圓餅圖
- 🏆 今日 Top 10 + 🔮 明日預測 Top 10
- 👀 關注股票（分類 Tab 切換）
- 📁 歷史報告回查

---

## 重要名詞說明

| 名詞 | 白話說明 |
|------|---------|
| **NAV** | 帳戶總資產淨值（Net Asset Value）= 現金 + 持倉市值 |
| **回撤（Drawdown）** | 從歷史最高點下跌的幅度，代表最大曾虧損多少 |
| **P/E 本益比** | 股價 ÷ 每股盈餘，越低代表估值相對較低（需結合產業判斷）|
| **再平衡** | 重新調整各股比例，維持每股 10% 的目標配置 |
| **Paper Trading** | 模擬交易，不使用真實資金，用於測試策略 |

---

## 開發階段

| 階段 | 內容 | 測試 Cases |
|------|------|-----------|
| Phase 1 | API 連線、市場資料 | TC-01~05 |
| Phase 2 | 策略引擎、再平衡 | TC-06~11 |
| Phase 3 | 報告系統 | TC-12~16 |
| Phase 4 | Email 通知 | TC-17~19 |
| Phase 5 | Streamlit Dashboard | TC-20~23 |
| Phase 6 | GitHub Actions | TC-24~26 |

---

> ⚠️ **免責聲明**：本系統所有輸出（排名、預測、績效分析）僅供資訊整理與研究參考，
> 不構成任何投資建議。P/E 數字越低不代表越適合買入，需結合產業特性判斷。
> 投資有風險，請謹慎評估自身財務狀況。
