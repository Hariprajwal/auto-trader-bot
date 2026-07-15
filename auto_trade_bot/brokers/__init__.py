"""
Broker factory — returns the right broker based on config string.
Usage:
    broker = get_broker("angel_one", config)
"""
from .base_broker import BaseBroker, Order
from .angel_one_broker import AngelOneBroker
from .zerodha_broker import ZerodhaBroker
from .upstox_broker import UpstoxBroker
from .dhan_broker import DhanBroker
from .fyers_broker import FyersBroker
from .groww_broker import GrowwBroker


def get_broker(broker_name: str, config, logger=None) -> BaseBroker:
    """
    Instantiate and return the correct broker implementation.
    broker_name: "angel_one" | "zerodha" | "upstox" | "dhan" | "fyers" | "groww"
    """
    name = broker_name.lower().strip().replace(" ", "_").replace("-", "_")

    if name == "angel_one":
        return AngelOneBroker(
            api_key=config.BROKER_API_KEY,
            client_id=config.BROKER_CLIENT_ID,
            password=config.BROKER_PASSWORD,
            totp_secret=config.BROKER_TOTP_SECRET,
            logger=logger,
        )
    elif name == "zerodha":
        return ZerodhaBroker(
            api_key=config.BROKER_API_KEY,
            api_secret=config.BROKER_API_SECRET,
            access_token=getattr(config, "BROKER_ACCESS_TOKEN", None),
            logger=logger,
        )
    elif name == "upstox":
        return UpstoxBroker(
            api_key=config.BROKER_API_KEY,
            api_secret=config.BROKER_API_SECRET,
            redirect_uri=getattr(config, "BROKER_REDIRECT_URI", ""),
            access_token=getattr(config, "BROKER_ACCESS_TOKEN", None),
            logger=logger,
        )
    elif name == "dhan":
        return DhanBroker(
            client_id=config.BROKER_CLIENT_ID,
            access_token=config.BROKER_ACCESS_TOKEN,
            logger=logger,
        )
    elif name == "fyers":
        return FyersBroker(
            client_id=config.BROKER_CLIENT_ID,
            access_token=config.BROKER_ACCESS_TOKEN,
            logger=logger,
        )
    elif name == "groww":
        return GrowwBroker(
            client_id=config.BROKER_CLIENT_ID,
            access_token=config.BROKER_ACCESS_TOKEN,
            logger=logger,
        )
    else:
        raise ValueError(
            f"Unknown broker '{broker_name}'. "
            f"Valid options: angel_one, zerodha, upstox, dhan, fyers, groww"
        )


__all__ = ["get_broker", "BaseBroker", "Order"]
