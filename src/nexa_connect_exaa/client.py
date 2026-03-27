"""Main entry points for the EXAA Trading API client.

Two client classes are provided:

- :class:`AsyncEXAAClient` — native async client using ``async with``.
- :class:`EXAAClient` — synchronous wrapper for use in scripts and
  non-async applications.

Both support the context-manager protocol for session lifecycle management
(login on entry, logout on exit).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING

from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.auth import CertificateAuth, RSAAuth
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.endpoints import auctions as _auctions_ep
from nexa_connect_exaa.endpoints import orders as _orders_ep
from nexa_connect_exaa.endpoints import posttrading as _posttrading_ep
from nexa_connect_exaa.endpoints import results as _results_ep
from nexa_connect_exaa.models.auction import Auction, AuctionState
from nexa_connect_exaa.models.orders import OrderSubmission
from nexa_connect_exaa.models.posttrading import PostTradingInfo, PostTradingOrder
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)
from nexa_connect_exaa.polling import wait_for_state, watch_auction

if TYPE_CHECKING:
    import pandas as pd

AuthType = RSAAuth | CertificateAuth


class AsyncEXAAClient:
    """Async EXAA Trading API client.

    Use as an async context manager to handle session lifecycle::

        async with AsyncEXAAClient(auth=CertificateAuth(...)) as client:
            auctions = await client.get_auctions(delivery_day="2026-04-01")

    Args:
        auth: Authentication provider (:class:`~nexa_connect_exaa.auth.RSAAuth`
            or :class:`~nexa_connect_exaa.auth.CertificateAuth`).
        environment: EXAA environment to connect to. Ignored when ``base_url``
            is provided.
        base_url: Override the environment's base URL (e.g. for a local mock
            server in tests).
        config: Full :class:`~nexa_connect_exaa.config.EXAAConfig` instance.
            When supplied, ``environment`` and ``base_url`` are ignored.
    """

    def __init__(
        self,
        auth: AuthType,
        environment: Environment = Environment.PRODUCTION,
        *,
        base_url: str | None = None,
        config: EXAAConfig | None = None,
    ) -> None:
        if config is not None:
            self._config = config
        elif base_url is not None:
            self._config = EXAAConfig(environment=environment, base_url=base_url)
        else:
            self._config = EXAAConfig(environment=environment)

        self._auth = auth
        self._session = HTTPSession(self._config)
        self._login_time: datetime | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    async def __aenter__(self) -> AsyncEXAAClient:
        await self._session.aopen()
        await self._do_login()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self._logout()
        await self._session.aclose()

    async def _do_login(self) -> None:
        """Authenticate and store the bearer token."""
        token = await self._auth.login(
            self._session._async_client,  # type: ignore[arg-type]
            self._config.base_url,
        )
        self._session.set_token(token)
        self._login_time = datetime.now(tz=UTC)

    async def _logout(self) -> None:
        """Invalidate the bearer token (best-effort)."""
        if self._session._token is None:
            return
        try:
            if self._session._async_client is not None:
                await self._session._async_client.post(
                    f"{self._config.base_url}/login/V1/logout",
                    headers=self._session._auth_headers(),
                )
        except Exception:
            pass  # Logout is best-effort

    async def _maybe_refresh_token(self) -> None:
        """Re-authenticate if the token is within the refresh margin."""
        if self._login_time is None:
            return
        age = datetime.now(tz=UTC) - self._login_time
        if age > timedelta(seconds=86400 - self._config.token_refresh_margin):
            await self._do_login()

    # ------------------------------------------------------------------
    # Auctions
    # ------------------------------------------------------------------

    async def get_auctions(
        self,
        delivery_day: date | str | None = None,
        trading_day: date | str | None = None,
    ) -> list[Auction]:
        """List auctions, optionally filtered by delivery or trading day.

        Args:
            delivery_day: ISO date or ``datetime.date`` for the delivery day.
            trading_day: ISO date or ``datetime.date`` for the trading day.

        Returns:
            List of :class:`~nexa_connect_exaa.models.auction.Auction`.
        """
        await self._maybe_refresh_token()
        return await _auctions_ep.get_auctions(self._session, delivery_day, trading_day)

    async def get_auction(self, auction_id: str) -> Auction:
        """Fetch the full detail of a single auction.

        Args:
            auction_id: Auction identifier (e.g. ``"Classic_2026-04-01"``).

        Returns:
            :class:`~nexa_connect_exaa.models.auction.Auction`.
        """
        await self._maybe_refresh_token()
        return await _auctions_ep.get_auction(self._session, auction_id)

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    async def get_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> OrderSubmission:
        """Retrieve current orders for an auction."""
        await self._maybe_refresh_token()
        return await _orders_ep.get_orders(self._session, auction_id, account_ids)

    async def submit_orders(
        self,
        auction_id: str,
        orders: OrderSubmission,
    ) -> OrderSubmission:
        """Submit (replace) orders for an auction.

        .. warning::
            This performs a **full replacement** per account. All existing
            orders for each included account are deleted and replaced.
        """
        await self._maybe_refresh_token()
        return await _orders_ep.submit_orders(self._session, auction_id, orders)

    async def delete_orders(
        self,
        auction_id: str,
        account_ids: list[str],
    ) -> None:
        """Delete all orders for the specified accounts."""
        await self._maybe_refresh_token()
        await _orders_ep.delete_orders(self._session, auction_id, account_ids)

    # ------------------------------------------------------------------
    # Post-trading
    # ------------------------------------------------------------------

    async def get_posttrading_info(self, auction_id: str) -> PostTradingInfo:
        """Retrieve post-trading info for a Classic auction."""
        await self._maybe_refresh_token()
        return await _posttrading_ep.get_posttrading_info(self._session, auction_id)

    async def get_posttrading_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> list[PostTradingOrder]:
        """Retrieve post-trading orders for a Classic auction."""
        await self._maybe_refresh_token()
        return await _posttrading_ep.get_posttrading_orders(self._session, auction_id, account_ids)

    async def submit_posttrading_orders(
        self,
        auction_id: str,
        orders: list[PostTradingOrder],
    ) -> list[PostTradingOrder]:
        """Submit post-trading orders for a Classic auction."""
        await self._maybe_refresh_token()
        return await _posttrading_ep.submit_posttrading_orders(self._session, auction_id, orders)

    async def delete_posttrading_orders(
        self,
        auction_id: str,
        account_ids: list[str],
    ) -> None:
        """Delete post-trading orders for a Classic auction."""
        await self._maybe_refresh_token()
        await _posttrading_ep.delete_posttrading_orders(self._session, auction_id, account_ids)

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    async def get_trade_results(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> list[TradeResult]:
        """Retrieve trade results for an auction."""
        await self._maybe_refresh_token()
        return await _results_ep.get_trade_results(self._session, auction_id, accounts)

    async def get_market_results(self, auction_id: str) -> list[MarketResult]:
        """Retrieve market-wide clearing results for an auction."""
        await self._maybe_refresh_token()
        return await _results_ep.get_market_results(self._session, auction_id)

    async def get_trade_confirmations(self, auction_id: str) -> list[TradeConfirmation]:
        """Retrieve final trade confirmations for an auction."""
        await self._maybe_refresh_token()
        return await _results_ep.get_trade_confirmations(self._session, auction_id)

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def wait_for_state(
        self,
        auction_id: str,
        target_state: AuctionState | str,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
    ) -> Auction:
        """Poll until the auction reaches the target state.

        Args:
            auction_id: Auction identifier.
            target_state: Target state (enum or string value).
            poll_interval: Seconds between polls (minimum 5–10 recommended).
            timeout: Maximum wait time in seconds.

        Returns:
            :class:`~nexa_connect_exaa.models.auction.Auction` in the target
            state.

        Raises:
            ~nexa_connect_exaa.exceptions.PollingTimeoutError: If timeout
                exceeded.
        """
        return await wait_for_state(self._session, auction_id, target_state, poll_interval, timeout)

    async def watch_auction(
        self,
        auction_id: str,
        poll_interval: float = 5.0,
    ) -> AsyncGenerator[AuctionState, None]:
        """Async generator that yields each distinct state change.

        Args:
            auction_id: Auction identifier.
            poll_interval: Seconds between polls.

        Yields:
            :class:`~nexa_connect_exaa.models.auction.AuctionState` on each
            change (including the initial state).
        """
        async for state in watch_auction(self._session, auction_id, poll_interval):
            yield state

    # ------------------------------------------------------------------
    # DataFrame methods
    # ------------------------------------------------------------------

    async def get_trade_results_df(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> pd.DataFrame:
        """Retrieve trade results as a pandas DataFrame."""
        from nexa_connect_exaa.pandas_helpers import trade_results_to_df

        results = await self.get_trade_results(auction_id, accounts)
        return trade_results_to_df(results)

    async def get_market_results_df(self, auction_id: str) -> pd.DataFrame:
        """Retrieve market results as a pandas DataFrame."""
        from nexa_connect_exaa.pandas_helpers import market_results_to_df

        results = await self.get_market_results(auction_id)
        return market_results_to_df(results)

    async def get_trade_confirmations_df(self, auction_id: str) -> pd.DataFrame:
        """Retrieve trade confirmations as a pandas DataFrame."""
        from nexa_connect_exaa.pandas_helpers import trade_confirmations_to_df

        confirmations = await self.get_trade_confirmations(auction_id)
        return trade_confirmations_to_df(confirmations)

    async def submit_orders_from_df(
        self,
        auction_id: str,
        account_id: str,
        product_type: str,
        type_of_order: str,
        df: pd.DataFrame,
    ) -> OrderSubmission:
        """Submit orders built from a pandas DataFrame.

        Args:
            auction_id: Auction identifier.
            account_id: Trade account identifier.
            product_type: ``"hourly"``, ``"block"``, or ``"quarter_hourly"``.
            type_of_order: ``"LINEAR"`` or ``"STEP"``.
            df: DataFrame with columns ``product_id``, ``price``, ``volume``.

        Returns:
            Accepted :class:`~nexa_connect_exaa.models.orders.OrderSubmission`.
        """
        from nexa_connect_exaa.pandas_helpers import df_to_order_submission

        orders = df_to_order_submission(df, account_id, product_type, type_of_order)
        return await self.submit_orders(auction_id, orders)


class EXAAClient:
    """Synchronous EXAA Trading API client.

    A thin synchronous wrapper around :class:`AsyncEXAAClient`. Uses a
    dedicated event loop so it does not conflict with a running event loop
    in Jupyter notebooks or other async frameworks.

    Use as a context manager::

        with EXAAClient(auth=CertificateAuth(...)) as client:
            auctions = client.get_auctions(delivery_day="2026-04-01")

    Args:
        auth: Authentication provider.
        environment: EXAA environment.
        base_url: Override base URL.
        config: Full configuration object.
    """

    def __init__(
        self,
        auth: AuthType,
        environment: Environment = Environment.PRODUCTION,
        *,
        base_url: str | None = None,
        config: EXAAConfig | None = None,
    ) -> None:
        self._async_client = AsyncEXAAClient(
            auth=auth,
            environment=environment,
            base_url=base_url,
            config=config,
        )
        self._loop: asyncio.AbstractEventLoop | None = None

    def _run(self, coro: object) -> object:
        """Run a coroutine on the private event loop."""
        if self._loop is None:
            raise RuntimeError("EXAAClient is not open. Use as a context manager.")

        return self._loop.run_until_complete(coro)  # type: ignore[arg-type]

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> EXAAClient:
        self._loop = asyncio.new_event_loop()
        self._loop.run_until_complete(self._async_client.__aenter__())
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        try:
            self._loop.run_until_complete(  # type: ignore[union-attr]
                self._async_client.__aexit__(exc_type, exc_val, exc_tb)
            )
        finally:
            if self._loop is not None:
                self._loop.close()
                self._loop = None

    # ------------------------------------------------------------------
    # Auctions
    # ------------------------------------------------------------------

    def get_auctions(
        self,
        delivery_day: date | str | None = None,
        trading_day: date | str | None = None,
    ) -> list[Auction]:
        """List auctions. See :meth:`AsyncEXAAClient.get_auctions`."""
        result = self._run(self._async_client.get_auctions(delivery_day, trading_day))
        return result  # type: ignore[return-value]

    def get_auction(self, auction_id: str) -> Auction:
        """Fetch auction detail. See :meth:`AsyncEXAAClient.get_auction`."""
        result = self._run(self._async_client.get_auction(auction_id))
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Orders
    # ------------------------------------------------------------------

    def get_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> OrderSubmission:
        """Retrieve orders. See :meth:`AsyncEXAAClient.get_orders`."""
        result = self._run(self._async_client.get_orders(auction_id, account_ids))
        return result  # type: ignore[return-value]

    def submit_orders(
        self,
        auction_id: str,
        orders: OrderSubmission,
    ) -> OrderSubmission:
        """Submit orders. See :meth:`AsyncEXAAClient.submit_orders`."""
        result = self._run(self._async_client.submit_orders(auction_id, orders))
        return result  # type: ignore[return-value]

    def delete_orders(self, auction_id: str, account_ids: list[str]) -> None:
        """Delete orders. See :meth:`AsyncEXAAClient.delete_orders`."""
        self._run(self._async_client.delete_orders(auction_id, account_ids))

    # ------------------------------------------------------------------
    # Post-trading
    # ------------------------------------------------------------------

    def get_posttrading_info(self, auction_id: str) -> PostTradingInfo:
        """See :meth:`AsyncEXAAClient.get_posttrading_info`."""
        result = self._run(self._async_client.get_posttrading_info(auction_id))
        return result  # type: ignore[return-value]

    def get_posttrading_orders(
        self,
        auction_id: str,
        account_ids: list[str] | None = None,
    ) -> list[PostTradingOrder]:
        """See :meth:`AsyncEXAAClient.get_posttrading_orders`."""
        result = self._run(self._async_client.get_posttrading_orders(auction_id, account_ids))
        return result  # type: ignore[return-value]

    def submit_posttrading_orders(
        self,
        auction_id: str,
        orders: list[PostTradingOrder],
    ) -> list[PostTradingOrder]:
        """See :meth:`AsyncEXAAClient.submit_posttrading_orders`."""
        result = self._run(self._async_client.submit_posttrading_orders(auction_id, orders))
        return result  # type: ignore[return-value]

    def delete_posttrading_orders(self, auction_id: str, account_ids: list[str]) -> None:
        """See :meth:`AsyncEXAAClient.delete_posttrading_orders`."""
        self._run(self._async_client.delete_posttrading_orders(auction_id, account_ids))

    # ------------------------------------------------------------------
    # Results
    # ------------------------------------------------------------------

    def get_trade_results(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> list[TradeResult]:
        """See :meth:`AsyncEXAAClient.get_trade_results`."""
        result = self._run(self._async_client.get_trade_results(auction_id, accounts))
        return result  # type: ignore[return-value]

    def get_market_results(self, auction_id: str) -> list[MarketResult]:
        """See :meth:`AsyncEXAAClient.get_market_results`."""
        result = self._run(self._async_client.get_market_results(auction_id))
        return result  # type: ignore[return-value]

    def get_trade_confirmations(self, auction_id: str) -> list[TradeConfirmation]:
        """See :meth:`AsyncEXAAClient.get_trade_confirmations`."""
        result = self._run(self._async_client.get_trade_confirmations(auction_id))
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    def wait_for_state(
        self,
        auction_id: str,
        target_state: AuctionState | str,
        poll_interval: float = 10.0,
        timeout: float = 3600.0,
    ) -> Auction:
        """See :meth:`AsyncEXAAClient.wait_for_state`."""
        result = self._run(
            self._async_client.wait_for_state(auction_id, target_state, poll_interval, timeout)
        )
        return result  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # DataFrame methods
    # ------------------------------------------------------------------

    def get_trade_results_df(
        self,
        auction_id: str,
        accounts: list[str] | None = None,
    ) -> pd.DataFrame:
        """See :meth:`AsyncEXAAClient.get_trade_results_df`."""
        result = self._run(self._async_client.get_trade_results_df(auction_id, accounts))
        return result  # type: ignore[return-value]

    def get_market_results_df(self, auction_id: str) -> pd.DataFrame:
        """See :meth:`AsyncEXAAClient.get_market_results_df`."""
        result = self._run(self._async_client.get_market_results_df(auction_id))
        return result  # type: ignore[return-value]

    def get_trade_confirmations_df(self, auction_id: str) -> pd.DataFrame:
        """See :meth:`AsyncEXAAClient.get_trade_confirmations_df`."""
        result = self._run(self._async_client.get_trade_confirmations_df(auction_id))
        return result  # type: ignore[return-value]

    def submit_orders_from_df(
        self,
        auction_id: str,
        account_id: str,
        product_type: str,
        type_of_order: str,
        df: pd.DataFrame,
    ) -> OrderSubmission:
        """See :meth:`AsyncEXAAClient.submit_orders_from_df`."""
        result = self._run(
            self._async_client.submit_orders_from_df(
                auction_id, account_id, product_type, type_of_order, df
            )
        )
        return result  # type: ignore[return-value]
