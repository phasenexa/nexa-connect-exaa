"""Order submission models for the EXAA Trading API.

Key serialisation notes
-----------------------
- Prices and volumes are ``decimal.Decimal`` in the public API but serialise
  to JSON numbers (floats) when sent to EXAA. This is handled via Pydantic's
  ``PlainSerializer``.
- The ``"15minProducts"`` JSON key starts with a digit and is mapped to
  ``quarter_hourly_products`` via a ``Field(alias=...)``.
- Always serialise request bodies with ``model.model_dump(by_alias=True,
  mode="json")`` to get the correct camelCase keys and float values.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.functional_serializers import PlainSerializer

# Decimal fields that must be serialised as JSON numbers (floats).
_DecimalAsFloat = Annotated[Decimal, PlainSerializer(lambda x: float(x), return_type=float)]


class PriceVolumePair(BaseModel):
    """A single step on a price/volume supply or demand curve.

    Args:
        price: Bid or offer price in EUR/MWh with 2 decimal places, or the
            string ``"M"`` for a market order. Valid numeric range is
            (-500, 4000) exclusive — use ``"M"`` at the boundaries.
        volume: Volume in MWh/h with 1 decimal place. Positive = buy,
            negative = sell.
    """

    model_config = ConfigDict(populate_by_name=True)

    price: _DecimalAsFloat | str
    volume: _DecimalAsFloat

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: object) -> object:
        """Coerce numeric strings to Decimal; only allow ``"M"`` as a string."""
        if isinstance(v, str) and v != "M":
            try:
                return Decimal(v)
            except Exception:
                raise ValueError(
                    f"price must be a Decimal, numeric string, or 'M', got {v!r}"
                ) from None
        return v


class ProductOrder(BaseModel):
    """Order for a single product within a product-type group.

    Args:
        product_id: Exchange-assigned product identifier (e.g. ``"hEXA10"``).
        fill_or_kill: Whether the order must be fully filled or cancelled.
            Allowed values depend on auction type and product type — see
            CLAUDE.md for the full constraint matrix.
        price_volume_pairs: Ordered list of price/volume steps forming the
            bid or offer curve.
    """

    model_config = ConfigDict(populate_by_name=True)

    product_id: str = Field(alias="productId")
    fill_or_kill: bool = Field(alias="fillOrKill")
    price_volume_pairs: list[PriceVolumePair] = Field(alias="priceVolumePairs")


class ProductTypeOrders(BaseModel):
    """Orders for all products of the same type within a trade account.

    Args:
        type_of_order: Curve shape — ``"LINEAR"`` (linear interpolation
            between steps) or ``"STEP"`` (staircase). Applies to all products
            in this group.
        products: Individual product orders.
    """

    model_config = ConfigDict(populate_by_name=True)

    type_of_order: str = Field(alias="typeOfOrder")
    products: list[ProductOrder]


class AccountOrders(BaseModel):
    """All orders for a single trade account.

    When this object is included in a ``POST orders`` request, **all existing
    orders for this account are replaced**. Omitting a product type (e.g.
    block products) deletes any existing orders of that type for the account.

    Args:
        account_id: Trade account identifier.
        affected: ``True`` when a submit operation modified orders for this
            account. Always ``False`` in request payloads.
        hourly_products: Hourly product orders.
        block_products: Block product orders.
        quarter_hourly_products: 15-minute product orders (Classic only).
            Serialised as ``"15minProducts"`` in the EXAA JSON schema.
    """

    model_config = ConfigDict(populate_by_name=True)

    account_id: str = Field(alias="accountId")
    affected: bool = False
    hourly_products: ProductTypeOrders | None = Field(alias="hourlyProducts", default=None)
    block_products: ProductTypeOrders | None = Field(alias="blockProducts", default=None)
    # Digit-leading JSON key — must use Field alias.
    quarter_hourly_products: ProductTypeOrders | None = Field(alias="15minProducts", default=None)


class OrderSubmission(BaseModel):
    """A complete order submission or retrieval payload.

    Contains orders for one or more trade accounts. On ``POST``, every
    account listed has its orders fully replaced.

    Args:
        orders: Per-account order data.
    """

    model_config = ConfigDict(populate_by_name=True)

    orders: list[AccountOrders]

    @classmethod
    def build(
        cls,
        account_id: str,
        *,
        hourly_products: dict[str, Any] | ProductTypeOrders | None = None,
        block_products: dict[str, Any] | ProductTypeOrders | None = None,
        quarter_hourly_products: dict[str, Any] | ProductTypeOrders | None = None,
    ) -> OrderSubmission:
        """Convenience factory for a single-account order submission.

        Args:
            account_id: Trade account identifier.
            hourly_products: Hourly product orders as a ``ProductTypeOrders``
                instance or a plain dict matching the ``ProductTypeOrders``
                schema (camelCase keys are supported via aliases).
            block_products: Block product orders.
            quarter_hourly_products: 15-minute product orders (Classic only).

        Returns:
            An ``OrderSubmission`` containing a single ``AccountOrders``.

        Example::

            submission = OrderSubmission.build(
                account_id="APTAP1",
                hourly_products={
                    "typeOfOrder": "LINEAR",
                    "products": [
                        {
                            "productId": "hEXA10",
                            "fillOrKill": False,
                            "priceVolumePairs": [
                                {"price": "40.00", "volume": "250.0"},
                            ],
                        }
                    ],
                },
            )
        """

        def _coerce(
            val: dict[str, Any] | ProductTypeOrders | None,
        ) -> ProductTypeOrders | None:
            if val is None:
                return None
            if isinstance(val, ProductTypeOrders):
                return val
            return ProductTypeOrders.model_validate(val)

        account = AccountOrders.model_validate(
            {
                "accountId": account_id,
                "hourlyProducts": _coerce(hourly_products),
                "blockProducts": _coerce(block_products),
                "15minProducts": _coerce(quarter_hourly_products),
            }
        )
        return cls(orders=[account])
