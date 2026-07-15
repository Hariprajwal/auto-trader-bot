import enum
from datetime import datetime

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer
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
    balance = Column(Float)
    inr_value = Column(Float)  # Price in INR
    btc_value = Column(Float, nullable=True)  # Optional BTC reference, can be None
    interval = Column(Enum(Interval), default=Interval.MINUTELY)
    datetime = Column(DateTime)

    stock = relationship("Stock")

    def __init__(self, stock, balance: float, inr_value: float, btc_value: float = None, interval=Interval.MINUTELY, datetime: datetime = None):
        self.stock = stock
        self.balance = balance
        self.inr_value = inr_value
        self.btc_value = btc_value
        self.interval = interval
        self.datetime = datetime or datetime.now()

    def info(self):
        return {
            "stock": self.stock_id,
            "balance": self.balance,
            "inr_value": self.inr_value,
            "interval": self.interval.value,
            "datetime": self.datetime.isoformat(),
        }


from sqlalchemy import String  # noqa: E402 — needed for ForeignKey string ref
