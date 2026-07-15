from sqlalchemy import Boolean, Column, String

from .base import Base


class Stock(Base):
    __tablename__ = "stocks"

    symbol = Column(String, primary_key=True)
    enabled = Column(Boolean, default=True)

    def __init__(self, symbol: str, enabled: bool = True):
        self.symbol = symbol
        self.enabled = enabled

    def __repr__(self):
        return f"<Stock {self.symbol}>"

    def __str__(self):
        return self.symbol

    def __add__(self, other):
        return f"{self.symbol}{other}"

    def __eq__(self, other):
        if isinstance(other, Stock):
            return self.symbol == other.symbol
        return self.symbol == other

    def __hash__(self):
        return hash(self.symbol)

    def info(self):
        return {"symbol": self.symbol, "enabled": self.enabled}
