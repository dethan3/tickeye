"""Observation cache and refresh audit persistence."""

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from tickeye.application.market_data_provider import MarketSeries, MarketValueType
from tickeye.infrastructure.db import (
    InstrumentRecord,
    MarketObservationRecord,
    MarketRefreshRecord,
    PositionRecord,
    WatchlistItemRecord,
)


class MarketDataRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def tracked_instruments(self) -> list[InstrumentRecord]:
        statement = (
            select(InstrumentRecord)
            .outerjoin(PositionRecord, PositionRecord.instrument_id == InstrumentRecord.id)
            .outerjoin(
                WatchlistItemRecord,
                WatchlistItemRecord.instrument_id == InstrumentRecord.id,
            )
            .where(
                or_(
                    PositionRecord.id.is_not(None),
                    WatchlistItemRecord.id.is_not(None),
                )
            )
            .distinct()
            .order_by(InstrumentRecord.code)
        )
        return list(self.session.scalars(statement))

    def observations(
        self,
        instrument_id: int,
        value_type: MarketValueType | None = None,
    ) -> list[MarketObservationRecord]:
        statement = select(MarketObservationRecord).where(
            MarketObservationRecord.instrument_id == instrument_id
        )
        if value_type is not None:
            statement = statement.where(MarketObservationRecord.value_type == value_type.value)
        return list(self.session.scalars(statement.order_by(MarketObservationRecord.observed_on)))

    def latest_refresh(
        self,
        instrument_id: int,
        *,
        successful_only: bool = False,
    ) -> MarketRefreshRecord | None:
        statement = select(MarketRefreshRecord).where(
            MarketRefreshRecord.instrument_id == instrument_id
        )
        if successful_only:
            statement = statement.where(MarketRefreshRecord.status == "success")
        return self.session.scalar(statement.order_by(MarketRefreshRecord.id.desc()).limit(1))

    def save_series(self, instrument_id: int, series: MarketSeries) -> int:
        existing = {
            item.observed_on: item
            for item in self.observations(instrument_id, series.value_type)
        }
        written = 0
        for point in series.points:
            observation = existing.get(point.observed_on)
            if observation is None:
                self.session.add(
                    MarketObservationRecord(
                        instrument_id=instrument_id,
                        observed_on=point.observed_on,
                        value=point.value,
                        value_type=series.value_type.value,
                        source=series.source,
                        fetched_at=series.fetched_at,
                    )
                )
                written += 1
            elif observation.value != point.value or observation.source != series.source:
                observation.value = point.value
                observation.source = series.source
                observation.fetched_at = series.fetched_at
                written += 1
        return written

    def add_refresh(self, refresh: MarketRefreshRecord) -> None:
        self.session.add(refresh)
