"""
Zerodha Kite broker implementation.
Install: pip install kiteconnect

NOTE: Zerodha requires a manual access token refresh every day.
The token is generated via browser login. After first login, save the token in user.cfg.
"""
import time
from typing import Optional

from .base_broker import BaseBroker, Order


class ZerodhaBroker(BaseBroker):
    def __init__(self, api_key: str, api_secret: str, access_token: str = None, logger=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.access_token = access_token
        self.logger = logger
        self._client = None

    def login(self) -> bool:
        try:
            from kiteconnect import KiteConnect
            self._client = KiteConnect(api_key=self.api_key)
            if self.access_token:
                self._client.set_access_token(self.access_token)
                profile = self._client.profile()
                if self.logger:
                    self.logger.info(f"Zerodha: Logged in as {profile['user_name']}")
                return True
            else:
                login_url = self._client.login_url()
                if self.logger:
                    self.logger.error(
                        f"Zerodha: No access_token provided. Please visit this URL to login and get request_token:\n{login_url}\n"
                        "Then set zerodha_access_token in user.cfg"
                    )
                return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Zerodha: Login error: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        try:
            instrument = f"{exchange.upper()}:{symbol}"
            quote = self._client.quote([instrument])
            return float(quote[instrument]["last_price"])
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Zerodha: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        try:
            margins = self._client.margins(segment="equity")
            return float(margins["available"]["live_balance"])
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Zerodha: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        try:
            positions = self._client.positions()
            for pos in positions.get("net", []):
                if pos["tradingsymbol"] == symbol:
                    return int(pos["quantity"])
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Zerodha: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                  order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            from kiteconnect import KiteConnect
            product = KiteConnect.PRODUCT_MIS if trade_type.upper() == "INTRADAY" else KiteConnect.PRODUCT_CNC
            otype = KiteConnect.ORDER_TYPE_LIMIT if order_type.upper() == "LIMIT" else KiteConnect.ORDER_TYPE_MARKET
            order_id = self._client.place_order(
                tradingsymbol=symbol,
                exchange=exchange.upper(),
                transaction_type=KiteConnect.TRANSACTION_TYPE_BUY,
                quantity=quantity,
                order_type=otype,
                price=round(price, 2),
                product=product,
                variety=KiteConnect.VARIETY_REGULAR,
            )
            return self._wait_for_order(str(order_id), symbol, exchange, "BUY", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Zerodha: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                   order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            from kiteconnect import KiteConnect
            product = KiteConnect.PRODUCT_MIS if trade_type.upper() == "INTRADAY" else KiteConnect.PRODUCT_CNC
            otype = KiteConnect.ORDER_TYPE_LIMIT if order_type.upper() == "LIMIT" else KiteConnect.ORDER_TYPE_MARKET
            order_id = self._client.place_order(
                tradingsymbol=symbol,
                exchange=exchange.upper(),
                transaction_type=KiteConnect.TRANSACTION_TYPE_SELL,
                quantity=quantity,
                order_type=otype,
                price=round(price, 2),
                product=product,
                variety=KiteConnect.VARIETY_REGULAR,
            )
            return self._wait_for_order(str(order_id), symbol, exchange, "SELL", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Zerodha: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            from kiteconnect import KiteConnect
            self._client.cancel_order(variety=KiteConnect.VARIETY_REGULAR, order_id=order_id)
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Zerodha: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            orders = self._client.orders()
            for o in orders:
                if str(o["order_id"]) == str(order_id):
                    avg_price = float(o.get("average_price", 0) or 0)
                    qty = int(o.get("filled_quantity", 0) or 0)
                    return Order(
                        order_id=order_id,
                        symbol=o["tradingsymbol"],
                        exchange=o["exchange"],
                        side=o["transaction_type"],
                        quantity=qty,
                        price=float(o.get("price", 0) or 0),
                        avg_price=avg_price,
                        inr_value=qty * avg_price,
                        status=o["status"].upper(),
                    )
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Zerodha: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        try:
            instrument = f"{exchange.upper()}:{symbol}"
            quote = self._client.quote([instrument])
            data = quote[instrument]
            ltp = data["last_price"]
            upper = data.get("upper_circuit_limit", None)
            lower = data.get("lower_circuit_limit", None)
            if upper and lower:
                return ltp >= upper or ltp <= lower
            return False
        except Exception:
            return False

    def _wait_for_order(self, order_id: str, symbol: str, exchange: str,
                        side: str, quantity: int, limit_price: float,
                        timeout_sec: int = 60) -> Optional[Order]:
        start = time.time()
        while time.time() - start < timeout_sec:
            order = self.get_order_status(order_id)
            if order and order.status == "COMPLETE":
                if self.logger:
                    self.logger.info(f"Zerodha: Order {order_id} FILLED — {side} {quantity} {symbol} @ ₹{order.avg_price}")
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Zerodha: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Zerodha: Order {order_id} timed out after {timeout_sec}s")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005
        return 0.0015
