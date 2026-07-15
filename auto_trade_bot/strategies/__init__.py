from .default_strategy import Strategy as DefaultStrategy
from .multiple_stocks_strategy import Strategy as MultipleStocksStrategy


def get_strategy(strategy_name: str):
    """
    Strategy factory.
    
    Available strategies:
      - "default"          : Hold one stock, rotate when ratio improves
      - "multiple_stocks"  : Hold N stocks, rotate only the weakest one
    
    Author: K R HARI PRAJWAL
    """
    strategies = {
        "default": DefaultStrategy,
        "multiple_stocks": MultipleStocksStrategy,
    }
    strategy_cls = strategies.get(strategy_name.lower(), None)
    if strategy_cls is None:
        print(
            f"ERROR: Unknown strategy '{strategy_name}'. "
            f"Valid options: {', '.join(strategies.keys())}"
        )
    return strategy_cls
