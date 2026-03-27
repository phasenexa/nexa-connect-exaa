"""Environment configuration for the EXAA Trading API client."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Environment(str, Enum):
    """EXAA deployment environment.

    Inherits from ``str`` so that ``env == "production"`` comparisons work.
    """

    PRODUCTION = "production"
    TEST = "test"
    STUDY = "study"


_BASE_URLS: dict[Environment, str] = {
    Environment.PRODUCTION: "https://trade.exaa.at",
    Environment.TEST: "https://test-trade.exaa.at",
    Environment.STUDY: "https://study-trade.exaa.at",
}


@dataclass
class EXAAConfig:
    """Client configuration for the EXAA Trading API.

    Args:
        environment: Which EXAA environment to connect to. Ignored when
            ``base_url`` is supplied explicitly.
        base_url: Override the environment's base URL. Useful for pointing at
            a local mock server in tests.
        timeout: HTTP request timeout in seconds.
        max_retries: Maximum number of retry attempts for transient server
            errors (5xx) and network failures.
        retry_backoff_factor: Multiplier for exponential back-off between
            retries. Wait time = ``retry_backoff_factor * (2 ** attempt)``.
        token_refresh_margin: Seconds before the 24-hour token expiry at which
            the client will proactively re-authenticate. Defaults to 3600
            (re-auth after 23 hours).
    """

    environment: Environment = Environment.PRODUCTION
    base_url: str = field(default="")
    timeout: float = 30.0
    max_retries: int = 3
    retry_backoff_factor: float = 1.0
    token_refresh_margin: float = 3600.0

    def __post_init__(self) -> None:
        if not self.base_url:
            self.base_url = _BASE_URLS[self.environment]
