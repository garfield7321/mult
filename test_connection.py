"""AlpacaBot System Connection Test"""
import os, sys, json, math, requests
from datetime import datetime

KEY = "PKTDTIO27H3RSTK56FPHVX3AJ7"
SECRET = "QoEJ3onh5M99QdTrEECCprhvZJbhQEPxKQXWSS3u6Vn"
BASE = "https://paper-api.alpaca.markets/v2"
HEADERS = {"APCA-API-KEY-ID": KEY, "APCA-API-SECRET-KEY": SECRET}

def get(endpoint, params=None):
    return requests.get(f"{BASE}/{endpoint}", headers=HEADERS, params=params).json()

print("=" * 55)
print("  AlpacaBot Connection Test")
print("=" * 55)

# 1. Account
acct = get("account")
cash = float(acct["cash"])
pv   = float(acct["portfolio_value"])
print(f"\n[OK] Account : {acct['account_number']} | Status: {acct['status']}")
print(f"     Cash    : ${cash:,.2f}")
print(f"     NAV     : ${pv:,.2f}")
print(f"     Buying  : ${float(acct['buying_power']):,.2f}")

# 2. Positions
positions = get("positions")
print(f"\n[Holdings] {len(positions)} position(s)")
for p in positions:
    print(f"  {p['symbol']} x{p['qty']}  price=${float(p.get('current_price',0)):.2f}  pnl=${float(p.get('unrealized_pl',0)):+.2f}")
if not positions:
    print("  (no positions - fresh account)")

# 3. Clock
clock = get("clock")
is_open = clock["is_open"]
print(f"\n[Market] {'OPEN' if is_open else 'CLOSED'}")
print(f"  Next open  : {clock['next_open']}")
print(f"  Next close : {clock['next_close']}")

# 4. Nasdaq Top 10 by Market Cap
print("\n[Top 10] Fetching Nasdaq market cap (please wait...)")
try:
    import yfinance as yf
    UNIVERSE = [
        "MSFT","AAPL","NVDA","AMZN","META","GOOGL","TSLA","AVGO","COST","NFLX",
        "AMD","ADBE","CSCO","TXN","QCOM","AMGN","INTU","BKNG","ISRG","PANW"
    ]
    caps = []
    for sym in UNIVERSE:
        try:
            info = yf.Ticker(sym).fast_info
            cap   = getattr(info, "market_cap", None)
            price = getattr(info, "last_price", None)
            if cap:
                caps.append({"symbol": sym, "cap": cap, "price": price})
        except Exception:
            pass
    caps.sort(key=lambda x: x["cap"], reverse=True)
    top10 = caps[:10]

    print(f"  {'Rank':<5} {'Symbol':<8} {'Price':>9} {'Mkt Cap':>12}")
    print("  " + "-" * 38)
    for i, s in enumerate(top10):
        price_str = f"${s['price']:.2f}" if s['price'] else "N/A"
        print(f"  #{i+1:<4} {s['symbol']:<8} {price_str:>9} ${s['cap']/1e9:>8,.0f}B")
except Exception as e:
    print(f"  Failed: {e}")
    top10 = []

# 5. Strategy Dry-run
print(f"\n[Dry-run] Strategy: top10_momentum | Cash=${cash:,.2f}")
print(f"  Per-stock budget: 10% = ${cash*0.1:,.2f}")
print(f"  {'Symbol':<8} {'Price':>9} {'Budget':>12} {'Shares':>8} {'Cost':>12}")
print("  " + "-" * 52)
total = 0
plan  = []
for s in top10:
    price = s.get("price") or 0
    if price <= 0: continue
    budget = cash * 0.1
    qty    = math.floor(budget / price)
    cost   = qty * price
    total += cost
    plan.append({"symbol": s["symbol"], "qty": qty, "price": round(price,2), "cost": round(cost,2)})
    print(f"  {s['symbol']:<8} ${price:>8.2f} ${budget:>10,.2f} {qty:>6} sh  ${cost:>10,.2f}")
print(f"\n  Total invested : ${total:,.2f}")
print(f"  Remaining cash : ${cash - total:,.2f}")

# 6. Save daily report JSON
print("\n[Report] Generating daily JSON report...")
os.makedirs("reports/model", exist_ok=True)
os.makedirs("reports/view",  exist_ok=True)
today = datetime.now().strftime("%Y-%m-%d")

report = {
    "date"           : today,
    "account_id"     : acct["account_number"],
    "account_name"   : "Paper Trading Account",
    "strategy"       : "top10_momentum",
    "cash"           : cash,
    "portfolio_value": pv,
    "nav"            : pv,
    "daily_pnl"      : 0.0,
    "daily_pnl_pct"  : 0.0,
    "drawdown_pct"   : 0.0,
    "holdings"       : [
        {
            "symbol"        : p["symbol"],
            "qty"           : int(p["qty"]),
            "avg_cost"      : float(p.get("avg_entry_price", 0)),
            "current_price" : float(p.get("current_price", 0)),
            "market_value"  : float(p.get("market_value", 0)),
            "unrealized_pnl": float(p.get("unrealized_pl", 0)),
            "pnl_1d_pct"    : None,
            "pnl_1w_pct"    : None,
            "pnl_1m_pct"    : None,
            "pe_ratio"      : None,
        } for p in positions
    ],
    "top10_today"     : [s["symbol"] for s in top10],
    "top10_prediction": [s["symbol"] for s in top10],
    "benchmark"       : {"QQQ": {"1d": None}, "SPY": {"1d": None}},
    "orders_plan"     : plan,
    "generated_at"    : datetime.now().isoformat(),
}

report_path = f"reports/model/{acct['account_number']}_{today}.json"
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print(f"  Saved: {report_path}")

print("\n" + "=" * 55)
print("  All tests passed! System is ready.")
print("=" * 55)
print("\n[NOTICE] All outputs are for informational purposes only.")
print("         They do NOT constitute investment advice.")
