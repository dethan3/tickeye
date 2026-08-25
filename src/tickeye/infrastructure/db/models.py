"""SQLAlchemy records for user-owned portfolio facts."""

from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from tickeye.infrastructure.db.base import Base


def utc_now() -> datetime:
    """Return an aware timestamp suitable for persisted audit fields."""

    return datetime.now(UTC)


class ProfileRecord(Base):
    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    base_currency: Mapped[str] = mapped_column(String(3), nullable=False, default="CNY")
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    accounts: Mapped[list["AccountRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["PositionSnapshotRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    risk_snapshots: Mapped[list["RiskSnapshotRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    scenarios: Mapped[list["ScenarioRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )
    watchlists: Mapped[list["WatchlistRecord"]] = relationship(
        back_populates="profile", cascade="all, delete-orphan"
    )


class InstrumentRecord(Base):
    __tablename__ = "instruments"
    __table_args__ = (UniqueConstraint("code", "market", name="uq_instrument_code_market"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(32), nullable=False)
    market: Mapped[str] = mapped_column(String(32), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    asset_class: Mapped[str] = mapped_column(String(32), nullable=False)
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    positions: Mapped[list["PositionRecord"]] = relationship(back_populates="instrument")
    observations: Mapped[list["MarketObservationRecord"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )
    refreshes: Mapped[list["MarketRefreshRecord"]] = relationship(
        back_populates="instrument", cascade="all, delete-orphan"
    )


class AccountRecord(Base):
    __tablename__ = "accounts"
    __table_args__ = (UniqueConstraint("profile_id", "name", name="uq_account_profile_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    profile: Mapped[ProfileRecord] = relationship(back_populates="accounts")
    positions: Mapped[list["PositionRecord"]] = relationship(
        back_populates="account", cascade="all, delete-orphan"
    )


class PositionRecord(Base):
    __tablename__ = "positions"
    __table_args__ = (
        UniqueConstraint("account_id", "instrument_id", name="uq_position_account_instrument"),
        CheckConstraint(
            "quantity IS NOT NULL OR manual_value IS NOT NULL",
            name="ck_position_has_quantity_or_manual_value",
        ),
        CheckConstraint(
            "quantity IS NULL OR quantity >= 0",
            name="ck_position_quantity_nonnegative",
        ),
        CheckConstraint(
            "manual_value IS NULL OR manual_value >= 0",
            name="ck_position_manual_value_nonnegative",
        ),
        CheckConstraint("cost IS NULL OR cost >= 0", name="ck_position_cost_nonnegative"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(24, 8))
    manual_value: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    cost: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    account: Mapped[AccountRecord] = relationship(back_populates="positions")
    instrument: Mapped[InstrumentRecord] = relationship(back_populates="positions")


class PositionSnapshotRecord(Base):
    __tablename__ = "position_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    import_fingerprint: Mapped[str | None] = mapped_column(String(64), unique=True)

    profile: Mapped[ProfileRecord] = relationship(back_populates="snapshots")


class MarketObservationRecord(Base):
    __tablename__ = "market_observations"
    __table_args__ = (
        UniqueConstraint(
            "instrument_id",
            "observed_on",
            "value_type",
            name="uq_market_observation_instrument_date_type",
        ),
        CheckConstraint("value > 0", name="ck_market_observation_positive_value"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE")
    )
    observed_on: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(24, 8), nullable=False)
    value_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    instrument: Mapped[InstrumentRecord] = relationship(back_populates="observations")


class MarketRefreshRecord(Base):
    __tablename__ = "market_refreshes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE")
    )
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))
    value_type: Mapped[str | None] = mapped_column(String(32))
    received_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    written_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    invalid_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(50))
    error_message: Mapped[str | None] = mapped_column(String(500))
    limitations_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    instrument: Mapped[InstrumentRecord] = relationship(back_populates="refreshes")


class RiskSnapshotRecord(Base):
    __tablename__ = "risk_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    portfolio_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    portfolio_as_of: Mapped[date | None] = mapped_column(Date)
    market_data_as_of: Mapped[date | None] = mapped_column(Date)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    profile: Mapped[ProfileRecord] = relationship(back_populates="risk_snapshots")


class PolicyRuleRecord(Base):
    __tablename__ = "policy_rules"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "rule_type", "subject_key", name="uq_policy_rule_subject"
        ),
        CheckConstraint("threshold >= 0 AND threshold <= 1", name="ck_policy_threshold"),
        CheckConstraint(
            "warning_ratio > 0 AND warning_ratio < 1", name="ck_policy_warning_ratio"
        ),
        CheckConstraint(
            "tolerance IS NULL OR (tolerance > 0 AND tolerance <= 1)",
            name="ck_policy_tolerance",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_key: Mapped[str] = mapped_column(String(64), nullable=False)
    subject_label: Mapped[str] = mapped_column(String(200), nullable=False)
    threshold: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    tolerance: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    warning_ratio: Mapped[Decimal] = mapped_column(Numeric(12, 8), nullable=False)
    enabled: Mapped[bool] = mapped_column(nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class RiskEvaluationRecord(Base):
    __tablename__ = "risk_evaluations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    risk_snapshot_id: Mapped[int] = mapped_column(
        ForeignKey("risk_snapshots.id", ondelete="CASCADE")
    )
    policy_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    findings_json: Mapped[str] = mapped_column(Text, nullable=False)


class InsightEventRecord(Base):
    __tablename__ = "insight_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    evaluation_id: Mapped[int] = mapped_column(
        ForeignKey("risk_evaluations.id", ondelete="CASCADE")
    )
    finding_key: Mapped[str] = mapped_column(String(100), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(16))
    to_state: Mapped[str] = mapped_column(String(16), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    dedupe_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)


class ScenarioRecord(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="evaluated")
    base_portfolio_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    candidate_instrument_id: Mapped[int | None] = mapped_column(
        ForeignKey("instruments.id")
    )
    base_inputs_json: Mapped[str] = mapped_column(Text, nullable=False)
    assumptions_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    profile: Mapped[ProfileRecord] = relationship(back_populates="scenarios")
    operations: Mapped[list["ScenarioOperationRecord"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )
    comparisons: Mapped[list["ScenarioComparisonRecord"]] = relationship(
        back_populates="scenario", cascade="all, delete-orphan"
    )


class ScenarioOperationRecord(Base):
    __tablename__ = "scenario_operations"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence", name="uq_scenario_operation_sequence"),
        CheckConstraint("amount IS NULL OR amount >= 0", name="ck_scenario_amount"),
        CheckConstraint(
            "target_weight IS NULL OR (target_weight >= 0 AND target_weight <= 1)",
            name="ck_scenario_target_weight",
        ),
        CheckConstraint("estimated_cost >= 0", name="ck_scenario_estimated_cost"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    amount: Mapped[Decimal | None] = mapped_column(Numeric(24, 2))
    target_weight: Mapped[Decimal | None] = mapped_column(Numeric(12, 8))
    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(24, 2), nullable=False, default=Decimal(0)
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    scenario: Mapped[ScenarioRecord] = relationship(back_populates="operations")


class ScenarioComparisonRecord(Base):
    __tablename__ = "scenario_comparisons"
    __table_args__ = (
        UniqueConstraint(
            "scenario_id", "operation_count", name="uq_scenario_comparison_version"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    scenario_id: Mapped[int] = mapped_column(
        ForeignKey("scenarios.id", ondelete="CASCADE")
    )
    operation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)

    scenario: Mapped[ScenarioRecord] = relationship(back_populates="comparisons")


class WatchlistRecord(Base):
    __tablename__ = "watchlists"
    __table_args__ = (
        UniqueConstraint("profile_id", "name", name="uq_watchlist_profile_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    profile: Mapped[ProfileRecord] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItemRecord"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItemRecord(Base):
    __tablename__ = "watchlist_items"
    __table_args__ = (
        UniqueConstraint(
            "watchlist_id", "instrument_id", name="uq_watchlist_item_instrument"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    watchlist_id: Mapped[int] = mapped_column(
        ForeignKey("watchlists.id", ondelete="CASCADE")
    )
    instrument_id: Mapped[int] = mapped_column(
        ForeignKey("instruments.id", ondelete="CASCADE")
    )
    reason: Mapped[str | None] = mapped_column(Text)
    tags_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    watchlist: Mapped[WatchlistRecord] = relationship(back_populates="items")
    instrument: Mapped[InstrumentRecord] = relationship()
