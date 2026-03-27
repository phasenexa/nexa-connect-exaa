# CLAUDE.md - nexa-connect-exaa

## What this project is

A Python client library for the EXAA (Energy Exchange Austria) Trading API. Handles authentication (RSA and certificate-based JWS), session management, order submission, result retrieval, and auction state polling for EXAA's day-ahead power auctions.

The Python package name is `nexa_connect_exaa`. It is part of the Phase Nexa `nexa-connect-*` family of exchange connectivity libraries. Each `nexa-connect-*` library follows the same structural conventions so that a developer familiar with one is immediately productive with another.

The target users are market participants, quants, and developers at energy trading companies who connect to EXAA via API. The library provides a clean Python interface over EXAA's REST API, with pandas integration for results and order construction.

This library works standalone. It does NOT require `nexa-bidkit`, but when bidkit is installed, users get a richer experience through the `nexa_bidkit.exaa` exchange module (separate repo). The boundary is clean: this library handles HTTP transport, authentication, and JSON serialization. bidkit handles domain modelling and bid construction.

### Scope

In scope: authentication (RSA V1 + certificate-based V2), session/token lifecycle, all EXAA Trading API V1 endpoints (auctions, orders, post-trading, results), pandas DataFrame conversion for results and orders, auction state polling utilities, typed exception hierarchy mapped to EXAA error codes.

Out of scope: bid construction logic, EUPHEMIA domain modelling, exchange-agnostic order books. These belong in `nexa-bidkit` and its exchange modules.

## Domain context

EXAA operates two day-ahead auction types for Austria, Germany, and the Netherlands:

- **Classic (10:15 CET)**: EXAA's own local clearing. Supports hourly, block, and 15-minute products. Has a unique post-trading phase where residual volume is available at the clearing price.
- **Market Coupling (12:00 CET)**: SDAC/EUPHEMIA coupling auction. Supports hourly and block products only.

EXAA does not operate intraday auctions or intraday continuous markets.

The API is RESTful (OpenAPI 3.0, JSON, HTTPS 1.1). Authentication produces a bearer token valid for 24 hours. All trading operations use this token.

### Auction ID conventions

- Classic: `Classic_YYYY-MM-DD` (delivery date), e.g. `Classic_2026-04-01`
- Market Coupling: `MC_YYYY-MM-DD`, e.g. `MC_2026-04-01`

### Base URLs

- Production: `https://trade.exaa.at`
- Test: `https://test-trade.exaa.at`
- Study: `https://study-trade.exaa.at`

API paths:

- `{base_url}/login/V1/` - RSA authentication
- `{base_url}/login/V2/` - Certificate-based authentication
- `{base_url}/exaa-trading-api/V1/` - All trading operations

### Product types

Three product types, identified by exchange-assigned string IDs returned per auction:

- **Hourly**: `hEXA01` through `hEXA24`, each with a single delivery time period
- **15-minute**: `qEXA01_1 (00:00 - 00:15)` etc., Classic auction only
- **Block**: `bEXAbase (01-24)`, `bEXApeak (09-20)`, etc. Can have non-contiguous delivery periods (e.g. off-peak)

Product IDs and their delivery periods come from the `GET /auctions/{id}` response. Never hardcode product ID-to-time mappings.

### Order model key points

- Orders are grouped by trade account, not portfolio
- `POST orders` is a **full replacement** per account. All orders for included accounts are replaced. Accounts not in the request are untouched.
- `typeOfOrder` (LINEAR/STEP) applies to all products of the same type within an account
- `fillOrKill` is per-product, with allowed values depending on auction type and product type
- Volumes: positive = buy, negative = sell. MWh/h with 1 decimal place.
- Prices: EUR/MWh with 2 decimal places. Range -500 to 4000 (exclusive). Use `"M"` for market orders.
- Max 30,000 price/volume pairs per POST, max 2 MB body

### Auction states

Classic lifecycle:
`TRADE_OPEN` -> `TRADE_CLOSED` -> `AUCTIONING` -> `AUCTIONED` -> `POSTTRADE_OPEN` -> `POSTTRADE_CLOSED` -> `POSTAUCTIONING` -> `POSTAUCTIONED` -> `FINALIZED`

Market Coupling lifecycle:
`TRADE_OPEN` -> `TRADE_CLOSED` -> `AUCTIONING` -> `PRELIMINARY_RESULTS` -> `FINALIZED`

MC fallback variants: `TRADE_OPEN_FALLBACK` -> `TRADE_CLOSED_FALLBACK` -> `AUCTIONING_FALLBACK` -> `AUCTIONED_FALLBACK` -> `FINALIZED_FALLBACK`

## Architecture

### Module layout

```
src/nexa_connect_exaa/
    __init__.py              # Public API re-exports
    client.py                # EXAAClient - main entry point (sync + async)
    auth.py                  # RSAAuth, CertificateAuth credential providers
    config.py                # Environment enum, client configuration
    exceptions.py            # Exception hierarchy mapped to EXAA error codes
    models/
        __init__.py
        auction.py           # Auction, AuctionType, AuctionState, TradeAccount
        orders.py            # OrderSubmission, AccountOrders, ProductTypeOrders, ProductOrder, PriceVolumePair
        posttrading.py       # PostTradingInfo, PostTradingOrder
        results.py           # TradeResult, MarketResult, TradeConfirmation
        common.py            # Units, ErrorResponse, ErrorDetail
    endpoints/
        __init__.py
        auctions.py          # get_auctions, get_auction, wait_for_state, watch_auction
        orders.py            # get_orders, submit_orders, delete_orders
        posttrading.py       # get_posttrading_info, get_posttrading_orders, submit_posttrading_orders, delete_posttrading_orders
        results.py           # get_trade_results, get_market_results, get_trade_confirmations
    polling.py               # Auction state polling helpers (wait_for_state, watch_auction)
    pandas_helpers.py        # DataFrame conversion for results and order construction
    _http.py                 # httpx session wrapper, retry logic, error response parsing
```

### Key design decisions

1. **`nexa-connect-*` consistency** - All exchange connectivity libraries in the Phase Nexa ecosystem share the same structural pattern: `client.py` (entry point), `auth.py` (credentials), `models/` (Pydantic response/request types), `endpoints/` (grouped API methods), `exceptions.py` (exchange error codes), `pandas_helpers.py` (DataFrame conversions). A future `nexa-connect-nordpool` or `nexa-connect-epex` must follow this same layout.

2. **httpx for HTTP** - Use `httpx` for both async (`AsyncClient`) and sync (`Client`) support. The primary API surface is async. Provide a thin sync wrapper via `EXAAClient` (sync) and `AsyncEXAAClient` (async), or a single client class with both sync and async methods.

3. **Pydantic v2 for all models** - Every request and response type is a `BaseModel` with `model_config = ConfigDict(populate_by_name=True)` and camelCase aliases matching the EXAA JSON schema. The `15minProducts` JSON key should alias to `quarter_hourly_products` in Python.

4. **Context manager for session lifecycle** - `EXAAClient` supports `with`/`async with`. Logs in on entry, logs out on exit. Token refresh is automatic.

5. **Typed exceptions from error codes** - EXAA returns structured error codes (A001, F010, etc.). Each class of error maps to a specific exception type. The `code` and `message` fields are always available on the exception.

6. **No dependency on nexa-bidkit** - This library is self-contained. The models in `models/` are native to this library, not re-exports from bidkit. If someone wants bidkit integration, they install `nexa-bidkit` separately and use its EXAA exchange module.

7. **Polling, not push** - EXAA has no WebSocket or push mechanism. Provide `wait_for_state()` and `watch_auction()` helpers that poll with configurable intervals and timeouts.

## Authentication details

### RSA (V1)

Endpoint: `POST {base_url}/login/V1/login`

Two flows:

- **Hardware token**: Single call with `{"username": "...", "pin": "1234", "passcode": "654321"}`. Returns `{"status": "OK", "referenceToken": "..."}`.
- **On-demand token**: First call with `{"username": "...", "pin": "1234"}` returns `{"status": "NEXTTOKEN"}`. EXAA sends passcode via email/SMS. Second call includes the received passcode.

### Certificate-based (V2)

Endpoint: `POST {base_url}/login/V2/login`

Body: `{"method": "JWS", "credentials": "<JWS compact serialization>"}`

JWS construction:

- Header: `alg=RS256`, `x5t` (base64url SHA-1 of DER certificate), `sub` (username). No `certificate` or `chain` fields.
- Claims: `sub`, `exp` (within 60s of `iat`), `iat` (not in future, within ~10s of now), `password` (4-digit), `aud` (optional, recommended: `trade.exaa.at` / `test-trade.exaa.at` / `study-trade.exaa.at`)

x5t pitfalls:

- Must be base64url-encoded (not base64), no padding characters
- Encode the BINARY SHA-1 hash, not the hex string
- Must not contain `/`, `+`, or `=` characters

### Token lifecycle

- Valid for 24 hours
- Multiple tokens can coexist for the same user
- Bearer token goes in `Authorization: Bearer {token}` header on all API calls
- Logout: `POST {base_url}/login/V1/logout` with bearer token header

The client should auto-refresh well before expiry (e.g. re-authenticate at 23 hours).

## Error handling

EXAA returns errors as:

```json
{"errors": [{"code": "F010", "message": "Monotonic rule is violated", "path": "[json path]"}]}
```

Exception hierarchy:

```text
EXAAError (base)
    EXAAAuthError           # A001-A004 (HTTP 403)
    EXAASyntaxError         # S001-S005 (HTTP 400)
    EXAAFunctionalError     # F001-F034 (HTTP 400/404/409)
        AuctionNotFoundError    # F006
        AuctionNotOpenError     # F008
        MonotonicViolationError # F010
        InvalidProductError     # F015
    EXAARequestError        # R001-R004 (HTTP 404/405/415)
    EXAAValueError          # V001-V005 (HTTP 400)
    EXAAServerError         # U001-U003 (HTTP 500)
    EXAAConnectionError     # network/timeout (not an EXAA code)
```

Each exception carries `code`, `message`, and optionally `path` and `support_reference` from the EXAA response.

## Pandas integration

Provide `_df` suffixed methods on the client for direct DataFrame returns:

```python
# Results
df = client.get_market_results_df("Classic_2026-04-01")
df = client.get_trade_results_df("Classic_2026-04-01", accounts=["APTAP1"])
df = client.get_trade_confirmations_df("Classic_2026-04-01")

# Orders from DataFrame
client.submit_orders_from_df(
    auction_id="Classic_2026-04-01",
    account_id="APTAP1",
    product_type="hourly",
    type_of_order="LINEAR",
    df=orders_df,  # columns: product_id, price, volume
)
```

pandas is an optional dependency. Guard the import. DataFrame methods should raise `ImportError` with a helpful message if pandas is not installed.

## Build and test

```bash
make install    # Install dev dependencies
make test       # Run pytest with coverage
make lint       # Run ruff check + format check
make typecheck  # Run mypy strict
make ci         # Run all checks (lint + typecheck + test)
```

### Test fixtures

Use VCR cassettes (vcrpy or pytest-recording) to record/replay HTTP interactions. Cassettes go in `tests/fixtures/cassettes/`. Strip any real credentials before committing.

Provide `nexa_connect_exaa.testing.FakeEXAAClient` for downstream consumers to use in their own tests without hitting the network.

### Test strategy

- Unit tests for authentication (RSA flow, JWS construction, token refresh)
- Unit tests for all endpoint methods (mocked HTTP responses)
- Unit tests for Pydantic model serialization/deserialization (round-trip against example JSON from the OpenAPI spec)
- Unit tests for exception mapping (each EXAA error code -> correct exception type)
- Unit tests for polling helpers (state transitions, timeouts)
- Integration-style tests using VCR cassettes (optional, for full request/response validation)
- DataFrame conversion tests (results -> DataFrame, DataFrame -> order payload)

## Style and conventions

- Python 3.11+
- Pydantic v2 for all models. `ConfigDict(populate_by_name=True)` and `Field(alias="camelCase")` for JSON mapping.
- httpx for HTTP (async primary, sync wrapper)
- ruff for linting and formatting
- mypy for type checking (strict mode)
- pytest for testing
- All public API types re-exported from `__init__.py`
- Google-style docstrings on all public classes and methods
- `snake_case` throughout Python. EXAA's camelCase JSON fields mapped via Pydantic aliases.
- `decimal.Decimal` for prices and volumes in the public API. Convert to `float` only at the serialization boundary (EXAA's API uses JSON numbers).
- Timezone-aware datetimes only. EXAA operates in CET/CEST (Europe/Vienna). Never use naive datetimes.
- No abbreviations in public API except domain terms (EXAA, MTU, MWh, EUR)

## Implementation order

1. `exceptions.py` - Exception hierarchy
2. `config.py` - Environment enum, base URL mapping
3. `models/common.py` - Units, ErrorResponse, ErrorDetail
4. `models/auction.py` - AuctionType, AuctionState enums, Auction model, TradeAccount, AccountConstraints, ProductInfo
5. `models/orders.py` - PriceVolumePair, ProductOrder, ProductTypeOrders, AccountOrders, OrderSubmission
6. `models/results.py` - TradeResult, MarketResult, TradeConfirmation models
7. `models/posttrading.py` - PostTradingInfo, PostTradingProductInfo, PostTradingOrder
8. `auth.py` - RSAAuth, CertificateAuth credential providers
9. `_http.py` - httpx session wrapper, error response parsing, retry logic
10. `endpoints/auctions.py` - Auction listing and detail
11. `endpoints/orders.py` - Order CRUD
12. `endpoints/posttrading.py` - Post-trading CRUD
13. `endpoints/results.py` - Trade results, market results, confirmations
14. `polling.py` - wait_for_state, watch_auction
15. `pandas_helpers.py` - DataFrame conversions
16. `client.py` - EXAAClient tying everything together
17. `__init__.py` - Public API re-exports
18. `testing.py` - FakeEXAAClient for downstream tests

## Common pitfalls

- **Full replacement on POST**: Submitting orders for account X replaces ALL orders for X. If you include hourly products but omit block products, existing block orders for X are deleted. Users must be warned about this. Consider a safety mechanism (diff preview, explicit confirmation kwarg).
- **Product IDs are opaque**: Never parse product IDs to derive delivery times. Always use the `deliveryTimePeriods` from the auction response.
- **Market orders at price boundaries**: Orders at exactly -500 or 4000 EUR/MWh are rejected. Must use `"M"` (market order) instead.
- **typeOfOrder is per product type, not per product**: You cannot mix LINEAR and STEP within hourly products on the same account.
- **MC block constraints**: Market Coupling blocks must be STEP + fillOrKill=true. No other combination is valid.
- **MC has no 15-minute products**: Submitting `15minProducts` to an MC auction will fail.
- **Post-trading is Classic only**: Attempting post-trading calls on MC auctions returns F001.
- **No rate limit docs**: EXAA does not document rate limits. Be defensive with polling intervals (minimum 5-10 seconds between calls).
- **Token refresh timing**: Tokens last 24 hours. Re-authenticate well before expiry. Multiple valid tokens can coexist.
- **Spread order deletion**: Must use the source account (AT/NL leg), never the sink (DE leg).
- **EXAA uses CET/CEST**: All delivery times and gate closures are in Europe/Vienna timezone.
- **x5t encoding**: The certificate thumbprint must be base64url-encoded binary SHA-1, not hex. If the value contains `/`, `+`, or `=`, it is wrong.

## nexa-connect-* consistency contract

All libraries in the `nexa-connect-*` family must follow these conventions:

| Aspect | Convention |
|--------|------------|
| Entry point | `client.py` with a main client class named `{Exchange}Client` |
| Auth | `auth.py` with credential provider classes |
| Models | `models/` directory with Pydantic v2 BaseModels, camelCase aliases |
| Endpoints | `endpoints/` directory, one module per logical group |
| Errors | `exceptions.py` with exchange-specific hierarchy inheriting from a base error |
| Pandas | `pandas_helpers.py` with `_df` suffixed client methods, optional dependency |
| Testing | `testing.py` with a `Fake{Exchange}Client` for downstream consumers |
| HTTP | `_http.py` (private) with httpx session management |
| Config | `config.py` with environment/base URL configuration |
| Context manager | Client supports `with`/`async with` for session lifecycle |
| Public API | All public types re-exported from `__init__.py` |

## Definition of Done

- Track implementation status in @README.md
- Update tests to include new/changed work, aim for >80% code coverage
- Run tests and ensure they pass using `make ci`
- Update README and/or docs to document new behaviour
- Check if Makefile (and `make ci`) is missing any common operations
- Add anything needed in @.gitignore to avoid checking in secrets or temp files
- Never commit API keys, tokens, certificates, or credentials
