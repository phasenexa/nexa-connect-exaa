"""Order retrieval, submission, and deletion endpoints.

.. warning::
    ``submit_orders`` performs a **full replacement** for each included
    account. All existing orders for a given account are deleted and replaced
    by the submitted orders. Accounts not included in the request are
    unaffected. Omitting a product type (e.g. block products) within an
    account's submission **deletes** any existing orders of that type.
"""

from __future__ import annotations

from typing import Any

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.models.orders import AccountOrders, OrderSubmission


def _parse_order_submission(data: Any) -> OrderSubmission:
    """Parse the API response into an ``OrderSubmission``."""
    if isinstance(data, dict) and "orders" in data:
        return OrderSubmission.model_validate(data)
    # Bare list of account orders
    return OrderSubmission(orders=[AccountOrders.model_validate(item) for item in data])


def _account_id_params(
    account_ids: list[str] | None,
) -> dict[str, list[str]] | None:
    """Build repeated ``accountIds`` query parameters."""
    if not account_ids:
        return None
    return {"accountIds": account_ids}


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


async def get_orders(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> OrderSubmission:
    """Retrieve current orders for an auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        account_ids: Restrict results to these account IDs. Returns all
            accessible accounts when ``None``.

    Returns:
        Current orders as an :class:`~nexa_connect_exaa.models.orders.OrderSubmission`.
    """
    data = await session.aget(
        f"auctions/{auction_id}/orders",
        params=_account_id_params(account_ids),
    )
    return _parse_order_submission(data)


async def submit_orders(
    session: HTTPSession,
    auction_id: str,
    orders: OrderSubmission,
) -> OrderSubmission:
    """Submit (replace) orders for an auction.

    .. warning::
        This is a **full replacement** per account. See module docstring.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        orders: Order payload. Serialised with camelCase aliases and Decimal
            values converted to floats.

    Returns:
        The accepted order submission, with ``affected=True`` on accounts
        where orders were modified.

    Raises:
        ~nexa_connect_exaa.exceptions.AuctionNotOpenError: If the auction
            gate is closed.
        ~nexa_connect_exaa.exceptions.MonotonicViolationError: If a
            price/volume curve is not monotonic.
    """
    body = orders.model_dump(by_alias=True, mode="json", exclude_none=True)
    data = await session.apost(f"auctions/{auction_id}/orders", json=body)
    return _parse_order_submission(data)


async def delete_orders(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str],
) -> None:
    """Delete all orders for the specified accounts in an auction.

    Args:
        session: An open :class:`~nexa_connect_exaa._http.HTTPSession`.
        auction_id: Auction identifier.
        account_ids: Accounts whose orders should be deleted.

    Raises:
        ~nexa_connect_exaa.exceptions.AuctionNotOpenError: If the auction
            gate is closed.
    """
    await session.adelete(
        f"auctions/{auction_id}/orders",
        params={"accountIds": account_ids},
    )


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def get_orders_sync(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str] | None = None,
) -> OrderSubmission:
    """Synchronous version of :func:`get_orders`."""
    data = session.get(
        f"auctions/{auction_id}/orders",
        params=_account_id_params(account_ids),
    )
    return _parse_order_submission(data)


def submit_orders_sync(
    session: HTTPSession,
    auction_id: str,
    orders: OrderSubmission,
) -> OrderSubmission:
    """Synchronous version of :func:`submit_orders`."""
    body = orders.model_dump(by_alias=True, mode="json", exclude_none=True)
    data = session.post(f"auctions/{auction_id}/orders", json=body)
    return _parse_order_submission(data)


def delete_orders_sync(
    session: HTTPSession,
    auction_id: str,
    account_ids: list[str],
) -> None:
    """Synchronous version of :func:`delete_orders`."""
    session.delete(
        f"auctions/{auction_id}/orders",
        params={"accountIds": account_ids},
    )
