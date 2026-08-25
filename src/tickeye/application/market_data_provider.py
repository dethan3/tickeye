"""Stable market-data port shared by providers and application services."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


class MarketInstrumentKind(StrEnum):
    FUND = "fund"
    ETF = "etf"
    DOMESTIC_INDEX = "domestic_index"
    GLOBAL_INDEX = "global_index"


class MarketValueType(StrEnum):
    CUMULATIVE_NAV = "cumulative_nav"
    UNIT_NAV = "unit_nav"
    ADJUSTED_CLOSE = "adjusted_close"
    INDEX_CLOSE = "index_close"


@dataclass(frozen=True, slots=True)
class MarketDataRequest:
    code: str
    kind: MarketInstrumentKind
    symbol: str | None = None


@dataclass(frozen=True, slots=True)
class MarketPoint:
    observed_on: date
    value: Decimal


@dataclass(frozen=True, slots=True)
class MarketSeries:
    points: tuple[MarketPoint, ...]
    value_type: MarketValueType
    source: str
    fetched_at: datetime
    received_rows: int
    invalid_rows: int
    limitations: tuple[str, ...] = ()


class MarketDataProvider(Protocol):
    @property
    def name(self) -> str: ...

    def fetch(self, request: MarketDataRequest) -> MarketSeries: ...


class MarketDataProviderError(Exception):
    code = "provider_error"


class MarketDataNetworkError(MarketDataProviderError):
    code = "network_error"


class MarketDataEmptyError(MarketDataProviderError):
    code = "empty_data"


class MarketDataSchemaError(MarketDataProviderError):
    code = "schema_changed"


class MarketDataInvalidError(MarketDataProviderError):
    code = "invalid_values"


class MarketDataUnsupportedError(MarketDataProviderError):
    code = "unsupported_instrument"


class MarketDataUpstreamError(MarketDataProviderError):
    code = "upstream_error"
