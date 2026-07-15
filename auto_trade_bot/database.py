import json
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Union

from sqlalchemy import create_engine, func
from sqlalchemy.orm import Session, scoped_session, sessionmaker

from .config import Config
from .logger import Logger
from .models import *


class Database:
    def __init__(self, logger: Logger, config: Config, uri="sqlite:///data/stock_trading.db"):
        self.logger = logger
        self.config = config
        os.makedirs("data", exist_ok=True)
        self.engine = create_engine(uri)
        self.SessionMaker = sessionmaker(bind=self.engine)

    @contextmanager
    def db_session(self):
        session: Session = scoped_session(self.SessionMaker)
        yield session
        session.commit()
        session.close()

    def set_stocks(self, symbols: List[str]):
        with self.db_session() as session:
            stocks: List[Stock] = session.query(Stock).all()
            for stock in stocks:
                if stock.symbol not in symbols:
                    stock.enabled = False
            for symbol in symbols:
                stock = next((s for s in stocks if s.symbol == symbol), None)
                if stock is None:
                    session.add(Stock(symbol))
                else:
                    stock.enabled = True

        with self.db_session() as session:
            stocks: List[Stock] = session.query(Stock).filter(Stock.enabled).all()
            for from_stock in stocks:
                for to_stock in stocks:
                    if from_stock != to_stock:
                        pair = session.query(Pair).filter(
                            Pair.from_stock_id == from_stock.symbol,
                            Pair.to_stock_id == to_stock.symbol
                        ).first()
                        if pair is None:
                            session.add(Pair(from_stock, to_stock))

    def get_stocks(self, only_enabled=True) -> List[Stock]:
        with self.db_session() as session:
            if only_enabled:
                stocks = session.query(Stock).filter(Stock.enabled).all()
            else:
                stocks = session.query(Stock).all()
            session.expunge_all()
            return stocks

    def get_stock(self, stock: Union[Stock, str]) -> Stock:
        if isinstance(stock, Stock):
            return stock
        with self.db_session() as session:
            s = session.query(Stock).get(stock)
            session.expunge(s)
            return s

    def set_current_stock(self, stock: Union[Stock, str]):
        stock = self.get_stock(stock)
        with self.db_session() as session:
            if isinstance(stock, Stock):
                stock = session.merge(stock)
            cs = CurrentStock(stock)
            session.add(cs)

    def get_current_stock(self) -> Optional[Stock]:
        with self.db_session() as session:
            current = session.query(CurrentStock).order_by(CurrentStock.datetime.desc()).first()
            if current is None:
                return None
            stock = current.stock
            session.expunge(stock)
            return stock

    def get_pair(self, from_stock: Union[Stock, str], to_stock: Union[Stock, str]):
        from_stock = self.get_stock(from_stock)
        to_stock = self.get_stock(to_stock)
        with self.db_session() as session:
            pair = session.query(Pair).filter(
                Pair.from_stock_id == from_stock.symbol,
                Pair.to_stock_id == to_stock.symbol
            ).first()
            session.expunge(pair)
            return pair

    def get_pairs_from(self, from_stock: Union[Stock, str], only_enabled=True) -> List[Pair]:
        from_stock = self.get_stock(from_stock)
        with self.db_session() as session:
            pairs = session.query(Pair).filter(Pair.from_stock_id == from_stock.symbol)
            if only_enabled:
                pairs = pairs.filter(Pair.enabled.is_(True))
            pairs = pairs.all()
            session.expunge_all()
            return pairs

    def log_scout(self, pair: Pair, target_ratio: float, current_stock_price: float, other_stock_price: float):
        with self.db_session() as session:
            pair = session.merge(pair)
            sh = ScoutHistory(pair, target_ratio, current_stock_price, other_stock_price)
            session.add(sh)

    def prune_scout_history(self):
        time_diff = datetime.now() - timedelta(hours=self.config.SCOUT_HISTORY_PRUNE_TIME)
        with self.db_session() as session:
            session.query(ScoutHistory).filter(ScoutHistory.datetime < time_diff).delete()

    def prune_value_history(self):
        with self.db_session() as session:
            hourly = session.query(StockValue).group_by(
                StockValue.stock_id, func.strftime("%H", StockValue.datetime)
            ).all()
            for e in hourly:
                e.interval = Interval.HOURLY

            daily = session.query(StockValue).group_by(
                StockValue.stock_id, func.date(StockValue.datetime)
            ).all()
            for e in daily:
                e.interval = Interval.DAILY

            time_diff = datetime.now() - timedelta(hours=24)
            session.query(StockValue).filter(
                StockValue.interval == Interval.MINUTELY, StockValue.datetime < time_diff
            ).delete()

            time_diff = datetime.now() - timedelta(days=28)
            session.query(StockValue).filter(
                StockValue.interval == Interval.HOURLY, StockValue.datetime < time_diff
            ).delete()

    def create_database(self):
        Base.metadata.create_all(self.engine)

    def start_trade_log(self, from_stock: Stock, to_stock: Stock, selling: bool):
        return TradeLog(self, from_stock, to_stock, selling)


class TradeLog:
    def __init__(self, db: Database, from_stock: Stock, to_stock: Stock, selling: bool):
        self.db = db
        with self.db.db_session() as session:
            from_stock = session.merge(from_stock)
            to_stock = session.merge(to_stock)
            self.trade = Trade(from_stock, to_stock, selling)
            session.add(self.trade)
            session.flush()

    def set_ordered(self, shares_starting, inr_starting_balance, shares_traded):
        with self.db.db_session() as session:
            trade = session.merge(self.trade)
            trade.shares_starting = shares_starting
            trade.shares_traded   = shares_traded
            trade.inr_starting    = inr_starting_balance
            trade.state = TradeState.ORDERED

    def set_complete(self, inr_exchanged):
        with self.db.db_session() as session:
            trade = session.merge(self.trade)
            trade.inr_exchanged = inr_exchanged
            trade.state = TradeState.COMPLETE

    def set_failed(self):
        with self.db.db_session() as session:
            trade = session.merge(self.trade)
            trade.state = TradeState.FAILED
