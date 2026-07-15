"""
Multiple Stocks Strategy
========================
Unlike the default strategy (hold ONE stock at a time), this strategy
holds MULTIPLE stocks simultaneously and rotates only the worst performer.

How it works:
  - Divide your capital equally among N stocks (configurable)
  - Every scout cycle, find the worst-performing stock in your portfolio
  - Check if any other stock has a better ratio against it
  - If yes, sell the worst stock → buy the better one
  - This gives more diversification and reduces the impact of a single bad trade

Configuration (add to user.cfg):
  strategy = multiple_stocks
  portfolio_size = 3     ← how many stocks to hold at once (default: 3)

Author  : K R HARI PRAJWAL
License : MIT
"""

import random
import sys
from datetime import datetime
from typing import List, Optional

from auto_trade_bot.auto_trader import AutoTrader
from auto_trade_bot.models import Stock, Pair


class Strategy(AutoTrader):

    def initialize(self):
        super().initialize()
        self.portfolio_size = int(getattr(self.config, "PORTFOLIO_SIZE", 3))
        self.logger.info(f"Multiple Stocks Strategy — holding up to {self.portfolio_size} stocks")
        self._initialize_portfolio()

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio Initialisation
    # ─────────────────────────────────────────────────────────────────────────

    def _initialize_portfolio(self):
        """
        On first startup, buy into `portfolio_size` stocks with equal capital allocation.
        """
        inr_balance = self.broker.get_inr_balance()
        stocks = self.db.get_stocks()

        if not stocks:
            self.logger.error("No stocks in database. Check supported_stock_list.")
            sys.exit(1)

        # See which stocks we already hold
        held = [s for s in stocks if self.broker.get_stock_quantity(s.symbol) > 0]
        need_to_buy = self.portfolio_size - len(held)

        if need_to_buy <= 0:
            self.logger.info(f"Already holding {len(held)} stocks: {[s.symbol for s in held]}")
            return

        # Pick random stocks we don't already hold
        available = [s for s in stocks if s not in held]
        random.shuffle(available)
        to_buy = available[:need_to_buy]

        if not to_buy:
            self.logger.warning("Not enough stocks in list to fill portfolio_size.")
            return

        capital_per_stock = inr_balance / max(need_to_buy, 1)
        self.logger.info(
            f"Initialising portfolio: buying {[s.symbol for s in to_buy]} "
            f"at ₹{capital_per_stock:,.0f} each"
        )

        for stock in to_buy:
            if not self.is_market_open():
                self.logger.info("Market closed during portfolio init — will resume next open")
                break
            price = self.get_stock_price(stock.symbol)
            if not price:
                self.logger.warning(f"Can't get price for {stock.symbol} — skipping")
                continue
            qty = self.get_buy_quantity(stock.symbol, capital_per_stock, price)
            if qty <= 0:
                self.logger.warning(f"Insufficient balance for {stock.symbol} — skipping")
                continue
            order = self.broker.buy_stock(
                symbol=stock.symbol,
                quantity=qty,
                price=price,
                exchange=self.config.EXCHANGE,
                order_type="LIMIT",
                trade_type=self.config.TRADE_TYPE,
            )
            if order:
                self.logger.info(f"Portfolio init: Bought {qty} {stock.symbol} @ ₹{order.avg_price:.2f}")
                self.db.set_current_stock(stock)
                self.update_trade_threshold(stock, order.avg_price)

    # ─────────────────────────────────────────────────────────────────────────
    # Portfolio State Helpers
    # ─────────────────────────────────────────────────────────────────────────

    def _get_held_stocks(self) -> List[Stock]:
        """Return list of stocks we currently hold (qty > 0)."""
        held = []
        for stock in self.db.get_stocks():
            qty = self.broker.get_stock_quantity(stock.symbol)
            if qty > 0:
                held.append(stock)
        return held

    def _find_worst_stock(self, held: List[Stock]) -> Optional[Stock]:
        """
        Find the held stock with the worst recent performance.
        'Worst' = lowest ratio score relative to all other stocks.
        Falls back to smallest current INR value if prices unavailable.
        """
        if not held:
            return None
        if len(held) == 1:
            return held[0]

        worst_stock = None
        worst_score = float("inf")

        for stock in held:
            price = self.get_stock_price(stock.symbol)
            if not price:
                continue
            qty = self.broker.get_stock_quantity(stock.symbol)
            inr_value = price * qty

            # Lower INR value → weaker performer
            if inr_value < worst_score:
                worst_score = inr_value
                worst_stock = stock

        return worst_stock

    # ─────────────────────────────────────────────────────────────────────────
    # Main Scout Loop
    # ─────────────────────────────────────────────────────────────────────────

    def scout(self):
        """
        On each cycle:
          1. Check market hours
          2. Get currently held stocks
          3. For each held stock, compute ratios against unheid stocks
          4. Rotate the worst-performing held stock into the best available target
        """
        if not self.is_market_open():
            print(
                f"{datetime.now().strftime('%H:%M:%S')} — Market CLOSED. Bot is idle.",
                end="\r",
            )
            return

        held = self._get_held_stocks()

        print(
            f"{datetime.now()} — Holding: {[s.symbol for s in held]} "
            f"[{self.config.TRADE_TYPE}] Scouting...",
            end="\r",
        )

        # Near close — handle square-off for all held intraday positions
        if self.is_near_close(threshold_minutes=12) and self.config.TRADE_TYPE == "INTRADAY":
            self._handle_near_close(held)
            return

        if not held:
            self.logger.warning("No stocks currently held. Re-initialising portfolio...")
            self._initialize_portfolio()
            return

        # Find the worst held stock
        worst = self._find_worst_stock(held)
        if worst is None:
            return

        worst_price = self.get_stock_price(worst.symbol)
        if not worst_price:
            return

        # Find the best non-held stock relative to the worst held stock
        all_stocks = self.db.get_stocks()
        held_symbols = {s.symbol for s in held}
        candidates = [s for s in all_stocks if s.symbol not in held_symbols]

        best_target = None
        best_score = 0.0

        for candidate in candidates:
            candidate_price = self.get_stock_price(candidate.symbol)
            if not candidate_price or candidate_price <= 0:
                continue

            pair = self.db.get_pair(worst, candidate)
            if pair is None or pair.ratio is None:
                continue

            self.db.log_scout(pair, pair.ratio, worst_price, candidate_price)

            current_ratio = worst_price / candidate_price
            fee = self.broker.get_effective_fee_pct(self.config.TRADE_TYPE)
            transaction_fee = fee * 2

            if self.config.USE_MARGIN == "yes":
                score = (1 - transaction_fee) * current_ratio / pair.ratio - 1 - self.config.SCOUT_MARGIN / 100
            else:
                score = (current_ratio - transaction_fee * self.config.SCOUT_MULTIPLIER * current_ratio) - pair.ratio

            if score > best_score:
                best_score = score
                best_target = candidate

        if best_target:
            pair = self.db.get_pair(worst, best_target)
            if pair:
                self.logger.info(
                    f"Rotating: sell {worst.symbol} → buy {best_target.symbol} "
                    f"(score: {best_score:.4f})"
                )
                self.transaction_through_inr(pair)

    # ─────────────────────────────────────────────────────────────────────────
    # Near-Close Handling
    # ─────────────────────────────────────────────────────────────────────────

    def _handle_near_close(self, held: List[Stock]):
        """Square-off or convert all intraday positions near market close."""
        self.logger.info(
            f"Near market close ({self.minutes_to_close():.0f} min). "
            f"Handling {len(held)} position(s)..."
        )
        for stock in held:
            qty = self.broker.get_stock_quantity(stock.symbol)
            if qty <= 0:
                continue
            price = self.get_stock_price(stock.symbol)
            if not price:
                continue

            decision = self._decide_trade_type_for_squareoff(stock.symbol, qty, price)
            if decision == "INTRADAY":
                self.logger.info(f"Squaring off {qty} {stock.symbol} @ ~₹{price:.2f}")
                self.broker.sell_stock(
                    symbol=stock.symbol,
                    quantity=qty,
                    price=price,
                    exchange=self.config.EXCHANGE,
                    order_type="MARKET",
                    trade_type="INTRADAY",
                )
            else:
                self.logger.info(f"Converting {stock.symbol} to delivery — holding overnight")
