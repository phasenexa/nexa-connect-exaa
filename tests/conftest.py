"""Shared test fixtures for nexa-connect-exaa tests."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest
from nexa_connect_exaa.models.auction import (
    Auction,
    AuctionState,
    AuctionType,
    DeliveryTimePeriod,
    ProductInfo,
    TradeAccount,
)
from nexa_connect_exaa.models.orders import (
    AccountOrders,
    OrderSubmission,
    PriceVolumePair,
    ProductOrder,
    ProductTypeOrders,
)
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)


def _dt(hour: int, tz_offset: int = 1) -> datetime:
    """Helper to build a timezone-aware datetime."""
    from datetime import timedelta

    tz = timezone(timedelta(hours=tz_offset))
    return datetime(2026, 4, 1, hour, 0, 0, tzinfo=tz)


@pytest.fixture
def delivery_period() -> DeliveryTimePeriod:
    """A single delivery time period."""
    return DeliveryTimePeriod(start=_dt(9), end=_dt(10))


@pytest.fixture
def hourly_product(delivery_period: DeliveryTimePeriod) -> ProductInfo:
    """A single hourly product."""
    return ProductInfo(
        product_id="hEXA10",
        delivery_time_periods=[delivery_period],
    )


@pytest.fixture
def classic_auction(hourly_product: ProductInfo) -> Auction:
    """A Classic auction in TRADE_OPEN state."""
    return Auction(
        id="Classic_2026-04-01",
        auction_type=AuctionType.CLASSIC,
        state=AuctionState.TRADE_OPEN,
        delivery_day=date(2026, 4, 1),
        trading_day=date(2026, 3, 31),
        hourly_products=[hourly_product],
        block_products=[],
        quarter_hourly_products=[],
        trade_accounts=[
            TradeAccount(account_id="APTAP1"),
        ],
    )


@pytest.fixture
def mc_auction(hourly_product: ProductInfo) -> Auction:
    """A Market Coupling auction in TRADE_OPEN state."""
    return Auction(
        id="MC_2026-04-01",
        auction_type=AuctionType.MARKET_COUPLING,
        state=AuctionState.TRADE_OPEN,
        delivery_day=date(2026, 4, 1),
        trading_day=date(2026, 3, 31),
        hourly_products=[hourly_product],
        block_products=[],
        quarter_hourly_products=[],
        trade_accounts=[
            TradeAccount(account_id="APTAP1"),
        ],
    )


@pytest.fixture
def price_volume_pair() -> PriceVolumePair:
    """A single price/volume step."""
    return PriceVolumePair(price=Decimal("40.00"), volume=Decimal("250.0"))


@pytest.fixture
def product_order(price_volume_pair: PriceVolumePair) -> ProductOrder:
    """A product order with one step."""
    return ProductOrder(
        product_id="hEXA10",
        fill_or_kill=False,
        price_volume_pairs=[price_volume_pair],
    )


@pytest.fixture
def order_submission(product_order: ProductOrder) -> OrderSubmission:
    """A simple order submission for one account."""
    return OrderSubmission(
        orders=[
            AccountOrders(
                account_id="APTAP1",
                hourly_products=ProductTypeOrders(
                    type_of_order="LINEAR",
                    products=[product_order],
                ),
            )
        ]
    )


@pytest.fixture
def trade_result() -> TradeResult:
    """A single trade result."""
    return TradeResult(
        product_id="hEXA10",
        account_id="APTAP1",
        price=Decimal("42.50"),
        volume_awarded=Decimal("200.0"),
    )


@pytest.fixture
def market_result() -> MarketResult:
    """A single market result."""
    return MarketResult(
        product_id="hEXA10",
        price_zone="AT",
        price=Decimal("42.50"),
        volume=Decimal("1000.0"),
    )


@pytest.fixture
def trade_confirmation() -> TradeConfirmation:
    """A single trade confirmation."""
    return TradeConfirmation(
        product_id="hEXA10",
        account_id="APTAP1",
        price=Decimal("42.50"),
        volume=Decimal("200.0"),
    )
