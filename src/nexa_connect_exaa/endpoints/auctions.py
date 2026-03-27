"""Auction listing and detail endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.models.auction import Auction


def _date_param(d: date | str | None) -> str | None:
    """Normalise a date argument to an ISO-format string, or ``None``."""
    if d is None:
        return None
    if isinstance(d, str):
        return d
    return d.isoformat()


def _parse_auctions(data: Any) -> list[Auction]:
    """Parse the API response for the auctions list endpoint.

    The API may return either a bare JSON array or a wrapper object with an
    ``"auctions"`` key.
    """
    if isinstance(data, list):
        return [Auction.model_validate(item) for item in data]
    auctions_data = data.get("auctions", data)
    return [Auction.model_validate(item) for item in auctions_data]


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


async def get_auctions(
    session: HTTPSession,
    delivery_day: date | str | None = None,
    trading_day: date | str | None = None,
) -> list[Auction]:
    """List auctions, optionally filtered by delivery or trading day.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        delivery_day: Filter to auctions for this delivery date (ISO format
            or ``datetime.date``).
        trading_day: Filter to auctions traded on this date.

    Returns:
        List of :class:`~nexa_connect_exaa.models.auction.Auction` objects.
    """
    params: dict[str, str] = {}
    dd = _date_param(delivery_day)
    if dd is not None:
        params["deliveryDay"] = dd
    td = _date_param(trading_day)
    if td is not None:
        params["tradingDay"] = td

    data = await session.aget("auctions", params=params or None)
    return _parse_auctions(data)


async def get_auction(session: HTTPSession, auction_id: str) -> Auction:
    """Fetch the full detail of a single auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier (e.g. ``"Classic_2026-04-01"``).

    Returns:
        The :class:`~nexa_connect_exaa.models.auction.Auction`.

    Raises:
        ~nexa_connect_exaa.exceptions.AuctionNotFoundError: If no auction with
            this ID exists.
    """
    data = await session.aget(f"auctions/{auction_id}")
    return Auction.model_validate(data)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def get_auctions_sync(
    session: HTTPSession,
    delivery_day: date | str | None = None,
    trading_day: date | str | None = None,
) -> list[Auction]:
    """Synchronous version of :func:`get_auctions`."""
    params: dict[str, str] = {}
    dd = _date_param(delivery_day)
    if dd is not None:
        params["deliveryDay"] = dd
    td = _date_param(trading_day)
    if td is not None:
        params["tradingDay"] = td

    data = session.get("auctions", params=params or None)
    return _parse_auctions(data)


def get_auction_sync(session: HTTPSession, auction_id: str) -> Auction:
    """Synchronous version of :func:`get_auction`."""
    data = session.get(f"auctions/{auction_id}")
    return Auction.model_validate(data)
