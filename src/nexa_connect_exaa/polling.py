"""Auction state polling helpers.

Provides two utilities for monitoring auction state transitions:

- :func:`wait_for_state` — blocks (async or sync) until an auction reaches a
  target state, with a configurable timeout.
- :func:`watch_auction` — async generator that yields each distinct
  :class:`~nexa_connect_exaa.models.auction.AuctionState` as it changes.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.endpoints.auctions import get_auction, get_auction_sync
from nexa_connect_exaa.exceptions import PollingTimeoutError
from nexa_connect_exaa.models.auction import Auction, AuctionState


def _normalise_state(state: AuctionState | str) -> AuctionState:
    """Coerce a string or enum to :class:`AuctionState`."""
    if isinstance(state, AuctionState):
        return state
    return AuctionState(state)


async def wait_for_state(
    session: HTTPSession,
    auction_id: str,
    target_state: AuctionState | str,
    poll_interval: float = 10.0,
    timeout: float = 3600.0,
) -> Auction:
    """Poll an auction until it reaches the target state.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        target_state: The :class:`~nexa_connect_exaa.models.auction.AuctionState`
            to wait for (or its string value, e.g. ``"AUCTIONED"``).
        poll_interval: Seconds between polling requests. EXAA does not
            publish rate limits; 10 seconds is a conservative default.
        timeout: Maximum seconds to wait before raising
            :class:`~nexa_connect_exaa.exceptions.PollingTimeoutError`.

    Returns:
        The :class:`~nexa_connect_exaa.models.auction.Auction` in the target
        state.

    Raises:
        ~nexa_connect_exaa.exceptions.PollingTimeoutError: If the timeout is
            exceeded before the target state is reached.
    """
    target = _normalise_state(target_state)
    deadline = time.monotonic() + timeout

    while True:
        auction = await get_auction(session, auction_id)
        if auction.state == target:
            return auction

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PollingTimeoutError(
                auction_id=auction_id,
                target_state=target.value,
                timeout=timeout,
            )

        await asyncio.sleep(min(poll_interval, remaining))


async def watch_auction(
    session: HTTPSession,
    auction_id: str,
    poll_interval: float = 5.0,
) -> AsyncGenerator[AuctionState, None]:
    """Async generator that yields each distinct auction state change.

    Polls the auction at ``poll_interval`` and yields the new state whenever
    it differs from the previous one. This generator runs indefinitely; the
    caller is responsible for breaking out (e.g. when ``FINALIZED`` is
    reached).

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        poll_interval: Seconds between polling requests.

    Yields:
        :class:`~nexa_connect_exaa.models.auction.AuctionState` on each
        state change (including the initial state on first poll).

    Example::

        async for state in client.watch_auction("Classic_2026-04-01"):
            print(f"State: {state}")
            if state == AuctionState.FINALIZED:
                break
    """
    last_state: AuctionState | None = None

    while True:
        auction = await get_auction(session, auction_id)
        if auction.state != last_state:
            last_state = auction.state
            yield auction.state
        await asyncio.sleep(poll_interval)


def wait_for_state_sync(
    session: HTTPSession,
    auction_id: str,
    target_state: AuctionState | str,
    poll_interval: float = 10.0,
    timeout: float = 3600.0,
) -> Auction:
    """Synchronous version of :func:`wait_for_state`.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        target_state: Target :class:`~nexa_connect_exaa.models.auction.AuctionState`.
        poll_interval: Seconds between polling requests.
        timeout: Maximum wait time in seconds.

    Returns:
        The :class:`~nexa_connect_exaa.models.auction.Auction` in the target
        state.

    Raises:
        ~nexa_connect_exaa.exceptions.PollingTimeoutError: If timeout exceeded.
    """
    target = _normalise_state(target_state)
    deadline = time.monotonic() + timeout

    while True:
        auction = get_auction_sync(session, auction_id)
        if auction.state == target:
            return auction

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PollingTimeoutError(
                auction_id=auction_id,
                target_state=target.value,
                timeout=timeout,
            )

        time.sleep(min(poll_interval, remaining))
