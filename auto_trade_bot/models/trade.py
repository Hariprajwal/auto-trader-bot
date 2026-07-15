"""
Trade model — records every buy/sell order with its full lifecycle state.

States:  INITIATED → ORDERED → COMPLETE
                              → FAILED

Author  : K R HARI PRAJWAL
License : MIT
"""
import enum
from datetime import datetime as dt

from sqlalchemy import Boolean, Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class TradeState(enum.Enum):
    INITIATED = "initiated"
    ORDERED   = "ordered"
    COMPLETE  = "complete"
    FAILED    = "failed"


class Trade(Base):
    __tablename__ = "trades"

    id           = Column(Integer, primary_key=True)
    from_stock_id = Column(String, ForeignKey("stocks.symbol"))
    to_stock_id   = Column(String, ForeignKey("stocks.symbol"))
    selling       = Column(Boolean)   # True = sell leg, False = buy leg

    state = Column(Enum(TradeState), default=TradeState.INITIATED)

    # ── Trade legs ─────────────────────────────────────────────────────────────
    shares_starting   = Column(Float, nullable=True)   # Shares held before the trade
    shares_traded     = Column(Float, nullable=True)   # Shares actually transacted
    inr_starting      = Column(Float, nullable=True)   # INR balance before the trade
    inr_exchanged     = Column(Float, nullable=True)   # Total INR value of the trade

    datetime = Column(DateTime)

    from_stock = relationship("Stock", foreign_keys=[from_stock_id])
    to_stock   = relationship("Stock", foreign_keys=[to_stock_id])

    def __init__(self, from_stock, to_stock, selling: bool):
        self.from_stock = from_stock
        self.to_stock   = to_stock
        self.selling    = selling
        self.datetime   = dt.now()

    def info(self) -> dict:
        return {
            "from_stock":       self.from_stock_id,
            "to_stock":         self.to_stock_id,
            "selling":          self.selling,
            "state":            self.state.value,
            "shares_starting":  self.shares_starting,
            "shares_traded":    self.shares_traded,
            "inr_starting":     self.inr_starting,
            "inr_exchanged":    self.inr_exchanged,
            "datetime":         self.datetime.isoformat(),
        }
