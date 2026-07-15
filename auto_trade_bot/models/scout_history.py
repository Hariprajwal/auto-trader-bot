from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class ScoutHistory(Base):
    __tablename__ = "scout_history"

    id = Column(Integer, primary_key=True)
    pair_id = Column(Integer, ForeignKey("pairs.id"))
    target_ratio = Column(Float)
    current_stock_price = Column(Float)  # INR price
    other_stock_price = Column(Float)    # INR price
    datetime = Column(DateTime)

    pair = relationship("Pair")

    def __init__(self, pair, target_ratio: float, current_stock_price: float, other_stock_price: float):
        self.pair = pair
        self.target_ratio = target_ratio
        self.current_stock_price = current_stock_price
        self.other_stock_price = other_stock_price
        self.datetime = datetime.now()

    def info(self):
        return {
            "pair": self.pair_id,
            "target_ratio": self.target_ratio,
            "current_stock_price": self.current_stock_price,
            "other_stock_price": self.other_stock_price,
            "datetime": self.datetime.isoformat(),
        }
