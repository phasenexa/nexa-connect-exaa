"""Tests for the exception hierarchy and raise_for_error_code factory."""

from __future__ import annotations

import pytest
from nexa_connect_exaa.exceptions import (
    AuctionNotFoundError,
    AuctionNotOpenError,
    EXAAAuthError,
    EXAAConnectionError,
    EXAAError,
    EXAAFunctionalError,
    EXAARequestError,
    EXAAServerError,
    EXAASyntaxError,
    EXAAValueError,
    InvalidProductError,
    MonotonicViolationError,
    PollingTimeoutError,
    raise_for_error_code,
)


class TestEXAAError:
    def test_attributes(self) -> None:
        exc = EXAAError(code="F010", message="test", path="orders[0]", support_reference="REF1")
        assert exc.code == "F010"
        assert exc.message == "test"
        assert exc.path == "orders[0]"
        assert exc.support_reference == "REF1"

    def test_str(self) -> None:
        exc = EXAAError(code="F010", message="Monotonic rule violated")
        assert str(exc) == "[F010] Monotonic rule violated"

    def test_repr(self) -> None:
        exc = EXAAError(code="F010", message="test")
        assert "EXAAError" in repr(exc)
        assert "F010" in repr(exc)

    def test_optional_fields_default_none(self) -> None:
        exc = EXAAError(code="U001", message="server error")
        assert exc.path is None
        assert exc.support_reference is None

    def test_is_exception(self) -> None:
        with pytest.raises(EXAAError):
            raise EXAAError(code="U001", message="err")


class TestConnectionError:
    def test_code_is_network(self) -> None:
        exc = EXAAConnectionError("timeout")
        assert exc.code == "NETWORK"

    def test_original_error(self) -> None:
        inner = RuntimeError("inner")
        exc = EXAAConnectionError("outer", original_error=inner)
        assert exc.original_error is inner


class TestPollingTimeoutError:
    def test_attributes(self) -> None:
        exc = PollingTimeoutError("Classic_2026-04-01", "AUCTIONED", 3600.0)
        assert exc.auction_id == "Classic_2026-04-01"
        assert exc.target_state == "AUCTIONED"
        assert exc.timeout == 3600.0
        assert exc.code == "TIMEOUT"

    def test_is_exaa_error(self) -> None:
        assert issubclass(PollingTimeoutError, EXAAError)


class TestRaiseForErrorCode:
    @pytest.mark.parametrize(
        "code,expected_class",
        [
            ("A001", EXAAAuthError),
            ("A002", EXAAAuthError),
            ("A003", EXAAAuthError),
            ("A004", EXAAAuthError),
            ("S001", EXAASyntaxError),
            ("S005", EXAASyntaxError),
            ("F001", EXAAFunctionalError),
            ("F006", AuctionNotFoundError),
            ("F008", AuctionNotOpenError),
            ("F010", MonotonicViolationError),
            ("F015", InvalidProductError),
            ("F034", EXAAFunctionalError),
            ("R001", EXAARequestError),
            ("R004", EXAARequestError),
            ("V001", EXAAValueError),
            ("V005", EXAAValueError),
            ("U001", EXAAServerError),
            ("U003", EXAAServerError),
        ],
    )
    def test_known_codes(self, code: str, expected_class: type) -> None:
        with pytest.raises(expected_class) as exc_info:
            raise_for_error_code(code, "test message")
        assert exc_info.value.code == code
        assert exc_info.value.message == "test message"

    def test_unknown_code_with_known_prefix_fallback(self) -> None:
        with pytest.raises(EXAAAuthError):
            raise_for_error_code("A099", "unknown auth code")

    def test_completely_unknown_code_falls_back_to_base(self) -> None:
        with pytest.raises(EXAAError):
            raise_for_error_code("Z999", "completely unknown")

    def test_path_preserved(self) -> None:
        with pytest.raises(MonotonicViolationError) as exc_info:
            raise_for_error_code("F010", "monotonic violation", path="orders[0].price")
        assert exc_info.value.path == "orders[0].price"

    def test_support_reference_preserved(self) -> None:
        with pytest.raises(EXAAServerError) as exc_info:
            raise_for_error_code("U001", "server error", support_reference="SR-123")
        assert exc_info.value.support_reference == "SR-123"

    def test_specific_subclasses_are_functional_errors(self) -> None:
        assert issubclass(AuctionNotFoundError, EXAAFunctionalError)
        assert issubclass(AuctionNotOpenError, EXAAFunctionalError)
        assert issubclass(MonotonicViolationError, EXAAFunctionalError)
        assert issubclass(InvalidProductError, EXAAFunctionalError)

    def test_all_classes_inherit_exaa_error(self) -> None:
        for cls in [
            EXAAAuthError,
            EXAASyntaxError,
            EXAAFunctionalError,
            AuctionNotFoundError,
            EXAARequestError,
            EXAAValueError,
            EXAAServerError,
            EXAAConnectionError,
        ]:
            assert issubclass(cls, EXAAError)
