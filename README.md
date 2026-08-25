# TickEye V2

[简体中文](README_CN.md)

TickEye is a local-first personal investment decision-support and risk-control tool built around one question:

> What risk state is my money in right now?

It organizes portfolio facts, user-selected watchlists, market data, risk evidence, explicit personal boundaries, and before/after adjustment scenarios. TickEye does not execute trades, promise returns, recommend funds, or replace the user's judgment.

The V2 Web MVP is implemented and feature-frozen. Product and engineering decisions are archived in [docs/](docs/).

## MVP capabilities

- Local single-user portfolio with accounts, instruments, positions, and immutable position snapshots
- Manual position editing and strict two-step CSV import
- SQLite persistence with Alembic migrations
- AkShare market-data adapter for funds, QDII funds, and ETFs
- Manual, idempotent market refresh with structured failure auditing
- Data-quality states for freshness, coverage, sample size, rejected rows, and source limitations
- Current-weight historical risk simulation with volatility, downside volatility, drawdown, concentration, and correlation
- Immutable risk snapshots that become stale when portfolio facts or market data change
- Optional user-defined concentration, allocation, and cash boundaries
- Deduplicated risk events for first detection, state changes, and recovery
- A risk homepage with evidence-driven next steps and the three most recent recorded changes
- User-curated watchlists that remain separate from actual holdings
- Frozen risk-adjustment scenarios that compare `NO_ACTION` with hypothetical changes without mutating positions
- Versioned JSON export of user facts and documented SQLite backup/restore procedures
- A guarded V1 watchlist migration command

Historical risk being calculable does not mean a portfolio is safe. Without an explicit user boundary, TickEye reports facts but does not invent a compliance or suitability conclusion. The MVP has no cash-flow ledger and therefore does not report account returns or return attribution.

## MVP freeze boundary

The frozen workflow is:

```text
Record actual holdings
  → refresh and inspect market data
  → review current risk and important changes
  → optionally define personal boundaries
  → compare a user-proposed adjustment in a frozen scenario
```

After the freeze, the MVP accepts bug fixes, acceptance-driven UX corrections, documentation improvements, and necessary dependency or security maintenance. The following are intentionally out of scope:

- Account returns, a cash-flow ledger, TWR, XIRR, and return attribution
- Opportunity discovery, fund recommendations, candidate ranking, and automatic buy/sell conclusions
- Brokerage or bank integrations, order execution, paper-trading fills, virtual P&L, and leaderboards
- Scheduled market refresh, IM/Agent notifications, and event read/unread tracking
- Multi-user accounts, authentication, cloud deployment, and commercialization controls
- Tracking the indices found in the old V1 configuration; their product role and data methodology remain deferred

## Technology

- Python 3.11+, FastAPI, SQLAlchemy, Alembic, SQLite
- pandas, NumPy, and an AkShare provider adapter
- React, TypeScript, Vite, TanStack Query
- pnpm for frontend dependency management
- pytest, Ruff, mypy, Vitest, Oxlint, and Playwright

## Local development

Prerequisites:

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Node.js 22 or newer
- pnpm

Install dependencies and migrate the local database:

```bash
uv sync --group dev
pnpm --dir frontend install
cp .env.example .env
.venv/bin/alembic upgrade head
```

Start the API with reload enabled:

```bash
.venv/bin/tickeye --reload
```

In a second terminal, start Vite:

```bash
pnpm --dir frontend dev
```

Open `http://127.0.0.1:5173`. Vite proxies `/api` to `http://127.0.0.1:8000`.

Main routes:

| Route | Purpose |
|---|---|
| `/` | Current risk, evidence-driven next step, and recent important changes |
| `/portfolio` | Accounts and actual holdings |
| `/watchlists` | User-selected instruments, reasons, and tags |
| `/data-quality` | Market refresh and data-quality evidence |
| `/policies` | Optional user-defined risk boundaries |
| `/scenarios` | Frozen risk-adjustment comparisons |
| `/events` | Full risk-state change history |

## Single-process local run

After building the frontend, FastAPI serves both the SPA and `/api/v1`:

```bash
pnpm --dir frontend build
.venv/bin/alembic upgrade head
.venv/bin/tickeye
```

Open `http://127.0.0.1:8000`.

## Core financial semantics

### Historical risk simulation

TickEye's `historical-risk-v1` output is not the user's historical account return. It replays historical market series using current valuation weights and assumes daily fixed-weight rebalancing.

- Non-cash positions use `quantity × latest usable NAV/adjusted close` when available, otherwise a manual value.
- Cash uses its manual value or quantity as the balance and assumes a daily return of zero.
- The engine uses at most 252 aligned observations and requires at least 120.
- It does not forward-fill missing market observations or silently shorten the minimum window.
- Missing valuations, stale or failed market data, insufficient history, and incomplete coverage produce `UNKNOWN` rather than a fabricated zero.
- A full-cash portfolio is reported separately; zero simulated market volatility does not cover inflation, liquidity, or credit risk.

Risk snapshots are generated explicitly from the homepage or with `POST /api/v1/risk/recalculate`. `GET /api/v1/risk/current` reads the latest immutable snapshot. Later portfolio or market-data changes mark it stale instead of rewriting it.

### Market data and quality

All held or watched non-cash instruments participate in market-data quality checks. Refresh is manual in the MVP.

- Open-end funds prefer cumulative NAV and fall back to unit NAV only when necessary.
- ETFs use forward-adjusted daily history.
- Duplicate observations are idempotent.
- Network failures, empty responses, upstream schema changes, and invalid values remain distinct errors.
- A failed refresh preserves the last valid cached observations.

### Watchlists and scenarios

Watchlists contain instruments explicitly selected by the user. They are not recommendations and never create positions.

A Scenario freezes the current portfolio facts, market history, policy revision, and optional watched candidate. Ordered hypothetical changes apply only to that copy. The before/after comparison uses the same data window and methodology and can include:

- `NO_ACTION`
- amount-based `BUY` and `SELL`
- `SET_AMOUNT`
- `SET_TARGET_WEIGHT`
- user-entered estimated transaction cost
- optional manual asset-class stress assumptions

Overselling, negative cash, missing required prices, costs exceeding sale proceeds, and non-closing operations are rejected atomically. Scenario results are not orders, forecasts, or investment advice.

## CSV portfolio import

CSV import first validates a preview and then requires explicit confirmation. Confirmation replaces the complete current portfolio; one invalid row rejects the batch.

Minimum columns are `account`, `code`, `market`, and `as_of`. A newly seen instrument also requires `name`, `type`, `currency`, `asset_class`, and `region`. At least one of `quantity` or `manual_value` is required.

```csv
account,code,name,type,market,currency,asset_class,region,quantity,manual_value,cost,as_of
Long-term account,510300,CSI 300 ETF,etf,CN,CNY,equity,China,1000,4000,3800,2026-08-24
Cash account,CASH-CNY,CNY Cash,cash,CN,CNY,cash,China,,10000,,2026-08-24
```

Supported instrument types: `fund`, `etf`, `qdii_fund`, `cash`.

Supported asset classes: `equity`, `fixed_income`, `mixed`, `cash`, `commodity`, `other`.

The MVP accepts only CNY accounts and CNY-denominated instruments. Dates must be `YYYY-MM-DD` and cannot be in the future. Quantity, value, and cost cannot be negative.

## Export, backup, and restore

The footer's data export downloads versioned JSON containing the Profile, actual holdings, user policies, watchlists, and the frozen inputs and operations needed to explain existing scenarios. It excludes reproducible market caches and derived results. JSON export is not yet an automatic restore format and does not replace a database backup.

The default database is `data/tickeye.db`. Do not copy a live SQLite file directly. Create and verify an online backup:

```bash
mkdir -p backups
sqlite3 data/tickeye.db ".backup 'backups/tickeye-20260825.db'"
sqlite3 backups/tickeye-20260825.db "PRAGMA integrity_check;"
```

The integrity check must return `ok`. Database and backup files contain personal financial facts and must never be committed.

Restore to a new file while TickEye is stopped:

```bash
sqlite3 backups/tickeye-20260825.db ".backup 'data/tickeye-restored.db'"
TICKEYE_DATABASE_URL=sqlite:///./data/tickeye-restored.db .venv/bin/alembic upgrade head
TICKEYE_DATABASE_URL=sqlite:///./data/tickeye-restored.db .venv/bin/tickeye
```

Verify the restored application before changing `TICKEYE_DATABASE_URL` in `.env`.

## V1 watchlist migration

V1 configuration is isolated under `legacy/v1/`. It is never a runtime source for V2. The migration command defaults to a read-only preview and imports eligible fund codes into a watchlist, never into positions:

```bash
.venv/bin/alembic upgrade head
.venv/bin/tickeye-migrate-v1
```

After reviewing the inferred type, asset class, region, deferred indices, validation issues, and preview token:

```bash
.venv/bin/tickeye-migrate-v1 \
  --confirm \
  --preview-token <token-from-preview>
```

Confirmation is atomic and idempotent. It does not modify `Position` or advance the portfolio revision. Changing the source configuration or target watchlist invalidates the old token and requires a new preview. Indices remain deferred.

## API type generation

FastAPI OpenAPI is the frontend contract source. After changing an API schema:

```bash
.venv/bin/tickeye-export-openapi frontend/src/api/openapi.json
pnpm --dir frontend generate:api
```

Do not edit `frontend/src/api/generated/` manually.

## Quality checks

```bash
.venv/bin/ruff check .
.venv/bin/mypy src
.venv/bin/pytest
pnpm --dir frontend typecheck
pnpm --dir frontend test
pnpm --dir frontend lint
pnpm --dir frontend build
pnpm --dir frontend exec playwright test
```

Install Chromium before the first E2E run:

```bash
pnpm --dir frontend exec playwright install chromium
```

The E2E suite starts temporary FastAPI, Vite, and SQLite instances with a deterministic market-data provider. It does not read or write `data/tickeye.db` and does not access external market services.

## Repository layout

```text
docs/                 Product vision, product definition, and engineering plan
frontend/             React and TypeScript application
legacy/v1/            Isolated V1 configuration used only by the migration command
migrations/           Alembic database migrations
src/tickeye/           Python application
  domain/              Financial domain models and pure rules
  application/         Use-case orchestration
  infrastructure/      SQLite repositories and external providers
  web/                 FastAPI routes and static SPA hosting
tests/                 Python tests
data/                  Local user database, ignored except for .gitkeep
backups/               Local database backups, ignored
```

## Documentation

- [V2 vision](docs/v2_plan.md)
- [V2 product definition](docs/v2_product.md)
- [V2 engineering plan](docs/v2_development_plan.md)
- [简体中文说明](README_CN.md)

## License

[MIT](LICENSE)
