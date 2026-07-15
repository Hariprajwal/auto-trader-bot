from sqlalchemy import Boolean, Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Pair(Base):
    __tablename__ = "pairs"

    id = Column(Integer, primary_key=True)
    from_stock_id = Column(String, ForeignKey("stocks.symbol"))
    to_stock_id = Column(String, ForeignKey("stocks.symbol"))
    ratio = Column(Float, nullable=True)
    enabled = Column(Boolean, default=True)

    from_stock = relationship("Stock", foreign_keys=[from_stock_id])
    to_stock = relationship("Stock", foreign_keys=[to_stock_id])

    def __init__(self, from_stock, to_stock):
        self.from_stock = from_stock
        self.to_stock = to_stock

    def __repr__(self):
        return f"<Pair {self.from_stock_id} → {self.to_stock_id} ratio={self.ratio}>"

    def info(self):
        return {
            "from_stock": self.from_stock_id,
            "to_stock": self.to_stock_id,
            "ratio": self.ratio,
        }
