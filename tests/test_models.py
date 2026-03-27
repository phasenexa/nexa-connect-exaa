"""Tests for Pydantic model serialisation and deserialisation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest
from nexa_connect_exaa.models.auction import (
    Auction,
    DeliveryTimePeriod,
)
from nexa_connect_exaa.models.orders import (
    AccountOrders,
    OrderSubmission,
    PriceVolumePair,
    ProductTypeOrders,
)
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)


class TestPriceVolumePair:
    def test_decimal_price_serialises_as_float(self) -> None:
        pvp = PriceVolumePair(price=Decimal("40.50"), volume=Decimal("100.0"))
        dumped = pvp.model_dump(mode="json")
        assert dumped["price"] == 40.5
        assert isinstance(dumped["price"], float)
        assert dumped["volume"] == 100.0
        assert isinstance(dumped["volume"], float)

    def test_market_order_price_serialises_as_string(self) -> None:
        pvp = PriceVolumePair(price="M", volume=Decimal("100.0"))
        dumped = pvp.model_dump(mode="json")
        assert dumped["price"] == "M"
        assert isinstance(dumped["price"], str)

    def test_invalid_string_price_raises(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            PriceVolumePair(price="NOTM", volume=Decimal("100.0"))

    def test_roundtrip_from_dict(self) -> None:
        data = {"price": 40.5, "volume": 250.0}
        pvp = PriceVolumePair.model_validate(data)
        assert pvp.volume == Decimal("250.0")


class TestAccountOrders15MinAlias:
    def test_quarter_hourly_serialises_as_15min_key(self) -> None:
        orders = AccountOrders(
            account_id="APTAP1",
            quarter_hourly_products=ProductTypeOrders(
                type_of_order="STEP",
                products=[],
            ),
        )
        dumped = orders.model_dump(by_alias=True, mode="json", exclude_none=True)
        assert "15minProducts" in dumped
        assert "quarter_hourly_products" not in dumped

    def test_deserialise_15min_key(self) -> None:
        data = {
            "accountId": "APTAP1",
            "affected": False,
            "15minProducts": {
                "typeOfOrder": "STEP",
                "products": [],
            },
        }
        orders = AccountOrders.model_validate(data)
        assert orders.quarter_hourly_products is not None
        assert orders.quarter_hourly_products.type_of_order == "STEP"

    def test_hourly_products_none_when_absent(self) -> None:
        orders = AccountOrders(account_id="APTAP1")
        assert orders.hourly_products is None
        assert orders.block_products is None
        assert orders.quarter_hourly_products is None


class TestOrderSubmission:
    def test_by_alias_serialisation(self) -> None:
        submission = OrderSubmission.build(
            account_id="APTAP1",
            hourly_products={
                "typeOfOrder": "LINEAR",
                "products": [
                    {
                        "productId": "hEXA10",
                        "fillOrKill": False,
                        "priceVolumePairs": [{"price": "40.00", "volume": "250.0"}],
                    }
                ],
            },
        )
        dumped = submission.model_dump(by_alias=True, mode="json", exclude_none=True)
        account = dumped["orders"][0]
        assert account["accountId"] == "APTAP1"
        hourly = account["hourlyProducts"]
        assert hourly["typeOfOrder"] == "LINEAR"
        pair = hourly["products"][0]["priceVolumePairs"][0]
        assert pair["price"] == 40.0  # float, not string
        assert isinstance(pair["price"], float)

    def test_build_with_ptype_orders_instance(self) -> None:
        ptype = ProductTypeOrders(type_of_order="STEP", products=[])
        submission = OrderSubmission.build(account_id="X", block_products=ptype)
        assert submission.orders[0].block_products is not None


class TestAuction15MinAlias:
    def test_quarter_hourly_products_deserialise(self) -> None:
        data = {
            "id": "Classic_2026-04-01",
            "auctionType": "CLASSIC",
            "state": "TRADE_OPEN",
            "deliveryDay": "2026-04-01",
            "tradingDay": "2026-03-31",
            "15minProducts": [
                {
                    "productId": "qEXA01_1",
                    "deliveryTimePeriods": [
                        {
                            "start": "2026-04-01T00:00:00+01:00",
                            "end": "2026-04-01T00:15:00+01:00",
                        }
                    ],
                }
            ],
        }
        auction = Auction.model_validate(data)
        assert len(auction.quarter_hourly_products) == 1
        assert auction.quarter_hourly_products[0].product_id == "qEXA01_1"

    def test_quarter_hourly_defaults_to_empty_list(self) -> None:
        data = {
            "id": "MC_2026-04-01",
            "auctionType": "MARKET_COUPLING",
            "state": "TRADE_OPEN",
            "deliveryDay": "2026-04-01",
            "tradingDay": "2026-03-31",
        }
        auction = Auction.model_validate(data)
        assert auction.quarter_hourly_products == []


class TestDeliveryTimePeriod:
    def test_timezone_aware_required(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            DeliveryTimePeriod(
                start=datetime(2026, 4, 1, 0, 0, 0),  # naive
                end=datetime(2026, 4, 1, 1, 0, 0),
            )

    def test_parses_iso_with_offset(self) -> None:
        period = DeliveryTimePeriod.model_validate(
            {
                "start": "2026-04-01T09:00:00+01:00",
                "end": "2026-04-01T10:00:00+01:00",
            }
        )
        assert period.start.tzinfo is not None
        assert period.end.tzinfo is not None


class TestResultModels:
    def test_trade_result_decimal_from_float(self) -> None:
        result = TradeResult.model_validate(
            {
                "productId": "hEXA10",
                "accountId": "APTAP1",
                "price": 42.5,
                "volumeAwarded": 200.0,
            }
        )
        assert isinstance(result.price, Decimal)
        assert isinstance(result.volume_awarded, Decimal)

    def test_market_result_extra_fields_allowed(self) -> None:
        result = MarketResult.model_validate(
            {
                "productId": "hEXA10",
                "priceZone": "AT",
                "price": 42.5,
                "volume": 1000.0,
                "unknownField": "ignored",
            }
        )
        assert result.price_zone == "AT"

    def test_trade_confirmation_fields(self) -> None:
        conf = TradeConfirmation.model_validate(
            {
                "productId": "hEXA10",
                "accountId": "APTAP1",
                "price": 42.5,
                "volume": 200.0,
            }
        )
        assert conf.product_id == "hEXA10"
        assert conf.account_id == "APTAP1"
