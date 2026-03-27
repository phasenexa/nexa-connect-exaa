"""Testing utilities for downstream consumers of nexa-connect-exaa.

:class:`FakeEXAAClient` is an in-memory implementation of the
:class:`~nexa_connect_exaa.client.EXAAClient` interface. Use it in your own
tests to avoid hitting the EXAA API::

    from nexa_connect_exaa.testing import FakeEXAAClient
    from nexa_connect_exaa.models.auction import Auction, AuctionType, AuctionState

    fake = FakeEXAAClient(auctions=[...])
    with fake as client:
        auctions = client.get_auctions()
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from nexa_connect_exaa.exceptions import AuctionNotFoundError
from nexa_connect_exaa.models.auction import Auction, AuctionState
from nexa_connect_exaa.models.orders import OrderSubmission
from nexa_connect_exaa.models.posttrading import PostTradingInfo, PostTradingOrder
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)


def _date_str(d: date | str | None) -> str | None:
    """Normalise a date parameter to ISO string."""
    if d is None:
        return None
    return d.isoformat() if isinstance(d, date) and not isinstance(d, datetime) else str(d)


class FakeEXAAClient:
    """In-memory EXAA client for use in downstream tests.

    Pre-populate responses by passing data to the constructor, or mutate the
    instance attributes directly before use.

    Submitted orders are stored in :attr:`submitted_orders` for assertion.

    Args:
        auctions: List of auctions returned by ``get_auctions`` and
            ``get_auction``.
        orders: Per-auction ``OrderSubmission`` returned by ``get_orders``.
        trade_results: Per-auction list of ``TradeResult``.
        market_results: Per-auction list of ``MarketResult``.
        trade_confirmations: Per-auction list of ``TradeConfirmation``.
        posttrading_info: Per-auction ``PostTradingInfo``.
        posttrading_orders: Per-auction list of ``PostTradingOrder``.
    """

    def __init__(
        self,
        auctions: list[Auction] | None = None,
        orders: dict[str, OrderSubmission] | None = None,
        trade_results: dict[str, list[TradeResult]] | None = None,
        market_results: dict[str, list[MarketResult]] | None = None,
        trade_confirmations: dict[str, list[TradeConfirmation]] | None = None,
        posttrading_info: dict[str, PostTradingInfo] | None = None,
        posttrading_orders: dict[str, list[PostTradingOrder]] | None = None,
    ) -> None:
        self._auctions: list[Auction] = auctions or []
        self._orders: dict[str, OrderSubmission] = orders or {}
        self._trade_results: dict[str, list[TradeResult]] = trade_results or {}
        self._market_results: dict[str, list[MarketResult]] = market_results or {}
        self._trade_confirmations: dict[str, list[TradeConfirmation]] = trade_confirmations or {}
        self._posttrading_info: dict[str, PostTradingInfo] = posttrading_info or {}
        self._posttrading_orders: dict[str, list[PostTradingOrder]] = posttrading_orders or {}
        self.submitted_orders: dict[str, list[OrderSubmission]] = {}
        self.submitted_posttrading_orders: dict[str, list[list[PostTradingOrder]]] = {}

    # ------------------------------------------------------------------
    # Context manager (sync and async)
    # ------------------------------------------------------------------

    def __enter__(self) -> FakeEXAAClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        pass

    async def __aenter__(self) -> FakeEXAAClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        pass

    # ------------------------------------------------------------------
    # Fixtures
    # ------------------------------------------------------------------

    @classmethod
    def from_fixture(cls, path: str | Path) -> FakeEXAAClient:
        """Load pre-baked responses from a JSON fixture file.

        The JSON file should have the following structure::

            {
                "auctions": [...],
                "orders": {"Classic_2026-04-01": {...}},
                "trade_results": {"Classic_2026-04-01": [...]},
                "market_results": {"Classic_2026-04-01": [...]},
                "trade_confirmations": {"Classic_2026-04-01": [...]},
                "posttrading_info": {"Classic_2026-04-01": {...}},
                "posttrading_orders": {"Classic_2026-04-01": [...]}
            }

        Args:
            path: Path to the JSON fixture file.

        Returns:
            A :class:`FakeEXAAClient` pre-populated with the fixture data.
        """
        data: dict[str, Any] = json.loads(Path(path).read_text())

        auctions = [Auction.model_validate(a) for a in data.get("auctions", [])]
        orders = {k: OrderSubmission.model_validate(v) for k, v in data.get("orders", {}).items()}
        trade_results = {
            k: [TradeResult.model_validate(r) for r in v]
            for k, v in data.get("trade_results", {}).items()
        }
        market_results = {
            k: [MarketResult.model_validate(r) for r in v]
            for k, v in data.get("market_results", {}).items()
        }
        trade_confirmations = {
            k: [TradeConfirmation.model_validate(r) for r in v]
            for k, v in data.get("trade_confirmations", {}).items()
        }
        posttrading_info = {
            k: PostTradingInfo.model_validate(v)
            for k, v in data.get("posttrading_info", {}).items()
        }
        posttrading_orders = {
            k: [PostTradingOrder.model_validate(o) for o in v]
            for k, v in data.get("posttrading_orders", {}).items()
        }

        return cls(
            auctions=auctions,
            orders=orders,
            trade_results=trade_results,
            market_results=market_results,
            trade_confirmations=trade_confirmations,
            posttrading_info=posttrading_info,
            posttrading_orders=posttrading_orders,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_auction_or_raise(self, auction_id: str) -> Auction:
        for auction in self._auctions:
            if auction.id == auction_id:
                return auction
        raise AuctionNotFoundError(
            code="F006",
            message=f"Auction {auction_id!r} not found",
        )

    # ------------------------------------------------------------------
    # Auctions (sync)
    # ------------------------------------------------------------------

    def get_auctions(
        self,
        delivery_day: date | str | None = None,
        trading_day: date | str | None = None,
    ) -> list[Auction]:
        """Return pre-configured auctions, optionally filtered by date."""
        dd = _date_str(delivery_day)
        td = _date_str(trading_day)
        result = self._auctions
        if dd is not None:
            result = [a for a in result if a.delivery_day.isoformat() == dd]
        if td is not None:
            result = [a for a in result if a.trading_day.isoformat() == td]
        return result

    def get_auction(self, auction_id: str) -> Auction:
        """Return the auction with the given ID, or raise ``AuctionNotFoundError``."""
        return self._get_auction_or_raise(auction_id)

    # ------------------------------------------------------------------
    # Orders (sync)
    # ------------------------------------------------------------------

    def get_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> OrderSubmission:
        """Return pre-configured orders for the auction."""
        self._get_auction_or_raise(auction_id)
        submission = self._orders.get(auction_id, OrderSubmission(orders=[]))
        if account_ids is not None:
            filtered = [o for o in submission.orders if o.account_id in account_ids]
            return OrderSubmission(orders=filtered)
        return submission

    def submit_orders(
        self,
        auction_id: str,
        orders: OrderSubmission,
    ) -> OrderSubmission:
        """Record the submitted orders and return them."""
        self._get_auction_or_raise(auction_id)
        self.submitted_orders.setdefault(auction_id, []).append(orders)
        self._orders[auction_id] = orders
        return orders

    def delete_orders(self, auction_id: str, account_ids: list[str]) -> None:
        """Delete orders for the specified accounts."""
        self._get_auction_or_raise(auction_id)
        existing = self._orders.get(auction_id)
        if existing is not None:
            remaining = [o for o in existing.orders if o.account_id not in account_ids]
            self._orders[auction_id] = OrderSubmission(orders=remaining)

    # ------------------------------------------------------------------
    # Post-trading (sync)
    # ------------------------------------------------------------------

    def get_posttrading_info(self, auction_id: str) -> PostTradingInfo:
        """Return pre-configured post-trading info."""
        self._get_auction_or_raise(auction_id)
        if auction_id not in self._posttrading_info:
            from nexa_connect_exaa.exceptions import EXAAFunctionalError

            raise EXAAFunctionalError(
                code="F001",
                message=f"No post-trading info for auction {auction_id!r}",
            )
        return self._posttrading_info[auction_id]

    def get_posttrading_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> list[PostTradingOrder]:
        """Return pre-configured post-trading orders."""
        self._get_auction_or_raise(auction_id)
        orders = self._posttrading_orders.get(auction_id, [])
        if account_ids is not None:
            orders = [o for o in orders if o.account_id in account_ids]
        return orders

    def submit_posttrading_orders(
        self,
        auction_id: str,
        orders: list[PostTradingOrder],
    ) -> list[PostTradingOrder]:
        """Record post-trading orders and return them."""
        self._get_auction_or_raise(auction_id)
        self.submitted_posttrading_orders.setdefault(auction_id, []).append(orders)
        self._posttrading_orders[auction_id] = orders
        return orders

    def delete_posttrading_orders(self, auction_id: str, account_ids: list[str]) -> None:
        """Delete post-trading orders for the specified accounts."""
        self._get_auction_or_raise(auction_id)
        existing = self._posttrading_orders.get(auction_id, [])
        self._posttrading_orders[auction_id] = [
            o for o in existing if o.account_id not in account_ids
        ]

    # ------------------------------------------------------------------
    # Results (sync)
    # ------------------------------------------------------------------

    def get_trade_results(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> list[TradeResult]:
        """Return pre-configured trade results."""
        self._get_auction_or_raise(auction_id)
        results = self._trade_results.get(auction_id, [])
        if accounts is not None:
            results = [r for r in results if r.account_id in accounts]
        return results

    def get_market_results(self, auction_id: str) -> list[MarketResult]:
        """Return pre-configured market results."""
        self._get_auction_or_raise(auction_id)
        return self._market_results.get(auction_id, [])

    def get_trade_confirmations(self, auction_id: str) -> list[TradeConfirmation]:
        """Return pre-configured trade confirmations."""
        self._get_auction_or_raise(auction_id)
        return self._trade_confirmations.get(auction_id, [])

    # ------------------------------------------------------------------
    # Polling (sync)
    # ------------------------------------------------------------------

    def wait_for_state(
        self,
        auction_id: str,
        target_state: AuctionState | str,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
    ) -> Auction:
        """Return the auction if it is already in the target state.

        Since :class:`FakeEXAAClient` is stateless, this simply checks the
        current state. Use :meth:`set_auction_state` to change it before
        calling this method.
        """
        from nexa_connect_exaa.polling import _normalise_state

        target = _normalise_state(target_state)
        auction = self._get_auction_or_raise(auction_id)
        if auction.state == target:
            return auction
        from nexa_connect_exaa.exceptions import PollingTimeoutError

        raise PollingTimeoutError(
            auction_id=auction_id,
            target_state=target.value,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # Async variants
    # ------------------------------------------------------------------

    async def aget_auctions(
        self,
        delivery_day: date | str | None = None,
        trading_day: date | str | None = None,
    ) -> list[Auction]:
        """Async version of :meth:`get_auctions`."""
        return self.get_auctions(delivery_day, trading_day)

    async def aget_auction(self, auction_id: str) -> Auction:
        """Async version of :meth:`get_auction`."""
        return self.get_auction(auction_id)

    async def aget_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> OrderSubmission:
        """Async version of :meth:`get_orders`."""
        return self.get_orders(auction_id, account_ids)

    async def asubmit_orders(
        self,
        auction_id: str,
        orders: OrderSubmission,
    ) -> OrderSubmission:
        """Async version of :meth:`submit_orders`."""
        return self.submit_orders(auction_id, orders)

    async def adelete_orders(self, auction_id: str, account_ids: list[str]) -> None:
        """Async version of :meth:`delete_orders`."""
        self.delete_orders(auction_id, account_ids)

    async def aget_trade_results(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> list[TradeResult]:
        """Async version of :meth:`get_trade_results`."""
        return self.get_trade_results(auction_id, accounts)

    async def aget_market_results(self, auction_id: str) -> list[MarketResult]:
        """Async version of :meth:`get_market_results`."""
        return self.get_market_results(auction_id)

    async def aget_trade_confirmations(self, auction_id: str) -> list[TradeConfirmation]:
        """Async version of :meth:`get_trade_confirmations`."""
        return self.get_trade_confirmations(auction_id)

    # ------------------------------------------------------------------
    # Test helpers
    # ------------------------------------------------------------------

    def set_auction_state(self, auction_id: str, state: AuctionState) -> None:
        """Update the state of a pre-configured auction (for test setup).

        Args:
            auction_id: Auction identifier.
            state: New state to set.
        """
        for i, auction in enumerate(self._auctions):
            if auction.id == auction_id:
                self._auctions[i] = auction.model_copy(update={"state": state})
                return
        raise AuctionNotFoundError(
            code="F006",
            message=f"Auction {auction_id!r} not found",
        )
