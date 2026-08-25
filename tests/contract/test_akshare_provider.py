from decimal import Decimal
from typing import Any

import pandas as pd
import pytest

from tickeye.application.market_data_provider import (
    MarketDataNetworkError,
    MarketDataRequest,
    MarketDataSchemaError,
    MarketInstrumentKind,
    MarketValueType,
)
from tickeye.infrastructure.market_data.akshare import AkShareMarketDataProvider


class FakeAkShare:
    def __init__(self) -> None:
        self.fund_frames: dict[str, pd.DataFrame] = {}
        self.etf_frame = pd.DataFrame()
        self.domestic_index_frame = pd.DataFrame()
        self.hk_index_frame = pd.DataFrame()
        self.us_index_frame = pd.DataFrame()
        self.etf_call: dict[str, Any] | None = None

    def fund_open_fund_info_em(self, *, symbol: str, indicator: str) -> pd.DataFrame:
        return self.fund_frames.get(indicator, pd.DataFrame())

    def fund_etf_hist_em(self, **kwargs: Any) -> pd.DataFrame:
        self.etf_call = kwargs
        return self.etf_frame

    def stock_zh_index_daily(self, *, symbol: str) -> pd.DataFrame:
        return self.domestic_index_frame

    def stock_hk_index_daily_sina(self, *, symbol: str) -> pd.DataFrame:
        return self.hk_index_frame

    def index_us_stock_sina(self, *, symbol: str) -> pd.DataFrame:
        return self.us_index_frame


def test_fund_prefers_cumulative_nav_and_rejects_bad_rows() -> None:
    client = FakeAkShare()
    client.fund_frames["累计净值走势"] = pd.DataFrame(
        {
            "净值日期": ["2026-08-21", "2026-08-22", "2026-08-22"],
            "累计净值": ["1.2500", None, "1.2600"],
        }
    )
    provider = AkShareMarketDataProvider(client)

    series = provider.fetch(
        MarketDataRequest(code="007360", kind=MarketInstrumentKind.FUND)
    )

    assert series.value_type == MarketValueType.CUMULATIVE_NAV
    assert [point.value for point in series.points] == [
        Decimal("1.25000000"),
        Decimal("1.26000000"),
    ]
    assert series.received_rows == 3
    assert series.invalid_rows == 1
    assert series.limitations == ()


def test_empty_cumulative_nav_falls_back_to_limited_unit_nav() -> None:
    client = FakeAkShare()
    client.fund_frames["单位净值走势"] = pd.DataFrame(
        {"净值日期": ["2026-08-21"], "单位净值": ["1.0200"]}
    )
    provider = AkShareMarketDataProvider(client)

    series = provider.fetch(
        MarketDataRequest(code="007360", kind=MarketInstrumentKind.FUND)
    )

    assert series.value_type == MarketValueType.UNIT_NAV
    assert series.limitations == ("unit_nav_only",)


def test_schema_change_is_not_silently_treated_as_empty_data() -> None:
    client = FakeAkShare()
    client.fund_frames["累计净值走势"] = pd.DataFrame(
        {"unexpected_date": ["2026-08-21"], "unexpected_value": [1.0]}
    )
    provider = AkShareMarketDataProvider(client)

    with pytest.raises(MarketDataSchemaError):
        provider.fetch(MarketDataRequest(code="007360", kind=MarketInstrumentKind.FUND))


def test_etf_uses_qfq_and_domestic_and_global_indices_normalize_daily_close() -> None:
    client = FakeAkShare()
    client.etf_frame = pd.DataFrame({"日期": ["2026-08-21"], "收盘": [4.123]})
    client.domestic_index_frame = pd.DataFrame(
        {"date": ["2026-08-21"], "close": [3888.1]}
    )
    client.us_index_frame = pd.DataFrame({"date": ["2026-08-21"], "close": [24200.5]})
    provider = AkShareMarketDataProvider(client)

    etf = provider.fetch(MarketDataRequest(code="510300", kind=MarketInstrumentKind.ETF))
    domestic = provider.fetch(
        MarketDataRequest(
            code="000001",
            symbol="sh000001",
            kind=MarketInstrumentKind.DOMESTIC_INDEX,
        )
    )
    global_index = provider.fetch(
        MarketDataRequest(code="NDX", kind=MarketInstrumentKind.GLOBAL_INDEX)
    )

    assert client.etf_call is not None and client.etf_call["adjust"] == "qfq"
    assert etf.value_type == MarketValueType.ADJUSTED_CLOSE
    assert domestic.value_type == MarketValueType.INDEX_CLOSE
    assert global_index.source == "akshare:index_us_stock_sina"


def test_network_failures_retry_and_remain_distinct_from_schema_errors() -> None:
    class FailingAkShare(FakeAkShare):
        calls = 0

        def fund_open_fund_info_em(self, *, symbol: str, indicator: str) -> pd.DataFrame:
            self.calls += 1
            raise TimeoutError("timed out")

    client = FailingAkShare()
    waits: list[float] = []
    provider = AkShareMarketDataProvider(
        client,
        max_attempts=3,
        retry_delay_seconds=0.1,
        sleeper=waits.append,
    )

    with pytest.raises(MarketDataNetworkError):
        provider.fetch(MarketDataRequest(code="007360", kind=MarketInstrumentKind.FUND))

    assert client.calls == 3
    assert waits == [0.1, 0.2]
