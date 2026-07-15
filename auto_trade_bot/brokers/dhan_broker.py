"""
Dhan broker implementation.
Install: pip install dhanhq
Simple REST API, great for beginners.
"""
import time
from typing import Optional

from .base_broker import BaseBroker, Order


class DhanBroker(BaseBroker):
    def __init__(self, client_id: str, access_token: str, logger=None):
        self.client_id = client_id
        self.access_token = access_token
        self.logger = logger
        self._client = None

    def login(self) -> bool:
        try:
            from dhanhq import dhanhq
            self._client = dhanhq(self.client_id, self.access_token)
            if self.logger:
                self.logger.info("Dhan: Connected successfully")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dhan: Login error: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        try:
            # Dhan needs security_id — use a local mapping or their instrument list
            from dhanhq import dhanhq
            exchange_segment = dhanhq.NSE if exchange.upper() == "NSE" else dhanhq.BSE
            # This is a simplified approach — in production, cache instrument list
            response = self._client.intraday_daily_minute_charts(
                security_id=symbol,
                exchange_segment=exchange_segment,
                instrument_type="EQUITY"
            )
            if response and response.get("data"):
                return float(response["data"][-1][4])  # Close price of last candle
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Dhan: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        try:
            response = self._client.get_fund_limits()
            return float(response["data"].get("availabelBalance", 0))
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Dhan: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        try:
            response = self._client.get_positions()
            for pos in response.get("data", []):
                if pos["tradingSymbol"] == symbol:
                    return int(pos["netQty"])
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Dhan: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                  order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            from dhanhq import dhanhq
            product = dhanhq.INTRA if trade_type.upper() == "INTRADAY" else dhanhq.CNC
            otype = dhanhq.LIMIT if order_type.upper() == "LIMIT" else dhanhq.MARKET
            exchange_segment = dhanhq.NSE if exchange.upper() == "NSE" else dhanhq.BSE
            response = self._client.place_order(
                security_id=symbol,
                exchange_segment=exchange_segment,
                transaction_type=dhanhq.BUY,
                quantity=quantity,
                order_type=otype,
                product_type=product,
                price=round(price, 2),
            )
            order_id = response["data"]["orderId"]
            return self._wait_for_order(order_id, symbol, exchange, "BUY", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dhan: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                   order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            from dhanhq import dhanhq
            product = dhanhq.INTRA if trade_type.upper() == "INTRADAY" else dhanhq.CNC
            otype = dhanhq.LIMIT if order_type.upper() == "LIMIT" else dhanhq.MARKET
            exchange_segment = dhanhq.NSE if exchange.upper() == "NSE" else dhanhq.BSE
            response = self._client.place_order(
                security_id=symbol,
                exchange_segment=exchange_segment,
                transaction_type=dhanhq.SELL,
                quantity=quantity,
                order_type=otype,
                product_type=product,
                price=round(price, 2),
            )
            order_id = response["data"]["orderId"]
            return self._wait_for_order(order_id, symbol, exchange, "SELL", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Dhan: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._client.cancel_order(order_id)
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Dhan: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            response = self._client.get_order_by_id(order_id)
            o = response["data"]
            avg_price = float(o.get("averageTradedPrice", 0) or 0)
            qty = int(o.get("filledQty", 0) or 0)
            return Order(
                order_id=order_id,
                symbol=o["tradingSymbol"],
                exchange=o.get("exchangeSegment", "NSE"),
                side=o["transactionType"],
                quantity=qty,
                price=float(o.get("price", 0) or 0),
                avg_price=avg_price,
                inr_value=qty * avg_price,
                status=o["orderStatus"].upper(),
            )
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Dhan: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        # Dhan doesn't expose circuit limits in basic API
        return False

    def _wait_for_order(self, order_id: str, symbol: str, exchange: str,
                        side: str, quantity: int, limit_price: float,
                        timeout_sec: int = 60) -> Optional[Order]:
        start = time.time()
        while time.time() - start < timeout_sec:
            order = self.get_order_status(order_id)
            if order and order.status in ("TRADED", "COMPLETE"):
                if self.logger:
                    self.logger.info(f"Dhan: Order {order_id} FILLED — {side} {quantity} {symbol} @ ₹{order.avg_price}")
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Dhan: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Dhan: Order {order_id} timed out after {timeout_sec}s")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        # Dhan: ₹20/order flat, similar effective % to others
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005
        return 0.0015
