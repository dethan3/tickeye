"""Manual market refresh and transparent data-quality assessment."""

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from sqlalchemy.orm import Session, sessionmaker

from tickeye.application.market_data_provider import (
    MarketDataProvider,
    MarketDataProviderError,
    MarketDataRequest,
    MarketInstrumentKind,
    MarketValueType,
)
from tickeye.domain.enums import InstrumentType
from tickeye.infrastructure.db import InstrumentRecord, MarketRefreshRecord
from tickeye.infrastructure.repositories import MarketDataRepository


class DataQualityStatus(StrEnum):
    GOOD = "good"
    PARTIAL = "partial"
    STALE = "stale"
    MISSING = "missing"
    REFRESH_FAILED = "refresh_failed"
    SHORT_HISTORY = "short_history"
    NOT_APPLICABLE = "not_applicable"


class RefreshStatus(StrEnum):
    SUCCESS = "success"
    ERROR = "error"
    SKIPPED = "skipped"


class MarketDataSelectionError(Exception):
    def __init__(self, unknown_ids: set[int]) -> None:
        super().__init__("Some selected instruments are neither held nor watched.")
        self.unknown_ids = frozenset(unknown_ids)


@dataclass(frozen=True, slots=True)
class DataQualityItem:
    instrument_id: int
    code: str
    name: str
    instrument_type: InstrumentType
    status: DataQualityStatus
    last_observation_date: date | None
    latest_value: Decimal | None
    value_type: MarketValueType | None
    source: str | None
    sample_count: int
    freshness_days: int | None
    freshness_limit_days: int | None
    rejected_rate: Decimal | None
    last_refresh_at: datetime | None
    last_refresh_status: RefreshStatus | None
    failure_code: str | None
    failure_message: str | None
    limitations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    items: tuple[DataQualityItem, ...]
    calculated_at: datetime

    @property
    def tracked_count(self) -> int:
        return len(self.items)

    @property
    def available_count(self) -> int:
        return sum(item.last_observation_date is not None for item in self.items)

    @property
    def problem_count(self) -> int:
        healthy = {DataQualityStatus.GOOD, DataQualityStatus.NOT_APPLICABLE}
        return sum(item.status not in healthy for item in self.items)


@dataclass(frozen=True, slots=True)
class RefreshResult:
    instrument_id: int
    code: str
    status: RefreshStatus
    accepted_rows: int
    written_rows: int
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class RefreshReport:
    results: tuple[RefreshResult, ...]
    quality: DataQualityReport


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _kind_for(instrument: InstrumentRecord) -> MarketInstrumentKind | None:
    instrument_type = InstrumentType(instrument.type)
    if instrument_type in {InstrumentType.FUND, InstrumentType.QDII_FUND}:
        return MarketInstrumentKind.FUND
    if instrument_type == InstrumentType.ETF:
        return MarketInstrumentKind.ETF
    return None


def _freshness_limit(instrument_type: InstrumentType) -> int | None:
    if instrument_type == InstrumentType.CASH:
        return None
    if instrument_type == InstrumentType.QDII_FUND:
        return 5
    return 3


class MarketDataService:
    """Refresh held or watched instruments and preserve failures without erasing cache."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        provider: MarketDataProvider,
    ) -> None:
        self.session_factory = session_factory
        self.provider = provider

    def refresh(self, instrument_ids: set[int] | None = None) -> RefreshReport:
        with self.session_factory() as session:
            instruments = MarketDataRepository(session).tracked_instruments()
        available_ids = {instrument.id for instrument in instruments}
        if instrument_ids is not None:
            unknown_ids = instrument_ids - available_ids
            if unknown_ids:
                raise MarketDataSelectionError(unknown_ids)
            instruments = [item for item in instruments if item.id in instrument_ids]

        results = tuple(self._refresh_one(instrument) for instrument in instruments)
        return RefreshReport(results=results, quality=self.get_quality())

    def _refresh_one(self, instrument: InstrumentRecord) -> RefreshResult:
        kind = _kind_for(instrument)
        if kind is None:
            return RefreshResult(
                instrument_id=instrument.id,
                code=instrument.code,
                status=RefreshStatus.SKIPPED,
                accepted_rows=0,
                written_rows=0,
            )

        requested_at = datetime.now(UTC)
        try:
            series = self.provider.fetch(
                MarketDataRequest(code=instrument.code, kind=kind, symbol=instrument.code)
            )
        except MarketDataProviderError as exc:
            completed_at = datetime.now(UTC)
            with self.session_factory.begin() as session:
                MarketDataRepository(session).add_refresh(
                    MarketRefreshRecord(
                        instrument_id=instrument.id,
                        requested_at=requested_at,
                        completed_at=completed_at,
                        status=RefreshStatus.ERROR.value,
                        provider=self.provider.name,
                        received_rows=0,
                        accepted_rows=0,
                        written_rows=0,
                        invalid_rows=0,
                        error_code=exc.code,
                        error_message=str(exc),
                        limitations_json="[]",
                    )
                )
            return RefreshResult(
                instrument_id=instrument.id,
                code=instrument.code,
                status=RefreshStatus.ERROR,
                accepted_rows=0,
                written_rows=0,
                error_code=exc.code,
                error_message=str(exc),
            )

        with self.session_factory.begin() as session:
            repository = MarketDataRepository(session)
            written_rows = repository.save_series(instrument.id, series)
            repository.add_refresh(
                MarketRefreshRecord(
                    instrument_id=instrument.id,
                    requested_at=requested_at,
                    completed_at=datetime.now(UTC),
                    status=RefreshStatus.SUCCESS.value,
                    provider=self.provider.name,
                    source=series.source,
                    value_type=series.value_type.value,
                    received_rows=series.received_rows,
                    accepted_rows=len(series.points),
                    written_rows=written_rows,
                    invalid_rows=series.invalid_rows,
                    limitations_json=json.dumps(series.limitations),
                )
            )
        return RefreshResult(
            instrument_id=instrument.id,
            code=instrument.code,
            status=RefreshStatus.SUCCESS,
            accepted_rows=len(series.points),
            written_rows=written_rows,
        )

    def get_quality(self) -> DataQualityReport:
        calculated_at = datetime.now(UTC)
        with self.session_factory() as session:
            repository = MarketDataRepository(session)
            instruments = repository.tracked_instruments()
            items = tuple(
                self._quality_item(repository, instrument, calculated_at.date())
                for instrument in instruments
            )
        return DataQualityReport(items=items, calculated_at=calculated_at)

    @staticmethod
    def _quality_item(
        repository: MarketDataRepository,
        instrument: InstrumentRecord,
        today: date,
    ) -> DataQualityItem:
        instrument_type = InstrumentType(instrument.type)
        if instrument_type == InstrumentType.CASH:
            return DataQualityItem(
                instrument_id=instrument.id,
                code=instrument.code,
                name=instrument.name,
                instrument_type=instrument_type,
                status=DataQualityStatus.NOT_APPLICABLE,
                last_observation_date=None,
                latest_value=None,
                value_type=None,
                source=None,
                sample_count=0,
                freshness_days=None,
                freshness_limit_days=None,
                rejected_rate=None,
                last_refresh_at=None,
                last_refresh_status=None,
                failure_code=None,
                failure_message=None,
                limitations=(),
            )

        latest_refresh = repository.latest_refresh(instrument.id)
        latest_success = repository.latest_refresh(instrument.id, successful_only=True)
        value_type = (
            MarketValueType(latest_success.value_type)
            if latest_success is not None and latest_success.value_type is not None
            else None
        )
        observations = repository.observations(instrument.id, value_type)
        latest_observation = observations[-1] if observations else None
        freshness_days = (
            (today - latest_observation.observed_on).days if latest_observation else None
        )
        freshness_limit = _freshness_limit(instrument_type)
        rejected_rate = None
        limitations: tuple[str, ...] = ()
        if latest_success is not None:
            if latest_success.received_rows > 0:
                rejected_rate = (
                    Decimal(latest_success.invalid_rows) / Decimal(latest_success.received_rows)
                ).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            try:
                limitations = tuple(json.loads(latest_success.limitations_json))
            except (TypeError, ValueError):
                limitations = ("invalid_stored_limitations",)

        last_refresh_status = (
            RefreshStatus(latest_refresh.status) if latest_refresh is not None else None
        )
        if latest_refresh is not None and latest_refresh.status == RefreshStatus.ERROR.value:
            quality_status = DataQualityStatus.REFRESH_FAILED
        elif latest_observation is None:
            quality_status = DataQualityStatus.MISSING
        elif (
            freshness_limit is not None
            and freshness_days is not None
            and freshness_days > freshness_limit
        ):
            quality_status = DataQualityStatus.STALE
        elif len(observations) < 120:
            quality_status = DataQualityStatus.SHORT_HISTORY
        elif rejected_rate is not None and rejected_rate > 0:
            quality_status = DataQualityStatus.PARTIAL
        else:
            quality_status = DataQualityStatus.GOOD

        return DataQualityItem(
            instrument_id=instrument.id,
            code=instrument.code,
            name=instrument.name,
            instrument_type=instrument_type,
            status=quality_status,
            last_observation_date=(
                latest_observation.observed_on if latest_observation is not None else None
            ),
            latest_value=latest_observation.value if latest_observation is not None else None,
            value_type=value_type,
            source=latest_observation.source if latest_observation is not None else None,
            sample_count=len(observations),
            freshness_days=freshness_days,
            freshness_limit_days=freshness_limit,
            rejected_rate=rejected_rate,
            last_refresh_at=_as_utc(
                latest_refresh.completed_at if latest_refresh is not None else None
            ),
            last_refresh_status=last_refresh_status,
            failure_code=latest_refresh.error_code if latest_refresh is not None else None,
            failure_message=(
                latest_refresh.error_message if latest_refresh is not None else None
            ),
            limitations=limitations,
        )
