# AlpacaBot — 專案記憶文件

> 此文件供 AI（Claude）或新進開發者快速上手本專案。
> 每次重要變更後請更新此文件。

---

## 專案目的

全自動美股投資系統，以 Alpaca Paper/Live Trading API 為核心，功能包含：
- 多帳戶自動下單（策略由 JSON 定義，不需改 Python）
- 每日 Email 日報（上午 6 點，含持倉、盈虧、Top10、關注股）
- Streamlit 視覺化 Dashboard
- GitHub Actions 全自動每日執行
- 歷史報告儲存與回查

---

## 核心設計原則

| 原則 | 說明 |
|------|------|
| 策略 = JSON | 新增/修改策略只需 `config/strategies/*.json`，不改 Python |
| 報告 Model-View 分離 | `reports/model/*.json`（純資料）+ `reports/view/*.html`（呈現層）|
| 多帳戶獨立 | 每帳戶各自的 API Key、策略、Email、watchlist |
| 每帳戶同時只能用一策略 | `accounts.json` 中 `active_strategy` 控制 |
| 只買整數股 | `math.floor(budget / price)` |
| 每股投入 10% | `per_stock_pct: 10` |
| 再平衡觸發 | 新資金進入（>$1000）或每月 1 日 |
| GitHub Actions 是唯一自動執行入口 | `.github/workflows/daily_trade.yml` |

---

## 目錄結構

```
AlpacaBot/
├── config/
│   ├── accounts.json              # 帳戶設定（含策略、email、watchlist）
│   └── strategies/
│       ├── top10_momentum.json    # 策略1：Nasdaq市值前十
│       └── value_pe.json          # 策略2：低本益比
├── core/
│   ├── alpaca_client.py           # Alpaca REST API v2 封裝
│   ├── market_data.py             # yfinance：股價、市值、P/E、漲跌幅
│   ├── strategy_engine.py         # 讀 JSON 策略 → 執行買賣
│   ├── rebalancer.py              # 再平衡邏輯
│   └── notifier.py                # Email 通知（日報、即時交易）
├── reports/
│   ├── model/
│   │   ├── generate.py            # 產生 JSON 日報（Model 層）
│   │   └── ACCT_YYYY-MM-DD.json  # 歷史報告（永久保存）
│   └── view/
│       ├── render.py              # JSON → HTML（View 層）
│       └── ACCT_YYYY-MM-DD.html  # HTML 報告
├── dashboard/
│   └── app.py                     # Streamlit Dashboard
├── tests/
│   ├── test_alpaca_client.py      # Phase 1 tests (TC-01~02, TC-09)
│   ├── test_market_data.py        # Phase 1 tests (TC-03~05)
│   ├── test_strategy_engine.py    # Phase 2 tests (TC-06~11)
│   ├── test_reports.py            # Phase 3 tests (TC-12~16)
│   └── test_notifier.py           # Phase 4 tests (TC-17~19)
├── .github/workflows/
│   └── daily_trade.yml            # GitHub Actions 主流程
├── requirements.txt
├── .env.example                   # 環境變數範例
├── .gitignore
├── CLAUDE.md                      # 本文件
├── PLAN.md                        # 完整專案計劃書
└── README.md                      # 使用說明
```

---

## 重要檔案說明

### config/accounts.json
- 帳戶清單、API Key（以 `${ENV_VAR}` 引用環境變數）
- `active_strategy`: 指定使用哪個策略
- `watchlist`: 關注股分類（科技股、AI相關、ETF）

### config/strategies/*.json
- 每個 JSON = 一個策略
- 欄位：`strategy_id`, `selection`, `allocation`, `rebalance`, `entry`, `exit`, `notify`
- 新增策略：只需在此目錄新增 JSON 檔

### core/strategy_engine.py
- 入口函式：`run_all_accounts()` — GitHub Actions 呼叫此函式
- 流程：載入策略 → 選股 → 計算目標持倉 → 比對現有持倉 → 下單

### core/rebalancer.py
- `check_and_rebalance(client, strategy)` — 自動偵測再平衡觸發條件
- 狀態儲存於 `reports/model/{account_id}_state.json`

### reports/model/generate.py
- `generate_all_reports()` — 產生所有帳戶當日 JSON 報告
- `get_history(account_id, start, end)` — 歷史報告回查

### dashboard/app.py
- `streamlit run dashboard/app.py`
- 功能：帳戶切換、NAV 線圖（可勾選 QQQ/SPY）、持倉表、Top10、關注股、歷史回查

---

## API 資訊

| 項目 | 說明 |
|------|------|
| Alpaca Paper API | `https://paper-api.alpaca.markets/v2` |
| Alpaca Live API | `https://api.alpaca.markets/v2` |
| 市場資料 | `yfinance`（P/E、市值、歷史股價） |
| Headers | `APCA-API-KEY-ID`, `APCA-API-SECRET-KEY` |

---

## 再平衡規則

1. **新資金進入**：`cash 增加 > deposit_threshold`（預設 $1000）
2. **每月 1 日**：無論是否有新資金
3. 再平衡執行時：賣出多餘持倉 → 買入不足持倉

---

## 環境變數設定

```bash
cp .env.example .env
# 填入 API Key、SMTP 設定
```

GitHub Actions Secrets 需設定：
- `ALPACA_KEY_1` / `ALPACA_SECRET_1`
- `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD`
- `NOTIFY_EMAIL`

---

## 執行指令

```bash
# 安裝套件
pip install -r requirements.txt

# 執行測試
pytest tests/ -v

# 手動執行策略（試算模式）
python core/strategy_engine.py --run-all --dry-run

# 產生今日日報
python reports/model/generate.py --all

# 啟動 Dashboard
streamlit run dashboard/app.py
```

---

## 測試 Cases 總覽（共 26 個）

| TC# | 模組 | 說明 |
|-----|------|------|
| TC-01 | alpaca_client | 帳戶連線，回傳 ACTIVE |
| TC-02 | alpaca_client | 多帳戶隔離 |
| TC-03 | market_data | 即時股價字典 |
| TC-04 | market_data | 市值前十，降序 |
| TC-05 | market_data | P/E 本益比 |
| TC-06 | strategy_engine | JSON 策略載入 |
| TC-07 | strategy_engine | 資金分配（10%） |
| TC-08 | strategy_engine | 整數股計算 |
| TC-09 | alpaca_client | 下單回傳 order_id |
| TC-10 | rebalancer | 新資金偵測 |
| TC-11 | rebalancer | 每月 1 日再平衡 |
| TC-12 | reports.model | 日報 JSON 生成 |
| TC-13 | reports.model | NAV 損益計算 |
| TC-14 | reports.model | 回撤計算 |
| TC-15 | reports.model | 歷史報告回查 |
| TC-16 | reports.view | HTML 渲染 |
| TC-17 | notifier | Email 發送 |
| TC-18 | notifier | 即時交易通知 |
| TC-19 | notifier | 多帳戶 Email 隔離 |
| TC-20~26 | dashboard/CI | Dashboard + GitHub Actions |

---

## 免責聲明

> ⚠️ 本系統所有輸出（排名、預測、績效）**僅供資訊整理與研究參考**，
> **不構成任何投資建議**。投資有風險，請謹慎評估。

---

*最後更新：2026-05-24 | AlpacaBot v1.0*
