"""Persistence for immutable risk analysis snapshots."""

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tickeye.infrastructure.db import (
    AccountRecord,
    MarketRefreshRecord,
    PositionRecord,
    RiskSnapshotRecord,
)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class RiskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def latest_snapshot(self, profile_id: int) -> RiskSnapshotRecord | None:
        return self.session.scalar(
            select(RiskSnapshotRecord)
            .where(RiskSnapshotRecord.profile_id == profile_id)
            .order_by(RiskSnapshotRecord.id.desc())
            .limit(1)
        )

    def add_snapshot(self, snapshot: RiskSnapshotRecord) -> RiskSnapshotRecord:
        self.session.add(snapshot)
        self.session.flush()
        return snapshot

    def latest_market_refresh_at(self, profile_id: int) -> datetime | None:
        statement = (
            select(func.max(MarketRefreshRecord.completed_at))
            .join(PositionRecord, PositionRecord.instrument_id == MarketRefreshRecord.instrument_id)
            .join(AccountRecord, AccountRecord.id == PositionRecord.account_id)
            .where(AccountRecord.profile_id == profile_id)
        )
        return _aware_utc(self.session.scalar(statement))
