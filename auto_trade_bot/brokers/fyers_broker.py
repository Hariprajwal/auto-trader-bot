"""
Fyers API broker implementation.
Install: pip install fyers-apiv3
Good for intraday with fast order execution.
"""
import time
from typing import Optional

from .base_broker import BaseBroker, Order


class FyersBroker(BaseBroker):
    def __init__(self, client_id: str, access_token: str, logger=None):
        self.client_id = client_id
        self.access_token = access_token
        self.logger = logger
        self._client = None

    def login(self) -> bool:
        try:
            from fyers_apiv3 import fyersModel
            self._client = fyersModel.FyersModel(
                client_id=self.client_id,
                is_async=False,
                token=self.access_token,
                log_path=""
            )
            profile = self._client.get_profile()
            if profile["code"] == 200:
                if self.logger:
                    self.logger.info(f"Fyers: Logged in as {profile['data']['name']}")
                return True
            if self.logger:
                self.logger.error(f"Fyers: Login failed: {profile}")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Fyers: Login error: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        try:
            # Fyers format: NSE:RELIANCE-EQ
            fyers_symbol = f"{exchange.upper()}:{symbol}-EQ"
            response = self._client.quotes({"symbols": fyers_symbol})
            if response["code"] == 200:
                return float(response["d"][0]["v"]["lp"])
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Fyers: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        try:
            response = self._client.funds()
            for item in response.get("fund_limit", []):
                if item["title"] == "Available Balance":
                    return float(item["equityAmount"])
            return 0.0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Fyers: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        try:
            response = self._client.positions()
            for pos in response.get("netPositions", []):
                if symbol in pos.get("symbol", ""):
                    return int(pos["netQty"])
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Fyers: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                  order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            product_type = 1 if trade_type.upper() == "INTRADAY" else 2  # 1=INTRADAY, 2=CNC
            otype = 1 if order_type.upper() == "LIMIT" else 2              # 1=LIMIT, 2=MARKET
            fyers_symbol = f"{exchange.upper()}:{symbol}-EQ"
            data = {
                "symbol": fyers_symbol,
                "qty": quantity,
                "type": otype,
                "side": 1,  # 1=BUY
                "productType": "INTRADAY" if trade_type.upper() == "INTRADAY" else "CNC",
                "limitPrice": round(price, 2),
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": False,
            }
            response = self._client.place_order(data)
            order_id = response["id"]
            return self._wait_for_order(order_id, symbol, exchange, "BUY", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Fyers: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                   order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            product_type = 1 if trade_type.upper() == "INTRADAY" else 2
            otype = 1 if order_type.upper() == "LIMIT" else 2
            fyers_symbol = f"{exchange.upper()}:{symbol}-EQ"
            data = {
                "symbol": fyers_symbol,
                "qty": quantity,
                "type": otype,
                "side": -1,  # -1=SELL
                "productType": "INTRADAY" if trade_type.upper() == "INTRADAY" else "CNC",
                "limitPrice": round(price, 2),
                "stopPrice": 0,
                "validity": "DAY",
                "disclosedQty": 0,
                "offlineOrder": False,
            }
            response = self._client.place_order(data)
            order_id = response["id"]
            return self._wait_for_order(order_id, symbol, exchange, "SELL", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Fyers: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._client.cancel_order({"id": order_id})
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Fyers: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            response = self._client.orderbook()
            for o in response.get("orderBook", []):
                if str(o["id"]) == str(order_id):
                    avg_price = float(o.get("tradedPrice", 0) or 0)
                    qty = int(o.get("filledQty", 0) or 0)
                    side_map = {1: "BUY", -1: "SELL"}
                    return Order(
                        order_id=order_id,
                        symbol=symbol_from_fyers(o.get("symbol", "")),
                        exchange="NSE",
                        side=side_map.get(o.get("side", 1), "BUY"),
                        quantity=qty,
                        price=float(o.get("limitPrice", 0) or 0),
                        avg_price=avg_price,
                        inr_value=qty * avg_price,
                        status="COMPLETE" if o["status"] == 2 else o.get("statusDescription", "OPEN").upper(),
                    )
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Fyers: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        try:
            fyers_symbol = f"{exchange.upper()}:{symbol}-EQ"
            response = self._client.depth({"symbol": fyers_symbol, "ohlcv_flag": 1})
            data = response.get("d", {})
            ltp = data.get("ltp", 0)
            upper = data.get("upper_ckt", None)
            lower = data.get("lower_ckt", None)
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
                    self.logger.info(f"Fyers: Order {order_id} FILLED — {side} {quantity} {symbol} @ ₹{order.avg_price}")
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Fyers: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Fyers: Order {order_id} timed out after {timeout_sec}s")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005
        return 0.0015


def symbol_from_fyers(fyers_symbol: str) -> str:
    """Convert 'NSE:RELIANCE-EQ' → 'RELIANCE'"""
    return fyers_symbol.split(":")[-1].replace("-EQ", "").replace("-BE", "").replace("-N", "")
