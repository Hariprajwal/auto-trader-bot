"""
StockValue model — snapshots of portfolio value over time.
Used for tracking how your total INR value changes as trades happen.

Author  : K R HARI PRAJWAL
License : MIT
"""
import enum
from datetime import datetime as dt

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Interval(enum.Enum):
    MINUTELY = "minutely"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class StockValue(Base):
    __tablename__ = "stock_values"

    id = Column(Integer, primary_key=True)
    stock_id = Column(String, ForeignKey("stocks.symbol"))
    balance = Column(Float)          # Number of shares held
    inr_value = Column(Float)        # LTP (price in INR) at this snapshot
    interval = Column(Enum(Interval), default=Interval.MINUTELY)
    datetime = Column(DateTime)

    stock = relationship("Stock")

    def __init__(
        self,
        stock,
        balance: float,
        inr_value: float,
        interval: Interval = Interval.MINUTELY,
        datetime: dt = None,
    ):
        self.stock = stock
        self.balance = balance
        self.inr_value = inr_value
        self.interval = interval
        self.datetime = datetime if datetime is not None else dt.now()

    @property
    def total_inr(self) -> float:
        """Total INR value of this holding = shares × price."""
        return (self.balance or 0) * (self.inr_value or 0)

    def info(self):
        return {
            "stock": self.stock_id,
            "shares": self.balance,
            "price_inr": self.inr_value,
            "total_inr": self.total_inr,
            "interval": self.interval.value,
            "datetime": self.datetime.isoformat(),
        }
