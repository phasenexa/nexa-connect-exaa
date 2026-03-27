"""Tests for the synchronous endpoint function variants."""

from __future__ import annotations

import httpx
import pytest
import respx
from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.endpoints.auctions import get_auction_sync, get_auctions_sync
from nexa_connect_exaa.endpoints.orders import (
    delete_orders_sync,
    get_orders_sync,
    submit_orders_sync,
)
from nexa_connect_exaa.endpoints.posttrading import (
    delete_posttrading_orders_sync,
    get_posttrading_info_sync,
    get_posttrading_orders_sync,
    submit_posttrading_orders_sync,
)
from nexa_connect_exaa.endpoints.results import (
    get_market_results_sync,
    get_trade_confirmations_sync,
    get_trade_results_sync,
)
from nexa_connect_exaa.models.orders import AccountOrders, OrderSubmission
from nexa_connect_exaa.models.posttrading import PostTradingOrder

BASE_URL = "https://test-trade.exaa.at"
TRADING_BASE = f"{BASE_URL}/exaa-trading-api/V1"

AUCTION_JSON = {
    "id": "Classic_2026-04-01",
    "auctionType": "CLASSIC",
    "state": "TRADE_OPEN",
    "deliveryDay": "2026-04-01",
    "tradingDay": "2026-03-31",
}


@pytest.fixture
def session() -> HTTPSession:
    config = EXAAConfig(environment=Environment.TEST, max_retries=0)
    s = HTTPSession(config)
    s._sync_client = httpx.Client()
    s.set_token("test-token")
    return s


class TestSyncAuctionEndpoints:
    @respx.mock
    def test_get_auctions_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json=[AUCTION_JSON])
        )
        auctions = get_auctions_sync(session)
        assert len(auctions) == 1

    @respx.mock
    def test_get_auction_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01").mock(
            return_value=httpx.Response(200, json=AUCTION_JSON)
        )
        auction = get_auction_sync(session, "Classic_2026-04-01")
        assert auction.id == "Classic_2026-04-01"


class TestSyncOrderEndpoints:
    @respx.mock
    def test_get_orders_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(
                200, json={"orders": [{"accountId": "APTAP1", "affected": False}]}
            )
        )
        result = get_orders_sync(session, "Classic_2026-04-01")
        assert len(result.orders) == 1

    @respx.mock
    def test_submit_orders_sync(self, session: HTTPSession) -> None:
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1", affected=False)])
        respx.post(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(
                200, json={"orders": [{"accountId": "APTAP1", "affected": True}]}
            )
        )
        result = submit_orders_sync(session, "Classic_2026-04-01", orders)
        assert result.orders[0].affected is True

    @respx.mock
    def test_delete_orders_sync(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/Classic_2026-04-01/orders").mock(
            return_value=httpx.Response(204)
        )
        result = delete_orders_sync(session, "Classic_2026-04-01", ["APTAP1"])
        assert result is None


class TestSyncResultEndpoints:
    @respx.mock
    def test_get_trade_results_sync(self, session: HTTPSession) -> None:
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
        results = get_trade_results_sync(session, "Classic_2026-04-01")
        assert len(results) == 1

    @respx.mock
    def test_get_market_results_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/results/market").mock(
            return_value=httpx.Response(
                200,
                json=[{"productId": "hEXA10", "priceZone": "AT", "price": 42.5, "volume": 1000.0}],
            )
        )
        results = get_market_results_sync(session, "Classic_2026-04-01")
        assert len(results) == 1

    @respx.mock
    def test_get_trade_confirmations_sync(self, session: HTTPSession) -> None:
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
        confirmations = get_trade_confirmations_sync(session, "Classic_2026-04-01")
        assert len(confirmations) == 1


class TestSyncPostTradingEndpoints:
    @respx.mock
    def test_get_posttrading_info_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading").mock(
            return_value=httpx.Response(
                200,
                json={
                    "auctionId": "Classic_2026-04-01",
                    "state": "POSTTRADE_OPEN",
                    "products": [],
                },
            )
        )
        info = get_posttrading_info_sync(session, "Classic_2026-04-01")
        assert info.auction_id == "Classic_2026-04-01"

    @respx.mock
    def test_get_posttrading_orders_sync(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading/orders").mock(
            return_value=httpx.Response(200, json=[])
        )
        orders = get_posttrading_orders_sync(session, "Classic_2026-04-01")
        assert orders == []

    @respx.mock
    def test_submit_posttrading_orders_sync(self, session: HTTPSession) -> None:
        from decimal import Decimal

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
        result = submit_posttrading_orders_sync(session, "Classic_2026-04-01", orders)
        assert len(result) == 1

    @respx.mock
    def test_delete_posttrading_orders_sync(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/Classic_2026-04-01/postTrading/orders").mock(
            return_value=httpx.Response(204)
        )
        result = delete_posttrading_orders_sync(session, "Classic_2026-04-01", ["APTAP1"])
        assert result is None
