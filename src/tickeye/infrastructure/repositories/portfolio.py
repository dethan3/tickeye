"""Persistence operations for the single-user current portfolio."""

from datetime import UTC, datetime

from sqlalchemy import Select, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.models import PortfolioFacts, PositionFact
from tickeye.infrastructure.db import (
    AccountRecord,
    InstrumentRecord,
    PositionRecord,
    PositionSnapshotRecord,
    ProfileRecord,
)


def _aware_utc(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


class PortfolioRepository:
    """SQLAlchemy repository with no HTTP or presentation behavior."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_or_create_profile(self) -> ProfileRecord:
        profile = self.session.scalar(select(ProfileRecord).order_by(ProfileRecord.id).limit(1))
        if profile is None:
            profile = ProfileRecord(name="我的投资组合", base_currency="CNY", revision=0)
            self.session.add(profile)
            self.session.flush()
        return profile

    def get_account(self, profile_id: int, name: str) -> AccountRecord | None:
        return self.session.scalar(
            select(AccountRecord).where(
                AccountRecord.profile_id == profile_id,
                AccountRecord.name == name,
            )
        )

    def get_instrument(self, code: str, market: str) -> InstrumentRecord | None:
        return self.session.scalar(
            select(InstrumentRecord).where(
                InstrumentRecord.code == code,
                InstrumentRecord.market == market,
            )
        )

    def position_rows(
        self, profile_id: int
    ) -> list[tuple[PositionRecord, AccountRecord, InstrumentRecord]]:
        statement: Select[tuple[PositionRecord, AccountRecord, InstrumentRecord]] = (
            select(PositionRecord, AccountRecord, InstrumentRecord)
            .join(AccountRecord, PositionRecord.account_id == AccountRecord.id)
            .join(InstrumentRecord, PositionRecord.instrument_id == InstrumentRecord.id)
            .where(AccountRecord.profile_id == profile_id)
            .order_by(AccountRecord.name, InstrumentRecord.code, PositionRecord.id)
        )
        return list(self.session.execute(statement).tuples())

    def advance_revision(self, profile_id: int, expected_revision: int) -> int | None:
        result = self.session.execute(
            update(ProfileRecord)
            .where(
                ProfileRecord.id == profile_id,
                ProfileRecord.revision == expected_revision,
            )
            .values(
                revision=ProfileRecord.revision + 1,
                updated_at=func.current_timestamp(),
            )
        )
        assert isinstance(result, CursorResult)
        if result.rowcount != 1:
            return None
        return expected_revision + 1

    def has_import(self, fingerprint: str) -> bool:
        statement = select(PositionSnapshotRecord.id).where(
            PositionSnapshotRecord.import_fingerprint == fingerprint
        )
        return self.session.scalar(statement) is not None

    def load(self, profile_id: int) -> PortfolioFacts:
        profile = self.session.get(ProfileRecord, profile_id, populate_existing=True)
        if profile is None:
            raise RuntimeError("Portfolio profile disappeared during its transaction.")

        positions = tuple(
            PositionFact(
                id=position.id,
                account_id=account.id,
                account_name=account.name,
                institution=account.institution,
                account_currency=account.currency,
                instrument_id=instrument.id,
                code=instrument.code,
                name=instrument.name,
                instrument_type=InstrumentType(instrument.type),
                market=instrument.market,
                instrument_currency=instrument.currency,
                asset_class=AssetClass(instrument.asset_class),
                region=instrument.region,
                quantity=position.quantity,
                manual_value=position.manual_value,
                cost=position.cost,
                as_of=position.as_of,
            )
            for position, account, instrument in self.position_rows(profile_id)
        )
        latest_snapshot = self.session.scalar(
            select(func.max(PositionSnapshotRecord.captured_at)).where(
                PositionSnapshotRecord.profile_id == profile_id
            )
        )
        return PortfolioFacts(
            profile_id=profile.id,
            profile_name=profile.name,
            base_currency=profile.base_currency,
            revision=profile.revision,
            positions=positions,
            latest_snapshot_at=_aware_utc(latest_snapshot),
        )
