"""Tests for endpoint functions using respx to mock httpx."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import httpx
import pytest
import respx
from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.endpoints.auctions import get_auction, get_auctions
from nexa_connect_exaa.endpoints.orders import delete_orders, submit_orders
from nexa_connect_exaa.endpoints.results import (
    get_market_results,
    get_trade_confirmations,
    get_trade_results,
)
from nexa_connect_exaa.exceptions import (
    AuctionNotFoundError,
    AuctionNotOpenError,
    EXAAServerError,
    MonotonicViolationError,
)
from nexa_connect_exaa.models.orders import (
    AccountOrders,
    OrderSubmission,
)

BASE_URL = "https://test-trade.exaa.at"
TRADING_BASE = f"{BASE_URL}/exaa-trading-api/V1"


@pytest.fixture
def config() -> EXAAConfig:
    return EXAAConfig(environment=Environment.TEST)


@pytest.fixture
def session(config: EXAAConfig) -> HTTPSession:
    s = HTTPSession(config)
    # Manually open sync client and set token for tests
    s._sync_client = httpx.Client()
    s._async_client = httpx.AsyncClient()
    s.set_token("test-token")
    return s


CLASSIC_AUCTION_JSON = {
    "id": "Classic_2026-04-01",
    "auctionType": "CLASSIC",
    "state": "TRADE_OPEN",
    "deliveryDay": "2026-04-01",
    "tradingDay": "2026-03-31",
    "hourlyProducts": [
        {
            "productId": "hEXA10",
            "deliveryTimePeriods": [
                {
                    "start": "2026-04-01T09:00:00+01:00",
                    "end": "2026-04-01T10:00:00+01:00",
                }
            ],
        }
    ],
    "blockProducts": [],
    "15minProducts": [],
    "tradeAccounts": [{"accountId": "APTAP1", "constraints": {}}],
}


class TestGetAuctions:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_list_of_auctions(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json=[CLASSIC_AUCTION_JSON])
        )
        auctions = await get_auctions(session)
        assert len(auctions) == 1
        assert auctions[0].id == "Classic_2026-04-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_passes_delivery_day_param(self, session: HTTPSession) -> None:
        route = respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json=[CLASSIC_AUCTION_JSON])
        )
        await get_auctions(session, delivery_day=date(2026, 4, 1))
        assert route.called
        assert "deliveryDay=2026-04-01" in str(route.calls.last.request.url)

    @pytest.mark.asyncio
    @respx.mock
    async def test_handles_wrapper_dict_response(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json={"auctions": [CLASSIC_AUCTION_JSON]})
        )
        auctions = await get_auctions(session)
        assert len(auctions) == 1


class TestGetAuction:
    @pytest.mark.asyncio
    @respx.mock
    async def test_returns_auction(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01").mock(
            return_value=httpx.Response(200, json=CLASSIC_AUCTION_JSON)
        )
        auction = await get_auction(session, "Classic_2026-04-01")
        assert auction.id == "Classic_2026-04-01"

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_auction_not_found(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Unknown_2026-04-01").mock(
            return_value=httpx.Response(
                404,
                json={"errors": [{"code": "F006", "message": "Auction not found"}]},
            )
        )
        with pytest.raises(AuctionNotFoundError):
            await get_auction(session, "Unknown_2026-04-01")


class TestSubmitOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_submits_orders_and_returns_response(self, session: HTTPSession) -> None:
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1", affected=False)])
        response_json = {"orders": [{"accountId": "APTAP1", "affected": True}]}
        respx.post(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(200, json=response_json)
        )
        result = await submit_orders(session, "Classic_2026-04-01", orders)
        assert result.orders[0].affected is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_auction_not_open(self, session: HTTPSession) -> None:
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1", affected=False)])
        respx.post(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(
                409,
                json={"errors": [{"code": "F008", "message": "Auction is not open"}]},
            )
        )
        with pytest.raises(AuctionNotOpenError):
            await submit_orders(session, "Classic_2026-04-01", orders)

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_monotonic_violation(self, session: HTTPSession) -> None:
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1", affected=False)])
        respx.post(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(
                400,
                json={
                    "errors": [
                        {
                            "code": "F010",
                            "message": "Monotonic rule violated",
                            "path": "orders[0].priceVolumePairs[1]",
                        }
                    ]
                },
            )
        )
        with pytest.raises(MonotonicViolationError) as exc_info:
            await submit_orders(session, "Classic_2026-04-01", orders)
        assert exc_info.value.path == "orders[0].priceVolumePairs[1]"


class TestDeleteOrders:
    @pytest.mark.asyncio
    @respx.mock
    async def test_delete_returns_none_on_204(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(204)
        )
        result = await delete_orders(session, "Classic_2026-04-01", ["APTAP1"])
        assert result is None


class TestGetResults:
    @pytest.mark.asyncio
    @respx.mock
    async def test_get_trade_results(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/results/trade").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "productId": "hEXA10",
                        "accountId": "APTAP1",
                        "price": 42.5,
                        "volumeAwarded": 200.0,
                    }
                ],
            )
        )
        results = await get_trade_results(session, "Classic_2026-04-01")
        assert len(results) == 1
        assert results[0].price == Decimal("42.5")

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_market_results(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/results/market").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "productId": "hEXA10",
                        "priceZone": "AT",
                        "price": 42.5,
                        "volume": 1000.0,
                    }
                ],
            )
        )
        results = await get_market_results(session, "Classic_2026-04-01")
        assert results[0].price_zone == "AT"

    @pytest.mark.asyncio
    @respx.mock
    async def test_get_trade_confirmations(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/results/tradeConfirmations").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "productId": "hEXA10",
                        "accountId": "APTAP1",
                        "price": 42.5,
                        "volume": 200.0,
                    }
                ],
            )
        )
        confirmations = await get_trade_confirmations(session, "Classic_2026-04-01")
        assert len(confirmations) == 1


class TestRetryLogic:
    @pytest.mark.asyncio
    @respx.mock
    async def test_retries_on_500_then_succeeds(self, session: HTTPSession) -> None:
        # First call: 500, second call: 200
        route = respx.get(f"{TRADING_BASE}/auctions").mock(
            side_effect=[
                httpx.Response(500, json={"errors": [{"code": "U001", "message": "err"}]}),
                httpx.Response(200, json=[CLASSIC_AUCTION_JSON]),
            ]
        )
        # Disable retry backoff for test speed
        session._config.retry_backoff_factor = 0.0
        auctions = await get_auctions(session)
        assert len(auctions) == 1
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_raises_after_max_retries_exhausted(self, session: HTTPSession) -> None:
        session._config.max_retries = 1
        session._config.retry_backoff_factor = 0.0
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(
                500, json={"errors": [{"code": "U001", "message": "server error"}]}
            )
        )
        with pytest.raises(EXAAServerError):
            await get_auctions(session)
