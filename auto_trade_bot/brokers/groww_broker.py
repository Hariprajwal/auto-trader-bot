"""
Groww Pro API broker implementation.
Install: pip install requests  (Groww uses plain REST, no official SDK yet)

Groww Fee Structure (as of 2026):
  Delivery (CNC) : ZERO brokerage!  → round-trip ≈ 0.23% (only STT + exchange)
  Intraday (MIS) : ₹20/order flat  → round-trip ≈ 0.08%

Get your API credentials from: https://groww.in/trading-api
You'll need:
  - client_id      (your Groww user ID)
  - access_token   (from Groww Pro API dashboard)
"""
import time
from typing import Optional

import requests

from .base_broker import BaseBroker, Order


GROWW_BASE_URL = "https://api.groww.in/v1"


class GrowwBroker(BaseBroker):
    """
    Groww Pro API implementation.
    
    Groww is particularly good for DELIVERY trading because they charge
    ZERO brokerage on delivery — making delivery trades significantly
    cheaper than other brokers.
    
    Author: K R HARI PRAJWAL
    """

    def __init__(self, client_id: str, access_token: str, logger=None):
        self.client_id = client_id
        self.access_token = access_token
        self.logger = logger
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-groww-user-id": self.client_id,
        })

    def login(self) -> bool:
        """
        Groww uses a static access token (no interactive login needed).
        This validates the token by fetching the user profile.
        """
        try:
            resp = self._session.get(f"{GROWW_BASE_URL}/user/profile", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                name = data.get("data", {}).get("name", "Unknown")
                if self.logger:
                    self.logger.info(f"Groww: Connected as {name} (ID: {self.client_id})")
                return True
            if self.logger:
                self.logger.error(f"Groww: Auth failed — HTTP {resp.status_code}: {resp.text}")
            return False
        except Exception as e:
            if self.logger:
                self.logger.error(f"Groww: Login error: {e}")
            return False

    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """
        Get live LTP for a stock.
        Groww uses NSE symbol format directly.
        """
        try:
            params = {"symbol": symbol, "exchange": exchange.upper()}
            resp = self._session.get(
                f"{GROWW_BASE_URL}/market/quote",
                params=params,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return float(data.get("ltp") or data.get("lastPrice") or 0)
            if self.logger:
                self.logger.warning(f"Groww: get_stock_price({symbol}) HTTP {resp.status_code}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Groww: get_stock_price({symbol}) error: {e}")
            return None

    def get_inr_balance(self) -> float:
        """Get available cash balance in INR."""
        try:
            resp = self._session.get(f"{GROWW_BASE_URL}/user/funds", timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return float(data.get("availableBalance") or data.get("available_balance") or 0)
            return 0.0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Groww: get_inr_balance error: {e}")
            return 0.0

    def get_stock_quantity(self, symbol: str) -> int:
        """Get number of shares currently held for a symbol."""
        try:
            resp = self._session.get(f"{GROWW_BASE_URL}/portfolio/positions", timeout=10)
            if resp.status_code == 200:
                positions = resp.json().get("data", {}).get("positions", [])
                for pos in positions:
                    if pos.get("tradingSymbol") == symbol or pos.get("symbol") == symbol:
                        return int(pos.get("netQuantity") or pos.get("quantity") or 0)
            return 0
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Groww: get_stock_quantity({symbol}) error: {e}")
            return 0

    def buy_stock(
        self,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NSE",
        order_type: str = "LIMIT",
        trade_type: str = "INTRADAY",
    ) -> Optional[Order]:
        try:
            product = "MIS" if trade_type.upper() == "INTRADAY" else "CNC"
            payload = {
                "tradingSymbol": symbol,
                "exchange": exchange.upper(),
                "transactionType": "BUY",
                "orderType": order_type.upper(),
                "productType": product,
                "quantity": quantity,
                "price": round(price, 2),
                "validity": "DAY",
            }
            resp = self._session.post(
                f"{GROWW_BASE_URL}/orders/place",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                order_id = resp.json().get("data", {}).get("orderId")
                if order_id:
                    return self._wait_for_order(order_id, symbol, exchange, "BUY", quantity, price)
            if self.logger:
                self.logger.error(f"Groww: buy_stock failed — HTTP {resp.status_code}: {resp.text}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Groww: buy_stock({symbol}, {quantity}) error: {e}")
            return None

    def sell_stock(
        self,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NSE",
        order_type: str = "LIMIT",
        trade_type: str = "INTRADAY",
    ) -> Optional[Order]:
        try:
            product = "MIS" if trade_type.upper() == "INTRADAY" else "CNC"
            payload = {
                "tradingSymbol": symbol,
                "exchange": exchange.upper(),
                "transactionType": "SELL",
                "orderType": order_type.upper(),
                "productType": product,
                "quantity": quantity,
                "price": round(price, 2),
                "validity": "DAY",
            }
            resp = self._session.post(
                f"{GROWW_BASE_URL}/orders/place",
                json=payload,
                timeout=10,
            )
            if resp.status_code in (200, 201):
                order_id = resp.json().get("data", {}).get("orderId")
                if order_id:
                    return self._wait_for_order(order_id, symbol, exchange, "SELL", quantity, price)
            if self.logger:
                self.logger.error(f"Groww: sell_stock failed — HTTP {resp.status_code}: {resp.text}")
            return None
        except Exception as e:
            if self.logger:
                self.logger.error(f"Groww: sell_stock({symbol}, {quantity}) error: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        try:
            resp = self._session.delete(
                f"{GROWW_BASE_URL}/orders/{order_id}",
                timeout=10,
            )
            return resp.status_code in (200, 204)
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Groww: cancel_order({order_id}) error: {e}")
            return False

    def get_order_status(self, order_id: str) -> Optional[Order]:
        try:
            resp = self._session.get(
                f"{GROWW_BASE_URL}/orders/{order_id}",
                timeout=10,
            )
            if resp.status_code == 200:
                o = resp.json().get("data", {})
                avg_price = float(o.get("averagePrice") or o.get("avgPrice") or 0)
                qty = int(o.get("filledQuantity") or o.get("executedQuantity") or 0)
                status_raw = (o.get("status") or o.get("orderStatus") or "").upper()
                # Normalise Groww status strings
                if status_raw in ("EXECUTED", "TRADED", "COMPLETE", "FILLED"):
                    status = "COMPLETE"
                elif status_raw in ("CANCELLED", "CANCELED", "REJECTED"):
                    status = status_raw
                else:
                    status = "OPEN"
                return Order(
                    order_id=order_id,
                    symbol=o.get("tradingSymbol", ""),
                    exchange=o.get("exchange", "NSE"),
                    side=o.get("transactionType", "BUY"),
                    quantity=qty,
                    price=float(o.get("price") or 0),
                    avg_price=avg_price,
                    inr_value=qty * avg_price,
                    status=status,
                )
            return None
        except Exception as e:
            if self.logger:
                self.logger.warning(f"Groww: get_order_status({order_id}) error: {e}")
            return None

    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        """Check upper/lower circuit via quote data."""
        try:
            params = {"symbol": symbol, "exchange": exchange.upper()}
            resp = self._session.get(
                f"{GROWW_BASE_URL}/market/quote",
                params=params,
                timeout=5,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                ltp = float(data.get("ltp") or 0)
                upper = float(data.get("upperCircuitLimit") or data.get("upperCircuit") or 0)
                lower = float(data.get("lowerCircuitLimit") or data.get("lowerCircuit") or 0)
                if upper > 0 and lower > 0:
                    return ltp >= upper or ltp <= lower
            return False
        except Exception:
            return False

    def _wait_for_order(
        self,
        order_id: str,
        symbol: str,
        exchange: str,
        side: str,
        quantity: int,
        limit_price: float,
        timeout_sec: int = 60,
    ) -> Optional[Order]:
        """Poll order status until filled, cancelled, or timed out."""
        start = time.time()
        while time.time() - start < timeout_sec:
            order = self.get_order_status(order_id)
            if order and order.status == "COMPLETE":
                if self.logger:
                    self.logger.info(
                        f"Groww: Order {order_id} FILLED — "
                        f"{side} {quantity} {symbol} @ ₹{order.avg_price:.2f}"
                    )
                return order
            if order and order.status in ("CANCELLED", "REJECTED"):
                if self.logger:
                    self.logger.warning(f"Groww: Order {order_id} {order.status}")
                return None
            time.sleep(1)
        if self.logger:
            self.logger.warning(f"Groww: Order {order_id} timed out after {timeout_sec}s — cancelling")
        self.cancel_order(order_id)
        return None

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        """
        Groww fee breakdown (per side):

        INTRADAY (MIS):
          Brokerage     ₹20 flat (on ₹50k = ~0.04%)
          STT           0.025% on sell side (averaged ≈ 0.0125%)
          NSE Exchange  0.00345% per side
          GST (18%)     on brokerage + exchange ≈ 0.008%
          SEBI          0.0001%
          Stamp duty    0.003% on buy (averaged ≈ 0.0015%)
          ─────────────────────────────────────────────────
          Per-side ≈ 0.065%  →  round-trip ≈ 0.13%
          Recommended scout_margin: 0.3%

        DELIVERY (CNC):
          Brokerage     ZERO ✅  (Groww charges ₹0 for delivery!)
          STT           0.1% on BOTH sides = 0.2% total
          NSE Exchange  0.00345% per side
          GST (18%)     on exchange charges only ≈ 0.001%
          SEBI          0.0001%
          Stamp duty    0.015% on buy (≈ 0.0075% averaged)
          ─────────────────────────────────────────────────
          Per-side ≈ 0.107%  →  round-trip ≈ 0.21%
          Recommended scout_margin: 0.5%
          (cheaper than other brokers for delivery due to zero brokerage!)
        """
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.00065   # 0.065% per side → 0.13% round-trip
        return 0.00107       # 0.107% per side → 0.21% round-trip (cheaper delivery!)
