"""Shared enums and error response models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class Units(str, Enum):
    """Physical units used in EXAA order and result values."""

    MWH_H = "MWH_H"
    EUR_MWH = "EUR_MWH"


class ErrorDetail(BaseModel):
    """A single error entry from an EXAA error response.

    Args:
        code: EXAA error code (e.g. ``"F010"``).
        message: Human-readable description of the error.
        path: JSON path to the offending field, if applicable.
        support_reference: EXAA support reference, if provided.
    """

    model_config = ConfigDict(populate_by_name=True)

    code: str
    message: str
    path: str | None = Field(default=None)
    support_reference: str | None = Field(default=None, alias="supportReference")


class ErrorResponse(BaseModel):
    """Top-level error response body returned by the EXAA API on 4xx/5xx.

    Args:
        errors: List of one or more error details.
    """

    model_config = ConfigDict(populate_by_name=True)

    errors: list[ErrorDetail]
