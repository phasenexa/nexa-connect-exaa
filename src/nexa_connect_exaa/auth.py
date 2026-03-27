"""Authentication providers for the EXAA Trading API.

Two authentication mechanisms are supported:

- :class:`RSAAuth` — RSA token (V1). Supports both hardware tokens
  (single-step) and on-demand tokens delivered via email/SMS (two-step).
- :class:`CertificateAuth` — Certificate-based JWS (V2). Signs a JWT with an
  RSA private key and includes the certificate thumbprint in the header.
"""

from __future__ import annotations

import base64
import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

from nexa_connect_exaa.exceptions import EXAAAuthError, EXAAConnectionError

if TYPE_CHECKING:
    import httpx


@dataclass
class RSAAuth:
    """RSA token authentication (API V1).

    Supports hardware tokens (single call with ``passcode``) and on-demand
    tokens (two-step: first call triggers SMS/email, second call with
    ``complete_login``).

    Args:
        username: EXAA trading username.
        pin: Static PIN associated with the RSA token.
        passcode: One-time passcode from the hardware token. Leave ``None``
            for the on-demand (two-step) flow.
    """

    username: str
    pin: str
    passcode: str | None = None
    _pending_username: str = field(default="", init=False, repr=False)

    async def login(self, client: httpx.AsyncClient, base_url: str) -> str:
        """Authenticate with the EXAA RSA (V1) endpoint.

        For hardware tokens, includes the passcode in the request and returns
        the bearer token immediately.

        For on-demand tokens (``passcode=None``), sends the first request to
        trigger passcode delivery and returns an empty string. The caller must
        invoke :meth:`complete_login` after the user receives the passcode.

        Args:
            client: An open ``httpx.AsyncClient`` to use for the request.
            base_url: EXAA environment base URL (e.g.
                ``"https://test-trade.exaa.at"``).

        Returns:
            Bearer token string, or ``""`` when waiting for on-demand
            passcode delivery.

        Raises:
            EXAAAuthError: If the credentials are rejected.
            EXAAConnectionError: If the HTTP call fails.
        """
        payload: dict[str, str] = {"username": self.username, "pin": self.pin}
        if self.passcode is not None:
            payload["passcode"] = self.passcode

        response = await _post_login(client, f"{base_url}/login/V1/login", payload)
        status = response.get("status", "")
        if status == "OK":
            token = response.get("referenceToken", "")
            if not token:
                raise EXAAAuthError(
                    code="A001",
                    message="Login succeeded but no referenceToken was returned",
                )
            return str(token)
        if status == "NEXTTOKEN":
            self._pending_username = self.username
            return ""
        raise EXAAAuthError(
            code="A001",
            message=f"Unexpected login status: {status!r}",
        )

    async def complete_login(self, passcode: str, client: httpx.AsyncClient, base_url: str) -> str:
        """Complete the two-step on-demand token login.

        Args:
            passcode: One-time passcode received via email or SMS.
            client: An open ``httpx.AsyncClient``.
            base_url: EXAA environment base URL.

        Returns:
            Bearer token string.

        Raises:
            EXAAAuthError: If the passcode is incorrect.
            EXAAConnectionError: If the HTTP call fails.
        """
        payload = {
            "username": self._pending_username or self.username,
            "pin": self.pin,
            "passcode": passcode,
        }
        response = await _post_login(client, f"{base_url}/login/V1/login", payload)
        token = response.get("referenceToken", "")
        if not token:
            raise EXAAAuthError(
                code="A001",
                message="complete_login succeeded but no referenceToken was returned",
            )
        return str(token)


@dataclass
class CertificateAuth:
    """Certificate-based JWS authentication (API V2).

    Constructs an RS256-signed JWT with the certificate thumbprint (``x5t``)
    in the JOSE header and posts it to the V2 login endpoint.

    Args:
        username: EXAA trading username.
        password: 4-digit static password.
        private_key_path: Path to the RSA private key PEM file.
        certificate_path: Path to the X.509 certificate PEM file.
    """

    username: str
    password: str
    private_key_path: Path
    certificate_path: Path

    async def login(self, client: httpx.AsyncClient, base_url: str) -> str:
        """Authenticate with the EXAA certificate (V2) endpoint.

        Args:
            client: An open ``httpx.AsyncClient``.
            base_url: EXAA environment base URL.

        Returns:
            Bearer token string.

        Raises:
            EXAAAuthError: If the JWS is rejected.
            EXAAConnectionError: If the HTTP call fails.
        """
        jws_token = self._build_jws(base_url)
        payload = {"method": "JWS", "credentials": jws_token}
        response = await _post_login(client, f"{base_url}/login/V2/login", payload)
        token = response.get("referenceToken", "")
        if not token:
            raise EXAAAuthError(
                code="A001",
                message="Certificate login succeeded but no referenceToken was returned",
            )
        return str(token)

    def _build_jws(self, base_url: str) -> str:
        """Construct the JWS compact serialisation for V2 authentication.

        Args:
            base_url: EXAA environment base URL. Used to derive the ``aud``
                claim (hostname without scheme).

        Returns:
            JWS compact serialisation string (three base64url segments joined
            by ``"."``).
        """
        private_key = self._load_private_key()
        x5t = self._compute_x5t()

        # Derive audience from base URL hostname
        aud = base_url.replace("https://", "").replace("http://", "").rstrip("/")

        now = int(time.time())
        claims: dict[str, Any] = {
            "sub": self.username,
            "iat": now,
            "exp": now + 55,  # Within 60s; use 55 to guard against clock drift
            "password": self.password,
            "aud": aud,
        }
        additional_headers: dict[str, Any] = {
            "x5t": x5t,
            "sub": self.username,
        }
        token: str = jwt.encode(
            claims,
            private_key,
            algorithm="RS256",
            headers=additional_headers,
        )
        return token

    def _compute_x5t(self) -> str:
        """Compute the base64url-encoded SHA-1 thumbprint of the certificate.

        The x5t header parameter must be the base64url encoding of the binary
        SHA-1 hash of the DER-encoded certificate. Using ``hexdigest()``
        instead of ``digest()``, or standard base64 instead of URL-safe
        base64, will produce an incorrect thumbprint.

        Returns:
            base64url-encoded SHA-1 hash without padding characters.
        """
        cert_pem = self.certificate_path.read_bytes()
        cert = x509.load_pem_x509_certificate(cert_pem)
        der_bytes = cert.public_bytes(serialization.Encoding.DER)
        # Must be binary digest, NOT hexdigest
        sha1_binary = hashlib.sha1(der_bytes).digest()  # noqa: S324
        # Must be urlsafe base64 without padding
        return base64.urlsafe_b64encode(sha1_binary).rstrip(b"=").decode()

    def _load_private_key(self) -> RSAPrivateKey:
        """Load the RSA private key from the configured PEM file."""
        key_pem = self.private_key_path.read_bytes()
        key = serialization.load_pem_private_key(key_pem, password=None)
        if not isinstance(key, RSAPrivateKey):
            raise EXAAAuthError(
                code="A001",
                message=(
                    f"Expected an RSA private key, got {type(key).__name__}. "
                    f"Check the key file at {self.private_key_path}"
                ),
            )
        return key


async def _post_login(
    client: httpx.AsyncClient,
    url: str,
    payload: dict[str, str],
) -> dict[str, Any]:
    """POST to a login endpoint and return the parsed JSON response body.

    Raises:
        EXAAAuthError: If the server returns 401 or 403.
        EXAAConnectionError: If the request fails at the transport level.
    """
    import httpx as _httpx

    try:
        response = await client.post(url, json=payload)
    except _httpx.TimeoutException as exc:
        raise EXAAConnectionError(f"Timeout connecting to {url}", original_error=exc) from exc
    except _httpx.NetworkError as exc:
        raise EXAAConnectionError(
            f"Network error connecting to {url}: {exc}", original_error=exc
        ) from exc

    if response.status_code in (401, 403):
        _try_raise_from_body(response)
        raise EXAAAuthError(
            code="A001",
            message=f"Authentication failed (HTTP {response.status_code})",
        )
    if response.status_code >= 400:
        _try_raise_from_body(response)
        raise EXAAAuthError(
            code="A001",
            message=(
                f"Login endpoint returned HTTP {response.status_code}: " f"{response.text[:200]}"
            ),
        )

    result: dict[str, Any] = response.json()
    return result


def _try_raise_from_body(response: httpx.Response) -> None:
    """Attempt to parse an EXAA error body and raise the appropriate exception.

    If the body cannot be parsed as an error response, silently returns so
    that the caller can raise a generic exception instead.
    """
    from nexa_connect_exaa.exceptions import raise_for_error_code
    from nexa_connect_exaa.models.common import ErrorResponse

    try:
        err = ErrorResponse.model_validate(response.json())
    except Exception:
        return
    if err.errors:
        first = err.errors[0]
        raise_for_error_code(first.code, first.message, first.path, first.support_reference)
