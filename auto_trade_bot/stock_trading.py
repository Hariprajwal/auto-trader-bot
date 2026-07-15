import time

from .brokers import get_broker
from .config import Config
from .database import Database
from .logger import Logger
from .scheduler import SafeScheduler
from .strategies import get_strategy


def main():
    logger = Logger()
    logger.info("=" * 60)
    logger.info("  auto_trade_bot — Indian Stock Market Trading Bot")
    logger.info("=" * 60)

    config = Config()
    db = Database(logger, config)

    # --- Broker setup ---
    logger.info(f"Connecting to broker: {config.BROKER}")
    broker = get_broker(config.BROKER, config, logger)

    if not broker.login():
        logger.error("Failed to login to broker. Check your credentials in user.cfg")
        return

    inr_balance = broker.get_inr_balance()
    logger.info(f"Broker connected. Available balance: ₹{inr_balance:,.2f}")

    # --- Strategy ---
    strategy_cls = get_strategy(config.STRATEGY)
    if strategy_cls is None:
        logger.error(f"Unknown strategy '{config.STRATEGY}'. Check user.cfg.")
        return

    trader = strategy_cls(broker, db, logger, config)
    logger.info(f"Strategy: {config.STRATEGY}")

    # --- DB Setup ---
    logger.info("Initializing database...")
    db.create_database()
    db.set_stocks(config.SUPPORTED_STOCK_LIST)

    # --- Init ---
    trader.initialize()

    logger.info(f"Stocks loaded: {', '.join(config.SUPPORTED_STOCK_LIST)}")
    logger.info(f"Exchange: {config.EXCHANGE} | Trade type: {config.TRADE_TYPE}")
    logger.info(f"Scout margin: {config.SCOUT_MARGIN}% | Sleep: {config.SCOUT_SLEEP_TIME}s")
    logger.info("Bot is running. Press Ctrl+C to stop.\n")

    # --- Scheduler ---
    schedule = SafeScheduler(logger)
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(trader.scout).tag("scouting")
    schedule.every(1).minutes.do(trader.update_values).tag("updating values")
    schedule.every(1).minutes.do(db.prune_scout_history).tag("pruning scout history")
    schedule.every(1).hours.do(db.prune_value_history).tag("pruning value history")

    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
