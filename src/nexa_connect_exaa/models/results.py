"""Trade and market result models for the EXAA Trading API."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class TradeResult(BaseModel):
    """A single trade result entry for a specific account and product.

    Args:
        product_id: Exchange-assigned product identifier.
        account_id: Trade account that placed the order.
        price: Clearing price in EUR/MWh.
        volume_awarded: Volume awarded at clearing in MWh/h. Positive = buy,
            negative = sell.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    account_id: str = Field(alias="accountId")
    price: Decimal
    volume_awarded: Decimal = Field(alias="volumeAwarded")


class MarketResult(BaseModel):
    """Market-wide clearing result for a single product and price zone.

    Args:
        product_id: Exchange-assigned product identifier.
        price_zone: Price zone (e.g. ``"AT"``, ``"DE"``, ``"NL"``).
        price: Market clearing price in EUR/MWh.
        volume: Total cleared volume in MWh/h.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    price_zone: str = Field(alias="priceZone")
    price: Decimal
    volume: Decimal


class TradeConfirmation(BaseModel):
    """Final settlement confirmation for a specific account and product.

    Trade confirmations are issued after the post-trading phase (Classic) or
    after finalisation (Market Coupling).

    Args:
        product_id: Exchange-assigned product identifier.
        account_id: Trade account.
        price: Final confirmed price in EUR/MWh.
        volume: Final confirmed volume in MWh/h.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    account_id: str = Field(alias="accountId")
    price: Decimal
    volume: Decimal
