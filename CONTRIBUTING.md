# Contributing to nexa-connect-exaa

Thanks for your interest in contributing. This document covers how to get set up,
the conventions we follow, and the process for getting changes merged.

## Getting started

### Prerequisites

- Python 3.11+
- [Poetry](https://python-poetry.org/docs/#installation) for dependency management
- Make (for common tasks)
- A GitHub account

### Setup

```bash
# Clone the repo
git clone https://github.com/phasenexa/nexa-connect-exaa.git
cd nexa-connect-exaa

# Install dependencies (including dev extras)
make install

# Verify everything works
make ci
```

### Project structure

```
src/nexa_connect_exaa/    # library source
tests/                     # test suite
tests/fixtures/            # VCR cassettes and example JSON
```

See `CLAUDE.md` for a full breakdown of the code layout, EXAA domain context,
authentication details, and the `nexa-connect-*` consistency contract.

## Development workflow

We use **trunk-based development**. The `main` branch is protected and all changes
go through pull requests with squash merges.

### 1. Create a feature branch

```bash
git checkout main && git pull
git checkout -b feat/your-feature-name
```

Branch naming conventions:

| Prefix      | Use for                        |
|-------------|--------------------------------|
| `feat/`     | New features                   |
| `fix/`      | Bug fixes                      |
| `refactor/` | Refactoring (no new behaviour) |
| `docs/`     | Documentation updates          |
| `test/`     | Test improvements              |
| `chore/`    | Maintenance (deps, config)     |

### 2. Make your changes

Write code, write tests. See the code style section below. Commit as you go
with focused, atomic commits.

When implementing a new module, follow the implementation order in `CLAUDE.md`
and update the status table in `README.md` when done.

### 3. Run the checks

Before opening a PR, run the full check suite locally:

```bash
# Everything in one command
make ci

# Or individually:
make lint       # ruff check + format check
make typecheck  # mypy strict
make test       # pytest with coverage
```

### 4. Open a pull request

```bash
git push -u origin feat/your-feature-name
gh pr create --title "feat: short description" --body "Why this change is needed."
```

PR requirements:

- Clear title describing the change
- Description explaining the motivation
- All CI checks pass
- Code coverage meets or exceeds 80%
- At least 1 approving review (when branch protection is enabled)

### 5. After merge

Delete your feature branch. CI handles the rest.

## Code style

### Python conventions

- **Python 3.11+** with type hints on all public API
- **Pydantic v2** for all data models with `ConfigDict(populate_by_name=True)` and camelCase `Field(alias=...)` for JSON mapping
- **Ruff** for linting and formatting (handles both lint and format)
- **mypy** in strict mode for type checking
- **Google-style docstrings** on all public classes and methods
- **httpx** for HTTP (async primary, sync wrapper)

### Data handling

- **`decimal.Decimal`** for all prices and volumes in the public API. Convert to `float` only at the JSON serialization boundary.
- **Timezone-aware datetimes only**. EXAA operates in CET/CEST (Europe/Vienna). Never use naive datetimes.
- EXAA's `15minProducts` JSON key maps to `quarter_hourly_products` in Python.

### nexa-connect-* consistency

This library is part of the `nexa-connect-*` family. All libraries in the family follow the
same structural conventions. See `CLAUDE.md` for the full consistency contract. Key points:

- Entry point in `client.py` named `{Exchange}Client`
- Auth providers in `auth.py`
- Models in `models/` with Pydantic v2
- Endpoints in `endpoints/`
- Errors in `exceptions.py`
- DataFrame helpers in `pandas_helpers.py` (optional dependency)
- Test helper in `testing.py` with `Fake{Exchange}Client`

If you are also contributing to `nexa-connect-nordpool` or another `nexa-connect-*` library,
keep the conventions aligned.

### Testing

- **pytest** with descriptive test names
- Use VCR cassettes (vcrpy or pytest-recording) for HTTP interaction recording. Place in `tests/fixtures/cassettes/`.
- Strip real credentials from all fixtures before committing
- Aim for >80% coverage, but prioritise meaningful tests over chasing the number
- Model round-trip tests: build Pydantic model -> serialize to JSON (with aliases) -> deserialize -> compare
- Exception mapping tests: each EXAA error code -> correct exception class

### Dependencies

Keep them minimal. Core dependencies:

- `httpx` for HTTP
- `pydantic` for data models
- `cryptography` for JWS/certificate auth
- `PyJWT` for JWT token creation
- `pandas` (optional extra)

Everything else needs a good justification.

## Commit messages

Use conventional commits:

```
feat: add certificate-based authentication
fix: handle token refresh race condition
refactor: extract error code mapping to standalone function
docs: document post-trading order workflow
test: add VCR cassettes for auction endpoints
chore: update httpx to 0.28
```

The first line should be short (under 72 characters). Add a body if the "why"
is not obvious from the title.

## Domain context

This library wraps the EXAA Trading API for day-ahead power auctions in
Austria, Germany, and the Netherlands. Key concepts:

- **Classic auction (10:15 CET)** - EXAA's own clearing, with post-trading phase
- **Market Coupling auction (12:00 CET)** - SDAC/EUPHEMIA coupling
- **Trade account** - orders are grouped by account, not portfolio
- **Full replacement** - POST replaces all orders for included accounts
- **Product types** - hourly, block, 15-minute (Classic only)

Read `CLAUDE.md` thoroughly before contributing. The authentication flow,
error code mapping, and order model subtleties are all documented there.

## Reporting issues

Open a GitHub issue. Include:

- What you were trying to do
- What happened instead
- Which endpoint or auction type was involved
- The EXAA error code and message, if applicable
- Python version and OS
- Minimal reproduction if possible

## Licence

By contributing, you agree that your contributions will be licensed under
the MIT Licence.
