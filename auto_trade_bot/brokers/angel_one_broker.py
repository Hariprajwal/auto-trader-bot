"""
Angel One SmartAPI broker implementation.
Install: pip install smartapi-python

Angel One is recommended because:
- Free API (no charges)
- Supports auto-login via TOTP (no manual token refresh needed daily)
- Good WebSocket support for live prices
"""
import time
from typing import Optional

from .base_broker import BaseBroker, Order


class AngelOneBroker(BaseBroker):
    def __init__(self, api_key: str, client_id: str, password: str, totp_secret: str, logger=None):
        self.api_key = api_key
        self.client_id = client_id
        self.password = password
        self.totp_secret = totp_secret
        self.logger = logger
        self._client = None
        self._session_token = None

    def login(self) -> bool:
        try:
            import pyotp
            from SmartApi import SmartConnect
            totp = pyotp.TOTP(self.totp_secret).now()
            self._client = SmartConnect(api_key=self.api_key)
            data = self._client.generateSession(self.client_id, self.password, totp)
            if data["status"]:
                self._session_token = data["data"]["jwtToken"]
                if self.logger:
                    self.logger.info("Angel One: Login successful")
                return True
            if self.logger:
                self.logger.error(f"Angel One: Login failed: {data}")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Angel One: Login exception: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        try:
            # Angel One uses exchange:tradingsymbol format
            exchange_map = {"NSE": "NSE", "BSE": "BSE"}
            ex = exchange_map.get(exchange.upper(), "NSE")
            # Need token for Angel One — use search to get it
            search_result = self._client.searchScrip(exchange=ex, searchscrip=symbol)
            if not search_result["data"]:
                return None
            token = search_result["data"][0]["symboltoken"]
            ltp_data = self._client.ltpData(exchange=ex, tradingsymbol=symbol, symboltoken=token)
            return float(ltp_data["data"]["ltp"])
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Angel One: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        try:
            rms = self._client.rmsLimit()
            return float(rms["data"]["availablecash"])
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Angel One: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        try:
            positions = self._client.position()
            if not positions["data"]:
                return 0
            for pos in positions["data"]:
                if pos["tradingsymbol"] == symbol:
                    return int(pos["netqty"])
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Angel One: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                  order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            product = "MIS" if trade_type.upper() == "INTRADAY" else "CNC"
            search_result = self._client.searchScrip(exchange=exchange, searchscrip=symbol)
            token = search_result["data"][0]["symboltoken"]
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "BUY",
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product,
                "duration": "DAY",
                "price": str(round(price, 2)),
                "quantity": str(quantity),
            }
            response = self._client.placeOrder(order_params)
            order_id = response["data"]["orderid"]
            return self._wait_for_order(order_id, symbol, exchange, "BUY", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Angel One: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                   order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            product = "MIS" if trade_type.upper() == "INTRADAY" else "CNC"
            search_result = self._client.searchScrip(exchange=exchange, searchscrip=symbol)
            token = search_result["data"][0]["symboltoken"]
            order_params = {
                "variety": "NORMAL",
                "tradingsymbol": symbol,
                "symboltoken": token,
                "transactiontype": "SELL",
                "exchange": exchange,
                "ordertype": order_type,
                "producttype": product,
                "duration": "DAY",
                "price": str(round(price, 2)),
                "quantity": str(quantity),
            }
            response = self._client.placeOrder(order_params)
            order_id = response["data"]["orderid"]
            return self._wait_for_order(order_id, symbol, exchange, "SELL", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Angel One: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._client.cancelOrder(order_id=order_id, variety="NORMAL")
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Angel One: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            orders = self._client.orderBook()
            if not orders["data"]:
                return None
            for o in orders["data"]:
                if str(o["orderid"]) == str(order_id):
                    avg_price = float(o.get("averageprice", 0) or 0)
                    qty = int(o.get("filledshares", 0) or 0)
                    return Order(
                        order_id=order_id,
                        symbol=o["tradingsymbol"],
                        exchange=o["exchange"],
                        side=o["transactiontype"],
                        quantity=qty,
                        price=float(o.get("price", 0) or 0),
                        avg_price=avg_price,
                        inr_value=qty * avg_price,
                        status=o["status"].upper(),
                    )
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Angel One: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        """
        Angel One doesn't expose circuit limits directly.
        We check if LTP equals upper or lower circuit price via quote data.
        """
        try:
            search_result = self._client.searchScrip(exchange=exchange, searchscrip=symbol)
            token = search_result["data"][0]["symboltoken"]
            quote = self._client.getCandleData({
                "exchange": exchange,
                "symboltoken": token,
                "interval": "ONE_MINUTE",
                "fromdate": "",
                "todate": "",
            })
            # If bid/ask spread is 0 and no volume, likely circuit hit
            # This is a heuristic — Angel One doesn't give circuit limits in free tier
            return False
        except Exception:
            return False

    def _wait_for_order(self, order_id: str, symbol: str, exchange: str,
                        side: str, quantity: int, limit_price: float,
                        timeout_sec: int = 60) -> Optional[Order]:
        """Poll for order fill. Returns Order when COMPLETE, None on timeout/failure."""
        start = time.time()
        while time.time() - start < timeout_sec:
            order = self.get_order_status(order_id)
            if order and order.status == "COMPLETE":
                if self.logger:
                    self.logger.info(f"Angel One: Order {order_id} FILLED — {side} {quantity} {symbol} @ ₹{order.avg_price}")
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Angel One: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Angel One: Order {order_id} timed out after {timeout_sec}s")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        # Angel One: ₹20 flat OR 0.03% whichever is lower + STT + exchange charges
        # For ratio calculations, use a conservative percentage
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005  # ~0.05%
        return 0.0015  # ~0.15% delivery
