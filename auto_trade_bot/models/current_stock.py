from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class CurrentStock(Base):
    __tablename__ = "current_stock"

    id = Column(Integer, primary_key=True)
    stock_id = Column(String, ForeignKey("stocks.symbol"))
    datetime = Column(DateTime)

    stock = relationship("Stock")

    def __init__(self, stock):
        self.stock = stock
        self.datetime = datetime.now()

    def info(self):
        return {
            "stock": self.stock_id,
            "datetime": self.datetime.isoformat(),
        }
