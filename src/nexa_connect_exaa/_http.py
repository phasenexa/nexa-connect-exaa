"""HTTP session management for the EXAA Trading API client.

Wraps ``httpx`` with:
- Bearer token injection on every request
- Automatic parsing of EXAA error responses (``{"errors": [...]}`` bodies)
- Exponential back-off retry on transient server errors (5xx) and network
  failures
- Sync and async variants of the core HTTP verbs
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from nexa_connect_exaa.config import EXAAConfig
from nexa_connect_exaa.exceptions import (
    EXAAConnectionError,
    EXAAServerError,
    raise_for_error_code,
)
from nexa_connect_exaa.models.common import ErrorResponse

# HTTP status codes that warrant a retry.
_RETRYABLE_STATUS = frozenset({500, 502, 503, 504})


class HTTPSession:
    """Managed HTTP session for the EXAA Trading API.

    Provides sync and async wrappers around ``httpx`` with automatic auth
    header injection, EXAA error response parsing, and transient-error retry.

    Call :meth:`open` / :meth:`aopen` (or use as a context manager) before
    making requests.

    Args:
        config: Client configuration (base URL, timeouts, retry settings).
    """

    def __init__(self, config: EXAAConfig) -> None:
        self._config = config
        self._token: str | None = None
        self._async_client: httpx.AsyncClient | None = None
        self._sync_client: httpx.Client | None = None

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    @property
    def base_url(self) -> str:
        """Root URL of the EXAA environment (e.g. ``https://trade.exaa.at``)."""
        return self._config.base_url

    @property
    def trading_base_url(self) -> str:
        """Base URL for all trading API calls."""
        return f"{self._config.base_url}/exaa-trading-api/V1"

    @property
    def login_base_url(self) -> str:
        """Base URL for authentication calls."""
        return f"{self._config.base_url}/login"

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def set_token(self, token: str) -> None:
        """Store the bearer token to use on subsequent requests.

        Args:
            token: Bearer token returned by the EXAA login endpoint.
        """
        self._token = token

    def _auth_headers(self) -> dict[str, str]:
        if self._token is None:
            raise EXAAConnectionError(
                "No authentication token. Call auth.login() before making API requests."
            )
        return {"Authorization": f"Bearer {self._token}"}

    # ------------------------------------------------------------------
    # Lifecycle (sync)
    # ------------------------------------------------------------------

    def open(self) -> HTTPSession:
        """Open the underlying sync HTTP client."""
        self._sync_client = httpx.Client(timeout=self._config.timeout)
        return self

    def close(self) -> None:
        """Close the underlying sync HTTP client."""
        if self._sync_client is not None:
            self._sync_client.close()
            self._sync_client = None

    def __enter__(self) -> HTTPSession:
        return self.open()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Lifecycle (async)
    # ------------------------------------------------------------------

    async def aopen(self) -> HTTPSession:
        """Open the underlying async HTTP client."""
        self._async_client = httpx.AsyncClient(timeout=self._config.timeout)
        return self

    async def aclose(self) -> None:
        """Close the underlying async HTTP client."""
        if self._async_client is not None:
            await self._async_client.aclose()
            self._async_client = None

    async def __aenter__(self) -> HTTPSession:
        return await self.aopen()

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.aclose()

    # ------------------------------------------------------------------
    # Async HTTP verbs
    # ------------------------------------------------------------------

    async def aget(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Async GET to a trading API path.

        Args:
            path: Path relative to ``trading_base_url`` (without leading
                slash).
            params: Optional query parameters.

        Returns:
            Parsed JSON response body.
        """
        return await self._arequest("GET", path, params=params)

    async def apost(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Async POST to a trading API path.

        Args:
            path: Path relative to ``trading_base_url``.
            json: Request body (serialised to JSON).

        Returns:
            Parsed JSON response body, or ``None`` for 204 responses.
        """
        return await self._arequest("POST", path, json=json)

    async def adelete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Async DELETE to a trading API path.

        Args:
            path: Path relative to ``trading_base_url``.
            params: Optional query parameters (e.g. ``accountIds``).
        """
        await self._arequest("DELETE", path, params=params)

    async def apost_raw(
        self,
        url: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Async POST to an absolute URL (used for auth endpoints).

        Args:
            url: Full URL.
            json: Request body.

        Returns:
            Parsed JSON response body.
        """
        if self._async_client is None:
            raise EXAAConnectionError("HTTP session is not open. Use as a context manager.")
        response = await self._async_client.post(url, json=json)
        return self._handle_response(response)

    # ------------------------------------------------------------------
    # Sync HTTP verbs
    # ------------------------------------------------------------------

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        """Sync GET to a trading API path."""
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Sync POST to a trading API path."""
        return self._request("POST", path, json=json)

    def delete(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> None:
        """Sync DELETE to a trading API path."""
        self._request("DELETE", path, params=params)

    # ------------------------------------------------------------------
    # Internal request helpers
    # ------------------------------------------------------------------

    async def _arequest(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if self._async_client is None:
            raise EXAAConnectionError("HTTP session is not open. Use as a context manager.")

        url = f"{self.trading_base_url}/{path}"
        headers = self._auth_headers()

        for attempt in range(self._config.max_retries + 1):
            try:
                response = await self._async_client.request(
                    method, url, params=params, json=json, headers=headers
                )
            except httpx.TimeoutException as exc:
                if attempt < self._config.max_retries:
                    await asyncio.sleep(self._config.retry_backoff_factor * (2**attempt))
                    continue
                raise EXAAConnectionError(
                    f"Request timed out after {self._config.timeout}s: {method} {url}",
                    original_error=exc,
                ) from exc
            except httpx.NetworkError as exc:
                if attempt < self._config.max_retries:
                    await asyncio.sleep(self._config.retry_backoff_factor * (2**attempt))
                    continue
                raise EXAAConnectionError(
                    f"Network error: {exc}",
                    original_error=exc,
                ) from exc

            if response.status_code in _RETRYABLE_STATUS and attempt < self._config.max_retries:
                await asyncio.sleep(self._config.retry_backoff_factor * (2**attempt))
                continue

            return self._handle_response(response)

        # Should not be reached, but satisfies the type checker.
        raise EXAAServerError(code="U001", message="Max retries exceeded")  # pragma: no cover

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if self._sync_client is None:
            raise EXAAConnectionError("HTTP session is not open. Use as a context manager.")

        url = f"{self.trading_base_url}/{path}"
        headers = self._auth_headers()

        for attempt in range(self._config.max_retries + 1):
            try:
                response = self._sync_client.request(
                    method, url, params=params, json=json, headers=headers
                )
            except httpx.TimeoutException as exc:
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_backoff_factor * (2**attempt))
                    continue
                raise EXAAConnectionError(
                    f"Request timed out after {self._config.timeout}s: {method} {url}",
                    original_error=exc,
                ) from exc
            except httpx.NetworkError as exc:
                if attempt < self._config.max_retries:
                    time.sleep(self._config.retry_backoff_factor * (2**attempt))
                    continue
                raise EXAAConnectionError(
                    f"Network error: {exc}",
                    original_error=exc,
                ) from exc

            if response.status_code in _RETRYABLE_STATUS and attempt < self._config.max_retries:
                time.sleep(self._config.retry_backoff_factor * (2**attempt))
                continue

            return self._handle_response(response)

        raise EXAAServerError(code="U001", message="Max retries exceeded")  # pragma: no cover

    @staticmethod
    def _handle_response(response: httpx.Response) -> Any:
        """Parse a response or raise the appropriate EXAA exception.

        Returns:
            Parsed JSON body for 2xx responses with a body, or ``None`` for
            204 No Content.
        """
        if response.status_code == 204:
            return None
        if response.status_code < 400:
            return response.json()
        # Error response
        HTTPSession._parse_and_raise(response)
        return None  # pragma: no cover

    @staticmethod
    def _parse_and_raise(response: httpx.Response) -> None:
        """Parse the EXAA error response body and raise the appropriate exception.

        Falls back to a generic ``EXAAServerError`` or ``EXAAConnectionError``
        if the body cannot be parsed as an EXAA error response.
        """
        try:
            err = ErrorResponse.model_validate(response.json())
        except Exception as exc:
            raise EXAAServerError(
                code="U001",
                message=(f"HTTP {response.status_code}: " f"{response.text[:500]}"),
            ) from exc

        if not err.errors:
            raise EXAAServerError(
                code="U001",
                message=f"HTTP {response.status_code}: empty error list",
            )

        first = err.errors[0]
        raise_for_error_code(
            first.code,
            first.message,
            first.path,
            first.support_reference,
        )
