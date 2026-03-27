"""Exception hierarchy for the EXAA Trading API client.

EXAA returns structured error codes in the format ``{prefix}{number}`` where
prefix indicates the error class:

- ``A`` — Authentication errors (HTTP 403)
- ``S`` — Syntax errors (HTTP 400)
- ``F`` — Functional errors (HTTP 400/404/409)
- ``R`` — Request errors (HTTP 404/405/415)
- ``V`` — Value errors (HTTP 400)
- ``U`` — Server errors (HTTP 500)
"""

from __future__ import annotations


class EXAAError(Exception):
    """Base exception for all EXAA API errors.

    Args:
        code: EXAA error code (e.g. ``"F010"``). Use ``"NETWORK"`` for
            connection-level errors not originating from the EXAA API.
        message: Human-readable error description.
        path: JSON path to the offending field, if applicable.
        support_reference: EXAA support reference identifier, if provided.
    """

    def __init__(
        self,
        code: str,
        message: str,
        path: str | None = None,
        support_reference: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.support_reference = support_reference

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, message={self.message!r}, "
            f"path={self.path!r})"
        )


class EXAAAuthError(EXAAError):
    """Authentication error (A001–A004, HTTP 403).

    Raised when the provided credentials are invalid, the token has expired,
    or the user lacks permission for the requested operation.
    """


class EXAASyntaxError(EXAAError):
    """Syntax error in the request (S001–S005, HTTP 400).

    Raised when the request body or parameters fail structural validation
    before business logic is applied.
    """


class EXAAFunctionalError(EXAAError):
    """Functional/business-logic error (F001–F034, HTTP 400/404/409).

    Base class for errors that occur when a syntactically valid request
    violates a business rule or refers to a resource in an invalid state.
    """


class AuctionNotFoundError(EXAAFunctionalError):
    """Auction with the given ID does not exist (F006)."""


class AuctionNotOpenError(EXAAFunctionalError):
    """Auction gate is closed; orders cannot be submitted or modified (F008)."""


class MonotonicViolationError(EXAAFunctionalError):
    """Price/volume curve violates the monotonic constraint (F010).

    The ``path`` attribute indicates which price-volume pair is the first
    violation point.
    """


class InvalidProductError(EXAAFunctionalError):
    """Product ID is not valid for this auction (F015)."""


class EXAARequestError(EXAAError):
    """Request-level error (R001–R004, HTTP 404/405/415).

    Raised for invalid HTTP method, unsupported media type, or an unknown
    endpoint path.
    """


class EXAAValueError(EXAAError):
    """Value validation error (V001–V005, HTTP 400).

    Raised when a field value is syntactically valid but semantically out of
    range (e.g. price outside [-500, 4000]).
    """


class EXAAServerError(EXAAError):
    """Internal server error (U001–U003, HTTP 500).

    Raised when EXAA returns an unrecoverable server-side error. Transient
    server errors are retried automatically by the HTTP session before this
    exception is raised.
    """


class EXAAConnectionError(EXAAError):
    """Network or connection error (synthetic code ``"NETWORK"``).

    Raised for timeouts, DNS failures, connection resets, and other transport-
    layer problems that prevent a response from being received.

    Args:
        message: Description of the network failure.
        original_error: The underlying exception, if available.
    """

    def __init__(
        self,
        message: str,
        original_error: BaseException | None = None,
    ) -> None:
        super().__init__(code="NETWORK", message=message)
        self.original_error = original_error


class PollingTimeoutError(EXAAError):
    """Raised when ``wait_for_state`` exceeds the configured timeout.

    Args:
        auction_id: The auction being polled.
        target_state: The state that was never reached.
        timeout: The timeout in seconds that was exceeded.
    """

    def __init__(self, auction_id: str, target_state: str, timeout: float) -> None:
        message = (
            f"Auction {auction_id!r} did not reach state {target_state!r} " f"within {timeout}s"
        )
        super().__init__(code="TIMEOUT", message=message)
        self.auction_id = auction_id
        self.target_state = target_state
        self.timeout = timeout


# ---------------------------------------------------------------------------
# Error code dispatch
# ---------------------------------------------------------------------------

_EXACT_CODE_MAP: dict[str, type[EXAAError]] = {
    "F006": AuctionNotFoundError,
    "F008": AuctionNotOpenError,
    "F010": MonotonicViolationError,
    "F015": InvalidProductError,
}

_PREFIX_MAP: dict[str, type[EXAAError]] = {
    "A": EXAAAuthError,
    "S": EXAASyntaxError,
    "F": EXAAFunctionalError,
    "R": EXAARequestError,
    "V": EXAAValueError,
    "U": EXAAServerError,
}


def raise_for_error_code(
    code: str,
    message: str,
    path: str | None = None,
    support_reference: str | None = None,
) -> None:
    """Raise the most specific exception for the given EXAA error code.

    Looks up the exact code first, then falls back to the prefix-level class,
    then falls back to :class:`EXAAError` for completely unknown codes. Always
    raises — never returns.

    Args:
        code: EXAA error code (e.g. ``"F010"``).
        message: Human-readable error description from the API.
        path: JSON path to the offending field.
        support_reference: EXAA support reference string.

    Raises:
        EXAAError: Always raises an appropriate subclass.
    """
    exc_class: type[EXAAError] = _EXACT_CODE_MAP.get(code) or _PREFIX_MAP.get(code[:1], EXAAError)
    raise exc_class(
        code=code,
        message=message,
        path=path,
        support_reference=support_reference,
    )
