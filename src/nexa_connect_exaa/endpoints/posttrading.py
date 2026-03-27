"""Post-trading endpoints (Classic auction only).

Post-trading is exclusive to the Classic (10:15 CET) auction. Calling these
endpoints on a Market Coupling auction will result in
:class:`~nexa_connect_exaa.exceptions.EXAAFunctionalError` (F001) from the
API.
"""

from __future__ import annotations

from typing import Any

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.models.posttrading import PostTradingInfo, PostTradingOrder


def _parse_orders(data: Any) -> list[PostTradingOrder]:
    """Parse the post-trading orders response."""
    if isinstance(data, list):
        return [PostTradingOrder.model_validate(item) for item in data]
    orders_data = data.get("orders", data)
    return [PostTradingOrder.model_validate(item) for item in orders_data]


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


async def get_posttrading_info(session: HTTPSession, auction_id: str) -> PostTradingInfo:
    """Retrieve post-trading phase information for a Classic auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Classic auction identifier (e.g.
            ``"Classic_2026-04-01"``).

    Returns:
        :class:`~nexa_connect_exaa.models.posttrading.PostTradingInfo`
        with available products and their clearing prices.

    Raises:
        ~nexa_connect_exaa.exceptions.EXAAFunctionalError: F001 if called on
            a Market Coupling auction.
    """
    data = await session.aget(f"auctions/{auction_id}/postTrading")
    return PostTradingInfo.model_validate(data)


async def get_posttrading_orders(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> list[PostTradingOrder]:
    """Retrieve post-trading orders for a Classic auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Classic auction identifier.
        account_ids: Restrict results to these accounts.

    Returns:
        List of :class:`~nexa_connect_exaa.models.posttrading.PostTradingOrder`.
    """
    params: dict[str, list[str]] | None = {"accountIds": account_ids} if account_ids else None
    data = await session.aget(f"auctions/{auction_id}/postTrading/orders", params=params)
    return _parse_orders(data)


async def submit_posttrading_orders(
    session: HTTPSession,
    auction_id: str,
    orders: list[PostTradingOrder],
) -> list[PostTradingOrder]:
    """Submit post-trading orders for a Classic auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Classic auction identifier.
        orders: Post-trading orders to submit.

    Returns:
        Accepted post-trading orders as returned by EXAA.
    """
    body = [o.model_dump(by_alias=True, mode="json") for o in orders]
    data = await session.apost(f"auctions/{auction_id}/postTrading/orders", json={"orders": body})
    return _parse_orders(data)


async def delete_posttrading_orders(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str],
) -> None:
    """Delete post-trading orders for specified accounts.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Classic auction identifier.
        account_ids: Accounts whose post-trading orders should be deleted.
    """
    await session.adelete(
        f"auctions/{auction_id}/postTrading/orders",
        params={"accountIds": account_ids},
    )


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def get_posttrading_info_sync(session: HTTPSession, auction_id: str) -> PostTradingInfo:
    """Synchronous version of :func:`get_posttrading_info`."""
    data = session.get(f"auctions/{auction_id}/postTrading")
    return PostTradingInfo.model_validate(data)


def get_posttrading_orders_sync(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> list[PostTradingOrder]:
    """Synchronous version of :func:`get_posttrading_orders`."""
    params: dict[str, list[str]] | None = {"accountIds": account_ids} if account_ids else None
    data = session.get(f"auctions/{auction_id}/postTrading/orders", params=params)
    return _parse_orders(data)


def submit_posttrading_orders_sync(
    session: HTTPSession,
    auction_id: str,
    orders: list[PostTradingOrder],
) -> list[PostTradingOrder]:
    """Synchronous version of :func:`submit_posttrading_orders`."""
    body = [o.model_dump(by_alias=True, mode="json") for o in orders]
    data = session.post(f"auctions/{auction_id}/postTrading/orders", json={"orders": body})
    return _parse_orders(data)


def delete_posttrading_orders_sync(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str],
) -> None:
    """Synchronous version of :func:`delete_posttrading_orders`."""
    session.delete(
        f"auctions/{auction_id}/postTrading/orders",
        params={"accountIds": account_ids},
    )
