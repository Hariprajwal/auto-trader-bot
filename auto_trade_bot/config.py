# ─────────────────────────────────────────────────────────────────────────────
#  auto_trade_bot — Configuration
#  Author  : K R HARI PRAJWAL
#  License : MIT
#
#  Indian Brokerage Fee Reference (used to calibrate scout_margin):
#
#  INTRADAY (MIS) — round-trip cost breakdown:
#    Brokerage       ₹20 flat/order  → ~0.04% each side on ₹50k trade
#    STT             0.025% on SELL side only
#    Exchange (NSE)  0.00345% per side
#    GST (18%)       on brokerage + exchange charges
#    SEBI            0.0001% per side
#    Stamp duty      0.003% on BUY side
#    ─────────────────────────────────────────────
#    Total round-trip ≈ 0.13%
#    Recommended scout_margin: 0.3%  (covers fees + ~0.17% profit target)
#
#  DELIVERY (CNC) — round-trip cost breakdown:
#    Brokerage       ₹20 flat/order  → ~0.04% each side
#    STT             0.1% on BOTH buy AND sell = 0.2% total  ← big cost!
#    Exchange (NSE)  0.00345% per side
#    GST (18%)       on brokerage + exchange charges
#    SEBI            0.0001% per side
#    Stamp duty      0.015% on BUY side
#    ─────────────────────────────────────────────
#    Total round-trip ≈ 0.32%
#    Recommended scout_margin: 0.8%  (covers fees + ~0.48% profit target)
# ─────────────────────────────────────────────────────────────────────────────
import configparser
import os

CFG_FL_NAME = "user.cfg"
USER_CFG_SECTION = "auto_trade_bot_config"


class Config:
    def __init__(self):
        config = configparser.ConfigParser()
        config["DEFAULT"] = {
            "broker": "angel_one",
            "exchange": "NSE",
            "trade_type": "intraday",
            "bridge": "INR",
            "use_margin": "yes",
            "scout_multiplier": "5",
            # 0.3 for intraday (round-trip fee ~0.13%), 0.8 for delivery (round-trip fee ~0.32%)
            "scout_margin": "0.3",
            "scout_sleep_time": "10",
            "hour_to_keep_scout_history": "1",
            "strategy": "default",
            "sell_timeout": "30",
            "buy_timeout": "30",
            "market_open_time": "09:15",
            "market_close_time": "15:20",
            # Loss threshold: if unrealised loss > this %, don't convert to delivery, just cut loss
            "max_loss_to_carry_delivery_pct": "2.0",
        }

        if not os.path.exists(CFG_FL_NAME):
            print("No configuration file (user.cfg) found! See README. Assuming defaults...")
            config[USER_CFG_SECTION] = {}
        else:
            config.read(CFG_FL_NAME)

        # --- Broker ---
        self.BROKER = os.environ.get("BROKER") or config.get(USER_CFG_SECTION, "broker")
        self.BROKER_API_KEY = os.environ.get("BROKER_API_KEY") or config.get(USER_CFG_SECTION, "api_key", fallback="")
        self.BROKER_API_SECRET = os.environ.get("BROKER_API_SECRET") or config.get(USER_CFG_SECTION, "api_secret", fallback="")
        self.BROKER_CLIENT_ID = os.environ.get("BROKER_CLIENT_ID") or config.get(USER_CFG_SECTION, "client_id", fallback="")
        self.BROKER_PASSWORD = os.environ.get("BROKER_PASSWORD") or config.get(USER_CFG_SECTION, "password", fallback="")
        self.BROKER_TOTP_SECRET = os.environ.get("BROKER_TOTP_SECRET") or config.get(USER_CFG_SECTION, "totp_secret", fallback="")
        self.BROKER_ACCESS_TOKEN = os.environ.get("BROKER_ACCESS_TOKEN") or config.get(USER_CFG_SECTION, "access_token", fallback="")
        self.BROKER_REDIRECT_URI = os.environ.get("BROKER_REDIRECT_URI") or config.get(USER_CFG_SECTION, "redirect_uri", fallback="")

        # --- Trading ---
        self.EXCHANGE = (os.environ.get("EXCHANGE") or config.get(USER_CFG_SECTION, "exchange")).upper()
        self.TRADE_TYPE = (os.environ.get("TRADE_TYPE") or config.get(USER_CFG_SECTION, "trade_type")).upper()
        self.BRIDGE_SYMBOL = "INR"

        # --- Scout ---
        self.SCOUT_MULTIPLIER = float(os.environ.get("SCOUT_MULTIPLIER") or config.get(USER_CFG_SECTION, "scout_multiplier"))
        self.SCOUT_SLEEP_TIME = int(os.environ.get("SCOUT_SLEEP_TIME") or config.get(USER_CFG_SECTION, "scout_sleep_time"))
        self.SCOUT_MARGIN = float(os.environ.get("SCOUT_MARGIN") or config.get(USER_CFG_SECTION, "scout_margin"))
        self.USE_MARGIN = os.environ.get("USE_MARGIN") or config.get(USER_CFG_SECTION, "use_margin")
        self.SCOUT_HISTORY_PRUNE_TIME = float(os.environ.get("HOURS_TO_KEEP_SCOUTING_HISTORY") or config.get(USER_CFG_SECTION, "hour_to_keep_scout_history"))

        # --- Market hours ---
        self.MARKET_OPEN_TIME = os.environ.get("MARKET_OPEN_TIME") or config.get(USER_CFG_SECTION, "market_open_time")
        self.MARKET_CLOSE_TIME = os.environ.get("MARKET_CLOSE_TIME") or config.get(USER_CFG_SECTION, "market_close_time")

        # --- Order timeouts ---
        self.SELL_TIMEOUT = int(os.environ.get("SELL_TIMEOUT") or config.get(USER_CFG_SECTION, "sell_timeout"))
        self.BUY_TIMEOUT = int(os.environ.get("BUY_TIMEOUT") or config.get(USER_CFG_SECTION, "buy_timeout"))

        # --- Smart square-off ---
        self.MAX_LOSS_TO_CARRY_DELIVERY_PCT = float(
            os.environ.get("MAX_LOSS_TO_CARRY_DELIVERY_PCT")
            or config.get(USER_CFG_SECTION, "max_loss_to_carry_delivery_pct")
        )

        # --- Strategy ---
        self.STRATEGY = os.environ.get("STRATEGY") or config.get(USER_CFG_SECTION, "strategy")
        self.CURRENT_STOCK_SYMBOL = os.environ.get("CURRENT_STOCK_SYMBOL") or config.get(USER_CFG_SECTION, "current_stock", fallback="")

        # --- Supported stocks ---
        supported_stock_list = [
            s.strip() for s in os.environ.get("SUPPORTED_STOCK_LIST", "").split() if s.strip()
        ]
        if not supported_stock_list and os.path.exists("supported_stock_list"):
            with open("supported_stock_list") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or line in supported_stock_list:
                        continue
                    supported_stock_list.append(line)
        self.SUPPORTED_STOCK_LIST = supported_stock_list
