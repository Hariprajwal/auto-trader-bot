import logging
import os
from datetime import datetime

# ─────────────────────────────────────────────────────────────────────────────
#  auto_trade_bot
#  Author  : K R HARI PRAJWAL
#  License : MIT
# ─────────────────────────────────────────────────────────────────────────────

BANNER = """
╔══════════════════════════════════════════════════════════════╗
║          auto_trade_bot  —  Indian Stock Market Bot          ║
║                                                              ║
║  Author  : K R HARI PRAJWAL                                  ║
║  Version : 1.0.0                                             ║
║  License : MIT                                               ║
╚══════════════════════════════════════════════════════════════╝
"""


class Logger:
    def __init__(self, log_file="logs/auto_trade_bot.log"):
        os.makedirs("logs", exist_ok=True)
        self.logger = logging.getLogger("auto_trade_bot")
        self.logger.setLevel(logging.DEBUG)

        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

        # File handler — DEBUG and above
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)

        # Console handler — INFO and above
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(fmt)

        if not self.logger.handlers:
            self.logger.addHandler(fh)
            self.logger.addHandler(ch)

    def banner(self):
        """Print the startup banner."""
        print(BANNER)

    def info(self, msg):
        self.logger.info(msg)

    def warning(self, msg):
        self.logger.warning(msg)

    def error(self, msg):
        self.logger.error(msg)

    def debug(self, msg):
        self.logger.debug(msg)
