# auto_trade_bot 🇮🇳

An automated stock trading bot for the **Indian market (NSE/BSE)**, adapted from the crypto ratio-trading strategy. The bot constantly evaluates ratios between stocks in your portfolio and rotates capital into whichever stock is gaining the most relative ground — automatically.

Supports **Angel One, Zerodha, Upstox, Dhan, and Fyers**.

---

## How It Works

The bot holds one stock at a time. On every scout cycle (default: every 10 seconds), it:
1. Gets the live price of your current stock and all other supported stocks
2. Calculates a **ratio score** for each pair (same math as the original binance-trade-bot)
3. If any stock has gained enough relative to yours (above `scout_margin` %), it **sells your current stock → receives INR → immediately buys the better stock**
4. Over time, you accumulate more value per trade

> **INR is the bridge currency** — the same role USDT plays in the crypto bot.

---

## Quick Start

### 1. Install dependencies

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Install your broker's SDK (only install the one you use):
```bash
pip install smartapi-python      # Angel One
# pip install kiteconnect         # Zerodha
# pip install upstox-python-sdk   # Upstox
# pip install dhanhq              # Dhan
# pip install fyers-apiv3         # Fyers
```

### 2. Configure

```bash
copy user.cfg.example user.cfg
# Edit user.cfg with your broker credentials
```

Edit `supported_stock_list` to set which NSE stocks the bot should trade between.

### 3. Run the bot

```bash
python -m auto_trade_bot
```

### 4. Backtest first (recommended!)

Test the strategy on 1 year of real NSE historical data before going live:

```bash
# Basic backtest (reads supported_stock_list automatically)
python -m auto_trade_bot backtest

# Custom parameters
python -m auto_trade_bot backtest \
  --stocks RELIANCE,TCS,INFY,HDFCBANK,ICICIBANK \
  --start 2024-01-01 --end 2024-12-31 \
  --capital 100000 \
  --scout-margin 0.5 \
  --save
```

Example output:
```
============================================================
  BACKTEST RESULTS
============================================================
  Initial capital      :    ₹1,00,000.00
  Final portfolio      :    ₹1,18,432.50
  Total return         :       +18.43%
  Total trades         :           47
  Win rate             :        63.8%
  Avg trade P&L        :        +0.39%
  Max drawdown         :        -8.21%

  Buy-and-hold comparison:
        RELIANCE:    ₹1,09,200.00  (+9.20%)
             TCS:    ₹1,04,100.00  (+4.10%)
            INFY:     ₹98,700.00   (-1.30%)
============================================================
```

---

## Configuration Reference (`user.cfg`)

| Setting | Default | Description |
|---|---|---|
| `broker` | `angel_one` | Broker: `angel_one`, `zerodha`, `upstox`, `dhan`, `fyers` |
| `exchange` | `NSE` | `NSE` or `BSE` |
| `trade_type` | `intraday` | `intraday` (auto square-off) or `delivery` |
| `scout_margin` | `0.5` | Min % gain needed to trigger a trade |
| `scout_sleep_time` | `10` | Seconds between each scout cycle |
| `sell_timeout` | `30` | Seconds to wait for sell order to fill |
| `buy_timeout` | `30` | Seconds to wait for buy order to fill |
| `max_loss_to_carry_delivery_pct` | `2.0` | If intraday loss < this %, convert to delivery near close instead of forced square-off |

---

## Smart Square-Off (Intraday)

Near market close (default: 12 minutes before), the bot automatically decides:

- **Profit** → Square off and take the gain ✅
- **Small loss** (within `max_loss_to_carry_delivery_pct`) → Convert to **delivery** and hold overnight instead of taking a forced loss
- **Large loss** → Cut the loss and square off immediately

---

## Project Structure

```
auto_trade_bot/
├── auto_trade_bot/
│   ├── auto_trader.py          ← Core ratio logic
│   ├── backtest.py             ← Backtesting engine
│   ├── brokers/
│   │   ├── angel_one_broker.py
│   │   ├── zerodha_broker.py
│   │   ├── upstox_broker.py
│   │   ├── dhan_broker.py
│   │   └── fyers_broker.py
│   ├── strategies/
│   │   └── default_strategy.py
│   ├── config.py
│   ├── database.py
│   └── stock_trading.py
├── supported_stock_list
├── user.cfg.example
└── requirements.txt
```

---

## Important Notes

- **Market hours**: Bot is idle outside 9:15 AM – 3:30 PM IST and on weekends/holidays
- **Circuit breakers**: Bot skips stocks at upper/lower circuit limits automatically
- **This is not financial advice.** Always backtest before going live. Start with small capital.
