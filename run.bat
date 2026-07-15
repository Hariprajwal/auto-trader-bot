@echo off
REM ============================================================
REM  auto_trade_bot — Easy Windows Startup Script
REM  Author: K R HARI PRAJWAL
REM ============================================================

echo.
echo  auto_trade_bot - Indian Stock Market Bot
echo  Author: K R HARI PRAJWAL
echo.

IF NOT EXIST ".venv" (
    echo [SETUP] Creating virtual environment...
    python -m venv .venv
    echo [SETUP] Installing dependencies...
    .venv\Scripts\pip install -r requirements.txt
)

IF NOT EXIST "user.cfg" (
    echo [ERROR] user.cfg not found!
    echo [ERROR] Copy user.cfg.example to user.cfg and fill in your broker credentials.
    pause
    exit /b 1
)

IF "%1"=="backtest" (
    echo [BACKTEST] Running backtest...
    .venv\Scripts\python -m auto_trade_bot backtest %2 %3 %4 %5 %6 %7 %8 %9
) ELSE (
    echo [START] Starting bot...
    .venv\Scripts\python -m auto_trade_bot
)

pause
