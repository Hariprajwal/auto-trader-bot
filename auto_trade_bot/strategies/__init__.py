from .default_strategy import Strategy


def get_strategy(strategy_name: str):
    strategies = {
        "default": Strategy,
    }
    return strategies.get(strategy_name.lower(), None)
