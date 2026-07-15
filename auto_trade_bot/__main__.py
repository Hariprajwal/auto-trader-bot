import sys

if __name__ == "__main__":
    # Check if user wants to run backtesting
    if len(sys.argv) > 1 and sys.argv[1] == "backtest":
        from auto_trade_bot.backtest import run_backtest
        run_backtest()
    else:
        from auto_trade_bot.stock_trading import main
        main()
