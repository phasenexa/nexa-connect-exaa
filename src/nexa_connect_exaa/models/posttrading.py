"""Post-trading models for the EXAA Classic auction.

Post-trading is exclusive to the Classic (10:15 CET) auction. Attempting
post-trading operations on a Market Coupling auction will result in an
``EXAAFunctionalError`` (F001) from the API.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from nexa_connect_exaa.models.auction import AuctionState, DeliveryTimePeriod


class PostTradingProductInfo(BaseModel):
    """Information about a product available in the post-trading phase.

    Args:
        product_id: Exchange-assigned product identifier.
        clearing_price: The price at which residual volume is offered, equal
            to the auction clearing price for this product.
        available_volume: Residual volume available for post-trading in MWh/h.
        delivery_time_periods: Delivery intervals for this product.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    clearing_price: Decimal = Field(alias="clearingPrice")
    available_volume: Decimal = Field(alias="availableVolume")
    delivery_time_periods: list[DeliveryTimePeriod] = Field(
        alias="deliveryTimePeriods", default_factory=list
    )


class PostTradingInfo(BaseModel):
    """Overview of the post-trading phase for a Classic auction.

    Args:
        auction_id: Identifier of the parent Classic auction.
        state: Current auction state (expected to be ``POSTTRADE_OPEN`` or
            ``POSTTRADE_CLOSED`` when this endpoint is meaningful).
        products: Products available for post-trading with their clearing
            prices and residual volumes.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    auction_id: str = Field(alias="auctionId")
    state: AuctionState
    products: list[PostTradingProductInfo] = Field(default_factory=list)


class PostTradingOrder(BaseModel):
    """A post-trading order for residual volume in a Classic auction.

    Args:
        product_id: Exchange-assigned product identifier.
        account_id: Trade account submitting the order.
        volume: Volume in MWh/h. Positive = buy, negative = sell.
    """

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    product_id: str = Field(alias="productId")
    account_id: str = Field(alias="accountId")
    volume: Decimal
