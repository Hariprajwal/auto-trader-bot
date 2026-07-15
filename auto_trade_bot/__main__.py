"""
auto_trade_bot entry point.
Run with:  python -m auto_trade_bot
Backtest:  python -m auto_trade_bot backtest [--options]

Author  : K R HARI PRAJWAL
License : MIT
"""
import sys


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        from auto_trade_bot.backtest import run_backtest
        run_backtest()
    else:
        from auto_trade_bot.stock_trading import main as run_bot
        run_bot()


if __name__ == "__main__":
    main()
