import enum
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class TradeState(enum.Enum):
    INITIATED = "initiated"
    ORDERED = "ordered"
    COMPLETE = "complete"
    FAILED = "failed"


class Trade(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True)
    from_stock_id = Column(String, ForeignKey("stocks.symbol"))
    to_stock_id = Column(String, ForeignKey("stocks.symbol"))
    selling = Column(Boolean)  # True = selling from_stock, False = buying to_stock

    state = Column(Enum(TradeState), default=TradeState.INITIATED)

    # Quantities
    alt_starting_balance = Column(Float, nullable=True)     # Shares of stock being sold
    alt_trade_amount = Column(Float, nullable=True)         # Shares actually traded
    crypto_starting_balance = Column(Float, nullable=True)  # INR balance before trade
    crypto_trade_amount = Column(Float, nullable=True)      # INR exchanged in trade

    datetime = Column(DateTime)

    from_stock = relationship("Stock", foreign_keys=[from_stock_id])
    to_stock = relationship("Stock", foreign_keys=[to_stock_id])

    def __init__(self, from_stock, to_stock, selling: bool):
        self.from_stock = from_stock
        self.to_stock = to_stock
        self.selling = selling
        self.datetime = datetime.now()

    def info(self):
        return {
            "from_stock": self.from_stock_id,
            "to_stock": self.to_stock_id,
            "selling": self.selling,
            "state": self.state.value,
            "alt_starting_balance": self.alt_starting_balance,
            "alt_trade_amount": self.alt_trade_amount,
            "crypto_starting_balance": self.crypto_starting_balance,
            "crypto_trade_amount": self.crypto_trade_amount,
            "datetime": self.datetime.isoformat(),
        }
