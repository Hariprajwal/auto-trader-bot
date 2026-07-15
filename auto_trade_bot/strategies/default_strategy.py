import random
import sys
from datetime import datetime

from auto_trade_bot.auto_trader import AutoTrader


class Strategy(AutoTrader):
    def initialize(self):
        super().initialize()
        self.initialize_current_stock()

    def scout(self):
        """
        Main scouting loop — runs every SCOUT_SLEEP_TIME seconds.
        """
        # Market hours guard
        if not self.is_market_open():
            print(
                f"{datetime.now().strftime('%H:%M:%S')} — Market is CLOSED. Bot is idle.",
                end="\r",
            )
            return

        current_stock = self.db.get_current_stock()
        if current_stock is None:
            self.logger.warning("No current stock set. Bot idle.")
            return

        print(
            f"{datetime.now()} - Scouting... Current stock: {current_stock.symbol} "
            f"[{self.config.TRADE_TYPE}]  ",
            end="\r",
        )

        current_price = self.get_stock_price(current_stock.symbol)
        if current_price is None:
            self.logger.info(f"Skipping scout — can't get price for {current_stock.symbol}")
            return

        # Near market close — check if we need to act
        if self.is_near_close(threshold_minutes=12):
            qty = self.broker.get_stock_quantity(current_stock.symbol)
            if qty > 0 and self.config.TRADE_TYPE == "INTRADAY":
                self.logger.info(f"Near market close ({self.minutes_to_close():.0f} min remaining). Checking square-off...")
                decision = self._decide_trade_type_for_squareoff(current_stock.symbol, qty, current_price)
                if decision == "INTRADAY":
                    self.logger.info(f"Squaring off {current_stock.symbol} before close")
                    self.broker.sell_stock(
                        symbol=current_stock.symbol,
                        quantity=qty,
                        price=current_price,
                        exchange=self.config.EXCHANGE,
                        order_type="MARKET",
                        trade_type="INTRADAY",
                    )
                else:
                    self.logger.info(f"Converting {current_stock.symbol} to delivery — holding overnight")
                return

        self._jump_to_best_stock(current_stock, current_price)

    def initialize_current_stock(self):
        if self.db.get_current_stock() is None:
            symbol = self.config.CURRENT_STOCK_SYMBOL
            if not symbol:
                if not self.config.SUPPORTED_STOCK_LIST:
                    self.logger.error("supported_stock_list is empty! Add at least 2 stock symbols.")
                    import sys; sys.exit(1)
                symbol = random.choice(self.config.SUPPORTED_STOCK_LIST)

            if symbol not in self.config.SUPPORTED_STOCK_LIST:
                import sys; sys.exit(f"ERROR: '{symbol}' is not in supported_stock_list!")

            self.logger.info(f"Setting initial stock: {symbol} [{self.config.TRADE_TYPE} mode]")
            self.db.set_current_stock(symbol)

            # Only buy the initial stock if the market is currently open
            if not self.is_market_open():
                self.logger.info(
                    "Market is CLOSED. Will buy initial position when market opens. "
                    "Bot is running in delivery mode — holding position is fine."
                )
                return

            current_stock = self.db.get_current_stock()
            price = self.get_stock_price(current_stock.symbol)
            inr_balance = self.broker.get_inr_balance()

            if price and inr_balance and inr_balance > 0:
                qty = self.get_buy_quantity(current_stock.symbol, inr_balance, price)
                if qty > 0:
                    order = self.broker.buy_stock(
                        symbol=current_stock.symbol,
                        quantity=qty,
                        price=price,
                        exchange=self.config.EXCHANGE,
                        order_type="LIMIT",
                        trade_type=self.config.TRADE_TYPE,
                    )
                    if order:
                        self.update_trade_threshold(current_stock, order.avg_price)
                        self.logger.info(
                            f"Initial position: bought {qty} {current_stock.symbol} "
                            f"@ ₹{order.avg_price:.2f}. Ready to trade!"
                        )
                    else:
                        self.logger.warning(f"Initial buy order for {current_stock.symbol} failed.")
                else:
                    self.logger.warning(
                        f"Insufficient balance ₹{inr_balance:.2f} to buy "
                        f"{current_stock.symbol} @ ₹{price:.2f}"
                    )
            else:
                self.logger.warning("Cannot buy initial stock — no balance or no price available.")

