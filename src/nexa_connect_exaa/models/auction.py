"""Auction domain models for the EXAA Trading API."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AuctionType(str, Enum):
    """EXAA day-ahead auction type."""

    CLASSIC = "CLASSIC"
    MARKET_COUPLING = "MARKET_COUPLING"


class AuctionState(str, Enum):
    """Lifecycle state of an EXAA auction.

    Classic lifecycle:
    ``TRADE_OPEN`` → ``TRADE_CLOSED`` → ``AUCTIONING`` → ``AUCTIONED`` →
    ``POSTTRADE_OPEN`` → ``POSTTRADE_CLOSED`` → ``POSTAUCTIONING`` →
    ``POSTAUCTIONED`` → ``FINALIZED``

    Market Coupling lifecycle:
    ``TRADE_OPEN`` → ``TRADE_CLOSED`` → ``AUCTIONING`` →
    ``PRELIMINARY_RESULTS`` → ``FINALIZED``

    MC fallback variants:
    ``TRADE_OPEN_FALLBACK`` → ``TRADE_CLOSED_FALLBACK`` →
    ``AUCTIONING_FALLBACK`` → ``AUCTIONED_FALLBACK`` → ``FINALIZED_FALLBACK``
    """

    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSED = "TRADE_CLOSED"
    AUCTIONING = "AUCTIONING"
    AUCTIONED = "AUCTIONED"
    POSTTRADE_OPEN = "POSTTRADE_OPEN"
    POSTTRADE_CLOSED = "POSTTRADE_CLOSED"
    POSTAUCTIONING = "POSTAUCTIONING"
    POSTAUCTIONED = "POSTAUCTIONED"
    FINALIZED = "FINALIZED"
    PRELIMINARY_RESULTS = "PRELIMINARY_RESULTS"
    TRADE_OPEN_FALLBACK = "TRADE_OPEN_FALLBACK"
    TRADE_CLOSED_FALLBACK = "TRADE_CLOSED_FALLBACK"
    AUCTIONING_FALLBACK = "AUCTIONING_FALLBACK"
    AUCTIONED_FALLBACK = "AUCTIONED_FALLBACK"
    FINALIZED_FALLBACK = "FINALIZED_FALLBACK"


class DeliveryTimePeriod(BaseModel):
    """A single contiguous delivery time period.

    Args:
        start: Timezone-aware start of delivery (inclusive).
        end: Timezone-aware end of delivery (exclusive).
    """

    model_config = ConfigDict(populate_by_name=True)

    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def must_be_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure the datetime has timezone information."""
        if v.tzinfo is None:
            raise ValueError("Delivery time periods must be timezone-aware")
        return v


class ProductInfo(BaseModel):
    """Metadata for a single tradeable product within an auction.

    Product IDs are opaque strings assigned by EXAA (e.g. ``"hEXA10"``).
    Never parse a product ID to derive delivery times — always use
    ``delivery_time_periods`` from this model.

    Args:
        product_id: Exchange-assigned product identifier.
        delivery_time_periods: Ordered list of delivery intervals. Block
            products may have non-contiguous periods (e.g. off-peak).
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    delivery_time_periods: list[DeliveryTimePeriod] = Field(
        alias="deliveryTimePeriods", default_factory=list
    )


class AccountConstraints(BaseModel):
    """Account-level trading constraints for an auction.

    The exact fields depend on the auction configuration and are not fully
    documented. Extra fields from the API response are preserved.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class TradeAccount(BaseModel):
    """A trading account eligible to participate in an auction.

    Args:
        account_id: Account identifier (e.g. ``"APTAP1"``).
        constraints: Account-level constraints such as allowed product types
            and volume limits.
    """

    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(alias="accountId")
    constraints: AccountConstraints = Field(default_factory=AccountConstraints)


class Auction(BaseModel):
    """Full detail of an EXAA auction.

    Args:
        id: Auction identifier (e.g. ``"Classic_2026-04-01"``).
        auction_type: Whether this is a Classic or Market Coupling auction.
        state: Current lifecycle state of the auction.
        delivery_day: The day for which energy is being traded (ISO date).
        trading_day: The day on which trading occurs (ISO date).
        hourly_products: Hourly products (``hEXA01``–``hEXA24``).
        block_products: Block products (base, peak, off-peak, etc.).
        quarter_hourly_products: 15-minute products (Classic only).
            Serialised as ``"15minProducts"`` in the EXAA JSON schema.
        trade_accounts: Accounts eligible to trade in this auction.
    """

    model_config = ConfigDict(populate_by_name=True)

    id: str
    auction_type: AuctionType = Field(alias="auctionType")
    state: AuctionState
    delivery_day: date = Field(alias="deliveryDay")
    trading_day: date = Field(alias="tradingDay")
    hourly_products: list[ProductInfo] = Field(alias="hourlyProducts", default_factory=list)
    block_products: list[ProductInfo] = Field(alias="blockProducts", default_factory=list)
    # The JSON key "15minProducts" starts with a digit and cannot be a Python
    # identifier, so we use a Field alias.
    quarter_hourly_products: list[ProductInfo] = Field(alias="15minProducts", default_factory=list)
    trade_accounts: list[TradeAccount] = Field(alias="tradeAccounts", default_factory=list)
