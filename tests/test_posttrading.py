"""Tests for post-trading endpoint functions."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx
from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.endpoints.posttrading import (
    delete_posttrading_orders,
    get_posttrading_info,
    get_posttrading_orders,
    submit_posttrading_orders,
)
from nexa_connect_exaa.exceptions import EXAAFunctionalError
from nexa_connect_exaa.models.posttrading import PostTradingOrder

BASE_URL = "https://test-trade.exaa.at"
TRADING_BASE = f"{BASE_URL}/exaa-trading-api/V1"

POSTTRADING_INFO_JSON = {
    "auctionId": "Classic_2026-04-01",
    "state": "POSTTRADE_OPEN",
    "products": [
        {
            "productId": "hEXA10",
            "clearingPrice": 42.5,
            "availableVolume": 100.0,
            "deliveryTimePeriods": [
                {
                    "start": "2026-04-01T09:00:00+01:00",
                    "end": "2026-04-01T10:00:00+01:00",
                }
            ],
        }
    ],
}


@pytest.fixture
def session() -> HTTPSession:
    config = EXAAConfig(environment=Environment.TEST, max_retries=0)
    s = HTTPSession(config)
    s._async_client = httpx.AsyncClient()
    s.set_token("test-token")
    return s


class TestGetPostTradingInfo:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_post_trading_info(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading").mock(
            return_value=httpx.Response(200, json=POSTTRADING_INFO_JSON)
        )

        info = await get_posttrading_info(session, "Classic_2026-04-01")
        assert info.auction_id == "Classic_2026-04-01"
        assert len(info.products) == 1
        assert info.products[0].product_id == "hEXA10"
        assert info.products[0].clearing_price == Decimal("42.5")

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_on_mc_auction(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/MC_2026-04-01/postTrading").mock(
            return_value=httpx.Response(
                400,
                json={"errors": [{"code": "F001", "message": "Not Classic auction"}]},
            )
        )
        with pytest.raises(EXAAFunctionalError):
            await get_posttrading_info(session, "MC_2026-04-01")


class TestGetPostTradingOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_list_of_orders(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading/orders").mock(
            return_value=httpx.Response(
                200,
                json=[{"productId": "hEXA10", "accountId": "APTAP1", "volume": 50.0}],
            )
        )
        orders = await get_posttrading_orders(session, "Classic_2026-04-01")
        assert len(orders) == 1
        assert orders[0].product_id == "hEXA10"
        assert orders[0].volume == Decimal("50.0")


class TestSubmitPostTradingOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_submits_and_returns_orders(self, session: HTTPSession) -> None:
        orders = [
            PostTradingOrder(
                product_id="hEXA10",
                account_id="APTAP1",
                volume=Decimal("50.0"),
            )
        ]
        respx.post(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading/orders").mock(
            return_value=httpx.Response(
                200,
                json=[{"productId": "hEXA10", "accountId": "APTAP1", "volume": 50.0}],
            )
        )
        result = await submit_posttrading_orders(session, "Classic_2026-04-01", orders)
        assert len(result) == 1


class TestDeletePostTradingOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_returns_none(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading/orders").mock(
            return_value=httpx.Response(204)
        )
        result = await delete_posttrading_orders(session, "Classic_2026-04-01", ["APTAP1"])
        assert result is None
