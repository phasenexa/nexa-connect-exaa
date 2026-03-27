"""nexa-connect-exaa — Python client for the EXAA Trading API.

Quickstart::

    from nexa_connect_exaa import EXAAClient, CertificateAuth

    with EXAAClient(auth=CertificateAuth(
        username="trader1",
        password="1234",
        private_key_path="key.pem",
        certificate_path="cert.pem",
    )) as client:
        auctions = client.get_auctions(delivery_day="2026-04-01")
"""

from nexa_connect_exaa.auth import CertificateAuth, RSAAuth
from nexa_connect_exaa.client import AsyncEXAAClient, EXAAClient
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.exceptions import (
    AuctionNotFoundError,
    AuctionNotOpenError,
    EXAAAuthError,
    EXAAConnectionError,
    EXAAError,
    EXAAFunctionalError,
    EXAARequestError,
    EXAAServerError,
    EXAASyntaxError,
    EXAAValueError,
    InvalidProductError,
    MonotonicViolationError,
    PollingTimeoutError,
)
from nexa_connect_exaa.models.auction import (
    Auction,
    AuctionState,
    AuctionType,
    DeliveryTimePeriod,
    ProductInfo,
    TradeAccount,
)
from nexa_connect_exaa.models.common import Units
from nexa_connect_exaa.models.orders import (
    AccountOrders,
    OrderSubmission,
    PriceVolumePair,
    ProductOrder,
    ProductTypeOrders,
)
from nexa_connect_exaa.models.posttrading import (
    PostTradingInfo,
    PostTradingOrder,
    PostTradingProductInfo,
)
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)

__all__ = [
    # Clients
    "AsyncEXAAClient",
    "EXAAClient",
    # Auth
    "CertificateAuth",
    "RSAAuth",
    # Config
    "EXAAConfig",
    "Environment",
    # Exceptions
    "AuctionNotFoundError",
    "AuctionNotOpenError",
    "EXAAAuthError",
    "EXAAConnectionError",
    "EXAAError",
    "EXAAFunctionalError",
    "EXAARequestError",
    "EXAAServerError",
    "EXAASyntaxError",
    "EXAAValueError",
    "InvalidProductError",
    "MonotonicViolationError",
    "PollingTimeoutError",
    # Auction models
    "Auction",
    "AuctionState",
    "AuctionType",
    "DeliveryTimePeriod",
    "ProductInfo",
    "TradeAccount",
    # Order models
    "AccountOrders",
    "OrderSubmission",
    "PriceVolumePair",
    "ProductOrder",
    "ProductTypeOrders",
    # Result models
    "MarketResult",
    "TradeConfirmation",
    "TradeResult",
    # Post-trading models
    "PostTradingInfo",
    "PostTradingOrder",
    "PostTradingProductInfo",
    # Enums
    "Units",
]
