"""
Abstract base class for all Indian broker implementations.
Every broker (Zerodha, Angel One, Upstox, Dhan, Fyers) must implement this interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Order:
    """Represents a completed broker order."""
    order_id: str
    symbol: str
    exchange: str
    side: str           # "BUY" or "SELL"
    quantity: int
    price: float        # Limit price set
    avg_price: float    # Actual fill price (may differ from limit)
    inr_value: float    # Total INR value of the trade (qty * avg_price)
    status: str         # "COMPLETE", "OPEN", "CANCELLED", "REJECTED"


class BaseBroker(ABC):
    """
    Abstract broker interface. Implement this for each broker.
    All prices are in INR. All quantities are integer shares.
    """

    @abstractmethod
    def login(self) -> bool:
        """Authenticate with the broker API. Return True on success."""
        pass

    @abstractmethod
    def get_stock_price(self, symbol: str, exchange: str = "NSE") -> Optional[float]:
        """
        Get the current LTP (Last Traded Price) of a stock in INR.
        Returns None if the symbol doesn't exist or API fails.
        """
        pass

    @abstractmethod
    def get_inr_balance(self) -> float:
        """
        Get available cash balance in INR (available for trading today).
        For intraday this is the margin available.
        """
        pass

    @abstractmethod
    def get_stock_quantity(self, symbol: str) -> int:
        """
        Get the number of shares currently held for a given stock symbol.
        Returns 0 if none held.
        """
        pass

    @abstractmethod
    def buy_stock(
        self,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NSE",
        order_type: str = "LIMIT",
        trade_type: str = "INTRADAY",
    ) -> Optional[Order]:
        """
        Place a buy order.
        - order_type: "LIMIT" or "MARKET"
        - trade_type: "INTRADAY" (MIS) or "DELIVERY" (CNC)
        Returns the completed Order on fill, or None on failure.
        """
        pass

    @abstractmethod
    def sell_stock(
        self,
        symbol: str,
        quantity: int,
        price: float,
        exchange: str = "NSE",
        order_type: str = "LIMIT",
        trade_type: str = "INTRADAY",
    ) -> Optional[Order]:
        """
        Place a sell order.
        Returns the completed Order on fill, or None on failure.
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True on success."""
        pass

    @abstractmethod
    def get_order_status(self, order_id: str) -> Optional[Order]:
        """Fetch the latest status of a placed order."""
        pass

    @abstractmethod
    def is_circuit_breaker_hit(self, symbol: str, exchange: str = "NSE") -> bool:
        """
        Check if a stock has hit its upper or lower circuit limit.
        If True, the bot should skip this stock (can't trade it).
        """
        pass

    def get_effective_fee_pct(self, trade_type: str = "INTRADAY") -> float:
        """
        Returns the total effective fee percentage for ONE SIDE of a trade.
        The auto_trader doubles this for the round-trip calculation.

        Indian Intraday (MIS) — per side approximate breakdown:
          Brokerage (₹20 flat on ₹50k)  ≈ 0.040%
          STT (sell side only)            = 0.025% (only on sell, ~0.0125% averaged)
          NSE Exchange charges            = 0.003%
          GST on brokerage+exchange       ≈ 0.008%
          SEBI charges                    = 0.0001%
          Stamp duty (buy side only)      = 0.003% (averaged ≈ 0.0015%)
          ─────────────────────────────────────────
          Per-side total ≈ 0.065%  →  round-trip ≈ 0.13%

        Indian Delivery (CNC) — per side approximate breakdown:
          Brokerage (₹20 flat on ₹50k)  ≈ 0.040%
          STT (both sides)               = 0.100%   ← largest cost!
          NSE Exchange charges           = 0.003%
          GST on brokerage+exchange      ≈ 0.008%
          SEBI charges                   = 0.0001%
          Stamp duty (buy side)          = 0.015% (averaged ≈ 0.0075%)
          ─────────────────────────────────────────
          Per-side total ≈ 0.158%  →  round-trip ≈ 0.32%

        Note: scout_margin should comfortably exceed the round-trip fee.
          Recommended intraday  scout_margin: 0.3%
          Recommended delivery  scout_margin: 0.8%
        """
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.00065   # 0.065% per side → 0.13% round-trip
        return 0.00158       # 0.158% per side → 0.32% round-trip
