import json
import math
import os
import threading
import time
from datetime import datetime, time as dtime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from .brokers import BaseBroker, Order
from .config import Config
from .database import Database
from .logger import Logger
from .models import Stock, StockValue, Pair
from .models.stock_value import Interval


class AutoTrader:
    def __init__(
        self,
        broker: BaseBroker,
        database: Database,
        logger: Logger,
        config: Config,
    ):
        self.broker = broker
        self.db = database
        self.logger = logger
        self.config = config

    def initialize(self):
        self.initialize_trade_thresholds()

    # -------------------------------------------------------------------------
    # Market Hours
    # -------------------------------------------------------------------------

    def is_market_open(self) -> bool:
        """
        Returns True only if current time is within NSE/BSE trading hours
        on a weekday. Skips Saturdays, Sundays, and times outside 9:15 AM – 3:30 PM IST.
        """
        now = datetime.now()
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False

        open_h, open_m = map(int, self.config.MARKET_OPEN_TIME.split(":"))
        close_h, close_m = map(int, self.config.MARKET_CLOSE_TIME.split(":"))
        open_time = dtime(open_h, open_m)
        close_time = dtime(close_h, close_m)
        current_time = now.time()

        return open_time <= current_time <= close_time

    def minutes_to_close(self) -> float:
        """Returns how many minutes remain until market close."""
        now = datetime.now()
        close_h, close_m = map(int, self.config.MARKET_CLOSE_TIME.split(":"))
        close_time = dtime(close_h, close_m)
        current_time = now.time()
        current_minutes = current_time.hour * 60 + current_time.minute
        close_minutes = close_time.hour * 60 + close_time.minute
        return max(0.0, close_minutes - current_minutes)

    def is_near_close(self, threshold_minutes: float = 10.0) -> bool:
        """Returns True if we are within `threshold_minutes` of market close."""
        return self.minutes_to_close() <= threshold_minutes

    # -------------------------------------------------------------------------
    # Price & Quantity helpers
    # -------------------------------------------------------------------------

    def get_stock_price(self, symbol: str) -> Optional[float]:
        """Get LTP for a stock. Tries NSE first, then BSE if config says both."""
        price = self.broker.get_stock_price(symbol, exchange=self.config.EXCHANGE)
        if price is None and self.config.EXCHANGE == "BOTH":
            price = self.broker.get_stock_price(symbol, exchange="BSE")
        return price

    def get_buy_quantity(self, symbol: str, inr_balance: float, price: float) -> int:
        """
        Calculate how many whole shares we can buy with the available INR balance.
        Always rounds DOWN to avoid exceeding balance.
        Minimum 1 share.
        """
        if price <= 0:
            return 0
        return max(0, math.floor(inr_balance / price))

    # -------------------------------------------------------------------------
    # Smart Square-Off Logic
    # -------------------------------------------------------------------------

    def _decide_trade_type_for_squareoff(self, symbol: str, quantity: int, buy_price: float) -> str:
        """
        Called near market close when we are still holding a stock.
        Decides whether to:
          1. SQUARE OFF (sell intraday) — if loss is small OR stock is at a circuit
          2. CONVERT TO DELIVERY (CNC) — hold overnight if loss is acceptable
        
        Returns: "INTRADAY" to square off now, or "DELIVERY" to convert and hold.
        """
        if self.config.TRADE_TYPE != "INTRADAY":
            return self.config.TRADE_TYPE

        current_price = self.get_stock_price(symbol)
        if current_price is None:
            self.logger.warning(f"Smart square-off: Can't get price for {symbol}, defaulting to square off")
            return "INTRADAY"

        # Calculate unrealised P&L %
        pnl_pct = ((current_price - buy_price) / buy_price) * 100

        max_carry_loss = -abs(self.config.MAX_LOSS_TO_CARRY_DELIVERY_PCT)

        if pnl_pct >= 0:
            # In profit — square off and take the win
            self.logger.info(f"Smart square-off: {symbol} up {pnl_pct:.2f}% — squaring off to take profit")
            return "INTRADAY"
        elif pnl_pct >= max_carry_loss:
            # Small loss, within carry limit — convert to delivery and hold overnight
            self.logger.info(
                f"Smart square-off: {symbol} down {pnl_pct:.2f}% (within {max_carry_loss}% limit) "
                f"— converting to delivery to avoid forced exit"
            )
            return "DELIVERY"
        else:
            # Loss is too large to carry — cut loss now
            self.logger.info(
                f"Smart square-off: {symbol} down {pnl_pct:.2f}% (exceeds {max_carry_loss}% limit) "
                f"— cutting loss and squaring off"
            )
            return "INTRADAY"

    # -------------------------------------------------------------------------
    # Core Trade: sell current stock → buy target stock
    # -------------------------------------------------------------------------

    def transaction_through_inr(self, pair: Pair):
        """
        Sell the 'from_stock', receive INR, then immediately buy the 'to_stock'.
        This is the Indian stock market equivalent of 'transaction_through_bridge'.
        """
        from_symbol = pair.from_stock_id
        to_symbol = pair.to_stock_id

        # --- Guard: market must be open ---
        if not self.is_market_open():
            self.logger.info(f"Market is closed. Skipping trade {from_symbol} → {to_symbol}")
            return None

        # --- Guard: circuit breaker check ---
        if self.broker.is_circuit_breaker_hit(from_symbol, self.config.EXCHANGE):
            self.logger.warning(f"Circuit breaker hit for {from_symbol} — cannot sell. Skipping.")
            return None

        # --- Get current position ---
        quantity = self.broker.get_stock_quantity(from_symbol)
        from_price = self.get_stock_price(from_symbol)

        if not quantity or quantity <= 0:
            self.logger.info(f"No shares of {from_symbol} to sell. Skipping.")
            return None

        if not from_price:
            self.logger.info(f"Can't get price for {from_symbol}. Skipping.")
            return None

        # Decide trade type (smart near-close logic)
        trade_type = self.config.TRADE_TYPE
        if self.is_near_close():
            trade_type = self._decide_trade_type_for_squareoff(from_symbol, quantity, from_price)

        inr_balance_before = self.broker.get_inr_balance()

        # --- SELL ---
        self.logger.info(f"SELL: {quantity} shares of {from_symbol} @ ₹{from_price:.2f} [{trade_type}]")
        trade_log = self.db.start_trade_log(pair.from_stock, pair.to_stock, selling=True)
        trade_log.set_ordered(quantity, inr_balance_before, quantity)

        sell_order = self.broker.sell_stock(
            symbol=from_symbol,
            quantity=quantity,
            price=from_price,
            exchange=self.config.EXCHANGE,
            order_type="LIMIT",
            trade_type=trade_type,
        )

        if sell_order is None:
            self.logger.error(f"SELL failed for {from_symbol}. Aborting trade.")
            trade_log.set_failed()
            return None

        trade_log.set_complete(sell_order.inr_value)
        self.logger.info(f"SOLD {quantity} {from_symbol} @ ₹{sell_order.avg_price:.2f} = ₹{sell_order.inr_value:.2f}")

        # Allow balance to settle
        time.sleep(2)

        # --- BUY ---
        if self.broker.is_circuit_breaker_hit(to_symbol, self.config.EXCHANGE):
            self.logger.warning(f"Circuit breaker hit for {to_symbol} — cannot buy. INR sitting in account.")
            return None

        to_price = self.get_stock_price(to_symbol)
        if not to_price:
            self.logger.error(f"Can't get price for {to_symbol}. Holding INR.")
            return None

        inr_balance = self.broker.get_inr_balance()
        buy_qty = self.get_buy_quantity(to_symbol, inr_balance, to_price)

        if buy_qty <= 0:
            self.logger.warning(f"Insufficient balance (₹{inr_balance:.2f}) to buy {to_symbol} @ ₹{to_price:.2f}")
            return None

        self.logger.info(f"BUY: {buy_qty} shares of {to_symbol} @ ₹{to_price:.2f} [{trade_type}]")
        buy_trade_log = self.db.start_trade_log(pair.from_stock, pair.to_stock, selling=False)
        buy_trade_log.set_ordered(inr_balance, buy_qty, buy_qty)

        buy_order = self.broker.buy_stock(
            symbol=to_symbol,
            quantity=buy_qty,
            price=to_price,
            exchange=self.config.EXCHANGE,
            order_type="LIMIT",
            trade_type=trade_type,
        )

        if buy_order is None:
            self.logger.error(f"BUY failed for {to_symbol}.")
            buy_trade_log.set_failed()
            return None

        buy_trade_log.set_complete(buy_order.inr_value)
        self.logger.info(f"BOUGHT {buy_qty} {to_symbol} @ ₹{buy_order.avg_price:.2f} = ₹{buy_order.inr_value:.2f}")

        self.db.set_current_stock(pair.to_stock)
        self.update_trade_threshold(pair.to_stock, buy_order.avg_price)

        # --- Async JSON logging (never blocks trading) ---
        def _log_trade():
            time.sleep(2)
            actual_qty = self.broker.get_stock_quantity(to_symbol)
            trade_data = {
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "from_stock": from_symbol,
                "from_stock_sold_qty": quantity,
                "from_stock_price": sell_order.avg_price,
                "to_stock": to_symbol,
                "to_stock_bought_qty": actual_qty,
                "to_stock_price": buy_order.avg_price,
                "inr_spent": buy_order.inr_value,
                "trade_type": trade_type,
            }
            try:
                log_file = "trade_history.json"
                history = []
                if os.path.exists(log_file):
                    with open(log_file, "r") as f:
                        try:
                            history = json.load(f)
                        except Exception:
                            history = []
                history.append(trade_data)
                with open(log_file, "w") as f:
                    json.dump(history, f, indent=4)
            except Exception as e:
                self.logger.warning(f"Failed to write trade history: {e}")

        threading.Thread(target=_log_trade, daemon=True).start()

        return buy_order

    # -------------------------------------------------------------------------
    # Ratio Threshold Management
    # -------------------------------------------------------------------------

    def update_trade_threshold(self, stock: Stock, stock_price: float):
        if stock_price is None or stock_price <= 0:
            self.logger.info(f"Skipping threshold update — invalid price for {stock.symbol}")
            return

        with self.db.db_session() as session:
            for pair in session.query(Pair).filter(Pair.to_stock_id == stock.symbol):
                from_price = self.get_stock_price(pair.from_stock_id)
                if from_price is None:
                    continue
                pair.ratio = from_price / stock_price

    def initialize_trade_thresholds(self):
        with self.db.db_session() as session:
            for pair in session.query(Pair).filter(Pair.ratio.is_(None)).all():
                from_price = self.get_stock_price(pair.from_stock_id)
                if from_price is None:
                    self.logger.info(f"Skipping init: can't get price for {pair.from_stock_id}")
                    continue
                to_price = self.get_stock_price(pair.to_stock_id)
                if to_price is None:
                    self.logger.info(f"Skipping init: can't get price for {pair.to_stock_id}")
                    continue
                pair.ratio = from_price / to_price
                self.logger.info(f"Initialized ratio {pair.from_stock_id}/{pair.to_stock_id} = {pair.ratio:.6f}")

    # -------------------------------------------------------------------------
    # Ratio Scouting
    # -------------------------------------------------------------------------

    def _get_ratios(self, stock: Stock, stock_price: float) -> Dict[Pair, float]:
        ratio_dict: Dict[Pair, float] = {}

        for pair in self.db.get_pairs_from(stock):
            other_price = self.get_stock_price(pair.to_stock_id)
            if other_price is None or other_price <= 0:
                self.logger.debug(f"Skipping scouting — can't get price for {pair.to_stock_id}")
                continue

            if pair.ratio is None:
                continue

            self.db.log_scout(pair, pair.ratio, stock_price, other_price)

            # Ratio score: how much better is the target stock vs current, after fees?
            stock_opt_ratio = stock_price / other_price
            fee = self.broker.get_effective_fee_pct(self.config.TRADE_TYPE)
            transaction_fee = fee * 2  # buy + sell side

            if self.config.USE_MARGIN == "yes":
                ratio_dict[pair] = (
                    (1 - transaction_fee) * stock_opt_ratio / pair.ratio - 1 - self.config.SCOUT_MARGIN / 100
                )
            else:
                ratio_dict[pair] = (
                    stock_opt_ratio - transaction_fee * self.config.SCOUT_MULTIPLIER * stock_opt_ratio
                ) - pair.ratio

        return ratio_dict

    def _jump_to_best_stock(self, stock: Stock, stock_price: float):
        ratio_dict = self._get_ratios(stock, stock_price)

        print("\n\n=== Live Stock Distance to Target ===")
        for pair, val in sorted(ratio_dict.items(), key=lambda item: item[1], reverse=True):
            if self.config.USE_MARGIN == "yes":
                actual_pct = (val + self.config.SCOUT_MARGIN / 100) * 100
                print(f"  {pair.to_stock_id:>12} : {actual_pct:>6.2f}%  (Target: >{self.config.SCOUT_MARGIN}%)")
            else:
                print(f"  {pair.to_stock_id:>12} : {val:>8.5f}")
        print("=====================================")

        ratio_dict = {k: v for k, v in ratio_dict.items() if v > 0}

        if ratio_dict:
            best_pair = max(ratio_dict, key=ratio_dict.get)
            self.logger.info(f"Jumping from {stock.symbol} → {best_pair.to_stock_id}")
            self.transaction_through_inr(best_pair)

    # -------------------------------------------------------------------------
    # Scout (called by strategies)
    # -------------------------------------------------------------------------

    def scout(self):
        raise NotImplementedError()

    # -------------------------------------------------------------------------
    # Portfolio Value Tracking
    # -------------------------------------------------------------------------

    def update_values(self):
        now = datetime.now()
        with self.db.db_session() as session:
            stocks: List[Stock] = session.query(Stock).all()
            for stock in stocks:
                qty = self.broker.get_stock_quantity(stock.symbol)
                if qty == 0:
                    continue
                inr_price = self.get_stock_price(stock.symbol)
                sv = StockValue(
                    stock=stock,
                    balance=qty,
                    inr_value=inr_price,
                    interval=Interval.MINUTELY,
                    datetime=now,
                )
                session.add(sv)
