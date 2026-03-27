"""Tests for the EXAAClient and AsyncEXAAClient."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from nexa_connect_exaa.auth import RSAAuth
from nexa_connect_exaa.client import AsyncEXAAClient
from nexa_connect_exaa.config import Environment
from nexa_connect_exaa.models.auction import Auction, AuctionState, AuctionType
from nexa_connect_exaa.models.orders import AccountOrders, OrderSubmission
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)
from nexa_connect_exaa.testing import FakeEXAAClient


def _make_auction(
    state: AuctionState = AuctionState.TRADE_OPEN,
    auction_id: str = "Classic_2026-04-01",
) -> Auction:
    return Auction(
        id=auction_id,
        auction_type=AuctionType.CLASSIC,
        state=state,
        delivery_day=date(2026, 4, 1),
        trading_day=date(2026, 3, 31),
    )


class TestFakeEXAAClient:
    """Tests using the FakeEXAAClient (also validates the fake behaviour)."""

    def test_get_auctions_returns_all(self) -> None:
        auction = _make_auction()
        with FakeEXAAClient(auctions=[auction]) as client:
            result = client.get_auctions()
        assert len(result) == 1

    def test_get_auctions_filters_by_delivery_day(self) -> None:
        a1 = _make_auction(auction_id="Classic_2026-04-01")
        a2 = _make_auction(auction_id="Classic_2026-04-02")
        a2_copy = a2.model_copy(update={"delivery_day": date(2026, 4, 2)})
        with FakeEXAAClient(auctions=[a1, a2_copy]) as client:
            result = client.get_auctions(delivery_day="2026-04-01")
        assert len(result) == 1
        assert result[0].id == "Classic_2026-04-01"

    def test_get_auction_raises_not_found(self) -> None:
        from nexa_connect_exaa.exceptions import AuctionNotFoundError

        with FakeEXAAClient() as client, pytest.raises(AuctionNotFoundError):
            client.get_auction("Unknown_2026-04-01")

    def test_submit_orders_stores_and_returns(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1")])
        with FakeEXAAClient(auctions=[auction]) as client:
            result = client.submit_orders("Classic_2026-04-01", orders)
            assert result is orders
            assert len(client.submitted_orders["Classic_2026-04-01"]) == 1

    def test_get_orders_filters_by_account(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(
            orders=[
                AccountOrders(account_id="APTAP1"),
                AccountOrders(account_id="APTAP2"),
            ]
        )
        fake = FakeEXAAClient(
            auctions=[auction],
            orders={"Classic_2026-04-01": orders},
        )
        with fake as client:
            result = client.get_orders("Classic_2026-04-01", account_ids=["APTAP1"])
        assert len(result.orders) == 1
        assert result.orders[0].account_id == "APTAP1"

    def test_get_trade_results(self) -> None:
        auction = _make_auction()
        result = TradeResult(
            product_id="hEXA10",
            account_id="APTAP1",
            price=Decimal("42.5"),
            volume_awarded=Decimal("200.0"),
        )
        fake = FakeEXAAClient(
            auctions=[auction],
            trade_results={"Classic_2026-04-01": [result]},
        )
        with fake as client:
            results = client.get_trade_results("Classic_2026-04-01")
        assert len(results) == 1

    def test_set_auction_state(self) -> None:
        auction = _make_auction()
        fake = FakeEXAAClient(auctions=[auction])
        fake.set_auction_state("Classic_2026-04-01", AuctionState.AUCTIONED)
        assert fake.get_auction("Classic_2026-04-01").state == AuctionState.AUCTIONED

    def test_wait_for_state_already_in_state(self) -> None:
        auction = _make_auction(state=AuctionState.AUCTIONED)
        fake = FakeEXAAClient(auctions=[auction])
        result = fake.wait_for_state("Classic_2026-04-01", AuctionState.AUCTIONED)
        assert result.state == AuctionState.AUCTIONED

    def test_wait_for_state_wrong_state_raises_timeout(self) -> None:
        from nexa_connect_exaa.exceptions import PollingTimeoutError

        auction = _make_auction(state=AuctionState.TRADE_OPEN)
        fake = FakeEXAAClient(auctions=[auction])
        with pytest.raises(PollingTimeoutError):
            fake.wait_for_state("Classic_2026-04-01", AuctionState.AUCTIONED)

    def test_delete_orders(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(
            orders=[
                AccountOrders(account_id="APTAP1"),
                AccountOrders(account_id="APTAP2"),
            ]
        )
        fake = FakeEXAAClient(
            auctions=[auction],
            orders={"Classic_2026-04-01": orders},
        )
        with fake as client:
            client.delete_orders("Classic_2026-04-01", ["APTAP1"])
            remaining = client.get_orders("Classic_2026-04-01")
        assert len(remaining.orders) == 1
        assert remaining.orders[0].account_id == "APTAP2"

    def test_context_manager_async(self) -> None:
        import asyncio

        async def _test() -> None:
            auction = _make_auction()
            async with FakeEXAAClient(auctions=[auction]) as client:
                result = await client.aget_auctions()
            assert len(result) == 1

        asyncio.run(_test())

    def test_from_fixture(self, tmp_path: pytest.FixturePath) -> None:
        import json

        fixture = {
            "auctions": [
                {
                    "id": "Classic_2026-04-01",
                    "auctionType": "CLASSIC",
                    "state": "TRADE_OPEN",
                    "deliveryDay": "2026-04-01",
                    "tradingDay": "2026-03-31",
                }
            ]
        }
        fixture_file = tmp_path / "fixture.json"
        fixture_file.write_text(json.dumps(fixture))

        fake = FakeEXAAClient.from_fixture(fixture_file)
        assert len(fake._auctions) == 1


class TestFakeEXAAClientAsync:
    """Tests for async methods on FakeEXAAClient."""

    @pytest.mark.asyncio
    async def test_aget_auction(self) -> None:
        auction = _make_auction()
        async with FakeEXAAClient(auctions=[auction]) as client:
            result = await client.aget_auction("Classic_2026-04-01")
        assert result.id == "Classic_2026-04-01"

    @pytest.mark.asyncio
    async def test_aget_orders(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1")])
        async with FakeEXAAClient(
            auctions=[auction],
            orders={"Classic_2026-04-01": orders},
        ) as client:
            result = await client.aget_orders("Classic_2026-04-01")
        assert len(result.orders) == 1

    @pytest.mark.asyncio
    async def test_asubmit_orders(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(orders=[AccountOrders(account_id="APTAP1")])
        async with FakeEXAAClient(auctions=[auction]) as client:
            result = await client.asubmit_orders("Classic_2026-04-01", orders)
        assert result is orders

    @pytest.mark.asyncio
    async def test_adelete_orders(self) -> None:
        auction = _make_auction()
        orders = OrderSubmission(
            orders=[
                AccountOrders(account_id="APTAP1"),
                AccountOrders(account_id="APTAP2"),
            ]
        )
        fake = FakeEXAAClient(
            auctions=[auction],
            orders={"Classic_2026-04-01": orders},
        )
        async with fake as client:
            await client.adelete_orders("Classic_2026-04-01", ["APTAP1"])
        remaining = fake._orders["Classic_2026-04-01"]
        assert len(remaining.orders) == 1

    @pytest.mark.asyncio
    async def test_aget_market_results(self) -> None:
        auction = _make_auction()
        mresult = MarketResult(
            product_id="hEXA10",
            price_zone="AT",
            price=Decimal("42.5"),
            volume=Decimal("1000.0"),
        )
        async with FakeEXAAClient(
            auctions=[auction],
            market_results={"Classic_2026-04-01": [mresult]},
        ) as client:
            results = await client.aget_market_results("Classic_2026-04-01")
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_aget_trade_confirmations(self) -> None:
        auction = _make_auction()
        conf = TradeConfirmation(
            product_id="hEXA10",
            account_id="APTAP1",
            price=Decimal("42.5"),
            volume=Decimal("200.0"),
        )
        async with FakeEXAAClient(
            auctions=[auction],
            trade_confirmations={"Classic_2026-04-01": [conf]},
        ) as client:
            confirmations = await client.aget_trade_confirmations("Classic_2026-04-01")
        assert len(confirmations) == 1


class TestFakeEXAAClientPostTrading:
    """Tests for post-trading operations on FakeEXAAClient."""

    def test_get_posttrading_info_raises_when_absent(self) -> None:
        auction = _make_auction()
        fake = FakeEXAAClient(auctions=[auction])
        from nexa_connect_exaa.exceptions import EXAAFunctionalError

        with pytest.raises(EXAAFunctionalError):
            fake.get_posttrading_info("Classic_2026-04-01")

    def test_submit_posttrading_orders(self) -> None:
        from nexa_connect_exaa.models.posttrading import PostTradingOrder

        auction = _make_auction()
        orders = [
            PostTradingOrder(
                product_id="hEXA10",
                account_id="APTAP1",
                volume=Decimal("50.0"),
            )
        ]
        fake = FakeEXAAClient(auctions=[auction])
        result = fake.submit_posttrading_orders("Classic_2026-04-01", orders)
        assert len(result) == 1

    def test_get_posttrading_orders_filtered(self) -> None:
        from nexa_connect_exaa.models.posttrading import PostTradingOrder

        auction = _make_auction()
        orders = [
            PostTradingOrder(
                product_id="hEXA10",
                account_id="APTAP1",
                volume=Decimal("50.0"),
            ),
            PostTradingOrder(
                product_id="hEXA10",
                account_id="APTAP2",
                volume=Decimal("30.0"),
            ),
        ]
        fake = FakeEXAAClient(
            auctions=[auction],
            posttrading_orders={"Classic_2026-04-01": orders},
        )
        result = fake.get_posttrading_orders("Classic_2026-04-01", account_ids=["APTAP1"])
        assert len(result) == 1
        assert result[0].account_id == "APTAP1"

    def test_delete_posttrading_orders(self) -> None:
        from nexa_connect_exaa.models.posttrading import PostTradingOrder

        auction = _make_auction()
        orders = [
            PostTradingOrder(
                product_id="hEXA10",
                account_id="APTAP1",
                volume=Decimal("50.0"),
            )
        ]
        fake = FakeEXAAClient(
            auctions=[auction],
            posttrading_orders={"Classic_2026-04-01": orders},
        )
        fake.delete_posttrading_orders("Classic_2026-04-01", ["APTAP1"])
        assert len(fake._posttrading_orders["Classic_2026-04-01"]) == 0


class TestAsyncEXAAClientConfig:
    def test_uses_environment_base_url(self) -> None:
        auth = RSAAuth(username="u", pin="1234")
        client = AsyncEXAAClient(auth=auth, environment=Environment.TEST)
        assert "test-trade.exaa.at" in client._config.base_url

    def test_uses_custom_base_url(self) -> None:
        auth = RSAAuth(username="u", pin="1234")
        client = AsyncEXAAClient(auth=auth, base_url="http://localhost:8080")
        assert client._config.base_url == "http://localhost:8080"
