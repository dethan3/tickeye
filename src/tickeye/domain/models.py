"""Framework-independent portfolio facts and commands."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from tickeye.domain.enums import AssetClass, InstrumentType


@dataclass(frozen=True, slots=True)
class PositionInput:
    """One user-supplied current holding with its instrument and account facts."""

    id: int | None
    account_name: str
    institution: str | None
    account_currency: str
    code: str
    name: str | None
    instrument_type: InstrumentType | None
    market: str
    instrument_currency: str | None
    asset_class: AssetClass | None
    region: str | None
    quantity: Decimal | None
    manual_value: Decimal | None
    cost: Decimal | None
    as_of: date


@dataclass(frozen=True, slots=True)
class PositionFact:
    """A persisted position returned to API consumers."""

    id: int
    account_id: int
    account_name: str
    institution: str | None
    account_currency: str
    instrument_id: int
    code: str
    name: str
    instrument_type: InstrumentType
    market: str
    instrument_currency: str
    asset_class: AssetClass
    region: str
    quantity: Decimal | None
    manual_value: Decimal | None
    cost: Decimal | None
    as_of: date


@dataclass(frozen=True, slots=True)
class PortfolioFacts:
    """Current local portfolio and its optimistic concurrency revision."""

    profile_id: int
    profile_name: str
    base_currency: str
    revision: int
    positions: tuple[PositionFact, ...]
    latest_snapshot_at: datetime | None
