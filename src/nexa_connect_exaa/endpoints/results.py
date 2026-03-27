"""Trade and market result retrieval endpoints."""

from __future__ import annotations

from typing import Any

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)


def _parse_list(data: Any, key: str | None = None) -> list[Any]:
    """Extract a list from a potentially-wrapped API response."""
    if isinstance(data, list):
        return data
    if key and key in data:
        return list(data[key])
    # Try common wrapper keys
    for k in ("results", "trades", "confirmations", "marketResults"):
        if k in data:
            return list(data[k])
    return list(data.values())[0] if isinstance(data, dict) else []


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


async def get_trade_results(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> list[TradeResult]:
    """Retrieve trade results for an auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        account_ids: Restrict results to these accounts. Returns all
            accessible results when ``None``.

    Returns:
        List of :class:`~nexa_connect_exaa.models.results.TradeResult`.
    """
    params: dict[str, list[str]] | None = {"accountIds": account_ids} if account_ids else None
    data = await session.aget(f"auctions/{auction_id}/results/trade", params=params)
    return [TradeResult.model_validate(item) for item in _parse_list(data)]


async def get_market_results(
    session: HTTPSession,
    auction_id: str,
) -> list[MarketResult]:
    """Retrieve market-wide clearing results for an auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.

    Returns:
        List of :class:`~nexa_connect_exaa.models.results.MarketResult`.
    """
    data = await session.aget(f"auctions/{auction_id}/results/market")
    return [MarketResult.model_validate(item) for item in _parse_list(data)]


async def get_trade_confirmations(
    session: HTTPSession,
    auction_id: str,
) -> list[TradeConfirmation]:
    """Retrieve final trade confirmations for an auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.

    Returns:
        List of :class:`~nexa_connect_exaa.models.results.TradeConfirmation`.
    """
    data = await session.aget(f"auctions/{auction_id}/results/tradeConfirmations")
    return [TradeConfirmation.model_validate(item) for item in _parse_list(data)]


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def get_trade_results_sync(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> list[TradeResult]:
    """Synchronous version of :func:`get_trade_results`."""
    params: dict[str, list[str]] | None = {"accountIds": account_ids} if account_ids else None
    data = session.get(f"auctions/{auction_id}/results/trade", params=params)
    return [TradeResult.model_validate(item) for item in _parse_list(data)]


def get_market_results_sync(
    session: HTTPSession,
    auction_id: str,
) -> list[MarketResult]:
    """Synchronous version of :func:`get_market_results`."""
    data = session.get(f"auctions/{auction_id}/results/market")
    return [MarketResult.model_validate(item) for item in _parse_list(data)]


def get_trade_confirmations_sync(
    session: HTTPSession,
    auction_id: str,
) -> list[TradeConfirmation]:
    """Synchronous version of :func:`get_trade_confirmations`."""
    data = session.get(f"auctions/{auction_id}/results/tradeConfirmations")
    return [TradeConfirmation.model_validate(item) for item in _parse_list(data)]
