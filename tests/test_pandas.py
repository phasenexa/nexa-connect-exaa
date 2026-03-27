"""Tests for pandas DataFrame conversion helpers."""

from __future__ import annotations

from decimal import Decimal

import pytest
from nexa_connect_exaa.models.results import (
    MarketResult,
    TradeConfirmation,
    TradeResult,
)
from nexa_connect_exaa.pandas_helpers import (
    _require_pandas,
    df_to_order_submission,
    market_results_to_df,
    trade_confirmations_to_df,
    trade_results_to_df,
)

pandas = pytest.importorskip("pandas")


class TestRequirePandas:
    def test_no_error_when_pandas_available(self) -> None:
        _require_pandas()  # Should not raise

    def test_import_error_when_pandas_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        monkeypatch.setitem(sys.modules, "pandas", None)  # type: ignore[arg-type]
        with pytest.raises(ImportError, match="pip install nexa-connect-exaa"):
            _require_pandas()


class TestTradeResultsToDf:
    def test_returns_dataframe_with_correct_columns(self, trade_result: TradeResult) -> None:
        df = trade_results_to_df([trade_result])
        assert "product_id" in df.columns
        assert "account_id" in df.columns
        assert "price" in df.columns
        assert "volume_awarded" in df.columns

    def test_empty_list_returns_empty_dataframe(self) -> None:
        df = trade_results_to_df([])
        assert len(df) == 0

    def test_multiple_results(self) -> None:
        results = [
            TradeResult(
                product_id="hEXA10",
                account_id="APTAP1",
                price=Decimal("42.5"),
                volume_awarded=Decimal("200.0"),
            ),
            TradeResult(
                product_id="hEXA11",
                account_id="APTAP1",
                price=Decimal("40.0"),
                volume_awarded=Decimal("100.0"),
            ),
        ]
        df = trade_results_to_df(results)
        assert len(df) == 2


class TestMarketResultsToDf:
    def test_returns_dataframe(self, market_result: MarketResult) -> None:
        df = market_results_to_df([market_result])
        assert "product_id" in df.columns
        assert "price_zone" in df.columns
        assert df.iloc[0]["price_zone"] == "AT"


class TestTradeConfirmationsToDf:
    def test_returns_dataframe(self, trade_confirmation: TradeConfirmation) -> None:
        df = trade_confirmations_to_df([trade_confirmation])
        assert "product_id" in df.columns
        assert "account_id" in df.columns


class TestDfToOrderSubmission:
    def test_basic_conversion(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
            {
                "product_id": ["hEXA10", "hEXA10", "hEXA11"],
                "price": [40.0, 55.0, 38.0],
                "volume": [250.0, 150.0, 200.0],
            }
        )
        submission = df_to_order_submission(df, "APTAP1", "hourly", "LINEAR")
        assert len(submission.orders) == 1
        account = submission.orders[0]
        assert account.account_id == "APTAP1"
        assert account.hourly_products is not None
        assert account.hourly_products.type_of_order == "LINEAR"
        assert len(account.hourly_products.products) == 2

        # hEXA10 has 2 price-volume pairs
        hexa10 = next(p for p in account.hourly_products.products if p.product_id == "hEXA10")
        assert len(hexa10.price_volume_pairs) == 2

    def test_market_order_price_m(self) -> None:
        import pandas as pd

        df = pd.DataFrame(
            {
                "product_id": ["hEXA10"],
                "price": ["M"],
                "volume": [100.0],
            }
        )
        submission = df_to_order_submission(df, "APTAP1", "hourly", "STEP")
        pair = submission.orders[0].hourly_products.products[0].price_volume_pairs[0]  # type: ignore[union-attr]
        assert pair.price == "M"

    def test_raises_on_missing_columns(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"product_id": ["hEXA10"], "price": [40.0]})
        with pytest.raises(ValueError, match="missing required columns"):
            df_to_order_submission(df, "APTAP1", "hourly", "LINEAR")

    def test_raises_on_invalid_product_type(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"product_id": ["hEXA10"], "price": [40.0], "volume": [100.0]})
        with pytest.raises(ValueError, match="product_type must be one of"):
            df_to_order_submission(df, "APTAP1", "monthly", "LINEAR")

    def test_block_product_type(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"product_id": ["bEXAbase"], "price": [30.0], "volume": [500.0]})
        submission = df_to_order_submission(df, "APTAP1", "block", "STEP")
        assert submission.orders[0].block_products is not None
        assert submission.orders[0].hourly_products is None

    def test_quarter_hourly_product_type(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"product_id": ["qEXA01_1"], "price": [35.0], "volume": [50.0]})
        submission = df_to_order_submission(df, "APTAP1", "quarter_hourly", "LINEAR")
        assert submission.orders[0].quarter_hourly_products is not None

    def test_serialises_with_15min_alias(self) -> None:
        import pandas as pd

        df = pd.DataFrame({"product_id": ["qEXA01_1"], "price": [35.0], "volume": [50.0]})
        submission = df_to_order_submission(df, "APTAP1", "quarter_hourly", "LINEAR")
        dumped = submission.model_dump(by_alias=True, mode="json", exclude_none=True)
        assert "15minProducts" in dumped["orders"][0]
