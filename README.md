# nexa-connect-exaa

[![CI](https://github.com/phasenexa/nexa-connect-exaa/actions/workflows/ci.yml/badge.svg)](https://github.com/phasenexa/nexa-connect-exaa/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/phasenexa/nexa-connect-exaa/branch/main/graph/badge.svg)](https://codecov.io/gh/phasenexa/nexa-connect-exaa)
![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

> **This project is a work in progress.** The API, documentation, and feature set are under active development and subject to change. If you want to get involved, receive progress updates, or have feedback, please [open an issue](https://github.com/phasenexa/nexa-connect-exaa/issues) or contact the repo admin.

Python client library for the EXAA (Energy Exchange Austria) Trading API. Covers authentication, order management, result retrieval, and auction state polling for EXAA's day-ahead power auctions.

Part of the Phase Nexa `nexa-connect-*` family of exchange connectivity libraries.

Built for the 75% who connect via API and build their own.

## What this does

This library wraps the EXAA Trading API, handling the transport layer so you can focus on trading logic.

- **Authenticate** - RSA (hardware/on-demand token) and certificate-based (JWS) authentication with automatic token refresh
- **Discover auctions** - List auctions by delivery or trading day, inspect available products and account constraints
- **Submit orders** - Build and submit hourly, block, and 15-minute orders with full validation feedback
- **Post-trading** - Submit post-trading orders for the Classic (10:15) auction's residual volume phase
- **Retrieve results** - Trade results, market results, and trade confirmations as typed models or DataFrames
- **Poll auction state** - Wait for specific states or watch state transitions with configurable intervals
- **Pandas integration** - Results as DataFrames, orders from DataFrames
- **Typed exceptions** - Every EXAA error code mapped to a specific exception class
- **Testable** - `FakeEXAAClient` for use in downstream tests without network access

**Out of scope:** Bid construction, EUPHEMIA domain modelling, price forecasting, position management. For bid construction, see [nexa-bidkit](https://github.com/phasenexa/nexa-bidkit) and its EXAA exchange module.

## Installation

```bash
pip install nexa-connect-exaa
```

With pandas support:

```bash
pip install nexa-connect-exaa[pandas]
```

## Quick start

### Connect and list auctions

```python
from nexa_connect_exaa import EXAAClient, CertificateAuth

client = EXAAClient(
    base_url="https://test-trade.exaa.at",
    auth=CertificateAuth(
        username="trader1",
        password="1234",
        private_key_path="/path/to/key.pem",
        certificate_path="/path/to/cert.pem",
    ),
)

with client:
    auctions = client.get_auctions(delivery_day="2026-04-01")
    for auction in auctions:
        print(f"{auction.id}: {auction.auction_type} - {auction.state}")
```

### Submit orders

```python
from nexa_connect_exaa import EXAAClient, CertificateAuth, OrderSubmission

with EXAAClient(
    base_url="https://test-trade.exaa.at",
    auth=CertificateAuth(
        username="trader1",
        password="1234",
        private_key_path="key.pem",
        certificate_path="cert.pem",
    ),
) as client:
    # Build an order payload
    orders = OrderSubmission.build(
        account_id="APTAP1",
        hourly_products={
            "type_of_order": "LINEAR",
            "products": [
                {
                    "product_id": "hEXA10",
                    "fill_or_kill": False,
                    "price_volume_pairs": [
                        {"price": 40.00, "volume": 250},
                        {"price": 55.00, "volume": 150},
                        {"price": 70.00, "volume": 50},
                    ],
                },
            ],
        },
    )

    response = client.submit_orders("Classic_2026-04-01", orders)
    for account in response.orders:
        print(f"{account.account_id}: affected={account.affected}")
```

### Submit orders from a DataFrame

```python
import pandas as pd

orders_df = pd.DataFrame({
    "product_id": ["hEXA10", "hEXA10", "hEXA10", "hEXA11", "hEXA11"],
    "price": [40.00, 55.00, 70.00, 38.00, 52.00],
    "volume": [250, 150, 50, 200, 100],
})

with EXAAClient(...) as client:
    response = client.submit_orders_from_df(
        auction_id="Classic_2026-04-01",
        account_id="APTAP1",
        product_type="hourly",
        type_of_order="LINEAR",
        df=orders_df,
    )
```

### Retrieve results as DataFrames

```python
with EXAAClient(...) as client:
    # Market-wide clearing prices
    market_df = client.get_market_results_df("Classic_2026-04-01")
    print(market_df[["product_id", "price_zone", "price", "volume"]])

    # Your trade results
    trades_df = client.get_trade_results_df(
        "Classic_2026-04-01",
        accounts=["APTAP1"],
    )
    print(trades_df[["product_id", "price", "volume_awarded"]])

    # Final trade confirmations
    confirms_df = client.get_trade_confirmations_df("Classic_2026-04-01")
```

### Wait for auction results

```python
with EXAAClient(...) as client:
    # Block until the auction reaches AUCTIONED state
    auction = client.wait_for_state(
        "Classic_2026-04-01",
        target_state="AUCTIONED",
        poll_interval=10,
        timeout=3600,
    )
    print(f"Auction cleared: {auction.state}")

    # Then fetch results
    results = client.get_trade_results("Classic_2026-04-01")
```

### Async usage

```python
import asyncio
from nexa_connect_exaa import AsyncEXAAClient, CertificateAuth

async def main():
    async with AsyncEXAAClient(
        base_url="https://test-trade.exaa.at",
        auth=CertificateAuth(
            username="trader1",
            password="1234",
            private_key_path="key.pem",
            certificate_path="cert.pem",
        ),
    ) as client:
        auctions = await client.get_auctions(delivery_day="2026-04-01")

        # Watch state changes
        async for state in client.watch_auction(
            "Classic_2026-04-01",
            poll_interval=5,
        ):
            print(f"State: {state}")
            if state.name == "FINALIZED":
                break

asyncio.run(main())
```

### RSA authentication

```python
from nexa_connect_exaa import EXAAClient, RSAAuth

# With hardware token (single-step login)
client = EXAAClient(
    base_url="https://test-trade.exaa.at",
    auth=RSAAuth(
        username="trader1",
        pin="1234",
        passcode="654321",
    ),
)

# With on-demand token (two-step login)
auth = RSAAuth(username="trader1", pin="1234")
client = EXAAClient(base_url="https://test-trade.exaa.at", auth=auth)
with client:
    # First call triggers passcode delivery via email/SMS
    # Then call client.complete_login(passcode="received_code")
    pass
```

### Error handling

```python
from nexa_connect_exaa import (
    EXAAClient,
    EXAAError,
    EXAAAuthError,
    AuctionNotOpenError,
    MonotonicViolationError,
)

with EXAAClient(...) as client:
    try:
        client.submit_orders("Classic_2026-04-01", orders)
    except AuctionNotOpenError:
        print("Auction gate is closed, cannot submit")
    except MonotonicViolationError as e:
        print(f"Curve not monotonic: {e.message} at {e.path}")
    except EXAAAuthError:
        print("Authentication failed")
    except EXAAError as e:
        print(f"EXAA error {e.code}: {e.message}")
```

## Using with nexa-bidkit

This library handles the HTTP transport. For bid construction, curve building, and EUPHEMIA domain modelling, install [nexa-bidkit](https://github.com/phasenexa/nexa-bidkit) alongside. The `nexa_bidkit.exaa` exchange module converts bidkit domain types to EXAA order payloads.

```python
from nexa_bidkit import create_order_book, add_bid, from_dataframe, CurveType
from nexa_bidkit.exaa import order_book_to_exaa, build_product_resolver
from nexa_connect_exaa import EXAAClient, CertificateAuth

with EXAAClient(...) as client:
    auction = client.get_auction("Classic_2026-04-01")
    resolver = build_product_resolver(auction)

    # ... build bids with nexa-bidkit ...

    payload = order_book_to_exaa(book, account_id="APTAP1",
                                 resolver=resolver, type_of_order="LINEAR")
    client.submit_orders("Classic_2026-04-01", payload)
```

## EXAA auction types

| Auction | Time (CET) | Products | Post-Trading | ID Format |
|---|---|---|---|---|
| Classic | 10:15 | Hourly, Block, 15-min | Yes | `Classic_YYYY-MM-DD` |
| Market Coupling | 12:00 | Hourly, Block | No | `MC_YYYY-MM-DD` |

### Order type constraints

| Auction | Product | typeOfOrder | fillOrKill |
|---|---|---|---|
| Classic | 15-min | STEP or LINEAR | false |
| Classic | Hourly | STEP or LINEAR | false |
| Classic | Block | STEP or LINEAR | STEP: true/false, LINEAR: false |
| MC | Hourly | STEP or LINEAR | false |
| MC | Block | STEP only | true only |

## Project structure

```
nexa-connect-exaa/
  examples/
  src/nexa_connect_exaa/
    __init__.py              # Public API re-exports
    client.py                # EXAAClient, AsyncEXAAClient
    auth.py                  # RSAAuth, CertificateAuth
    config.py                # Environment, configuration
    exceptions.py            # EXAA error code hierarchy
    polling.py               # Auction state polling helpers
    pandas_helpers.py        # DataFrame conversions
    testing.py               # FakeEXAAClient
    _http.py                 # httpx session management
    models/
      __init__.py
      auction.py             # Auction, AuctionState, TradeAccount
      orders.py              # OrderSubmission, PriceVolumePair
      posttrading.py         # PostTradingInfo, PostTradingOrder
      results.py             # TradeResult, MarketResult, TradeConfirmation
      common.py              # Units, ErrorResponse
    endpoints/
      __init__.py
      auctions.py
      orders.py
      posttrading.py
      results.py
  tests/
    conftest.py
    fixtures/
      cassettes/             # VCR HTTP cassettes
    test_auth.py
    test_client.py
    test_endpoints.py
    test_exceptions.py
    test_models.py
    test_pandas.py
    test_polling.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues and PRs welcome.

This project follows trunk-based development with a protected main branch and squash-only merges.

## License

MIT

## Links

- [EXAA Trading API documentation](https://www.exaa.at)
- [EXAA API contact](mailto:api@exaa.at)
- [nexa-bidkit](https://github.com/phasenexa/nexa-bidkit) - Bid construction and EUPHEMIA domain modelling
- [Phase Nexa](https://phasenexa.github.io) - The ecosystem
