"""Build, persist, and retrieve immutable portfolio risk snapshots."""

import json
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy.orm import Session, sessionmaker

from tickeye.application.market_data_provider import MarketValueType
from tickeye.application.market_data_service import RefreshStatus
from tickeye.domain.enums import AssetClass, InstrumentType
from tickeye.domain.risk import (
    HistoricalValue,
    RiskAnalysis,
    RiskPositionInput,
    analyze_portfolio_risk,
)
from tickeye.infrastructure.db import InstrumentRecord, RiskSnapshotRecord
from tickeye.infrastructure.repositories import (
    MarketDataRepository,
    PortfolioRepository,
    RiskRepository,
)


@dataclass(frozen=True, slots=True)
class StoredRiskSnapshot:
    snapshot_id: int
    profile_id: int
    portfolio_revision: int
    calculated_at: datetime
    is_current: bool
    stale_reasons: tuple[str, ...]
    payload_json: str
    analysis: RiskAnalysis | None = None


@dataclass(frozen=True, slots=True)
class FrozenRiskInputs:
    profile_id: int
    portfolio_revision: int
    positions: tuple[RiskPositionInput, ...]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def _freshness_limit(instrument_type: InstrumentType) -> int | None:
    if instrument_type == InstrumentType.CASH:
        return None
    if instrument_type == InstrumentType.QDII_FUND:
        return 5
    return 3


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return str(value.value)
    raise TypeError(f"Unsupported risk snapshot value: {type(value).__name__}")


def _payload_json(analysis: RiskAnalysis) -> str:
    return json.dumps(
        asdict(analysis),
        default=_json_default,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


class RiskService:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def current(self) -> StoredRiskSnapshot | None:
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            snapshot = RiskRepository(session).latest_snapshot(profile.id)
            if snapshot is None:
                return None
            return self._stored_snapshot(session, snapshot, profile.revision)

    def recalculate(self) -> StoredRiskSnapshot:
        calculated_at = datetime.now(UTC)
        with self.session_factory.begin() as session:
            portfolio_repository = PortfolioRepository(session)
            profile = portfolio_repository.get_or_create_profile()
            frozen = self._load_inputs(session, profile.id)

            analysis = analyze_portfolio_risk(
                frozen.positions, calculated_on=calculated_at.date()
            )
            record = RiskRepository(session).add_snapshot(
                RiskSnapshotRecord(
                    profile_id=profile.id,
                    portfolio_revision=frozen.portfolio_revision,
                    portfolio_as_of=analysis.portfolio_as_of,
                    market_data_as_of=analysis.market_data_as_of,
                    calculated_at=calculated_at,
                    methodology_version=analysis.methodology_version,
                    payload_json=_payload_json(analysis),
                )
            )
            return StoredRiskSnapshot(
                snapshot_id=record.id,
                profile_id=profile.id,
                portfolio_revision=record.portfolio_revision,
                calculated_at=calculated_at,
                is_current=True,
                stale_reasons=(),
                payload_json=record.payload_json,
                analysis=analysis,
            )

    def freeze_current_inputs(
        self, extra_instrument_ids: tuple[int, ...] = ()
    ) -> FrozenRiskInputs:
        """Capture the current facts and observations for a reproducible Scenario."""

        with self.session_factory.begin() as session:
            profile = PortfolioRepository(session).get_or_create_profile()
            frozen = self._load_inputs(session, profile.id)
            existing_ids = {item.instrument_id for item in frozen.positions}
            extras = tuple(
                self._candidate_input(session, instrument_id)
                for instrument_id in extra_instrument_ids
                if instrument_id not in existing_ids
            )
            return FrozenRiskInputs(
                profile_id=frozen.profile_id,
                portfolio_revision=frozen.portfolio_revision,
                positions=(*frozen.positions, *extras),
            )

    @staticmethod
    def _candidate_input(session: Session, instrument_id: int) -> RiskPositionInput:
        instrument = session.get(InstrumentRecord, instrument_id)
        if instrument is None:
            raise RuntimeError("Scenario candidate instrument disappeared.")
        instrument_type = InstrumentType(instrument.type)
        market_repository = MarketDataRepository(session)
        latest_refresh = market_repository.latest_refresh(instrument.id)
        latest_success = market_repository.latest_refresh(
            instrument.id, successful_only=True
        )
        observations = []
        limitations: tuple[str, ...] = ()
        if latest_success is not None and latest_success.value_type is not None:
            observations = market_repository.observations(
                instrument.id,
                MarketValueType(latest_success.value_type),
            )
            try:
                raw_limitations: Any = json.loads(latest_success.limitations_json)
                if isinstance(raw_limitations, list) and all(
                    isinstance(item, str) for item in raw_limitations
                ):
                    limitations = tuple(raw_limitations)
                else:
                    limitations = ("invalid_stored_limitations",)
            except (TypeError, ValueError):
                limitations = ("invalid_stored_limitations",)
        position_as_of = (
            observations[-1].observed_on if observations else datetime.now(UTC).date()
        )
        return RiskPositionInput(
            position_id=-(1_000_000 + instrument.id),
            instrument_id=instrument.id,
            account_name="Scenario 候选标的",
            code=instrument.code,
            name=instrument.name,
            instrument_type=instrument_type,
            asset_class=AssetClass(instrument.asset_class),
            quantity=Decimal(0),
            manual_value=None,
            position_as_of=position_as_of,
            history=tuple(
                HistoricalValue(observed_on=item.observed_on, value=item.value)
                for item in observations
            ),
            freshness_limit_days=_freshness_limit(instrument_type),
            last_refresh_failed=(
                latest_refresh is not None
                and latest_refresh.status == RefreshStatus.ERROR.value
            ),
            limitations=limitations,
        )

    @staticmethod
    def _load_inputs(session: Session, profile_id: int) -> FrozenRiskInputs:
        portfolio = PortfolioRepository(session).load(profile_id)
        market_repository = MarketDataRepository(session)
        inputs: list[RiskPositionInput] = []
        for position in portfolio.positions:
            latest_refresh = market_repository.latest_refresh(position.instrument_id)
            latest_success = market_repository.latest_refresh(
                position.instrument_id, successful_only=True
            )
            observations = []
            limitations: tuple[str, ...] = ()
            if latest_success is not None and latest_success.value_type is not None:
                observations = market_repository.observations(
                    position.instrument_id,
                    MarketValueType(latest_success.value_type),
                )
                try:
                    raw_limitations: Any = json.loads(latest_success.limitations_json)
                    if isinstance(raw_limitations, list) and all(
                        isinstance(item, str) for item in raw_limitations
                    ):
                        limitations = tuple(raw_limitations)
                    else:
                        limitations = ("invalid_stored_limitations",)
                except (TypeError, ValueError):
                    limitations = ("invalid_stored_limitations",)
            inputs.append(
                RiskPositionInput(
                    position_id=position.id,
                    instrument_id=position.instrument_id,
                    account_name=position.account_name,
                    code=position.code,
                    name=position.name,
                    instrument_type=position.instrument_type,
                    asset_class=position.asset_class,
                    quantity=position.quantity,
                    manual_value=position.manual_value,
                    position_as_of=position.as_of,
                    history=tuple(
                        HistoricalValue(
                            observed_on=item.observed_on,
                            value=item.value,
                        )
                        for item in observations
                    ),
                    freshness_limit_days=_freshness_limit(position.instrument_type),
                    last_refresh_failed=(
                        latest_refresh is not None
                        and latest_refresh.status == RefreshStatus.ERROR.value
                    ),
                    limitations=limitations,
                )
            )
        return FrozenRiskInputs(
            profile_id=portfolio.profile_id,
            portfolio_revision=portfolio.revision,
            positions=tuple(inputs),
        )

    @staticmethod
    def _stored_snapshot(
        session: Session,
        snapshot: RiskSnapshotRecord,
        current_revision: int,
    ) -> StoredRiskSnapshot:
        reasons: list[str] = []
        if snapshot.portfolio_revision != current_revision:
            reasons.append("portfolio_changed")
        latest_market_refresh = RiskRepository(session).latest_market_refresh_at(
            snapshot.profile_id
        )
        calculated_at = _aware_utc(snapshot.calculated_at)
        if latest_market_refresh is not None and latest_market_refresh > calculated_at:
            reasons.append("market_data_changed")
        return StoredRiskSnapshot(
            snapshot_id=snapshot.id,
            profile_id=snapshot.profile_id,
            portfolio_revision=snapshot.portfolio_revision,
            calculated_at=calculated_at,
            is_current=not reasons,
            stale_reasons=tuple(reasons),
            payload_json=snapshot.payload_json,
        )
