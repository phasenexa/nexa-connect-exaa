"""Tests for RSAAuth and CertificateAuth."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from nexa_connect_exaa.auth import CertificateAuth, RSAAuth
from nexa_connect_exaa.exceptions import EXAAAuthError


class TestRSAAuth:
    def _make_mock_client(self, response_data: dict) -> AsyncMock:
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = response_data
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        return mock_client

    @pytest.mark.asyncio
    async def test_single_step_login_returns_token(self) -> None:
        auth = RSAAuth(username="trader1", pin="1234", passcode="654321")
        mock_client = self._make_mock_client({"status": "OK", "referenceToken": "tok123"})
        token = await auth.login(mock_client, "https://test-trade.exaa.at")
        assert token == "tok123"
        mock_client.post.assert_called_once()
        call_kwargs = mock_client.post.call_args
        body = call_kwargs[1]["json"]
        assert body["passcode"] == "654321"

    @pytest.mark.asyncio
    async def test_two_step_login_first_call_returns_empty(self) -> None:
        auth = RSAAuth(username="trader1", pin="1234")
        mock_client = self._make_mock_client({"status": "NEXTTOKEN"})
        token = await auth.login(mock_client, "https://test-trade.exaa.at")
        assert token == ""

    @pytest.mark.asyncio
    async def test_two_step_complete_login(self) -> None:
        auth = RSAAuth(username="trader1", pin="1234")
        # First call: no passcode
        first_response = MagicMock()
        first_response.status_code = 200
        first_response.json.return_value = {"status": "NEXTTOKEN"}
        # Second call: complete login
        second_response = MagicMock()
        second_response.status_code = 200
        second_response.json.return_value = {"status": "OK", "referenceToken": "tok456"}

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[first_response, second_response])

        await auth.login(mock_client, "https://test-trade.exaa.at")
        token = await auth.complete_login("999888", mock_client, "https://test-trade.exaa.at")
        assert token == "tok456"

    @pytest.mark.asyncio
    async def test_auth_failure_raises_exaa_auth_error(self) -> None:
        auth = RSAAuth(username="trader1", pin="wrong", passcode="000000")
        response = MagicMock()
        response.status_code = 403
        response.json.return_value = {
            "errors": [{"code": "A001", "message": "Invalid credentials"}]
        }
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)
        with pytest.raises(EXAAAuthError):
            await auth.login(mock_client, "https://test-trade.exaa.at")

    @pytest.mark.asyncio
    async def test_missing_token_in_ok_response_raises(self) -> None:
        auth = RSAAuth(username="trader1", pin="1234", passcode="111111")
        mock_client = self._make_mock_client({"status": "OK"})
        with pytest.raises(EXAAAuthError):
            await auth.login(mock_client, "https://test-trade.exaa.at")


class TestCertificateAuthX5t:
    """Tests for the x5t thumbprint computation (the most security-critical part)."""

    def _make_cert_auth(self, tmp_path: Path, key_pem: bytes, cert_pem: bytes) -> CertificateAuth:
        key_file = tmp_path / "key.pem"
        cert_file = tmp_path / "cert.pem"
        key_file.write_bytes(key_pem)
        cert_file.write_bytes(cert_pem)
        return CertificateAuth(
            username="trader1",
            password="1234",
            private_key_path=key_file,
            certificate_path=cert_file,
        )

    def _generate_key_and_cert(self) -> tuple[bytes, bytes]:
        """Generate a self-signed certificate for testing."""
        import datetime as dt

        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        key_pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )

        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test")])
        cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(dt.datetime.now(dt.UTC))
            .not_valid_after(dt.datetime.now(dt.UTC) + dt.timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        cert_pem = cert.public_bytes(serialization.Encoding.PEM)
        return key_pem, cert_pem

    def test_x5t_is_urlsafe_base64_without_padding(self, tmp_path: Path) -> None:
        key_pem, cert_pem = self._generate_key_and_cert()
        auth = self._make_cert_auth(tmp_path, key_pem, cert_pem)
        x5t = auth._compute_x5t()
        # Must not contain standard base64 characters
        assert "+" not in x5t
        assert "/" not in x5t
        assert "=" not in x5t

    def test_x5t_is_sha1_of_der_not_hex(self, tmp_path: Path) -> None:
        from cryptography import x509
        from cryptography.hazmat.primitives import serialization

        key_pem, cert_pem = self._generate_key_and_cert()
        auth = self._make_cert_auth(tmp_path, key_pem, cert_pem)

        # Compute expected value manually
        cert = x509.load_pem_x509_certificate(cert_pem)
        der_bytes = cert.public_bytes(serialization.Encoding.DER)
        expected = (
            base64.urlsafe_b64encode(hashlib.sha1(der_bytes).digest())  # noqa: S324
            .rstrip(b"=")
            .decode()
        )

        assert auth._compute_x5t() == expected

    @pytest.mark.asyncio
    async def test_login_builds_jws_and_posts(self, tmp_path: Path) -> None:
        key_pem, cert_pem = self._generate_key_and_cert()
        auth = self._make_cert_auth(tmp_path, key_pem, cert_pem)

        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"referenceToken": "tok789"}
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=response)

        token = await auth.login(mock_client, "https://test-trade.exaa.at")
        assert token == "tok789"

        call_args = mock_client.post.call_args
        body = call_args[1]["json"]
        assert body["method"] == "JWS"
        assert "credentials" in body
        # Verify it's a valid JWS (three parts)
        parts = body["credentials"].split(".")
        assert len(parts) == 3
