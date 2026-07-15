<div align="center">

# 🇮🇳 auto_trade_bot

### Automated Stock Trading Bot for the Indian Market (NSE / BSE)

*A high-performance algorithmic trading engine that continuously rotates capital between NSE/BSE stocks using real-time price ratio analysis — maximising value on every trade.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-green.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](Dockerfile)
[![NSE](https://img.shields.io/badge/Exchange-NSE%20%7C%20BSE-orange.svg)]()

**Author: K R HARI PRAJWAL**

</div>

---

## 📖 Table of Contents

- [How It Works](#-how-it-works)
- [Key Features](#-key-features)
- [Supported Brokers](#-supported-brokers)
- [Indian Brokerage Fees Explained](#-indian-brokerage-fees--scout-margin-guide)
- [Quick Start](#-quick-start)
- [Docker Setup](#-docker-setup-recommended)
- [Configuration Reference](#-configuration-reference)
- [Backtesting](#-backtesting)
- [Project Structure](#-project-structure)
- [Smart Square-Off Logic](#-smart-square-off-logic)
- [FAQ](#-faq)
- [Disclaimer](#-disclaimer)

---

## 🧠 How It Works

The bot operates on a **continuous ratio-rotation strategy**:

1. At every scout cycle (default: every 10 seconds), it fetches the live price of your current stock and every other stock in your list
2. It computes a **ratio score** for each potential swap — measuring how much a target stock has gained *relative* to your current holding, after accounting for all brokerage fees
3. When any target stock's ratio score exceeds your configured `scout_margin` threshold, the bot executes: **Sell current stock → Receive INR → Buy target stock**
4. This repeats indefinitely during market hours

> **INR (cash) is the bridge currency** — you're never just sitting idle in cash. You always hold whichever stock is performing best relative to the others.

The strategy exploits **relative momentum**: if `RELIANCE` has moved up 1% while you're holding `TCS` which has been flat, the bot captures that divergence before the gap closes.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🏦 **6 Broker Support** | Angel One, Zerodha, Upstox, Dhan, Fyers, Groww — switch with one config line |
| 📊 **Real-time Ratio Scouting** | Live price comparison across all your stocks every 10 seconds |
| 🔀 **2 Strategies** | Default (1 stock) or Multiple Stocks (hold N, rotate worst) |
| 🕐 **Market Hours Guard** | Bot automatically idles outside 9:15 AM – 3:30 PM IST and on weekends |
| ⚡ **Circuit Breaker Detection** | Skips stocks at upper/lower circuit limits automatically |
| 🧮 **Precise Fee Calculation** | Uses real Indian brokerage breakdown (STT, GST, exchange charges, stamp duty) |
| 🌙 **Smart Square-Off** | Near close: auto-decides whether to cut loss or convert to delivery overnight |
| 📈 **Backtesting Engine** | Test your settings on real NSE/BSE historical data (free, open source) |
| 🐳 **Docker Ready** | One command to run — persistent volumes for DB, logs, trade history |
| 📝 **Trade History JSON** | Every trade logged with exact quantities, prices, and INR values |
| 🔁 **Auto-Restart** | Docker `restart: unless-stopped` keeps the bot running 24/7 |

---

## 🏦 Supported Brokers

| Broker | Library | Auto-login | Notes |
|---|---|---|---|
| **Angel One** | `smartapi-python` | ✅ Yes (TOTP) | Recommended — free API, no daily token refresh |
| **Zerodha** | `kiteconnect` | ⚠️ Partial | Access token must be refreshed manually every day |
| **Upstox** | `upstox-python-sdk` | ⚠️ Partial | Good websocket support |
| **Dhan** | `dhanhq` | ✅ Token-based | Simple REST, great for beginners |
| **Fyers** | `fyers-apiv3` | ⚠️ Partial | Best for intraday execution speed |
| **Groww** | `requests` (REST) | ✅ Token-based | **Zero brokerage on delivery** — cheapest for CNC trades |

---

## 💸 Indian Brokerage Fees & Scout Margin Guide

Unlike international markets, Indian brokerage involves multiple regulatory charges. Understanding these is critical to setting a profitable `scout_margin`.

### Intraday (MIS) — Per Trade Round-Trip

| Charge | Calculation | Approx % (₹50k trade) |
|---|---|---|
| Brokerage | ₹20 flat per order | ~0.04% per side |
| STT | 0.025% on **sell side only** | 0.025% (one-time) |
| NSE Exchange | 0.00345% per side | 0.007% |
| GST (18%) | On brokerage + exchange | ~0.008% |
| SEBI | 0.0001% per side | 0.0002% |
| Stamp Duty | 0.003% on buy side | 0.003% (one-time) |
| **Total Round-Trip** | | **≈ 0.13%** |

> ✅ **Recommended `scout_margin` for intraday: `0.3%`**
> This gives you ~0.17% profit per trade after all fees.

---

### Delivery (CNC) — Per Trade Round-Trip

**Standard brokers (Angel One, Zerodha, Upstox, Dhan, Fyers):**

| Charge | Calculation | Approx % (₹50k trade) |
|---|---|---|
| Brokerage | ₹20 flat per order | ~0.04% per side |
| STT | **0.1% on BOTH sides** | **0.2% total** ← biggest cost |
| NSE Exchange | 0.00345% per side | 0.007% |
| GST (18%) | On brokerage + exchange | ~0.008% |
| SEBI | 0.0001% per side | 0.0002% |
| Stamp Duty | 0.015% on buy side | 0.015% (one-time) |
| **Total Round-Trip** | | **≈ 0.32%** |

> ✅ **Recommended `scout_margin` for delivery (standard brokers): `0.8%`**

**Groww (zero brokerage on delivery):**

| Charge | Calculation | Approx % (₹50k trade) |
|---|---|---|
| Brokerage | **₹0 — FREE** ✅ | 0% |
| STT | **0.1% on BOTH sides** | **0.2% total** |
| NSE Exchange | 0.00345% per side | 0.007% |
| GST (18%) | On exchange charges only | ~0.001% |
| SEBI | 0.0001% per side | 0.0002% |
| Stamp Duty | 0.015% on buy side | 0.015% (one-time) |
| **Total Round-Trip** | | **≈ 0.21%** |

> ✅ **Recommended `scout_margin` for Groww delivery: `0.5%`** (cheaper than others!)

---

> [!TIP]
> Higher `scout_margin` = fewer trades, but each trade is more profitable.
> Lower `scout_margin` = more frequent trades, smaller gains each time.
> Start at the recommended values and tune based on your backtest results.

---

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- A broker account with API access enabled
- Minimum ₹5,000 capital to start (more = better — flat brokerage ₹20/order hurts on tiny trades)

### 1. Clone and install

```bash
git clone https://github.com/Hariprajwal/auto-trader-bot.git
cd auto-trader-bot

python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate    # Linux/Mac

pip install -r requirements.txt
```

Install **only your broker's SDK**:
```bash
pip install smartapi-python pyotp    # Angel One (recommended)
# pip install kiteconnect             # Zerodha
# pip install upstox-python-sdk       # Upstox
# pip install dhanhq                  # Dhan
# pip install fyers-apiv3             # Fyers
# pip install requests                # Groww (already included in requirements.txt)
```

### 2. Configure your broker

```bash
copy user.cfg.example user.cfg     # Windows
# cp user.cfg.example user.cfg      # Linux/Mac
```

Open `user.cfg` and fill in your credentials. Example for Angel One:

```ini
[auto_trade_bot_config]
broker        = angel_one
api_key       = your_api_key_here
client_id     = your_client_id
password      = your_login_password
totp_secret   = your_totp_base32_secret

exchange      = NSE
trade_type    = intraday
scout_margin  = 0.3
```

### 3. Set your stock list

Edit `supported_stock_list` — one NSE symbol per line:

```
RELIANCE
TCS
INFY
HDFCBANK
ICICIBANK
```

> Use large-cap, highly liquid stocks. Wide bid-ask spreads in low-volume stocks will eat into your margins.

### 4. Run a backtest first

Always backtest before going live:

```bash
python -m auto_trade_bot backtest
```

### 5. Start the bot (Windows)

**Option A — One-click batch file:**
```bat
run.bat
```

**Option B — Manual:**
```bash
python -m auto_trade_bot
```

---

## 🐳 Docker Setup (Recommended)

Docker is the cleanest way to run the bot — it auto-restarts on crashes, persists your data, and keeps everything isolated.

### Build and run

```bash
# First, make sure user.cfg exists and is filled in
docker compose up --build -d
```

### View live logs

```bash
docker compose logs -f
```

### Stop the bot

```bash
docker compose down
```

### Run a backtest in Docker

```bash
docker compose --profile backtest up backtest
```

### Docker volumes

Your data is persisted in named volumes and survives container restarts:

| Volume | Contents |
|---|---|
| `bot_data` | SQLite database (trade pairs, ratios, history) |
| `bot_logs` | Log files |
| `bot_results` | Backtest output JSONs |
| `./trade_history.json` | Your live trade log (mounted from host) |

---

## ⚙️ Configuration Reference

All settings go in `user.cfg` under `[auto_trade_bot_config]`.

### Broker Settings

| Key | Description |
|---|---|
| `broker` | `angel_one` / `zerodha` / `upstox` / `dhan` / `fyers` / `groww` |
| `api_key` | Your broker API key |
| `client_id` | Client/user ID (Angel One, Dhan, Fyers) |
| `password` | Login password (Angel One) |
| `totp_secret` | TOTP base32 secret for 2FA auto-login (Angel One) |
| `access_token` | Pre-generated token (Zerodha, Upstox, Dhan, Fyers) |
| `api_secret` | API secret (Zerodha, Upstox) |

### Trading Settings

| Key | Default | Description |
|---|---|---|
| `exchange` | `NSE` | `NSE`, `BSE` |
| `trade_type` | `delivery` | **`delivery`** (hold indefinitely, recommended) or `intraday` (day trading, must square off 3:20 PM) |
| `scout_margin` | `0.8` | Min % gain to trigger a trade. **0.8 for delivery, 0.5 for Groww delivery, 0.3 for intraday** |
| `scout_sleep_time` | `10` | Seconds between each price scan |
| `use_margin` | `yes` | `yes` = margin mode (scout_margin as %), `no` = multiplier mode |
| `scout_multiplier` | `5` | Only used when `use_margin = no` |
| `sell_timeout` | `30` | Seconds to wait for sell order fill before cancelling |
| `buy_timeout` | `30` | Seconds to wait for buy order fill before cancelling |

### Market Hours

| Key | Default | Description |
|---|---|---|
| `market_open_time` | `09:15` | Bot starts scouting at this time (IST) |
| `market_close_time` | `15:20` | Bot stops and handles square-off at this time (IST) |
| `max_loss_to_carry_delivery_pct` | `2.0` | If intraday loss < this %, convert to delivery near close instead of forced exit |

### Startup

| Key | Default | Description |
|---|---|---|
| `current_stock` | *(empty)* | Stock to hold when bot starts. Leave empty to pick randomly |
| `strategy` | `default` | `default` (hold 1 stock) or `multiple_stocks` (hold N, rotate worst) |
| `portfolio_size` | `3` | Number of stocks to hold simultaneously *(only for `multiple_stocks` strategy)* |

---

## 📊 Backtesting

The backtest engine downloads real historical NSE/BSE data (via Yahoo Finance, free and open source) and simulates the exact trading logic on it.

### Basic backtest

```bash
python -m auto_trade_bot backtest
```

Uses your `supported_stock_list` and runs for the past 12 months with default settings.

### Custom backtest

```bash
python -m auto_trade_bot backtest \
  --stocks RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK,SBIN,WIPRO \
  --start  2023-01-01 \
  --end    2024-12-31 \
  --capital 100000 \
  --scout-margin 0.8 \
  --exchange NSE \
  --interval 1d \
  --save

# Simulate intraday mode:
python -m auto_trade_bot backtest \
  --stocks RELIANCE,TCS,INFY \
  --scout-margin 0.3 \
  --fee 0.00065 \
  --save
```

### Backtest options

| Flag | Default | Description |
|---|---|---|
| `--stocks` | From file | Comma-separated NSE symbols |
| `--start` | 1 year ago | Start date `YYYY-MM-DD` |
| `--end` | Today | End date `YYYY-MM-DD` |
| `--capital` | `100000` | Starting capital in INR |
| `--exchange` | `NSE` | `NSE` or `BSE` |
| `--interval` | `1d` | `1d` daily, `1h` hourly, `5m` five-minute (max 60 days) |
| `--scout-margin` | `0.8` | Scout margin %. **0.8 delivery (default), 0.5 Groww delivery, 0.3 intraday** |
| `--fee` | `0.00158` | Per-side fee as decimal. **0.00158 delivery (default), 0.00065 intraday** |
| `--save` | Off | Save full trade + portfolio JSON to `backtest_results/` |
| `--initial-stock` | First in list | Which stock to hold at the start |

### Example output

```
════════════════════════════════════════════════════════════
  BACKTEST RESULTS
════════════════════════════════════════════════════════════
  Initial capital      :     ₹1,00,000.00
  Final portfolio      :     ₹1,21,843.50
  Total return         :        +21.84%
  Total trades         :             52
  Win rate             :          65.4%
  Avg trade P&L        :         +0.42%
  Max drawdown         :         -7.93%

  Buy-and-hold comparison:
         RELIANCE:    ₹1,09,200.00  (+9.20%)  ← you beat this!
              TCS:    ₹1,04,100.00  (+4.10%)  ← you beat this!
             INFY:     ₹98,700.00   (-1.30%)  ← you beat this!
           SBIN:     ₹1,15,300.00  (+15.30%)  ← you beat this!
════════════════════════════════════════════════════════════
```

---

## 🌙 Smart Square-Off Logic

For **intraday trades**, the bot automatically handles end-of-day positions 12 minutes before `market_close_time`:

```
Position still open near 3:20 PM?
        │
        ▼
Is current P&L ≥ 0?
    YES ──► Square off cleanly, take the profit ✅
        │
       NO
        │
        ▼
Is loss ≤ max_loss_to_carry_delivery_pct?
    YES ──► Convert to DELIVERY (CNC), hold overnight 🌙
        │   Avoids forced square-off at a bad price
       NO
        │
        ▼
Loss too large to carry ──► Cut loss, square off now 🛑
                             Protects from overnight risk
```

> Set `max_loss_to_carry_delivery_pct = 0` to always square off regardless.

---

## 📁 Project Structure

```
auto-trader-bot/
│
├── auto_trade_bot/
│   ├── __main__.py              ← Entry point (live or backtest)
│   ├── stock_trading.py         ← Main orchestrator
│   ├── auto_trader.py           ← Core ratio engine + market logic
│   ├── backtest.py              ← Backtesting engine (yfinance)
│   ├── config.py                ← Config reader (user.cfg / env vars)
│   ├── database.py              ← SQLite persistence layer
│   ├── logger.py                ← Dual file+console logger with startup banner
│   ├── scheduler.py             ← Safe scheduler (won't crash on job errors)
│   │
│   ├── brokers/
│   │   ├── base_broker.py       ← Abstract interface all brokers implement
│   │   ├── angel_one_broker.py  ← Angel One SmartAPI (recommended)
│   │   ├── zerodha_broker.py    ← Zerodha Kite
│   │   ├── upstox_broker.py     ← Upstox v2
│   │   ├── dhan_broker.py       ← Dhan
│   │   ├── fyers_broker.py      ← Fyers
│   │   └── groww_broker.py      ← Groww Pro (zero delivery brokerage!)
│   │
│   ├── models/
│   │   ├── stock.py             ← Stock entity
│   │   ├── pair.py              ← Stock pair with stored ratio
│   │   ├── trade.py             ← Trade record with full state
│   │   ├── current_stock.py     ← Currently held stock tracker
│   │   ├── stock_value.py       ← Portfolio value snapshots
│   │   └── scout_history.py     ← Ratio scout log (for analysis)
│   │
│   └── strategies/
│       ├── default_strategy.py        ← Hold 1 stock, rotate when ratio improves
│       └── multiple_stocks_strategy.py ← Hold N stocks, rotate the weakest one
│
├── supported_stock_list          ← One NSE symbol per line
├── user.cfg.example              ← Config template (copy → user.cfg)
├── run.bat                       ← Windows one-click startup script
├── Dockerfile                    ← Docker build file
├── docker-compose.yml            ← Docker Compose (live + backtest profiles)
├── requirements.txt
├── LICENSE                       ← MIT License — K R HARI PRAJWAL
└── README.md
```

---

## ❓ FAQ

**Q: Can I run this while the market is closed?**
> Yes — the bot will start up, load all data, and then idle with a `Market is CLOSED` message until 9:15 AM IST the next trading day.

**Q: What happens if my broker API goes down mid-trade?**
> The bot logs the error and returns to scouting mode. The sell order timeout (`sell_timeout`) ensures the bot doesn't hang indefinitely waiting for a fill.

**Q: How much capital do I need?**
> A minimum of ₹10,000–₹20,000 is recommended. The flat ₹20/order brokerage means very small trades (< ₹2,000) have disproportionately high fee percentages. Larger capital = smaller effective fee %.

**Q: Will it work on weekends / market holidays?**
> The bot detects weekends automatically. For market holidays (e.g. Republic Day, Diwali), the broker API will return no data or errors, which the bot handles gracefully by retrying on the next cycle.

**Q: Can I add/remove stocks while the bot is running?**
> Edit `supported_stock_list` and restart the bot. It will update the database on startup.

**Q: What's the difference between `use_margin = yes` and `no`?**
> - `yes` (margin mode): A trade is triggered when the ratio score exceeds `scout_margin` as a direct percentage. More intuitive.
> - `no` (multiplier mode): Uses `scout_multiplier` to scale the ratio threshold. Advanced — not recommended unless you know what you're doing.

**Q: What's the difference between `default` and `multiple_stocks` strategies?**
> - `default`: Bot holds ONE stock at a time. Entire capital is in one stock. Simple and aggressive.
> - `multiple_stocks`: Bot holds N stocks simultaneously (set `portfolio_size`). Rotates only the weakest one. More diversified, lower risk, but gains are spread across multiple positions.

---

## ⚠️ Disclaimer

> This software is provided for **educational and research purposes only**. It is **not financial advice**. Algorithmic trading involves significant risk including total loss of capital. Past backtest results do not guarantee future performance. Always test thoroughly with small capital before scaling up. The author (K R HARI PRAJWAL) is not responsible for any trading losses incurred through the use of this software.
>
> **Trade at your own risk.**

---

<div align="center">

Made with ❤️ by **K R HARI PRAJWAL**

[MIT License](LICENSE)

</div>
