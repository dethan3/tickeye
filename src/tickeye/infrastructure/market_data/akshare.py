"""AkShare adapter with explicit schemas, fallbacks, and failure categories."""

import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from typing import Protocol, cast

import pandas as pd
from requests import RequestException

from tickeye.application.market_data_provider import (
    MarketDataEmptyError,
    MarketDataInvalidError,
    MarketDataNetworkError,
    MarketDataProviderError,
    MarketDataRequest,
    MarketDataSchemaError,
    MarketDataUnsupportedError,
    MarketDataUpstreamError,
    MarketInstrumentKind,
    MarketPoint,
    MarketSeries,
    MarketValueType,
)


class AkShareClient(Protocol):
    def fund_open_fund_info_em(
        self, *, symbol: str, indicator: str
    ) -> pd.DataFrame: ...

    def fund_etf_hist_em(
        self,
        *,
        symbol: str,
        period: str,
        start_date: str,
        end_date: str,
        adjust: str,
    ) -> pd.DataFrame: ...

    def stock_zh_index_daily(self, *, symbol: str) -> pd.DataFrame: ...

    def stock_hk_index_daily_sina(self, *, symbol: str) -> pd.DataFrame: ...

    def index_us_stock_sina(self, *, symbol: str) -> pd.DataFrame: ...


NETWORK_ERRORS = (TimeoutError, ConnectionError, OSError, RequestException)
US_INDEX_SYMBOLS = {"SPX": ".INX", "NDX": ".NDX"}


class AkShareMarketDataProvider:
    """Normalize supported AkShare responses into one deterministic series."""

    def __init__(
        self,
        client: AkShareClient | None = None,
        *,
        max_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self.max_attempts = max(1, max_attempts)
        self.retry_delay_seconds = max(0.0, retry_delay_seconds)
        self.sleeper = sleeper

    @property
    def name(self) -> str:
        return "akshare"

    @property
    def client(self) -> AkShareClient:
        if self._client is None:
            import akshare  # type: ignore[import-untyped]

            self._client = cast(AkShareClient, akshare)
        return self._client

    def fetch(self, request: MarketDataRequest) -> MarketSeries:
        if request.kind in {MarketInstrumentKind.FUND}:
            return self._fetch_fund(request)
        if request.kind == MarketInstrumentKind.ETF:
            return self._fetch_etf(request)
        if request.kind == MarketInstrumentKind.DOMESTIC_INDEX:
            return self._fetch_domestic_index(request)
        if request.kind == MarketInstrumentKind.GLOBAL_INDEX:
            return self._fetch_global_index(request)
        raise MarketDataUnsupportedError(f"Unsupported instrument kind: {request.kind}")

    def _call(self, operation: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        last_network_error: Exception | None = None
        for attempt in range(self.max_attempts):
            try:
                return operation()
            except NETWORK_ERRORS as exc:
                last_network_error = exc
                if attempt + 1 < self.max_attempts:
                    self.sleeper(self.retry_delay_seconds * (2**attempt))
            except MarketDataProviderError:
                raise
            except Exception as exc:
                raise MarketDataUpstreamError("AkShare request failed unexpectedly.") from exc
        raise MarketDataNetworkError(
            "AkShare network request failed after retries."
        ) from last_network_error

    def _fetch_fund(self, request: MarketDataRequest) -> MarketSeries:
        cumulative = self._call(
            lambda: self.client.fund_open_fund_info_em(
                symbol=request.symbol or request.code,
                indicator="累计净值走势",
            )
        )
        try:
            return self._normalize(
                cumulative,
                date_column="净值日期",
                value_column="累计净值",
                value_type=MarketValueType.CUMULATIVE_NAV,
                source="akshare:fund_open_fund_info_em:cumulative_nav",
            )
        except MarketDataEmptyError:
            unit = self._call(
                lambda: self.client.fund_open_fund_info_em(
                    symbol=request.symbol or request.code,
                    indicator="单位净值走势",
                )
            )
            return self._normalize(
                unit,
                date_column="净值日期",
                value_column="单位净值",
                value_type=MarketValueType.UNIT_NAV,
                source="akshare:fund_open_fund_info_em:unit_nav",
                limitations=("unit_nav_only",),
            )

    def _fetch_etf(self, request: MarketDataRequest) -> MarketSeries:
        frame = self._call(
            lambda: self.client.fund_etf_hist_em(
                symbol=request.symbol or request.code,
                period="daily",
                start_date="20000101",
                end_date=date.today().strftime("%Y%m%d"),
                adjust="qfq",
            )
        )
        return self._normalize(
            frame,
            date_column="日期",
            value_column="收盘",
            value_type=MarketValueType.ADJUSTED_CLOSE,
            source="akshare:fund_etf_hist_em:qfq",
            limitations=("qfq_history_can_be_revised",),
        )

    def _fetch_domestic_index(self, request: MarketDataRequest) -> MarketSeries:
        frame = self._call(
            lambda: self.client.stock_zh_index_daily(symbol=request.symbol or request.code)
        )
        return self._normalize(
            frame,
            date_column="date",
            value_column="close",
            value_type=MarketValueType.INDEX_CLOSE,
            source="akshare:stock_zh_index_daily",
        )

    def _fetch_global_index(self, request: MarketDataRequest) -> MarketSeries:
        symbol = (request.symbol or request.code).upper()
        if symbol == "HSI":
            frame = self._call(lambda: self.client.stock_hk_index_daily_sina(symbol="HSI"))
            source = "akshare:stock_hk_index_daily_sina"
        elif symbol in US_INDEX_SYMBOLS:
            frame = self._call(
                lambda: self.client.index_us_stock_sina(symbol=US_INDEX_SYMBOLS[symbol])
            )
            source = "akshare:index_us_stock_sina"
        else:
            raise MarketDataUnsupportedError(f"No historical index source for {symbol}.")
        return self._normalize(
            frame,
            date_column="date",
            value_column="close",
            value_type=MarketValueType.INDEX_CLOSE,
            source=source,
        )

    @staticmethod
    def _normalize(
        frame: pd.DataFrame,
        *,
        date_column: str,
        value_column: str,
        value_type: MarketValueType,
        source: str,
        limitations: tuple[str, ...] = (),
    ) -> MarketSeries:
        if frame is None or frame.empty:
            raise MarketDataEmptyError("The provider returned no rows.")
        missing_columns = {date_column, value_column} - set(frame.columns)
        if missing_columns:
            columns = ", ".join(sorted(missing_columns))
            raise MarketDataSchemaError(f"Provider response is missing columns: {columns}.")

        points_by_date: dict[date, MarketPoint] = {}
        invalid_rows = 0
        for row in frame[[date_column, value_column]].to_dict(orient="records"):
            try:
                raw_date = row[date_column]
                raw_value = row[value_column]
                if pd.isna(raw_date) or pd.isna(raw_value):
                    raise ValueError
                observed_on = pd.Timestamp(raw_date).date()
                value = Decimal(str(raw_value))
                if not value.is_finite() or value <= 0:
                    raise ValueError
                value = value.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_EVEN)
            except (InvalidOperation, TypeError, ValueError):
                invalid_rows += 1
                continue
            if observed_on in points_by_date:
                invalid_rows += 1
            points_by_date[observed_on] = MarketPoint(observed_on=observed_on, value=value)

        if not points_by_date:
            raise MarketDataInvalidError("The provider returned no usable positive values.")
        return MarketSeries(
            points=tuple(points_by_date[key] for key in sorted(points_by_date)),
            value_type=value_type,
            source=source,
            fetched_at=datetime.now(UTC),
            received_rows=len(frame),
            invalid_rows=invalid_rows,
            limitations=limitations,
        )
