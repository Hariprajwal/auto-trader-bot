"""
Backtesting Engine for auto_trade_bot
======================================
Uses yfinance to download real NSE/BSE historical data (free, open source).

NSE symbols on yfinance: append ".NS"  → e.g. "RELIANCE.NS", "TCS.NS"
BSE symbols on yfinance: append ".BO"  → e.g. "RELIANCE.BO"

Run:
    python -m auto_trade_bot backtest

Or with custom params:
    python -m auto_trade_bot backtest --start 2024-01-01 --end 2024-12-31 \\
        --capital 100000 --scout-margin 0.5 --stocks RELIANCE,TCS,INFY
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

try:
    import yfinance as yf
    import pandas as pd
except ImportError:
    print("ERROR: yfinance and pandas are required for backtesting.")
    print("Install: pip install yfinance pandas")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────
# Data Fetching
# ─────────────────────────────────────────────────────────────

def fetch_historical_data(
    symbols: List[str],
    exchange: str = "NSE",
    start: str = None,
    end: str = None,
    interval: str = "1d",
) -> Dict[str, pd.DataFrame]:
    """
    Download historical OHLCV data from Yahoo Finance for all symbols.

    exchange: "NSE" → appends .NS | "BSE" → appends .BO
    interval: "1d" (daily), "1h" (hourly), "5m" (5-minute, max 60 days)
    """
    suffix = ".NS" if exchange.upper() == "NSE" else ".BO"
    data = {}

    print(f"\nDownloading {exchange} historical data ({interval})...")
    for symbol in symbols:
        yf_symbol = symbol + suffix
        try:
            df = yf.download(
                yf_symbol,
                start=start,
                end=end,
                interval=interval,
                progress=False,
                auto_adjust=True,
            )
            if df.empty:
                print(f"  ⚠  No data for {symbol} ({yf_symbol}) — skipping")
                continue
            # Keep only Close price for the ratio bot
            df = df[["Close"]].rename(columns={"Close": symbol})
            data[symbol] = df
            print(f"  ✓  {symbol}: {len(df)} rows ({df.index[0].date()} → {df.index[-1].date()})")
        except Exception as e:
            print(f"  ✗  {symbol}: Error — {e}")

    return data


def align_data(data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Merge all symbol dataframes on the datetime index.
    Fills forward for missing values (e.g. holidays), drops rows where ALL are NaN.
    """
    if not data:
        return pd.DataFrame()
    combined = pd.concat(data.values(), axis=1)
    combined.columns = list(data.keys())
    combined = combined.ffill().dropna(how="all")
    return combined


# ─────────────────────────────────────────────────────────────
# Ratio Engine (mirrors auto_trader logic)
# ─────────────────────────────────────────────────────────────

def compute_ratios(prices: pd.Series, current_stock: str, fee_pct: float, scout_margin: float, scout_multiplier: float, use_margin: bool) -> Dict[str, float]:
    """
    Given a row of prices, compute the ratio score for each stock
    relative to the currently held stock. Same math as auto_trader._get_ratios().
    """
    ratios = {}
    current_price = prices.get(current_stock)
    if not current_price or current_price <= 0:
        return ratios

    for symbol, price in prices.items():
        if symbol == current_stock or not price or price <= 0:
            continue
        ratio = current_price / price
        transaction_fee = fee_pct * 2  # buy + sell

        if use_margin:
            # Ratio score must exceed scout_margin %
            score = (1 - transaction_fee) * ratio - 1 - scout_margin / 100
        else:
            score = (ratio - transaction_fee * scout_multiplier * ratio)
        ratios[symbol] = score

    return ratios


# ─────────────────────────────────────────────────────────────
# Backtesting Simulation
# ─────────────────────────────────────────────────────────────

class BacktestResult:
    def __init__(self):
        self.trades: List[dict] = []
        self.portfolio_values: List[dict] = []
        self.initial_capital = 0.0
        self.final_value = 0.0

    @property
    def total_trades(self):
        return len(self.trades)

    @property
    def total_return_pct(self):
        if self.initial_capital == 0:
            return 0.0
        return ((self.final_value - self.initial_capital) / self.initial_capital) * 100

    @property
    def winning_trades(self):
        return [t for t in self.trades if t.get("pnl_pct", 0) > 0]

    @property
    def losing_trades(self):
        return [t for t in self.trades if t.get("pnl_pct", 0) <= 0]

    @property
    def win_rate(self):
        if not self.trades:
            return 0.0
        return len(self.winning_trades) / len(self.trades) * 100

    @property
    def max_drawdown(self):
        if not self.portfolio_values:
            return 0.0
        values = [v["portfolio_value"] for v in self.portfolio_values]
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak * 100
            if dd > max_dd:
                max_dd = dd
        return max_dd

    @property
    def avg_trade_pnl_pct(self):
        if not self.trades:
            return 0.0
        return sum(t.get("pnl_pct", 0) for t in self.trades) / len(self.trades)


def run_simulation(
    price_df: pd.DataFrame,
    symbols: List[str],
    initial_capital: float = 100000.0,
    scout_margin: float = 0.5,
    scout_multiplier: float = 5.0,
    fee_pct: float = 0.0005,
    use_margin: bool = True,
    initial_stock: str = None,
) -> BacktestResult:
    """
    Core backtesting simulation.
    Walks through each price row (each candle/day) and applies the ratio trading logic.
    """
    result = BacktestResult()
    result.initial_capital = initial_capital

    # State
    inr_balance = 0.0
    current_stock = initial_stock or symbols[0]
    current_price = price_df[current_stock].iloc[0]
    shares_held = int(initial_capital / current_price) if current_price > 0 else 0
    entry_price = current_price
    inr_balance = initial_capital - (shares_held * current_price)

    # Initialize pair ratios (buy-and-hold baseline for each pair)
    # ratio[A][B] = price(A)/price(B) at time of last trade
    pair_ratios: Dict[str, Dict[str, float]] = {}
    first_row = price_df.iloc[0]
    for s1 in symbols:
        pair_ratios[s1] = {}
        for s2 in symbols:
            if s1 != s2 and first_row.get(s1) and first_row.get(s2):
                pair_ratios[s1][s2] = first_row[s1] / first_row[s2]

    result.initial_capital = initial_capital

    print(f"\nSimulation start: ₹{initial_capital:,.0f} | Initial stock: {current_stock} ({shares_held} shares @ ₹{current_price:.2f})")

    for i, (timestamp, row) in enumerate(price_df.iterrows()):
        prices = row.to_dict()

        # Skip if current stock has no price this candle
        cp = prices.get(current_stock)
        if not cp or cp <= 0:
            continue

        # Portfolio value this candle
        portfolio_value = (shares_held * cp) + inr_balance
        result.portfolio_values.append({
            "datetime": str(timestamp),
            "stock": current_stock,
            "price": cp,
            "shares": shares_held,
            "inr_balance": inr_balance,
            "portfolio_value": portfolio_value,
        })

        # Scout: compute ratios for all other stocks
        best_symbol = None
        best_score = 0.0

        for symbol in symbols:
            if symbol == current_stock:
                continue
            other_price = prices.get(symbol)
            if not other_price or other_price <= 0:
                continue

            # Get the stored ratio for this pair
            stored_ratio = pair_ratios.get(current_stock, {}).get(symbol)
            if stored_ratio is None:
                continue

            current_ratio = cp / other_price
            transaction_fee = fee_pct * 2

            if use_margin:
                score = (1 - transaction_fee) * current_ratio / stored_ratio - 1 - scout_margin / 100
            else:
                score = (current_ratio - transaction_fee * scout_multiplier * current_ratio) - stored_ratio

            if score > best_score:
                best_score = score
                best_symbol = symbol

        # Execute trade if a better stock is found
        if best_symbol and shares_held > 0:
            to_price = prices.get(best_symbol)
            if not to_price or to_price <= 0:
                continue

            # --- SELL current stock ---
            sell_value = shares_held * cp * (1 - fee_pct)
            pnl_inr = sell_value - (shares_held * entry_price)
            pnl_pct = (pnl_inr / (shares_held * entry_price)) * 100 if entry_price > 0 else 0

            trade_record = {
                "datetime": str(timestamp),
                "from_stock": current_stock,
                "from_price": cp,
                "from_shares": shares_held,
                "to_stock": best_symbol,
                "to_price": to_price,
                "pnl_inr": round(pnl_inr, 2),
                "pnl_pct": round(pnl_pct, 2),
                "score": round(best_score, 6),
            }

            # --- BUY target stock ---
            inr_after_sell = sell_value
            buy_shares = int(inr_after_sell / (to_price * (1 + fee_pct)))
            inr_spent = buy_shares * to_price * (1 + fee_pct)
            inr_balance = inr_after_sell - inr_spent

            # Update pair ratios — reset the ratio for all pairs involving the new stock
            for s in symbols:
                if s != best_symbol and prices.get(s):
                    pair_ratios.setdefault(best_symbol, {})[s] = to_price / prices[s]
                    pair_ratios.setdefault(s, {})[best_symbol] = prices[s] / to_price

            trade_record["to_shares"] = buy_shares
            trade_record["inr_balance_after"] = round(inr_balance, 2)
            result.trades.append(trade_record)

            # Transition
            current_stock = best_symbol
            shares_held = buy_shares
            entry_price = to_price

    # Final value
    final_price = price_df[current_stock].iloc[-1] if current_stock in price_df.columns else 0
    result.final_value = (shares_held * final_price) + inr_balance

    return result


# ─────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────

def buy_and_hold_return(price_df: pd.DataFrame, symbol: str, capital: float) -> float:
    """Calculate what you'd have earned just holding one stock the whole time."""
    first_price = price_df[symbol].dropna().iloc[0]
    last_price = price_df[symbol].dropna().iloc[-1]
    shares = int(capital / first_price)
    return shares * last_price + (capital - shares * first_price)


def print_report(result: BacktestResult, symbols: List[str], price_df: pd.DataFrame, capital: float):
    print("\n" + "=" * 60)
    print("  BACKTEST RESULTS")
    print("=" * 60)
    print(f"  Initial capital      : ₹{result.initial_capital:>12,.2f}")
    print(f"  Final portfolio      : ₹{result.final_value:>12,.2f}")
    print(f"  Total return         : {result.total_return_pct:>+.2f}%")
    print(f"  Total trades         : {result.total_trades}")
    print(f"  Win rate             : {result.win_rate:.1f}%")
    print(f"  Avg trade P&L        : {result.avg_trade_pnl_pct:>+.2f}%")
    print(f"  Max drawdown         : -{result.max_drawdown:.2f}%")
    print()
    print("  Buy-and-hold comparison:")
    for symbol in symbols:
        if symbol in price_df.columns:
            bh = buy_and_hold_return(price_df, symbol, capital)
            bh_pct = ((bh - capital) / capital) * 100
            tag = " ← you beat this!" if result.final_value > bh else ""
            print(f"    {symbol:>14}: ₹{bh:>12,.2f}  ({bh_pct:>+.2f}%){tag}")
    print()

    if result.trades:
        print(f"  Last 5 trades:")
        for t in result.trades[-5:]:
            print(
                f"    [{t['datetime'][:10]}] {t['from_stock']:>12} → {t['to_stock']:<12}"
                f"  P&L: {t['pnl_pct']:>+.2f}%"
            )
    print("=" * 60)


def save_results(result: BacktestResult, output_dir: str = "backtest_results"):
    os.makedirs(output_dir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    trades_file = os.path.join(output_dir, f"trades_{ts}.json")
    with open(trades_file, "w") as f:
        json.dump(result.trades, f, indent=4)

    portfolio_file = os.path.join(output_dir, f"portfolio_{ts}.json")
    with open(portfolio_file, "w") as f:
        json.dump(result.portfolio_values, f, indent=4)

    summary = {
        "timestamp": ts,
        "initial_capital": result.initial_capital,
        "final_value": result.final_value,
        "total_return_pct": round(result.total_return_pct, 4),
        "total_trades": result.total_trades,
        "win_rate": round(result.win_rate, 2),
        "avg_trade_pnl_pct": round(result.avg_trade_pnl_pct, 4),
        "max_drawdown_pct": round(result.max_drawdown, 4),
        "winning_trades": len(result.winning_trades),
        "losing_trades": len(result.losing_trades),
    }
    summary_file = os.path.join(output_dir, f"summary_{ts}.json")
    with open(summary_file, "w") as f:
        json.dump(summary, f, indent=4)

    print(f"\n  Results saved to: {output_dir}/")
    print(f"    - {os.path.basename(trades_file)}")
    print(f"    - {os.path.basename(portfolio_file)}")
    print(f"    - {os.path.basename(summary_file)}")


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────

def run_backtest():
    parser = argparse.ArgumentParser(description="auto_trade_bot Backtester (NSE/BSE)")
    parser.add_argument("--stocks", type=str, default=None,
                        help="Comma-separated stock list, e.g. RELIANCE,TCS,INFY (default: reads supported_stock_list file)")
    parser.add_argument("--start", type=str, default=None,
                        help="Start date YYYY-MM-DD (default: 1 year ago)")
    parser.add_argument("--end", type=str, default=None,
                        help="End date YYYY-MM-DD (default: today)")
    parser.add_argument("--capital", type=float, default=100000.0,
                        help="Starting capital in INR (default: 100000)")
    parser.add_argument("--exchange", type=str, default="NSE",
                        help="NSE or BSE (default: NSE)")
    parser.add_argument("--interval", type=str, default="1d",
                        help="Data interval: 1d (daily), 1h (hourly), 5m (5-min, max 60 days). Default: 1d")
    parser.add_argument("--scout-margin", type=float, default=0.5,
                        help="Scout margin %% (default: 0.5)")
    parser.add_argument("--scout-multiplier", type=float, default=5.0,
                        help="Scout multiplier (default: 5.0)")
    parser.add_argument("--fee", type=float, default=0.0005,
                        help="Fee per trade as decimal (default: 0.0005 = 0.05%%)")
    parser.add_argument("--no-margin", action="store_true",
                        help="Use simple ratio mode (no margin mode)")
    parser.add_argument("--initial-stock", type=str, default=None,
                        help="Stock to start holding (default: first in list)")
    parser.add_argument("--save", action="store_true",
                        help="Save results to backtest_results/ folder")

    # Remove 'backtest' from sys.argv before parsing
    args = parser.parse_args([a for a in sys.argv[2:] if a != "backtest"])

    # --- Resolve stock list ---
    if args.stocks:
        symbols = [s.strip().upper() for s in args.stocks.split(",") if s.strip()]
    elif os.path.exists("supported_stock_list"):
        symbols = []
        with open("supported_stock_list") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    symbols.append(line.upper())
    else:
        print("ERROR: No stocks specified. Use --stocks or create a supported_stock_list file.")
        sys.exit(1)

    if len(symbols) < 2:
        print("ERROR: Need at least 2 stocks to trade between.")
        sys.exit(1)

    # --- Dates ---
    end_date = args.end or datetime.now().strftime("%Y-%m-%d")
    start_date = args.start or (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")

    print(f"\n{'='*60}")
    print(f"  auto_trade_bot — Backtest")
    print(f"{'='*60}")
    print(f"  Stocks       : {', '.join(symbols)}")
    print(f"  Period       : {start_date} → {end_date}")
    print(f"  Interval     : {args.interval}")
    print(f"  Capital      : ₹{args.capital:,.0f}")
    print(f"  Exchange     : {args.exchange}")
    print(f"  Scout margin : {args.scout_margin}%")
    print(f"  Fee/side     : {args.fee*100:.3f}%")

    # --- Download data ---
    raw_data = fetch_historical_data(
        symbols=symbols,
        exchange=args.exchange,
        start=start_date,
        end=end_date,
        interval=args.interval,
    )

    if len(raw_data) < 2:
        print("\nERROR: Not enough data downloaded. Check symbols and date range.")
        sys.exit(1)

    # Filter to only symbols with data
    available_symbols = list(raw_data.keys())
    price_df = align_data(raw_data)

    if price_df.empty:
        print("\nERROR: Price data is empty after alignment.")
        sys.exit(1)

    initial_stock = args.initial_stock or available_symbols[0]
    if initial_stock not in available_symbols:
        print(f"WARNING: --initial-stock '{initial_stock}' not in available data. Using {available_symbols[0]}")
        initial_stock = available_symbols[0]

    # --- Run simulation ---
    result = run_simulation(
        price_df=price_df,
        symbols=available_symbols,
        initial_capital=args.capital,
        scout_margin=args.scout_margin,
        scout_multiplier=args.scout_multiplier,
        fee_pct=args.fee,
        use_margin=not args.no_margin,
        initial_stock=initial_stock,
    )

    # --- Report ---
    print_report(result, available_symbols, price_df, args.capital)

    if args.save:
        save_results(result)
