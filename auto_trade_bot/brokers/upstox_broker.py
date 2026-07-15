"""
Upstox API v2 broker implementation.
Install: pip install upstox-python-sdk
"""
import time
from typing import Optional

from .base_broker import BaseBroker, Order


class UpstoxBroker(BaseBroker):
    def __init__(self, api_key: str, api_secret: str, redirect_uri: str, access_token: str = None, logger=None):
        self.api_key = api_key
        self.api_secret = api_secret
        self.redirect_uri = redirect_uri
        self.access_token = access_token
        self.logger = logger
        self._config = None
        self._order_api = None
        self._portfolio_api = None
        self._market_api = None

    def login(self) -> bool:
        try:
            import upstox_client
            configuration = upstox_client.Configuration()
            configuration.access_token = self.access_token
            self._config = configuration
            api_client = upstox_client.ApiClient(configuration)
            self._order_api = upstox_client.OrderApi(api_client)
            self._portfolio_api = upstox_client.PortfolioApi(api_client)
            self._market_api = upstox_client.MarketQuoteApi(api_client)
            if self.logger:
                self.logger.info("Upstox: Login configured with access token")
            return True
        except Exception as e:
            if self.logger:
                self.logger.error(f"Upstox: Login error: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        try:
            # Upstox uses NSE_EQ|RELIANCE format
            instrument_key = f"{exchange.upper()}_EQ|{symbol}"
            response = self._market_api.ltp(instrument_key)
            data = response.data
            key = list(data.keys())[0]
            return float(data[key].last_price)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Upstox: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        try:
            import upstox_client
            funds_api = upstox_client.UserApi(upstox_client.ApiClient(self._config))
            response = funds_api.get_fund_and_margin(segment="SEC")
            return float(response.data.equity.available_margin)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Upstox: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        try:
            response = self._portfolio_api.get_positions()
            for pos in response.data or []:
                if pos.tradingsymbol == symbol:
                    return int(pos.quantity)
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Upstox: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                  order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            import upstox_client
            product = "I" if trade_type.upper() == "INTRADAY" else "D"
            otype = "L" if order_type.upper() == "LIMIT" else "MKT"
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product=product,
                validity="DAY",
                price=round(price, 2),
                tag="auto_trade_bot",
                instrument_token=f"{exchange.upper()}_EQ|{symbol}",
                order_type=otype,
                transaction_type="B",
                disclosed_quantity=0,
                trigger_price=0,
                is_amo=False,
            )
            response = self._order_api.place_order(body)
            order_id = response.data.order_id
            return self._wait_for_order(order_id, symbol, exchange, "BUY", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Upstox: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(self, symbol: str, quantity: int, price: float, exchange: str = "NSE",
                   order_type: str = "LIMIT", trade_type: str = "INTRADAY") -> Optional[Order]:
        try:
            import upstox_client
            product = "I" if trade_type.upper() == "INTRADAY" else "D"
            otype = "L" if order_type.upper() == "LIMIT" else "MKT"
            body = upstox_client.PlaceOrderRequest(
                quantity=quantity,
                product=product,
                validity="DAY",
                price=round(price, 2),
                tag="auto_trade_bot",
                instrument_token=f"{exchange.upper()}_EQ|{symbol}",
                order_type=otype,
                transaction_type="S",
                disclosed_quantity=0,
                trigger_price=0,
                is_amo=False,
            )
            response = self._order_api.place_order(body)
            order_id = response.data.order_id
            return self._wait_for_order(order_id, symbol, exchange, "SELL", quantity, price)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Upstox: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            self._order_api.cancel_order(order_id)
            return True
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Upstox: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            response = self._order_api.get_order_details(order_id=order_id)
            o = response.data
            avg_price = float(o.average_price or 0)
            qty = int(o.filled_quantity or 0)
            return Order(
                order_id=order_id,
                symbol=o.tradingsymbol,
                exchange=o.exchange,
                side="BUY" if o.transaction_type == "B" else "SELL",
                quantity=qty,
                price=float(o.price or 0),
                avg_price=avg_price,
                inr_value=qty * avg_price,
                status=o.status.upper(),
            )
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Upstox: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        try:
            instrument_key = f"{exchange.upper()}_EQ|{symbol}"
            response = self._market_api.full_market_quotes(instrument_key)
            data = response.data
            key = list(data.keys())[0]
            quote = data[key]
            ltp = quote.last_price
            upper = getattr(quote, "upper_circuit_limit", None)
            lower = getattr(quote, "lower_circuit_limit", None)
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
            if order and order.status in ("COMPLETE", "FILLED"):
                if self.logger:
                    self.logger.info(f"Upstox: Order {order_id} FILLED — {side} {quantity} {symbol} @ ₹{order.avg_price}")
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Upstox: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Upstox: Order {order_id} timed out after {timeout_sec}s")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005
        return 0.0015
