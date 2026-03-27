"""Tests for HTTPSession sync and async behaviour."""

from __future__ import annotations

import httpx
import pytest
import respx
from nexa_connect_exaa._http import HTTPSession
from nexa_connect_exaa.config import Environment, EXAAConfig
from nexa_connect_exaa.exceptions import (
    EXAAConnectionError,
    EXAAServerError,
    MonotonicViolationError,
)

BASE_URL = "https://test-trade.exaa.at"
TRADING_BASE = f"{BASE_URL}/exaa-trading-api/V1"


@pytest.fixture
def config() -> EXAAConfig:
    return EXAAConfig(environment=Environment.TEST, max_retries=0)


@pytest.fixture
def session(config: EXAAConfig) -> HTTPSession:
    s = HTTPSession(config)
    s._sync_client = httpx.Client()
    s._async_client = httpx.AsyncClient()
    s.set_token("test-token")
    return s


class TestHTTPSessionLifecycle:
    def test_sync_context_manager(self, config: EXAAConfig) -> None:
        with HTTPSession(config) as session:
            assert session._sync_client is not None
        assert session._sync_client is None

    @pytest.mark.asyncio
    async def test_async_context_manager(self, config: EXAAConfig) -> None:
        async with HTTPSession(config) as session:
            assert session._async_client is not None
        assert session._async_client is None

    def test_no_token_raises_connection_error(self, config: EXAAConfig) -> None:
        session = HTTPSession(config)
        with pytest.raises(EXAAConnectionError, match="authentication token"):
            session._auth_headers()

    def test_sync_not_open_raises(self, config: EXAAConfig) -> None:
        session = HTTPSession(config)
        session.set_token("tok")
        with pytest.raises(EXAAConnectionError, match="not open"):
            session.get("auctions")

    @pytest.mark.asyncio
    async def test_async_not_open_raises(self, config: EXAAConfig) -> None:
        session = HTTPSession(config)
        session.set_token("tok")
        with pytest.raises(EXAAConnectionError, match="not open"):
            await session.aget("auctions")

    def test_base_url_properties(self, session: HTTPSession) -> None:
        assert session.base_url == BASE_URL
        assert session.trading_base_url == f"{BASE_URL}/exaa-trading-api/V1"
        assert session.login_base_url == f"{BASE_URL}/login"


class TestSyncRequests:
    @respx.mock
    def test_sync_get_returns_json(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json={"data": "value"})
        )
        result = session.get("auctions")
        assert result == {"data": "value"}

    @respx.mock
    def test_sync_post_returns_json(self, session: HTTPSession) -> None:
        respx.post(f"{TRADING_BASE}/auctions/test/orders").mock(
            return_value=httpx.Response(200, json={"orders": []})
        )
        result = session.post("auctions/test/orders", json={"orders": []})
        assert result == {"orders": []}

    @respx.mock
    def test_sync_delete_returns_none_on_204(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/test/orders").mock(return_value=httpx.Response(204))
        result = session.delete("auctions/test/orders")
        assert result is None

    @respx.mock
    def test_sync_raises_on_4xx(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(
                400,
                json={"errors": [{"code": "S001", "message": "bad request"}]},
            )
        )
        from nexa_connect_exaa.exceptions import EXAASyntaxError

        with pytest.raises(EXAASyntaxError):
            session.get("auctions")

    @respx.mock
    def test_sync_parses_error_with_path(self, session: HTTPSession) -> None:
        respx.post(f"{TRADING_BASE}/auctions/test/orders").mock(
            return_value=httpx.Response(
                400,
                json={
                    "errors": [
                        {
                            "code": "F010",
                            "message": "Monotonic violation",
                            "path": "orders[0]",
                        }
                    ]
                },
            )
        )
        with pytest.raises(MonotonicViolationError) as exc_info:
            session.post("auctions/test/orders", json={})
        assert exc_info.value.path == "orders[0]"

    @respx.mock
    def test_sync_unparseable_error_body_raises_server_error(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )
        with pytest.raises(EXAAServerError):
            session.get("auctions")

    @respx.mock
    def test_sync_auth_header_is_injected(self, session: HTTPSession) -> None:
        route = respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json=[])
        )
        session.get("auctions")
        assert route.calls.last.request.headers["authorization"] == "Bearer test-token"

    @respx.mock
    def test_sync_retries_on_500(self, config: EXAAConfig) -> None:
        config.max_retries = 1
        config.retry_backoff_factor = 0.0
        session = HTTPSession(config)
        session._sync_client = httpx.Client()
        session.set_token("tok")

        route = respx.get(f"{TRADING_BASE}/auctions").mock(
            side_effect=[
                httpx.Response(503, json={"errors": [{"code": "U001", "message": "err"}]}),
                httpx.Response(200, json=[]),
            ]
        )
        result = session.get("auctions")
        assert route.call_count == 2
        assert result == []


class TestAsyncRequests:
    @pytest.mark.asyncio
    @respx.mock
    async def test_async_get_returns_json(self, session: HTTPSession) -> None:
        respx.get(f"{TRADING_BASE}/auctions").mock(
            return_value=httpx.Response(200, json={"data": "ok"})
        )
        result = await session.aget("auctions")
        assert result == {"data": "ok"}

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_delete_204(self, session: HTTPSession) -> None:
        respx.delete(f"{TRADING_BASE}/auctions/x/orders").mock(return_value=httpx.Response(204))
        result = await session.adelete("auctions/x/orders")
        assert result is None

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_timeout_raises_connection_error(self, session: HTTPSession) -> None:
        session._config.max_retries = 0
        respx.get(f"{TRADING_BASE}/auctions").mock(side_effect=httpx.TimeoutException("timeout"))
        with pytest.raises(EXAAConnectionError, match="timed out"):
            await session.aget("auctions")

    @pytest.mark.asyncio
    @respx.mock
    async def test_async_network_error_raises_connection_error(self, session: HTTPSession) -> None:
        session._config.max_retries = 0
        respx.get(f"{TRADING_BASE}/auctions").mock(
            side_effect=httpx.NetworkError("connection refused")
        )
        with pytest.raises(EXAAConnectionError, match="Network error"):
            await session.aget("auctions")
