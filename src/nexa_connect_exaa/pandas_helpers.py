"""Optional pandas integration for the EXAA Trading API client.

Functions in this module require ``pandas`` to be installed::

    pip install nexa-connect-exaa[pandas]

All functions guard the import and raise a helpful ``ImportError`` if pandas
is not available. Type hints for ``pd.DataFrame`` are quoted strings so that
the module can be imported without pandas installed.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import pandas as pd

from nexa_connect_exaa.models.orders import (
    AccountOrders,
    OrderSubmission,
    PriceVolumePair,
    ProductOrder,
    ProductTypeOrders,
)
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)


def _require_pandas() -> None:
    """Raise ``ImportError`` with an install hint if pandas is missing."""
    try:
        import pandas  # noqa: F401
    except ImportError:
        raise ImportError(
            "pandas is required for DataFrame operations. "
            "Install with: pip install nexa-connect-exaa[pandas]"
        ) from None


def trade_results_to_df(results: list[TradeResult]) -> pd.DataFrame:
    """Convert a list of trade results to a DataFrame.

    Args:
        results: Trade results as returned by
            :meth:`~nexa_connect_exaa.client.EXAAClient.get_trade_results`.

    Returns:
        DataFrame with one row per trade result. Columns match the
        ``TradeResult`` field names (snake_case).
    """
    _require_pandas()
    import pandas as pd

    return pd.DataFrame([r.model_dump() for r in results])


def market_results_to_df(results: list[MarketResult]) -> pd.DataFrame:
    """Convert a list of market results to a DataFrame.

    Args:
        results: Market results as returned by
            :meth:`~nexa_connect_exaa.client.EXAAClient.get_market_results`.

    Returns:
        DataFrame with one row per product/price-zone combination.
    """
    _require_pandas()
    import pandas as pd

    return pd.DataFrame([r.model_dump() for r in results])


def trade_confirmations_to_df(
    confirmations: list[TradeConfirmation],
) -> pd.DataFrame:
    """Convert a list of trade confirmations to a DataFrame.

    Args:
        confirmations: Confirmations as returned by
            :meth:`~nexa_connect_exaa.client.EXAAClient.get_trade_confirmations`.

    Returns:
        DataFrame with one row per confirmation.
    """
    _require_pandas()
    import pandas as pd

    return pd.DataFrame([c.model_dump() for c in confirmations])


def df_to_order_submission(
    df: pd.DataFrame,
    account_id: str,
    product_type: str,
    type_of_order: str,
) -> OrderSubmission:
    """Build an :class:`~nexa_connect_exaa.models.orders.OrderSubmission` from a DataFrame.

    The DataFrame must have the columns ``product_id``, ``price``, and
    ``volume``. Each row represents one price/volume step. Rows are grouped
    by ``product_id``, with one :class:`~nexa_connect_exaa.models.orders.ProductOrder`
    per unique product ID.

    Args:
        df: DataFrame with columns ``product_id`` (str), ``price``
            (numeric or ``"M"`` for market orders), and ``volume`` (numeric).
        account_id: Trade account identifier.
        product_type: Which product type slot to populate. One of
            ``"hourly"``, ``"block"``, or ``"quarter_hourly"``.
        type_of_order: Curve shape — ``"LINEAR"`` or ``"STEP"``.

    Returns:
        :class:`~nexa_connect_exaa.models.orders.OrderSubmission` for the
        given account.

    Raises:
        ImportError: If pandas is not installed.
        ValueError: If required columns are missing or ``product_type`` is
            not one of the accepted values.
    """
    _require_pandas()

    required = {"product_id", "price", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(
            f"DataFrame is missing required columns: {sorted(missing)}. "
            f"Expected: {sorted(required)}"
        )

    valid_types = {"hourly", "block", "quarter_hourly"}
    if product_type not in valid_types:
        raise ValueError(f"product_type must be one of {sorted(valid_types)}, got {product_type!r}")

    products: list[ProductOrder] = []
    for product_id, group in df.groupby("product_id", sort=False):
        pairs: list[PriceVolumePair] = []
        for _, row in group.iterrows():
            raw_price = row["price"]
            if isinstance(raw_price, str) and raw_price == "M":
                price: Any = "M"
            else:
                price = Decimal(str(raw_price))
            pairs.append(
                PriceVolumePair(
                    price=price,
                    volume=Decimal(str(row["volume"])),
                )
            )
        products.append(
            ProductOrder.model_validate(
                {
                    "productId": str(product_id),
                    "fillOrKill": False,
                    "priceVolumePairs": pairs,
                }
            )
        )

    product_type_orders = ProductTypeOrders.model_validate(
        {"typeOfOrder": type_of_order, "products": products}
    )

    alias_map = {
        "hourly": "hourlyProducts",
        "block": "blockProducts",
        "quarter_hourly": "15minProducts",
    }
    account_data: dict[str, Any] = {
        "accountId": account_id,
        "hourlyProducts": None,
        "blockProducts": None,
        "15minProducts": None,
    }
    account_data[alias_map[product_type]] = product_type_orders
    account = AccountOrders.model_validate(account_data)
    return OrderSubmission(orders=[account])
