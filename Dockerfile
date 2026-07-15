# syntax=docker/dockerfile:1
FROM python:3.11-slim

# ── Metadata ──────────────────────────────────────────────────────────────────
LABEL maintainer="K R HARI PRAJWAL"
LABEL description="auto_trade_bot — Indian Stock Market Automated Trading Bot"
LABEL version="1.0.0"

# ── System deps ───────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Install Python dependencies ───────────────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source code ──────────────────────────────────────────────────────────
COPY auto_trade_bot/ ./auto_trade_bot/
COPY supported_stock_list .

# ── Data and log directories ──────────────────────────────────────────────────
RUN mkdir -p /app/data /app/logs /app/backtest_results

# ── Volumes (persist DB, logs, trade history across restarts) ─────────────────
VOLUME ["/app/data", "/app/logs", "/app/backtest_results"]

# ── Environment variable overrides (alternative to user.cfg) ─────────────────
# These can be set in docker-compose.yml or via -e flags
ENV BROKER=""
ENV BROKER_API_KEY=""
ENV BROKER_API_SECRET=""
ENV BROKER_CLIENT_ID=""
ENV BROKER_PASSWORD=""
ENV BROKER_TOTP_SECRET=""
ENV BROKER_ACCESS_TOKEN=""
ENV EXCHANGE="NSE"
ENV TRADE_TYPE="INTRADAY"
ENV SCOUT_MARGIN="0.3"
ENV SCOUT_SLEEP_TIME="10"
ENV STRATEGY="default"

# ── Health check ──────────────────────────────────────────────────────────────
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import auto_trade_bot; print('OK')" || exit 1

# ── Entry point ───────────────────────────────────────────────────────────────
CMD ["python", "-m", "auto_trade_bot"]
