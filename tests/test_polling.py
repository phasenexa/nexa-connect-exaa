"""Tests for auction state polling utilities."""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from nexa_connect_exaa.exceptions import PollingTimeoutError
from nexa_connect_exaa.models.auction import Auction, AuctionState, AuctionType
from nexa_connect_exaa.polling import wait_for_state, watch_auction


def _make_auction(state: AuctionState, auction_id: str = "Classic_2026-04-01") -> Auction:
    return Auction(
        id=auction_id,
        auction_type=AuctionType.CLASSIC,
        state=state,
        delivery_day=date(2026, 4, 1),
        trading_day=date(2026, 3, 31),
    )


class TestWaitForState:
    @pytest.mark.asyncio
    async def test_returns_immediately_when_already_in_target_state(self) -> None:
        auction = _make_auction(AuctionState.AUCTIONED)
        session = AsyncMock()

        with patch(
            "nexa_connect_exaa.polling.get_auction",
            new_callable=AsyncMock,
            return_value=auction,
        ):
            result = await wait_for_state(session, "Classic_2026-04-01", AuctionState.AUCTIONED)
        assert result.state == AuctionState.AUCTIONED

    @pytest.mark.asyncio
    async def test_polls_until_target_state_reached(self) -> None:
        states = [
            AuctionState.TRADE_CLOSED,
            AuctionState.AUCTIONING,
            AuctionState.AUCTIONED,
        ]
        side_effects = [_make_auction(s) for s in states]
        session = AsyncMock()

        with (
            patch(
                "nexa_connect_exaa.polling.get_auction",
                new_callable=AsyncMock,
                side_effect=side_effects,
            ),
            patch("nexa_connect_exaa.polling.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await wait_for_state(
                session,
                "Classic_2026-04-01",
                AuctionState.AUCTIONED,
                poll_interval=0.01,
            )
        assert result.state == AuctionState.AUCTIONED

    @pytest.mark.asyncio
    async def test_accepts_string_target_state(self) -> None:
        auction = _make_auction(AuctionState.FINALIZED)
        session = AsyncMock()

        with patch(
            "nexa_connect_exaa.polling.get_auction",
            new_callable=AsyncMock,
            return_value=auction,
        ):
            result = await wait_for_state(session, "Classic_2026-04-01", "FINALIZED")
        assert result.state == AuctionState.FINALIZED

    @pytest.mark.asyncio
    async def test_raises_polling_timeout_error(self) -> None:
        auction = _make_auction(AuctionState.TRADE_OPEN)
        session = AsyncMock()

        with (
            patch(
                "nexa_connect_exaa.polling.get_auction",
                new_callable=AsyncMock,
                return_value=auction,
            ),
            patch("nexa_connect_exaa.polling.asyncio.sleep", new_callable=AsyncMock),
            patch(
                "nexa_connect_exaa.polling.time.monotonic",
                side_effect=[0.0, 0.0, 9999.0],  # timeout after two calls
            ),
            pytest.raises(PollingTimeoutError) as exc_info,
        ):
            await wait_for_state(
                session,
                "Classic_2026-04-01",
                AuctionState.AUCTIONED,
                timeout=1.0,
            )
        assert exc_info.value.auction_id == "Classic_2026-04-01"
        assert exc_info.value.target_state == "AUCTIONED"


class TestWatchAuction:
    @pytest.mark.asyncio
    async def test_yields_initial_state(self) -> None:
        auction = _make_auction(AuctionState.TRADE_OPEN)
        session = AsyncMock()

        states_yielded = []

        async def _run() -> None:
            async for state in watch_auction(session, "Classic_2026-04-01", poll_interval=0.0):
                states_yielded.append(state)
                if len(states_yielded) >= 1:
                    break

        with (
            patch(
                "nexa_connect_exaa.polling.get_auction",
                new_callable=AsyncMock,
                return_value=auction,
            ),
            patch("nexa_connect_exaa.polling.asyncio.sleep", new_callable=AsyncMock),
        ):
            await _run()

        assert states_yielded[0] == AuctionState.TRADE_OPEN

    @pytest.mark.asyncio
    async def test_deduplicates_identical_states(self) -> None:
        """Should only yield when state changes, not on every poll."""
        auctions = [
            _make_auction(AuctionState.TRADE_OPEN),
            _make_auction(AuctionState.TRADE_OPEN),  # same — should not yield again
            _make_auction(AuctionState.TRADE_CLOSED),  # change — should yield
        ]
        session = AsyncMock()
        states_yielded = []

        async def _run() -> None:
            async for state in watch_auction(session, "Classic_2026-04-01", poll_interval=0.0):
                states_yielded.append(state)
                if len(states_yielded) >= 2:
                    break

        with (
            patch(
                "nexa_connect_exaa.polling.get_auction",
                new_callable=AsyncMock,
                side_effect=auctions,
            ),
            patch("nexa_connect_exaa.polling.asyncio.sleep", new_callable=AsyncMock),
        ):
            await _run()

        assert states_yielded == [AuctionState.TRADE_OPEN, AuctionState.TRADE_CLOSED]


class TestWaitForStateSync:
    def test_returns_when_in_target_state(self) -> None:
        from nexa_connect_exaa.polling import wait_for_state_sync

        auction = _make_auction(AuctionState.AUCTIONED)
        session = MagicMock()

        with patch(
            "nexa_connect_exaa.polling.get_auction_sync",
            return_value=auction,
        ):
            result = wait_for_state_sync(session, "Classic_2026-04-01", "AUCTIONED")
        assert result.state == AuctionState.AUCTIONED

    def test_raises_polling_timeout(self) -> None:
        from nexa_connect_exaa.polling import wait_for_state_sync

        auction = _make_auction(AuctionState.TRADE_OPEN)
        session = MagicMock()

        with (
            patch(
                "nexa_connect_exaa.polling.get_auction_sync",
                return_value=auction,
            ),
            patch("nexa_connect_exaa.polling.time.sleep"),
            patch(
                "nexa_connect_exaa.polling.time.monotonic",
                side_effect=[0.0, 0.0, 9999.0],
            ),
            pytest.raises(PollingTimeoutError),
        ):
            wait_for_state_sync(session, "Classic_2026-04-01", "AUCTIONED", timeout=1.0)
