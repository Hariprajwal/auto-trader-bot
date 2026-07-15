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
        Returns the total effective fee percentage for a trade.
        Includes brokerage, STT, GST, exchange charges, SEBI fees.
        
        Typical values (approximate):
          - Intraday (MIS): ~0.05% per side
          - Delivery (CNC): ~0.15% per side (STT higher)
        
        Override in subclass if your broker has different charges.
        """
        if trade_type.upper() in ("INTRADAY", "MIS"):
            return 0.0005  # 0.05%
        return 0.0015  # 0.15% delivery
